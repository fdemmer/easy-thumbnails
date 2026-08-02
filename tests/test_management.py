import datetime as dt
import io
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models as django_models
from django.test import override_settings
from django.utils import timezone

from easy_thumbnails.alias import aliases
from easy_thumbnails.conf import settings as thumbnail_settings
from easy_thumbnails.fields import ThumbnailerField
from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.management import (
    all_thumbnails,
    delete_all_thumbnails,
    delete_thumbnails,
    thumbnails_for_file,
)
from easy_thumbnails.management.commands.thumbnail import collect_fields, _matches
from easy_thumbnails.models import Source, Thumbnail
from easy_thumbnails.utils import get_storage_hash
from tests import utils as test
from tests.models import TestModel


class ThumbnailCommandTests(test.BaseTest):
    def test_can_import(self):
        """
        Just a simple test to see if we can actually import the command without
        any syntax errors.
        """
        import easy_thumbnails.management.commands.thumbnail  # NOQA


class ListStoragesCommandTest(test.BaseTest):
    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'other': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        }
    )
    def test_same_backend_used_twice_lists_both_aliases(self):
        # Two aliases using the same backend class share a storage hash, but
        # each alias must still get its own line in the output.
        #
        # Django <5.0 merges a default 'staticfiles' entry back into
        # STORAGES even when it's fully overridden, so don't assume these
        # are the only two aliases listed.
        stdout = io.StringIO()
        call_command('thumbnail', 'storages', stdout=stdout)
        hashes = {
            line.split()[0]: line.split()[1] for line in stdout.getvalue().splitlines()
        }
        self.assertIn('default', hashes)
        self.assertIn('other', hashes)
        self.assertEqual(hashes['default'], hashes['other'])


