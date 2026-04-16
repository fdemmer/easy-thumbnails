from pathlib import Path

from easy_thumbnails.management import (
    all_thumbnails,
    delete_all_thumbnails,
    delete_thumbnails,
    thumbnails_for_file,
)
from tests import utils as test


class ThumbnailCleanupTests(test.BaseTest):
    def test_can_import(self):
        """
        Just a simple test to see if we can actually import the command without
        any syntax errors.
        """
        import easy_thumbnails.management.commands.thumbnail_cleanup  # NOQA


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
