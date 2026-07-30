import datetime as dt
import fnmatch
import os
import sys
import time
from collections import Counter
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from django.apps import apps
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from easy_thumbnails.alias import aliases
from easy_thumbnails.compat import batched
from easy_thumbnails.conf import settings
from easy_thumbnails.engine import NoSourceGenerator
from easy_thumbnails.exceptions import EasyThumbnailsError
from easy_thumbnails.fields import ThumbnailerImageField
from easy_thumbnails.files import generate_all_aliases
from easy_thumbnails.models import Source
from easy_thumbnails.storage import thumbnail_default_storage
from easy_thumbnails.utils import get_storage_hash


class ThumbnailCollectionCleaner:
    """
    Remove thumbnails and DB references to non-existing source images.

    Orphaned thumbnail files without a Source record are not touched.
    Command only works DB-outward.
    """

    def __init__(self, stdout, stderr, dry_run=True, verbosity=1):
        self.stdout = stdout
        self.stderr = stderr
        self.dry_run = dry_run
        self.verbosity = verbosity
        self.storage_hash_map = build_storage_hash_map()
        self.counts = Counter()
        self.execution_time = None

    def _get_absolute_path(self, path, storage):
        if hasattr(storage, 'location'):
            return str(Path(storage.location) / path)
        else:
            return str(Path(settings.MEDIA_ROOT) / path)

    def _check_exists(self, storage, path):
        """
        Check if the given `path` exists in the `storage`.
        """
        try:
            exists = storage.exists(path)
            if self.verbosity > 1:
                self.stdout.write(f'{exists=} {type(storage).__name__} {path}')
            return exists
        except Exception as e:
            self.stderr.write(f'Something went wrong when checking existence of {path}:')
            self.stderr.write(str(e))

    def _build_query(self, last_n_days, cleanup_path):
        """
        Return a queryset for Source objects with the given filters.
        """
        query = Source.objects.all()
        if last_n_days > 0:
            today = timezone.now().date()
            query = query.filter(
                modified__date__range=(
                    today - dt.timedelta(days=last_n_days),
                    today,
                )
            )
        if cleanup_path:
            query = query.filter(name__startswith=cleanup_path)
        return query

    def _delete_with_missing_storage(self, query):
        """
        Delete Source objects with unknown `storage_hash` using the given `query`.
        """
        known_hashes = set(self.storage_hash_map.keys())
        missing_query = query.exclude(storage_hash__in=known_hashes)
        count = missing_query.count()
        self.counts['sources_missing_storage_deleted'] = count
        if self.verbosity > 0:
            self.stdout.write(f'Deleting {count} Source objects with unknown storage.')
        if not self.dry_run:
            missing_query.delete()

    def _delete_thumbnail(self, thumb, storage):
        """
        Delete thumbnail file from storage.
        """
        self.counts['thumbnails_deleted'] += 1
        abs_thumbnail_path = self._get_absolute_path(thumb.name, storage)
        if self._check_exists(storage, abs_thumbnail_path) is True:
            if self.verbosity > 0:
                self.stdout.write(f'Deleting thumbnail file: {abs_thumbnail_path}')
            if not self.dry_run:
                storage.delete(abs_thumbnail_path)

    def _process_source(self, source, thumbnail_storage):
        """
        Check if Source has a file in storage.

        If there is NO file, delete thumbnail files and return `source.id` for deletion.
        """
        source_storage_alias = self.storage_hash_map.get(source.storage_hash)
        source_storage = storages[source_storage_alias] if source_storage_alias else None
        if source_storage:
            self.counts['sources'] += 1
            abs_source_path = self._get_absolute_path(source.name, source_storage)
            if self._check_exists(source_storage, abs_source_path) is False:
                if self.verbosity > 0:
                    self.stdout.write(f'Source file not found: {abs_source_path}')

                self.counts['source_refs_deleted'] += 1
                for thumb in source.thumbnails.all():
                    self._delete_thumbnail(thumb, thumbnail_storage)

                return source.id

        else:
            self.stdout.write(
                f'Cannot determine source storage from hash ({source.storage_hash}),'
                f' skipping source (use --delete-with-missing-storage to remove)'
            )

    def _process_source_query(self, query):
        thumbnail_storage = thumbnail_default_storage
        for source in queryset_iterator(query):
            source_id = self._process_source(source, thumbnail_storage)
            if source_id is not None:
                yield source_id

    def _delete_with_missing_source_file(self, query, batch_size=1000):
        """
        Delete Source objects from database (cascades to Thumbnail) in batches.
        """
        for source_ids in batched(self._process_source_query(query), batch_size):
            if self.verbosity > 0:
                self.stdout.write(f'Deleting {len(source_ids)} Source objects.')
            if not self.dry_run:
                Source.objects.all().filter(id__in=source_ids).delete()

    def clean_up(
        self,
        last_n_days=0,
        cleanup_path=None,
        delete_with_missing_storage=False,
    ):
        """
        Clean up Source objects.

        Find and delete Source objects without files in storage or with missing storage.
        Delete cascades to Thumbnail objects and thumbnail files are deleted from storage.
        """
        if self.dry_run:
            self.stdout.write('Dry run...')

        time_start = time.time()

        # query for Source objects
        query = self._build_query(last_n_days, cleanup_path)

        if delete_with_missing_storage:
            # delete Source objects without storage
            self._delete_with_missing_storage(query)

        if self.verbosity > 0:
            self.stdout.write(f'Checking storage for {query.count()} Source objects...')

        # delete Source objects without files
        self._delete_with_missing_source_file(query)

        self.execution_time = round(time.time() - time_start)

    def print_stats(self):
        """
        Print statistics about the cleanup performed.
        """
        self.stdout.write(f'{timezone.now().strftime("%Y-%m-%d %H:%M "):-<48}')
        self.stdout.write(f'{"Sources checked:":<40} {self.counts["sources"]:>7}')
        self.stdout.write(
            f'{"Sources with missing storage deleted:":<40} '
            f'{self.counts["sources_missing_storage_deleted"]:>7}'
        )
        self.stdout.write(
            f'{"Source references deleted from DB:":<40} '
            f'{self.counts["source_refs_deleted"]:>7}'
        )
        self.stdout.write(
            f'{"Thumbnails deleted from disk:":<40} '
            f'{self.counts["thumbnails_deleted"]:>7}'
        )
        self.stdout.write(f'(Completed in {self.execution_time} seconds)\n')


