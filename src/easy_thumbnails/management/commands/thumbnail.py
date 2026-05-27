import datetime as dt
import os
import sys
import time
from collections import Counter
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from django.core.files.storage import storages
from django.core.management.base import BaseCommand
from django.utils import timezone

from easy_thumbnails.conf import settings
from easy_thumbnails.models import Source
from easy_thumbnails.storage import get_storage
from easy_thumbnails.utils import get_storage_hash


class ThumbnailCollectionCleaner:
    """
    Remove thumbnails and DB references to non-existing source images.

    Orphaned thumbnail files without a Source record are not touched.
    Command only works DB-outward.
    """

    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self.counts = Counter()
        self.execution_time = None

    def _get_absolute_path(self, path, storage):
        if hasattr(storage, 'location'):
            return str(Path(storage.location) / path)
        else:
            return str(Path(settings.MEDIA_ROOT) / path)

    def _check_if_exists(self, storage, path):
        try:
            return storage.exists(path)
        except Exception as e:
            self.stderr.write(f'Something went wrong when checking existence of {path}:')
            self.stderr.write(str(e))

    def _delete_sources_by_id(self, ids):
        Source.objects.all().filter(id__in=ids).delete()

    def _build_query(self, last_n_days, cleanup_path):
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

    def _delete_thumbnail(self, thumb, storage, dry_run, verbosity):
        self.counts['thumbnails_deleted'] += 1
        abs_thumbnail_path = self._get_absolute_path(thumb.name, storage)
        if self._check_if_exists(storage, abs_thumbnail_path) is True:
            if verbosity > 0:
                self.stdout.write(f'Deleting thumbnail: {abs_thumbnail_path}')
            if not dry_run:
                storage.delete(abs_thumbnail_path)

    def _process_source(self, source, storage_hash_map, storage, dry_run, verbosity):
        source_storage_alias = storage_hash_map.get(source.storage_hash)
        source_storage = storages[source_storage_alias] if source_storage_alias else None
        if source_storage:
            self.counts['sources'] += 1
            abs_source_path = self._get_absolute_path(source.name, source_storage)
            if self._check_if_exists(source_storage, abs_source_path) is False:
                if verbosity > 0:
                    self.stdout.write(f'Source not present: {abs_source_path}')

                self.counts['source_refs_deleted'] += 1
                for thumb in source.thumbnails.all():
                    self._delete_thumbnail(thumb, storage, dry_run, verbosity)

                return source.id

        else:
            self.stdout.write(
                f'Cannot determine source storage from hash ({source.storage_hash}),'
                f' skipping source (use --delete-with-missing-storage to remove)'
            )

    def _delete_with_missing_storage(self, query, storage_hash_map, dry_run, verbosity):
        known_hashes = set(storage_hash_map.keys())
        missing_query = query.exclude(storage_hash__in=known_hashes)
        count = missing_query.count()
        self.counts['sources_missing_storage_deleted'] = count
        if verbosity > 0:
            self.stdout.write(f'Sources with missing storage: {count}')
        if not dry_run:
            missing_query.delete()

    def clean_up(
        self,
        dry_run=False,
        verbosity=1,
        last_n_days=0,
        cleanup_path=None,
        delete_with_missing_storage=False,
        storage=None,
    ):
        """
        Iterate through sources. Delete database references to sources
        not existing, including its corresponding thumbnails (files and
        database references).
        """
        if dry_run:
            self.stdout.write('Dry run...')
        storage = storage if storage is not None else get_storage()

        storage_hash_map = build_storage_hash_map()

        time_start = time.time()

        sources_to_delete = []
        query = self._build_query(last_n_days, cleanup_path)

        if delete_with_missing_storage:
            self._delete_with_missing_storage(
                query,
                storage_hash_map,
                dry_run,
                verbosity,
            )

        for source in queryset_iterator(query):
            source_id = self._process_source(
                source,
                storage_hash_map,
                storage,
                dry_run,
                verbosity,
            )
            if source_id is not None:
                sources_to_delete.append(source_id)
                if not dry_run and len(sources_to_delete) >= 1000:
                    self._delete_sources_by_id(sources_to_delete)
                    sources_to_delete = []

        if not dry_run:
            self._delete_sources_by_id(sources_to_delete)

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


def build_storage_hash_map():
    return {
        get_storage_hash(storages[alias]): alias for alias in settings.STORAGES.keys()
    }


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
        for storage_hash, alias in build_storage_hash_map().items():
            self.stdout.write(f'{alias}: {storage_hash}')

    def do_cleanup(self, *args, **options):
        tcc = ThumbnailCollectionCleaner(self.stdout, self.stderr)
        tcc.clean_up(
            dry_run=options.get('dry_run', False),
            verbosity=int(options.get('verbosity', 1)),
            last_n_days=int(options.get('last_n_days', 0)),
            cleanup_path=options.get('cleanup_path'),
            delete_with_missing_storage=options.get('delete_with_missing_storage', False),
        )
        tcc.print_stats()
