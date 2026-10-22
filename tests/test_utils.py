import unittest

from PIL import features

from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.utils.functional import LazyObject

from easy_thumbnails import utils


class LazyStorage(LazyObject):
    def _setup(self):
        self._wrapped = FileSystemStorage()


class GetStorageHashTest(TestCase):
    def test_string(self):
        backend = 'django.core.files.storage.filesystem.FileSystemStorage'
        self.assertEqual(
            utils.get_storage_hash(backend),
            utils.get_storage_hash(FileSystemStorage()),
        )

    def test_lazy_object_not_yet_set_up(self):
        lazy = LazyStorage()
        self.assertEqual(
            utils.get_storage_hash(lazy),
            utils.get_storage_hash(FileSystemStorage()),
        )

    def test_lazy_object_already_set_up(self):
        lazy = LazyStorage()
        lazy.exists('x')  # triggers _setup()
        self.assertEqual(
            utils.get_storage_hash(lazy),
            utils.get_storage_hash(FileSystemStorage()),
        )


class GetPilFormatTest(TestCase):
    def test_known_extensions(self):
        for extension, expected in (
            ('jpg', 'JPEG'),
            ('JPEG', 'JPEG'),
            ('webp', 'WEBP'),
            ('png', 'PNG'),
        ):
            self.assertEqual(utils.get_pil_format(extension), expected)

    @unittest.skipUnless(features.check('avif'), 'AVIF not supported by Pillow')
    def test_avif(self):
        self.assertEqual(utils.get_pil_format('avif'), 'AVIF')

    def test_unknown_or_empty_extension(self):
        self.assertEqual(utils.get_pil_format(''), 'JPEG')
        self.assertEqual(utils.get_pil_format('foo'), 'JPEG')
