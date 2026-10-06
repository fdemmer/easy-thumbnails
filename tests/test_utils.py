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