@override_settings(MEDIA_ROOT=Path(settings.MEDIA_ROOT) / 'test_media')
class ThumbnailCleanupTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        self.storage = test.TemporaryStorage()

        # Create a source image
        filename = self.create_image(self.storage, 'test.jpg')
        with self.storage.open(filename) as f:
            self.source_image_path = f.name

        # Save a test image in both storages.
        self.thumbnailer = get_thumbnailer(self.storage, filename)
        self.thumbnailer.generate_thumbnail({'size': (100, 100)})

        self.thumbnail_name = self.thumbnailer.get_thumbnail_name({'size': (100, 100)})
        self.thumbnail_path = self.thumbnailer.get_thumbnail({'size': (100, 100)}).path

        self.source = Source.objects.get(name=filename)

    def tearDown(self):
        # Clean up files
        Path(self.source_image_path).unlink(missing_ok=True)
        Path(self.thumbnail_path).unlink(missing_ok=True)

        # Clean up the database
        Source.objects.all().delete()
        Thumbnail.objects.all().delete()

        # Remove test media directory if empty
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists() and not any(media_root.iterdir()):
            media_root.rmdir()

    def test_cleanup_command(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Delete the source image to simulate a missing source image
        Path(self.source_image_path).unlink()
        self.assertFalse(Path(self.source_image_path).exists())

        # Run the thumbnail cleanup command
        call_command('thumbnail', 'cleanup', verbosity=2)

        # Verify the thumbnail has been deleted
        self.assertFalse(Path(self.thumbnail_path).exists())

        # Verify the source reference has been deleted
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(id=self.source.id)

    def test_cleanup_command_exists_exception(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        source_storage = storages['easy_thumbnails']
        abs_source_path = str(Path(source_storage.location) / self.source.name)
        original_exists = source_storage.exists

        def mock_exists(path):
            if path == abs_source_path:
                raise OSError('Storage unavailable')
            return original_exists(path)

        # Run the thumbnail cleanup command mocking exception in storage.exists()
        with patch.object(source_storage, 'exists', side_effect=mock_exists):
            call_command('thumbnail', 'cleanup', verbosity=2)

        # Verify the source reference and thumbnail have NOT been deleted
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

    def test_cleanup_dry_run(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Delete the source image to simulate a missing source image
        Path(self.source_image_path).unlink()
        self.assertFalse(Path(self.source_image_path).exists())

        # Run the thumbnail cleanup command in dry run mode
        call_command('thumbnail', 'cleanup', dry_run=True, verbosity=2)

        # Verify the thumbnail has not been deleted
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Verify the source reference has not been deleted
        self.assertIsNotNone(Source.objects.get(id=self.source.id))

    def test_cleanup_last_n_days(self):
        old_time = timezone.now() - dt.timedelta(days=10)
        self.source.modified = old_time
        self.source.save()

        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Delete the source image to simulate a missing source image
        Path(self.source_image_path).unlink()
        self.assertFalse(Path(self.source_image_path).exists())

        # Run the thumbnail cleanup command with last_n_days parameter
        call_command('thumbnail', 'cleanup', last_n_days=5, verbosity=2)

        # Verify the thumbnail has not been deleted
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Verify the source reference has not been deleted
        self.assertIsNotNone(Source.objects.get(id=self.source.id))

        # Run the thumbnail cleanup command with last_n_days parameter
        # that includes the source
        call_command('thumbnail', 'cleanup', last_n_days=15, verbosity=2)

        # Verify the thumbnail has been deleted
        self.assertFalse(Path(self.thumbnail_path).exists())

        # Verify the source reference has been deleted
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(id=self.source.id)

    def test_cleanup_path_filter(self):
        # Create a second source + thumbnail under a subdirectory.
        filename_b = self.create_image(self.storage, 'subdir/b.jpg')
        with self.storage.open(filename_b) as f:
            source_b_image_path = f.name
        thumbnailer_b = get_thumbnailer(self.storage, filename_b)
        thumbnailer_b.generate_thumbnail({'size': (100, 100)})
        thumbnail_b_path = thumbnailer_b.get_thumbnail({'size': (100, 100)}).path
        source_b = Source.objects.get(name=filename_b)

        # Delete both source files to simulate missing sources.
        Path(self.source_image_path).unlink()
        Path(source_b_image_path).unlink()

        # Run cleanup scoped to 'subdir/' only.
        call_command('thumbnail', 'cleanup', cleanup_path='subdir/', verbosity=0)

        # The subdir source and its thumbnail should be cleaned up.
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(id=source_b.id)
        self.assertFalse(Path(thumbnail_b_path).exists())

        # The top-level source is outside the path scope — it must be untouched.
        Source.objects.get(id=self.source.id)
        self.assertTrue(Path(self.thumbnail_path).exists())

    def test_source_storage_hash_not_found(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Change the source's storage_hash to simulate an unknown storage hash
        self.source.storage_hash = 'unknown_storage_hash'
        self.source.save()

        # Run the thumbnail cleanup command
        call_command('thumbnail', 'cleanup', verbosity=2)

        # Verify the thumbnail and source still exist
        self.assertTrue(Path(self.thumbnail_path).exists())
        self.assertIsNotNone(Source.objects.get(id=self.source.id))

    def test_delete_with_missing_storage(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Change the source's storage_hash to simulate a removed storage backend
        self.source.storage_hash = 'unknown_storage_hash'
        self.source.save()

        call_command(
            'thumbnail',
            'cleanup',
            delete_with_missing_storage=True,
            verbosity=0,
        )

        # Source record must be deleted
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(id=self.source.id)

    def test_delete_with_missing_storage_dry_run(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Change the source's storage_hash to simulate a removed storage backend
        self.source.storage_hash = 'unknown_storage_hash'
        self.source.save()

        stdout = io.StringIO()
        call_command(
            'thumbnail',
            'cleanup',
            delete_with_missing_storage=True,
            dry_run=True,
            verbosity=1,
            stdout=stdout,
        )

        # Dry run — source must still exist
        self.assertIsNotNone(Source.objects.get(id=self.source.id))

        output = stdout.getvalue()
        self.assertIn('Dry run', output)
        self.assertIn('Deleting 1 Source objects with unknown storage.', output)


class CollectFieldsTest(test.BaseTest):
    def _pairs(self, **kwargs):
        return list(collect_fields(**kwargs))

    def _labels(self, **kwargs):
        return {(m._meta.label, f.name) for m, f in self._pairs(**kwargs)}

    def test_default_finds_thumbnailer_image_fields(self):
        self.assertIn(('easy_thumbnails_tests.TestModel', 'picture'), self._labels())

    def test_default_excludes_plain_file_fields(self):
        # Profile.logo is a plain FileField — not a ThumbnailerImageField
        self.assertNotIn(('easy_thumbnails_tests.Profile', 'logo'), self._labels())

    def test_default_excludes_thumbnailer_non_image_fields(self):
        # ThumbnailerField is not a ThumbnailerImageField subclass
        self.assertNotIn(('easy_thumbnails_tests.TestModel', 'avatar'), self._labels())
        self.assertNotIn(('easy_thumbnails_tests.Profile', 'avatar'), self._labels())

    def test_custom_field_class_file_field(self):
        # Passing models.FileField widens the search to all file-based fields
        labels = self._labels(field_class=django_models.FileField)
        self.assertIn(('easy_thumbnails_tests.Profile', 'logo'), labels)
        self.assertIn(('easy_thumbnails_tests.TestModel', 'picture'), labels)

    def test_custom_field_class_thumbnailer_field(self):
        # ThumbnailerImageField is also a ThumbnailerField subclass
        labels = self._labels(field_class=ThumbnailerField)
        self.assertIn(('easy_thumbnails_tests.Profile', 'avatar'), labels)
        self.assertIn(('easy_thumbnails_tests.TestModel', 'avatar'), labels)
        self.assertIn(('easy_thumbnails_tests.TestModel', 'picture'), labels)

    def test_fields_sorted_within_each_model(self):
        from itertools import groupby

        pairs = self._pairs(field_class=django_models.FileField)
        for _, group in groupby(
            pairs, key=lambda p: (p[0]._meta.app_label, p[0]._meta.model_name)
        ):
            names = [f.name for _, f in group]
            self.assertEqual(names, sorted(names))

    def test_yields_model_field_tuples(self):
        for model, field in self._pairs(field_class=django_models.FileField):
            self.assertTrue(hasattr(model, '_meta'))
            self.assertTrue(hasattr(field, 'name'))


class MatchesTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        # TestModel.picture is the only ThumbnailerImageField in test models
        self._model, self._field = next(
            (m, f)
            for m, f in collect_fields()
            if m._meta.label == 'easy_thumbnails_tests.TestModel' and f.name == 'picture'
        )

    def test_empty_specs_always_matches(self):
        self.assertTrue(_matches(self._model, self._field, []))

    def test_matches_by_app(self):
        self.assertTrue(_matches(self._model, self._field, ['easy_thumbnails_tests']))

    def test_no_match_wrong_app(self):
        self.assertFalse(_matches(self._model, self._field, ['auth']))

    def test_matches_by_app_model(self):
        self.assertTrue(
            _matches(self._model, self._field, ['easy_thumbnails_tests.testmodel'])
        )

    def test_no_match_wrong_model(self):
        self.assertFalse(
            _matches(self._model, self._field, ['easy_thumbnails_tests.profile'])
        )

    def test_matches_by_app_model_field(self):
        self.assertTrue(
            _matches(
                self._model, self._field, ['easy_thumbnails_tests.testmodel.picture']
            )
        )

    def test_no_match_wrong_field(self):
        self.assertFalse(
            _matches(self._model, self._field, ['easy_thumbnails_tests.testmodel.avatar'])
        )

    def test_wildcard_app(self):
        self.assertTrue(_matches(self._model, self._field, ['easy_thumbnails*']))

    def test_wildcard_model(self):
        self.assertTrue(
            _matches(self._model, self._field, ['easy_thumbnails_tests.test*'])
        )

    def test_wildcard_field(self):
        self.assertTrue(
            _matches(self._model, self._field, ['easy_thumbnails_tests.testmodel.*'])
        )

    def test_any_matching_spec_returns_true(self):
        self.assertTrue(
            _matches(self._model, self._field, ['auth', 'easy_thumbnails_tests'])
        )


class ThumbnailSourceFilesCommandTest(test.BaseTest):
    def _call(self, **kwargs):
        stdout = io.StringIO()
        stderr = io.StringIO()
        call_command('thumbnail', 'source_files', stdout=stdout, stderr=stderr, **kwargs)
        return stdout.getvalue(), stderr.getvalue()

    def test_list_mode_empty_db_no_output(self):
        stdout, stderr = self._call()
        self.assertEqual(stdout, '')
        self.assertIn('total', stderr)

    def test_list_mode_outputs_file_paths(self):
        TestModel.objects.create(avatar='avatars/a.jpg', picture='pictures/p.jpg')
        stdout, _ = self._call()
        lines = stdout.splitlines()
        self.assertIn('pictures/p.jpg', lines)

    def test_list_mode_skips_empty_paths(self):
        TestModel.objects.create(avatar='', picture='')
        stdout, _ = self._call()
        self.assertEqual(stdout, '')

    def test_summary_mode_shows_field_label(self):
        stdout, _ = self._call(summary=True)
        self.assertIn('easy_thumbnails_tests.TestModel.picture', stdout)

    def test_summary_mode_excludes_empty_and_null_values(self):
        TestModel.objects.create(picture='')
        TestModel.objects.create(picture=None)
        TestModel.objects.create(picture='pictures/p.jpg')
        stdout, _ = self._call(summary=True)
        self.assertIn(f'{1:>8} easy_thumbnails_tests.TestModel.picture', stdout)

    def test_stderr_reports_field_and_model_counts(self):
        _, stderr = self._call()
        self.assertIn('fields', stderr)
        self.assertIn('models', stderr)

    def test_include_limits_to_matching_model(self):
        stdout, _ = self._call(include=['easy_thumbnails_tests.testmodel'], summary=True)
        self.assertIn('TestModel', stdout)

    def test_include_no_match_returns_empty(self):
        stdout, _ = self._call(include=['auth'], summary=True)
        self.assertEqual(stdout, '')

    def test_exclude_hides_matching_model(self):
        # TestModel excluded and no other ThumbnailerImageField models, output is empty
        stdout, _ = self._call(exclude=['easy_thumbnails_tests.testmodel'], summary=True)
        self.assertNotIn('TestModel', stdout)

    def test_include_and_exclude_combined(self):
        stdout, _ = self._call(
            include=['easy_thumbnails_tests'],
            exclude=['easy_thumbnails_tests.testmodel'],
            summary=True,
        )
        self.assertNotIn('TestModel', stdout)

    def test_invalid_spec_too_many_parts(self):
        with self.assertRaises(CommandError):
            self._call(include=['too.many.parts.here'])

    def test_invalid_spec_in_exclude(self):
        with self.assertRaises(CommandError):
            self._call(exclude=['a.b.c.d'])


class ThumbnailSourceCleanupCommandTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        self.storage_hash = get_storage_hash(TestModel.picture.field.storage)

    def _call(self, **kwargs):
        stdout, stderr = io.StringIO(), io.StringIO()
        call_command(
            'thumbnail',
            'source_cleanup',
            stdout=stdout,
            stderr=stderr,
            **kwargs,
        )
        return stdout.getvalue(), stderr.getvalue()

    def _make_source(self, name):
        return Source.objects.create(storage_hash=self.storage_hash, name=name)

    def test_empty_db_no_deletions(self):
        _, stderr = self._call()
        self.assertIn('0 Source records', stderr)
        self.assertEqual(Source.objects.count(), 0)

    def test_deletes_source_with_no_matching_field_value(self):
        self._make_source('pictures/orphan.jpg')
        self.assertEqual(Source.objects.count(), 1)
        self._call()
        self.assertEqual(Source.objects.count(), 0)

    def test_preserves_source_with_matching_field_value(self):
        TestModel.objects.create(picture='pictures/keep.jpg')
        self._make_source('pictures/keep.jpg')
        self._make_source('pictures/orphan.jpg')
        self.assertEqual(Source.objects.count(), 2)
        self._call()
        self.assertEqual(Source.objects.count(), 1)
        self.assertTrue(Source.objects.filter(name='pictures/keep.jpg').exists())

    def test_ignores_rows_with_empty_or_null_field_value(self):
        # Rows without a source file must not count as "active" - otherwise
        # an orphaned Source named '' would be incorrectly preserved.
        TestModel.objects.create(picture='')
        TestModel.objects.create(picture=None)
        self._make_source('')
        self.assertEqual(Source.objects.count(), 1)
        self._call()
        self.assertEqual(Source.objects.count(), 0)

    def test_dry_run_prints_but_does_not_delete(self):
        TestModel.objects.create(picture='pictures/keep.jpg')
        self._make_source('pictures/keep.jpg')
        self._make_source('pictures/orphan.jpg')
        self.assertEqual(Source.objects.count(), 2)
        stdout, stderr = self._call(dry_run=True)
        self.assertIn('pictures/orphan.jpg', stdout)
        self.assertIn('Would delete', stderr)
        self.assertEqual(Source.objects.count(), 2)

    def test_stderr_reports_counts(self):
        self._make_source('pictures/orphan.jpg')
        _, stderr = self._call()
        self.assertIn('Source records', stderr)
        self.assertIn('1', stderr)

    def test_deleted_count_includes_cascaded_thumbnails(self):
        source = self._make_source('pictures/orphan.jpg')
        Thumbnail.objects.create(
            storage_hash=self.storage_hash,
            name='pictures/orphan.jpg.100x100.jpg',
            source=source,
        )
        _, stderr = self._call()
        self.assertIn('Deleted 2 Source records', stderr)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Thumbnail.objects.count(), 0)

    def test_deletes_orphans_across_multiple_batches(self):
        Source.objects.bulk_create(
            [
                Source(storage_hash=self.storage_hash, name=f'pictures/orphan-{i}.jpg')
                for i in range(1500)
            ]
        )
        TestModel.objects.create(picture='pictures/keep.jpg')
        self._make_source('pictures/keep.jpg')
        self.assertEqual(Source.objects.count(), 1501)
        _, stderr = self._call()
        self.assertIn('Deleted 1500 Source records', stderr)
        self.assertEqual(Source.objects.count(), 1)
        self.assertTrue(Source.objects.filter(name='pictures/keep.jpg').exists())


class ThumbnailRegenerateCommandTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        self.storage = test.TemporaryStorage()

        # Point the only ThumbnailerImageField in the test models at our
        # temporary storage, as done in tests/test_aliases.py.
        self.field = TestModel._meta.get_field('picture')
        self._original_storage = self.field.storage
        self._original_thumbnail_storage = self.field.thumbnail_storage
        self.field.storage = self.storage
        self.field.thumbnail_storage = self.storage

        self._original_aliases = aliases._aliases
        thumbnail_settings.THUMBNAIL_ALIASES = {
            'easy_thumbnails_tests.TestModel.picture': {'small': {'size': (20, 20)}},
        }
        aliases._aliases = {}
        aliases.populate_from_settings()

        filename = self.create_image(self.storage, 'pictures/test.jpg')
        self.instance = TestModel.objects.create(picture=filename)

    def tearDown(self):
        aliases._aliases = self._original_aliases
        self.field.storage = self._original_storage
        self.field.thumbnail_storage = self._original_thumbnail_storage
        self.storage.delete_temporary_storage()
        super().tearDown()

    def _call(self, **kwargs):
        stdout, stderr = io.StringIO(), io.StringIO()
        call_command('thumbnail', 'regenerate', stdout=stdout, stderr=stderr, **kwargs)
        return stdout.getvalue(), stderr.getvalue()

    def test_creates_alias_thumbnails_for_source_with_none_yet(self):
        self.assertEqual(Thumbnail.objects.count(), 0)
        self._call()
        self.assertEqual(Thumbnail.objects.count(), 1)
        thumbnail = self.instance.picture.get_thumbnail(
            {'size': (20, 20), 'ALIAS': 'small'}, generate=False
        )
        self.assertIsNotNone(thumbnail)

    def test_purges_stale_thumbnail_before_regenerating(self):
        # Seed a cached thumbnail under the 'small' alias name, but with a
        # size that no longer matches the currently configured alias.
        stale = self.instance.picture.generate_thumbnail(
            {'size': (50, 50), 'ALIAS': 'small'}
        )
        self.instance.picture.save_thumbnail(stale)
        self.assertEqual(Thumbnail.objects.count(), 1)

        self._call()

        # Only the freshly generated thumbnail (matching the current alias
        # options) should remain cached - the stale entry was purged first.
        self.assertEqual(Thumbnail.objects.count(), 1)
        current = self.instance.picture.get_thumbnail(
            {'size': (20, 20), 'ALIAS': 'small'}, generate=False
        )
        self.assertIsNotNone(current)

    def test_dry_run_makes_no_changes(self):
        stdout, _ = self._call(dry_run=True, verbosity=2)
        self.assertIn('Dry run', stdout)
        self.assertEqual(Thumbnail.objects.count(), 0)

    def test_dry_run_reports_same_totals_as_real_run(self):
        # Seed a stale cached thumbnail, as in
        # test_purges_stale_thumbnail_before_regenerating, so the dry run has
        # a non-zero purge count to estimate.
        stale = self.instance.picture.generate_thumbnail(
            {'size': (50, 50), 'ALIAS': 'small'}
        )
        self.instance.picture.save_thumbnail(stale)
        self.assertEqual(Thumbnail.objects.count(), 1)

        dry_stdout, _ = self._call(dry_run=True)
        self.assertIn(f'{"Sources processed:":<40} {1:>7}', dry_stdout)
        self.assertIn(f'{"Thumbnails purged:":<40} {1:>7}', dry_stdout)
        self.assertIn(f'{"Aliases regenerated:":<40} {1:>7}', dry_stdout)
        # Nothing was actually touched.
        self.assertEqual(Thumbnail.objects.count(), 1)

        real_stdout, _ = self._call()
        self.assertIn(f'{"Sources processed:":<40} {1:>7}', real_stdout)
        self.assertIn(f'{"Thumbnails purged:":<40} {1:>7}', real_stdout)
        self.assertIn(f'{"Aliases regenerated:":<40} {1:>7}', real_stdout)

    def test_dry_run_and_real_run_ignore_rows_with_empty_or_null_field(self):
        # Rows without a source file must not be counted by either code
        # path - `_estimate` (dry-run) and `_iter_fieldfiles` (real run) need
        # to agree, otherwise dry-run stats lie about what a real run does.
        TestModel.objects.create(picture='')
        TestModel.objects.create(picture=None)

        dry_stdout, _ = self._call(dry_run=True)
        self.assertIn(f'{"Sources processed:":<40} {1:>7}', dry_stdout)
        self.assertIn(f'{"Aliases regenerated:":<40} {1:>7}', dry_stdout)

        real_stdout, _ = self._call()
        self.assertIn(f'{"Sources processed:":<40} {1:>7}', real_stdout)
        self.assertIn(f'{"Aliases regenerated:":<40} {1:>7}', real_stdout)
        self.assertEqual(Thumbnail.objects.count(), 1)

    def test_dry_run_verbosity_shows_per_field_summary(self):
        stdout, _ = self._call(dry_run=True, verbosity=2)
        self.assertIn(
            'easy_thumbnails_tests.TestModel.picture: 1 source(s), '
            'purge 0 cached thumbnail(s), regenerate 1 alias(es): small',
            stdout,
        )
        # No more per-file lines - just the per-field summary above.
        self.assertNotIn('pictures/test.jpg:', stdout)

    def test_real_run_verbosity_lists_alias_names(self):
        stdout, _ = self._call(verbosity=2)
        self.assertIn(
            'pictures/test.jpg: purged 0 cached thumbnail(s), '
            'regenerated 1 alias(es): small',
            stdout,
        )

    def test_dry_run_query_count_does_not_scale_with_row_count(self):
        for i in range(5):
            filename = self.create_image(self.storage, f'pictures/extra{i}.jpg')
            TestModel.objects.create(picture=filename)

        with self.assertNumQueries(2):
            self._call(dry_run=True)

    def test_exclude_skips_matching_field(self):
        self._call(exclude=['easy_thumbnails_tests.testmodel'])
        self.assertEqual(Thumbnail.objects.count(), 0)

    def test_include_no_match_skips_everything(self):
        self._call(include=['auth'])
        self.assertEqual(Thumbnail.objects.count(), 0)

    def test_path_filter_restricts_scope(self):
        other_filename = self.create_image(self.storage, 'other/test2.jpg')
        TestModel.objects.create(picture=other_filename)

        self._call(path='pictures/')

        self.assertEqual(Thumbnail.objects.count(), 1)
        source = Source.objects.get()
        self.assertEqual(source.name, 'pictures/test.jpg')

    def test_include_global_also_regenerates_global_aliases(self):
        thumbnail_settings.THUMBNAIL_ALIASES = {
            '': {'tiny': {'size': (5, 5)}},
            'easy_thumbnails_tests.TestModel.picture': {'small': {'size': (20, 20)}},
        }
        aliases._aliases = {}
        aliases.populate_from_settings()

        self._call()
        self.assertEqual(Thumbnail.objects.count(), 1)

        self._call(include_global=True)
        self.assertEqual(Thumbnail.objects.count(), 2)

    def test_missing_source_file_counts_error_and_continues(self):
        other_filename = self.create_image(self.storage, 'pictures/missing.jpg')
        TestModel.objects.create(picture=other_filename)
        self.storage.delete(other_filename)

        stdout, stderr = self._call()

        self.assertIn('Could not regenerate', stderr)
        self.assertIn('missing.jpg', stderr)
        # The still-present source is processed successfully regardless.
        self.assertEqual(
            Thumbnail.objects.filter(source__name='pictures/test.jpg').count(), 1
        )
        self.assertIn(f'{"Errors:":<40} {1:>7}', stdout)

    def test_corrupt_source_file_counts_error_and_continues(self):
        # Not valid image data - PIL (and VIL) will fail to decode it, so all
        # source generators are exhausted and NoSourceGenerator is raised.
        corrupt_filename = self.storage.save(
            'pictures/corrupt.jpg', ContentFile(b'not an image')
        )
        TestModel.objects.create(picture=corrupt_filename)

        stdout, stderr = self._call()

        self.assertIn('Could not regenerate', stderr)
        self.assertIn('corrupt.jpg', stderr)
        # The still-valid source is processed successfully regardless.
        self.assertEqual(
            Thumbnail.objects.filter(source__name='pictures/test.jpg').count(), 1
        )
        self.assertIn(f'{"Errors:":<40} {1:>7}', stdout)

    def test_stats_output_format(self):
        # First run: nothing cached yet, so nothing to purge.
        stdout, _ = self._call()
        self.assertIn(f'{"Sources processed:":<40} {1:>7}', stdout)
        self.assertIn(f'{"Thumbnails purged:":<40} {0:>7}', stdout)
        self.assertIn(f'{"Aliases regenerated:":<40} {1:>7}', stdout)
        self.assertIn(f'{"Errors:":<40} {0:>7}', stdout)
        self.assertIn('Completed in', stdout)

        # Second run: the thumbnail cached by the first run gets purged
        # before the alias is regenerated.
        stdout, _ = self._call()
        self.assertIn(f'{"Sources processed:":<40} {1:>7}', stdout)
        self.assertIn(f'{"Thumbnails purged:":<40} {1:>7}', stdout)
        self.assertIn(f'{"Aliases regenerated:":<40} {1:>7}', stdout)
        self.assertIn(f'{"Errors:":<40} {0:>7}', stdout)


class ManagementTestBase(test.BaseTest):
    def setUp(self):
        super().setUp()
        self.storage = test.TemporaryStorage()
        self.root = Path(self.storage._location)

    def tearDown(self):
        self.storage.delete_temporary_storage()
        super().tearDown()

    def _make_file(self, *parts):
        """Create an empty file under self.root, ensuring parent dirs exist."""
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        self.assertTrue(path.exists())
        return path


class AllThumbnailsTest(ManagementTestBase):
    def test_empty_directory(self):
        result = all_thumbnails(str(self.root))
        self.assertEqual(result, {})

    def test_non_matching_files(self):
        self._make_file('source.jpg')
        self._make_file('random.txt')
        result = all_thumbnails(str(self.root))
        self.assertEqual(result, {})

    def test_single_thumbnail(self):
        thumb = self._make_file('source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root))
        self.assertIn('source.jpg', result)
        self.assertEqual(len(result['source.jpg']), 1)
        entry = result['source.jpg'][0]
        self.assertEqual(set(entry.keys()), {'x', 'y', 'options', 'quality', 'filename'})
        self.assertEqual(entry['x'], '100')
        self.assertEqual(entry['y'], '100')
        self.assertEqual(entry['quality'], '85')
        self.assertEqual(entry['options'], [])
        self.assertEqual(entry['filename'], str(thumb))

    def test_multiple_thumbnails_same_source(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        self._make_file('source.jpg_200x200_q90.jpg')
        result = all_thumbnails(str(self.root))
        self.assertIn('source.jpg', result)
        self.assertEqual(len(result['source.jpg']), 2)

    def test_thumbnail_with_options(self):
        self._make_file('source.jpg_100x100_webp_q85.jpg')
        result = all_thumbnails(str(self.root))
        self.assertEqual(result['source.jpg'][0]['options'], ['webp'])

    def test_recursive_finds_subdirectory(self):
        self._make_file('sub', 'source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root), recursive=True)
        self.assertIn('sub/source.jpg', result)

    def test_non_recursive_ignores_subdirectory(self):
        self._make_file('sub', 'source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root), recursive=False)
        self.assertEqual(result, {})

    def test_non_recursive_finds_top_level(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root), recursive=False)
        self.assertIn('source.jpg', result)

    def test_extensionless_source_with_underscore(self):
        # Corner-case bug (see management/__init__.py): a source file with no
        # extension but an underscore in its name (e.g. 'my_photo') cannot be
        # round-tripped — the last underscore is converted to '.' so the key
        # becomes 'my.photo' instead of 'my_photo'.
        self._make_file('my_photo_100x100_q85.jpg')
        result = all_thumbnails(str(self.root))
        self.assertIn('my.photo', result)
        self.assertNotIn('my_photo', result)

    def test_prefix_filters_non_matching(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root), prefix='thumb_')
        self.assertEqual(result, {})

    def test_prefix_strips_prefix(self):
        # source_filename captured by the regex is 'thumb_source.jpg';
        # with prefix='thumb_' that should yield key 'source.jpg'.
        self._make_file('thumb_source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root), prefix='thumb_')
        self.assertIn('source.jpg', result)

    def test_subdir_stripped_from_key(self):
        # With subdir='cache' the 'cache' component should be stripped from
        # the result key, so the source maps to 'source.jpg' not 'cache/source.jpg'.
        self._make_file('cache', 'source.jpg_100x100_q85.jpg')
        result = all_thumbnails(str(self.root), recursive=True, subdir='cache')
        self.assertIn('source.jpg', result)
        self.assertNotIn('cache/source.jpg', result)


class ThumbnailsForFileTest(ManagementTestBase):
    def _call(self, relative_source_path, **kwargs):
        kwargs.setdefault('root', str(self.root))
        kwargs.setdefault('basedir', '')
        kwargs.setdefault('subdir', '')
        kwargs.setdefault('prefix', '')
        return thumbnails_for_file(relative_source_path, **kwargs)

    def test_no_thumbnail_directory(self):
        result = self._call('source.jpg')
        self.assertEqual(result, [])

    def test_no_matching_thumbnails(self):
        self._make_file('source.jpg')
        result = self._call('source.jpg')
        self.assertEqual(result, [])

    def test_source_in_root(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        result = self._call('source.jpg')
        self.assertEqual(len(result), 1)

    def test_source_in_subdirectory(self):
        self._make_file('subdir', 'source.jpg_100x100_q85.jpg')
        result = self._call('subdir/source.jpg')
        self.assertEqual(len(result), 1)

    def test_multiple_thumbnails(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        self._make_file('source.jpg_200x200_q85.jpg')
        result = self._call('source.jpg')
        self.assertEqual(len(result), 2)

    def test_filename_in_result(self):
        thumb = self._make_file('source.jpg_100x100_q85.jpg')
        result = self._call('source.jpg')
        self.assertEqual(result[0]['filename'], str(thumb))


class DeleteThumbnailsTest(ManagementTestBase):
    def _call(self, relative_source_path, **kwargs):
        kwargs.setdefault('root', str(self.root))
        kwargs.setdefault('basedir', '')
        kwargs.setdefault('subdir', '')
        kwargs.setdefault('prefix', '')
        return delete_thumbnails(relative_source_path, **kwargs)

    def test_no_thumbnails(self):
        count = self._call('source.jpg')
        self.assertEqual(count, 0)

    def test_deletes_files(self):
        thumb1 = self._make_file('source.jpg_100x100_q85.jpg')
        thumb2 = self._make_file('source.jpg_200x200_q85.jpg')
        count = self._call('source.jpg')
        self.assertEqual(count, 2)
        self.assertFalse(thumb1.exists())
        self.assertFalse(thumb2.exists())

    def test_source_file_not_deleted(self):
        source = self._make_file('source.jpg')
        self._make_file('source.jpg_100x100_q85.jpg')
        self._call('source.jpg')
        self.assertTrue(source.exists())

    def test_returns_count(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        self._make_file('source.jpg_200x200_q85.jpg')
        self._make_file('source.jpg_300x300_q85.jpg')
        count = self._call('source.jpg')
        self.assertEqual(count, 3)


class DeleteAllThumbnailsTest(ManagementTestBase):
    def test_empty_directory(self):
        count = delete_all_thumbnails(str(self.root))
        self.assertEqual(count, 0)

    def test_deletes_all_matching_files(self):
        thumb1 = self._make_file('a.jpg_100x100_q85.jpg')
        thumb2 = self._make_file('b.jpg_200x200_q85.jpg')
        thumb3 = self._make_file('c.jpg_300x300_q85.jpg')
        count = delete_all_thumbnails(str(self.root))
        self.assertEqual(count, 3)
        self.assertFalse(thumb1.exists())
        self.assertFalse(thumb2.exists())
        self.assertFalse(thumb3.exists())

    def test_non_matching_files_untouched(self):
        source = self._make_file('source.jpg')
        self._make_file('source.jpg_100x100_q85.jpg')
        delete_all_thumbnails(str(self.root))
        self.assertTrue(source.exists())

    def test_recursive_true(self):
        self._make_file('source.jpg_100x100_q85.jpg')
        self._make_file('sub', 'source.jpg_200x200_q85.jpg')
        count = delete_all_thumbnails(str(self.root), recursive=True)
        self.assertEqual(count, 2)

    def test_recursive_false(self):
        top = self._make_file('source.jpg_100x100_q85.jpg')
        sub = self._make_file('sub', 'source.jpg_200x200_q85.jpg')
        count = delete_all_thumbnails(str(self.root), recursive=False)
        self.assertEqual(count, 1)
        self.assertFalse(top.exists())
        self.assertTrue(sub.exists())
