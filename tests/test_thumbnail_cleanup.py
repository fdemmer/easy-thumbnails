from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.models import Source, Thumbnail
from tests import utils as test


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
        call_command('thumbnail_cleanup', verbosity=2)

        # Verify the thumbnail has been deleted
        self.assertFalse(Path(self.thumbnail_path).exists())

        # Verify the source reference has been deleted
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(id=self.source.id)

    def test_cleanup_dry_run(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Delete the source image to simulate a missing source image
        Path(self.source_image_path).unlink()
        self.assertFalse(Path(self.source_image_path).exists())

        # Run the thumbnail cleanup command in dry run mode
        call_command('thumbnail_cleanup', dry_run=True, verbosity=2)

        # Verify the thumbnail has not been deleted
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Verify the source reference has not been deleted
        self.assertIsNotNone(Source.objects.get(id=self.source.id))

    def test_cleanup_last_n_days(self):
        old_time = timezone.now() - timedelta(days=10)
        self.source.modified = old_time
        self.source.save()

        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Delete the source image to simulate a missing source image
        Path(self.source_image_path).unlink()
        self.assertFalse(Path(self.source_image_path).exists())

        # Run the thumbnail cleanup command with last_n_days parameter
        call_command('thumbnail_cleanup', last_n_days=5, verbosity=2)

        # Verify the thumbnail has not been deleted
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Verify the source reference has not been deleted
        self.assertIsNotNone(Source.objects.get(id=self.source.id))

        # Run the thumbnail cleanup command with last_n_days parameter
        # that includes the source
        call_command('thumbnail_cleanup', last_n_days=15, verbosity=2)

        # Verify the thumbnail has been deleted
        self.assertFalse(Path(self.thumbnail_path).exists())

        # Verify the source reference has been deleted
        with self.assertRaises(Source.DoesNotExist):
            Source.objects.get(id=self.source.id)

    def test_source_storage_hash_not_found(self):
        self.assertTrue(Path(self.source_image_path).exists())
        self.assertTrue(Path(self.thumbnail_path).exists())

        # Change the source's storage_hash to simulate an unknown storage hash
        self.source.storage_hash = 'unknown_storage_hash'
        self.source.save()

        # Run the thumbnail cleanup command
        call_command('thumbnail_cleanup', verbosity=2)

        # Verify the thumbnail and source still exist
        self.assertTrue(Path(self.thumbnail_path).exists())
        self.assertIsNotNone(Source.objects.get(id=self.source.id))