class ThumbnailRegenerator:
    """
    Regenerate configured alias thumbnails for existing source files.

    Purges any cached thumbnails for each source, then regenerates every
    alias configured for its field, model, or app (and optionally
    project-wide aliases). Ad hoc option sets used directly via
    ``{% thumbnail %}`` that don't match a configured alias are simply
    purged, not regenerated - they'll be recreated lazily the next time
    they're requested.
    """

    def __init__(self, stdout, stderr, dry_run=True, verbosity=1, include_global=False):
        self.stdout = stdout
        self.stderr = stderr
        self.dry_run = dry_run
        self.verbosity = verbosity
        self.include_global = include_global
        self.counts = Counter()
        self.execution_time = None

    def _iter_fieldfiles(self, pairs, path):
        for model, field in pairs:
            query = (
                model.objects.select_related(None)
                .exclude(**{field.name: '', f'{field.name}__isnull': True})
                .only('pk', field.name)
            )
            if path:
                query = query.filter(**{f'{field.name}__startswith': path})
            for instance in queryset_iterator(query):
                fieldfile = getattr(instance, field.name)
                if fieldfile:
                    yield fieldfile

    def _process(self, fieldfile):
        source_cache = fieldfile.get_source_cache()
        purge_count = source_cache.thumbnails.count() if source_cache else 0
        alias_count = len(aliases.all(fieldfile, include_global=self.include_global))
        if self.verbosity > 1:
            self.stdout.write(
                f'{fieldfile.name}: {purge_count} cached thumbnail(s), '
                f'{alias_count} alias(es) to regenerate'
            )

        if not self.dry_run:
            try:
                fieldfile.delete_thumbnails()
                generate_all_aliases(fieldfile, include_global=self.include_global)
            except (OSError, EasyThumbnailsError, NoSourceGenerator) as e:
                # OSError: unreadable/corrupt source, or a storage read/write failure.
                # EasyThumbnailsError/NoSourceGenerator: the source generators couldn't
                # produce an image at all.
                # Third-party remote storage backends may raise their own non-OSError
                # exceptions for I/O failures; those are intentionally not
                # caught here and will abort the run.
                self.stderr.write(f'Could not regenerate {fieldfile.name}: {e}')
                self.counts['errors'] += 1
                return

        self.counts['sources_processed'] += 1
        self.counts['thumbnails_purged'] += purge_count
        self.counts['aliases_regenerated'] += alias_count

    def regenerate(self, pairs, path=None):
        if self.dry_run:
            self.stdout.write('Dry run...')

        time_start = time.time()

        for fieldfile in self._iter_fieldfiles(pairs, path):
            self._process(fieldfile)

        self.execution_time = round(time.time() - time_start)

    def print_stats(self):
        """
        Print statistics about the regeneration performed.
        """
        self.stdout.write(f'{timezone.now().strftime("%Y-%m-%d %H:%M "):-<48}')
        self.stdout.write(
            f'{"Sources processed:":<40} {self.counts["sources_processed"]:>7}'
        )
        self.stdout.write(
            f'{"Thumbnails purged:":<40} {self.counts["thumbnails_purged"]:>7}'
        )
        self.stdout.write(
            f'{"Aliases regenerated:":<40} {self.counts["aliases_regenerated"]:>7}'
        )
        self.stdout.write(f'{"Errors:":<40} {self.counts["errors"]:>7}')
        self.stdout.write(f'(Completed in {self.execution_time} seconds)\n')


