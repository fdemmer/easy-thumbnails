"""
Tests for the models module.
"""

from easy_thumbnails import utils
from easy_thumbnails.models import Source, Thumbnail
from tests import utils as test


class FileManagerTest(test.BaseTest):
    """Test for FileManager"""

    def setUp(self):
        super().setUp()

        self.storage = test.TemporaryStorage()
        self.storage_hash = utils.get_storage_hash(self.storage)
        self.source = Source.objects.create(
            name='Test source', storage_hash=self.storage_hash
        )

        # Generate a test image, save it.
        self.filename = self.create_image(self.storage, 'test.jpg')

    def tearDown(self):
        self.storage.delete_temporary_storage()
        super().tearDown()

    def test_create_file(self):
        """Create a new Thumbnail in the database"""
        img = Thumbnail.objects.get_file(
            self.storage, self.filename, create=True, source=self.source
        )

        self.assertEqual(img.name, self.filename)

    def test_get_file(self):
        """Fetch an existing thumb from database"""
        created = Thumbnail.objects.create(
            storage_hash=self.storage_hash, name=self.filename, source=self.source
        )

        fetched = Thumbnail.objects.get_file(self.storage, self.filename, create=False)

        self.assertTrue(fetched)
        self.assertEqual(created, fetched)

    def test_get_file_check_cache(self):
        """Fetch a thumb that is in the storage but not in the database"""
        # It's not in the database yet
        try:
            Thumbnail.objects.get(name=self.filename)
            self.fail('Thumb should not exist yet')
        except Thumbnail.DoesNotExist:
            pass

        Thumbnail.objects.get_file(
            self.storage, self.filename, source=self.source, check_cache_miss=True
        )

        # Now it is
        try:
            Thumbnail.objects.get(name=self.filename)
        except Thumbnail.DoesNotExist:
            self.fail('Thumb should exist now')


class SourceTest(test.BaseTest):
    def test_thumb_hash_default(self):
        source = Source.objects.create(name='Test source', storage_hash='x')
        self.assertEqual(source.thumb_hash, '')


class NameLengthTest(test.BaseTest):
    def test_name_max_length(self):
        for model in (Source, Thumbnail):
            self.assertEqual(model._meta.get_field('name').max_length, 512)

    def test_long_names_round_trip(self):
        storage = test.TemporaryStorage()
        self.addCleanup(storage.delete_temporary_storage)
        name = 'a/' * 255 + 'b.jpg'
        self.assertGreater(len(name), 255)
        source = Source.objects.get_file(storage, name, create=True)
        thumbnail = Thumbnail.objects.create(
            name='thumbs/' + name + '.100x100_q76.jpg',
            storage_hash=source.storage_hash,
            source=source,
        )
        self.assertEqual(Source.objects.get(pk=source.pk).name, name)
        self.assertEqual(
            Thumbnail.objects.get(pk=thumbnail.pk).name,
            'thumbs/' + name + '.100x100_q76.jpg',
        )
