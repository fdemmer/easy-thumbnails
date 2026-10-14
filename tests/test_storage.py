import shutil
import tempfile
from pathlib import Path

from django.conf import settings as django_settings
from django.test import override_settings

from easy_thumbnails import storage
from easy_thumbnails.conf import settings
from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.storage import ThumbnailFileSystemStorage
from tests import utils as test


class ThumbnailFileSystemStorageTest(test.BaseTest):
    def test_defaults_to_media_settings(self):
        fs = ThumbnailFileSystemStorage()
        self.assertEqual(Path(fs.location), Path(django_settings.MEDIA_ROOT))
        self.assertEqual(fs.base_url, django_settings.MEDIA_URL)

    def test_thumbnail_media_root(self):
        settings.THUMBNAIL_MEDIA_ROOT = '/tmp/thumb_root'
        fs = ThumbnailFileSystemStorage()
        self.assertEqual(Path(fs.location), Path('/tmp/thumb_root'))
        self.assertEqual(Path(fs.path('x.jpg')), Path('/tmp/thumb_root/x.jpg'))
        # URL is unaffected.
        self.assertEqual(fs.base_url, django_settings.MEDIA_URL)

    def test_thumbnail_media_url(self):
        settings.THUMBNAIL_MEDIA_URL = '/thumbs/'
        fs = ThumbnailFileSystemStorage()
        self.assertEqual(fs.base_url, '/thumbs/')
        self.assertEqual(fs.url('x.jpg'), '/thumbs/x.jpg')
        # Root is unaffected.
        self.assertEqual(Path(fs.location), Path(django_settings.MEDIA_ROOT))

    def test_explicit_arguments_win(self):
        settings.THUMBNAIL_MEDIA_ROOT = '/tmp/thumb_root'
        settings.THUMBNAIL_MEDIA_URL = '/thumbs/'
        fs = ThumbnailFileSystemStorage(
            location='/tmp/explicit',
            base_url='/explicit/',
        )
        self.assertEqual(Path(fs.location), Path('/tmp/explicit'))
        self.assertEqual(fs.base_url, '/explicit/')


class ThumbnailMediaSettingsIntegrationTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        self.source_storage = test.TemporaryStorage()
        self.thumb_root = tempfile.mkdtemp()
        settings.THUMBNAIL_MEDIA_ROOT = self.thumb_root
        settings.THUMBNAIL_MEDIA_URL = '/thumbs/'
        self._old_thumbnail_default_storage = storage.thumbnail_default_storage
        storage.thumbnail_default_storage = ThumbnailFileSystemStorage()

    def tearDown(self):
        storage.thumbnail_default_storage = self._old_thumbnail_default_storage
        self.source_storage.delete_temporary_storage()
        shutil.rmtree(self.thumb_root, ignore_errors=True)
        super().tearDown()

    def test_thumbnail_uses_thumbnail_media_settings(self):
        name = self.create_image(self.source_storage, 'test.jpg')
        thumbnailer = get_thumbnailer(self.source_storage, name)
        thumb = thumbnailer.get_thumbnail({'size': (50, 50)})

        self.assertTrue(thumb.url.startswith('/thumbs/'))
        self.assertTrue((Path(self.thumb_root) / thumb.name).exists())
        # Nothing was written next to the source.
        self.assertFalse((Path(self.source_storage.location) / thumb.name).exists())


class GetStorageTest(test.BaseTest):
    def test_missing_alias_uses_thumbnail_settings(self):
        with override_settings(
            STORAGES={
                'default': {
                    'BACKEND': 'django.core.files.storage.FileSystemStorage',
                },
            },
        ):
            settings.THUMBNAIL_MEDIA_ROOT = '/tmp/thumb_root'
            settings.THUMBNAIL_MEDIA_URL = '/thumbs/'
            fs = storage.get_storage()
        self.assertIsInstance(fs, ThumbnailFileSystemStorage)
        self.assertEqual(Path(fs.location), Path('/tmp/thumb_root'))
        self.assertEqual(fs.base_url, '/thumbs/')

    def test_configured_alias_is_used(self):
        fs = storage.get_storage()
        self.assertIsInstance(fs, test.TemporaryStorage)

    def test_alias_with_thumbnail_storage_uses_thumbnail_settings(self):
        with override_settings(
            STORAGES={
                'easy_thumbnails': {
                    'BACKEND': 'easy_thumbnails.storage.ThumbnailFileSystemStorage',
                },
            },
        ):
            settings.THUMBNAIL_MEDIA_ROOT = '/tmp/thumb_root'
            settings.THUMBNAIL_MEDIA_URL = '/thumbs/'
            fs = storage.get_storage()
        self.assertEqual(Path(fs.location), Path('/tmp/thumb_root'))
        self.assertEqual(fs.base_url, '/thumbs/')