def queryset_iterator(query, chunk_size=1000, order_by='pk'):
    # https://use-the-index-luke.com/sql/partial-results/fetch-next-page
    threshold = new_threshold = 0
    if order_by is not None:
        query = query.order_by(order_by)
    while True:
        chunk = query.filter(pk__gt=threshold)[:chunk_size].iterator()
        for row in chunk:
            new_threshold = row.pk
            yield row
        if threshold == new_threshold:
            break
        threshold = new_threshold


@contextmanager
def handle_broken_pipe() -> Generator[None, None, None]:
    """
    Prevent BrokenPipeError when the output stream is closed early, such as
    when piping to head.

    https://adamj.eu/tech/2025/07/20/python-fix-brokenpipeerror/
    """
    try:
        yield
        sys.stdout.flush()
    except BrokenPipeError:
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())


def get_storages():
    return [
        (alias, type(storages[alias]).__name__, get_storage_hash(storages[alias]))
        for alias in settings.STORAGES.keys()
    ]


def build_storage_hash_map():
    return {storage_hash: alias for alias, _, storage_hash in get_storages()}


def _collect_fields(field_class=ThumbnailerImageField):
    for app_config in sorted(apps.get_app_configs(), key=lambda a: a.label):
        for model in app_config.get_models():
            if model._meta.proxy or not model._meta.managed:
                continue
            for field in sorted(model._meta.get_fields(), key=lambda f: f.name):
                if isinstance(field, field_class):
                    yield model, field


def _matches(model, field, specs):
    if not specs:
        return True
    app = model._meta.app_label
    mod = model._meta.model_name
    fld = field.name
    for spec in specs:
        parts = spec.lower().split('.')
        if len(parts) == 1 and fnmatch.fnmatch(app, parts[0]):
            return True
        if (
            len(parts) == 2
            and fnmatch.fnmatch(app, parts[0])
            and fnmatch.fnmatch(mod, parts[1])
        ):
            return True
        if (
            len(parts) == 3
            and fnmatch.fnmatch(app, parts[0])
            and fnmatch.fnmatch(mod, parts[1])
            and fnmatch.fnmatch(fld, parts[2])
        ):
            return True
    return False


class Command(BaseCommand):
    help = 'Manage thumbnails.'

    def add_subparsers(self, subparsers):
        storages_parser = subparsers.add_parser(
            'storages',
            help='List configured storages with their alias and storage hash.',
        )
        storages_parser.set_defaults(method=self.do_list_storages)

        cleanup_parser = subparsers.add_parser(
            'cleanup',
            help='Delete thumbnails that no longer have an original file.',
        )
        cleanup_parser.set_defaults(method=self.do_cleanup)
        cleanup_parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Dry run the execution.',
        )
        cleanup_parser.add_argument(
            '--last-n-days',
            action='store',
            dest='last_n_days',
            default=0,
            type=int,
            help='The number of days back in time to clean thumbnails for.',
        )
        cleanup_parser.add_argument(
            '--path',
            action='store',
            dest='cleanup_path',
            type=str,
            help='Specify a path to clean up.',
        )
        cleanup_parser.add_argument(
            '--delete-with-missing-storage',
            action='store_true',
            dest='delete_with_missing_storage',
            default=False,
            help=(
                'Delete Source records whose storage hash is not present in the current '
                'STORAGES setting.'
            ),
        )

        files_parser = subparsers.add_parser(
            'source_files',
            help='List file paths stored in ThumbnailerImageField across all apps.',
        )
        files_parser.set_defaults(method=self.do_source_files)
        files_parser.add_argument(
            '-s',
            '--summary',
            action='store_true',
            help='Print file counts per model field only.',
        )
        files_parser.add_argument(
            '--include',
            dest='include',
            metavar='SPEC',
            action='append',
            default=[],
            help=(
                'Restrict output to "app" or "app.model" or "app.model.field". '
                'May be repeated.'
            ),
        )
        files_parser.add_argument(
            '--exclude',
            dest='exclude',
            metavar='SPEC',
            action='append',
            default=[],
            help=(
                'Exclude "app" or "app.model" or "app.model.field" from output. '
                'May be repeated.'
            ),
        )

        cleanup_sources_parser = subparsers.add_parser(
            'source_cleanup',
            help='Delete Source records with no matching ThumbnailerImageField value.',
        )
        cleanup_sources_parser.set_defaults(method=self.do_source_cleanup)
        cleanup_sources_parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Preview which Source records would be deleted without deleting them.',
        )

        regenerate_parser = subparsers.add_parser(
            'regenerate',
            help='Purge and regenerate configured alias thumbnails for existing sources.',
        )
        regenerate_parser.set_defaults(method=self.do_regenerate)
        regenerate_parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Report what would be purged/regenerated without making any changes.',
        )
        regenerate_parser.add_argument(
            '--path',
            action='store',
            dest='path',
            type=str,
            help='Restrict regeneration to source names starting with this path.',
        )
        regenerate_parser.add_argument(
            '--include-global',
            action='store_true',
            dest='include_global',
            default=False,
            help=(
                'Also regenerate project-wide aliases, not just field/model/app '
                'specific ones.'
            ),
        )
        regenerate_parser.add_argument(
            '--include',
            dest='include',
            metavar='SPEC',
            action='append',
            default=[],
            help=(
                'Restrict regeneration to "app" or "app.model" or "app.model.field". '
                'May be repeated.'
            ),
        )
        regenerate_parser.add_argument(
            '--exclude',
            dest='exclude',
            metavar='SPEC',
            action='append',
            default=[],
            help=(
                'Exclude "app" or "app.model" or "app.model.field" from regeneration. '
                'May be repeated.'
            ),
        )

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            title='sub-commands',
            required=True,
        )
        self.add_subparsers(subparsers)

    def handle(self, *args, method, **options):
        with handle_broken_pipe():
            method(*args, **options)

    def do_list_storages(self, *args, **options):
        for alias, class_name, storage_hash in get_storages():
            self.stdout.write(f'{alias:<16} {storage_hash} {class_name}')

    def do_cleanup(self, *args, **options):
        tcc = ThumbnailCollectionCleaner(
            self.stdout,
            self.stderr,
            dry_run=options.get('dry_run', False),
            verbosity=int(options.get('verbosity', 1)),
        )
        tcc.clean_up(
            last_n_days=int(options.get('last_n_days', 0)),
            cleanup_path=options.get('cleanup_path'),
            delete_with_missing_storage=options.get('delete_with_missing_storage', False),
        )
        tcc.print_stats()

    def do_source_files(self, *args, **options):
        include = options['include']
        exclude = options['exclude']
        for spec in include + exclude:
            if not 1 <= len(spec.split('.')) <= 3:
                raise CommandError(f'Invalid filter spec: {spec!r}')

        pairs = [
            (model, field)
            for model, field in _collect_fields()
            if _matches(model, field, include)
            and (not exclude or not _matches(model, field, exclude))
        ]
        self.stderr.write(
            f'Found {len(pairs)} fields in {len({m for m, _ in pairs})} models.'
        )
        self.stderr.write('Counting non-empty values per FileField...')

        if options['summary']:
            total = 0
            for model, field in pairs:
                query = model.objects.exclude(
                    **{
                        field.name: '',
                        f'{field.name}__isnull': True,
                    }
                )
                count = query.count()
                total += count
                self.stdout.write(f'{count:>8} {model._meta.label}.{field.name}')
            self.stderr.write(f'{total:>8} total')
        else:
            total = 0
            for model, field in pairs:
                for path in model.objects.values_list(field.name, flat=True).iterator():
                    total += 1
                    if path:
                        self.stdout.write(path)
            self.stderr.write(f'{total:>8} total')

    def do_source_cleanup(self, *args, **options):
        dry_run = options['dry_run']

        pairs = list(_collect_fields())
        self.stderr.write(
            f'Found {len(pairs)} fields in {len({m for m, _ in pairs})} models.'
        )
        self.stderr.write('Collecting active source file paths...')

        active_sources = set()
        for model, field in pairs:
            storage_hash = get_storage_hash(field.storage)
            for name in (
                model.objects.exclude(**{field.name: '', f'{field.name}__isnull': True})
                .values_list(field.name, flat=True)
                .iterator()
            ):
                if name:
                    active_sources.add((storage_hash, name))

        self.stderr.write(f'Found {len(active_sources)} active source file paths.')

        if active_sources:
            keep = Q()
            for storage_hash, name in active_sources:
                keep |= Q(storage_hash=storage_hash, name=name)
            qs = Source.objects.exclude(keep)
        else:
            qs = Source.objects.all()

        if dry_run:
            deleted = 0
            for source in qs.iterator():
                self.stdout.write(source.name)
                deleted += 1
        else:
            deleted, _ = qs.delete()

        action = 'Would delete' if dry_run else 'Deleted'
        self.stderr.write(f'{action} {deleted} Source records.')

    def do_regenerate(self, *args, **options):
        include = options['include']
        exclude = options['exclude']
        for spec in include + exclude:
            if not 1 <= len(spec.split('.')) <= 3:
                raise CommandError(f'Invalid filter spec: {spec!r}')

        pairs = [
            (model, field)
            for model, field in _collect_fields()
            if _matches(model, field, include)
            and (not exclude or not _matches(model, field, exclude))
        ]
        self.stderr.write(
            f'Found {len(pairs)} fields in {len({m for m, _ in pairs})} models.'
        )

        regenerator = ThumbnailRegenerator(
            self.stdout,
            self.stderr,
            dry_run=options.get('dry_run', False),
            verbosity=int(options.get('verbosity', 1)),
            include_global=options.get('include_global', False),
        )
        regenerator.regenerate(pairs, path=options.get('path'))
        regenerator.print_stats()
