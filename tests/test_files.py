import unittest
from io import BytesIO
from os import path
from pathlib import Path
from unittest import mock

from PIL import Image, features
from testfixtures import LogCapture

from django.test import TestCase

from easy_thumbnails import engine, exceptions, files, models, signals, utils
from easy_thumbnails.alias import aliases
from easy_thumbnails.conf import settings
from easy_thumbnails.options import ThumbnailOptions
from tests import utils as test


TESTS_DIR = Path(__file__).parent


def fake_hasher(image):
    return 'fake-{}x{}'.format(*image.size)


class FilesTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        self.storage = test.TemporaryStorage()
        self.remote_storage = test.FakeRemoteStorage()

        # Save a test image in both storages.
        filename = self.create_image(self.storage, 'test.jpg')
        self.thumbnailer = files.get_thumbnailer(self.storage, filename)
        self.thumbnailer.thumbnail_storage = self.storage

        filename = self.create_image(self.remote_storage, 'test.jpg')
        self.remote_thumbnailer = files.get_thumbnailer(self.remote_storage, filename)
        self.remote_thumbnailer.thumbnail_storage = self.remote_storage

        # Create another thumbnailer for extension test.
        self.ext_thumbnailer = files.get_thumbnailer(self.storage, filename)
        self.ext_thumbnailer.thumbnail_storage = self.storage

        # Generate test transparent images.
        filename = self.create_image(
            self.storage, 'transparent.png', image_mode='RGBA', image_format='PNG'
        )
        self.transparent_thumbnailer = files.get_thumbnailer(self.storage, filename)
        self.transparent_thumbnailer.thumbnail_storage = self.storage

        filename = self.create_image(
            self.storage, 'transparent-greyscale.png', image_mode='LA', image_format='PNG'
        )
        self.transparent_greyscale_thumbnailer = files.get_thumbnailer(
            self.storage, filename
        )
        self.transparent_greyscale_thumbnailer.thumbnail_storage = self.storage

    def tearDown(self):
        self.storage.delete_temporary_storage()
        self.remote_storage.delete_temporary_storage()
        super().tearDown()

    def test_tag(self):
        local = self.thumbnailer.get_thumbnail({'size': (100, 100)})
        remote = self.remote_thumbnailer.get_thumbnail({'size': (100, 100)})

        self.assertEqual(
            local.tag(), f'<img alt="" height="75" src="{local.url}" width="100" />'
        )
        self.assertEqual(
            local.tag(alt='A & B'),
            f'<img alt="A &amp; B" height="75" src="{local.url}" width="100" />',
        )

        # Can turn off dimensions.
        self.assertEqual(remote.tag(use_size=False), f'<img alt="" src="{remote.url}" />')

        # Even a remotely generated thumbnail has the dimensions cached if it
        # was just created.
        self.assertEqual(
            remote.tag(), f'<img alt="" height="75" src="{remote.url}" width="100" />'
        )

        # Future requests to thumbnails on remote storage don't get
        # dimensions...
        remote = self.remote_thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(remote.tag(), f'<img alt="" src="{remote.url}" />')
        # ...unless explicitly requested.
        self.assertEqual(
            remote.tag(use_size=True),
            f'<img alt="" height="75" src="{remote.url}" width="100" />',
        )

        # All other arguments are passed through as attributes.
        self.assertEqual(
            local.tag(**{'rel': 'A&B', 'class': 'fish'}),
            f'<img alt="" class="fish" height="75" rel="A&amp;B"'
            f' src="{local.url}" width="100" />',
        )

    def test_tag_cached_dimensions(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        self.remote_thumbnailer.get_thumbnail({'size': (100, 100)})

        # Look up thumbnail again to ensure dimensions are a *really* cached.
        remote = self.remote_thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(
            remote.tag(), f'<img alt="" height="75" src="{remote.url}" width="100" />'
        )

    def test_transparent_thumbnailing(self):
        thumb_file = self.thumbnailer.get_thumbnail({'size': (100, 100)})
        thumb_file.seek(0)
        with Image.open(thumb_file) as thumb:
            self.assertFalse(
                utils.is_transparent(thumb),
                f"{thumb_file.name} shouldn't be transparent.",
            )

        thumb_file = self.transparent_thumbnailer.get_thumbnail({'size': (100, 100)})
        thumb_file.seek(0)
        with Image.open(thumb_file) as thumb:
            self.assertTrue(
                utils.is_transparent(thumb), f'{thumb_file.name} should be transparent.'
            )

        thumb_file = self.transparent_greyscale_thumbnailer.get_thumbnail(
            {'size': (100, 100)}
        )
        thumb_file.seek(0)
        with Image.open(thumb_file) as thumb:
            self.assertTrue(
                utils.is_transparent(thumb), f'{thumb_file.name} should be transparent.'
            )

    def test_missing_thumb(self):
        opts = {'size': (100, 100)}
        thumb = self.thumbnailer.get_thumbnail(opts)
        thumb_cache = self.thumbnailer.get_thumbnail_cache(thumbnail_name=thumb.name)
        thumb_cache.delete()
        thumb.storage.delete(thumb.name)
        self.thumbnailer.get_thumbnail(opts)

    def test_missing_thumb_from_storage(self):
        opts = {'size': (100, 100)}
        thumb = self.thumbnailer.get_thumbnail(opts)
        thumb.storage.delete(thumb.name)
        new_thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual(thumb.name, new_thumb.name)
        self.assertTrue(thumb.storage.exists(new_thumb.name))

    def test_missing_remote_thumb(self):
        opts = {'size': (100, 100)}
        thumb = self.remote_thumbnailer.get_thumbnail(opts)
        thumb_cache = self.remote_thumbnailer.get_thumbnail_cache(
            thumbnail_name=thumb.name
        )
        thumb_cache.delete()
        thumb.storage.delete(thumb.name)
        self.remote_thumbnailer.get_thumbnail(opts)

    def test_missing_source(self):
        opts = {'size': (100, 100)}
        self.storage.delete(self.thumbnailer.name)
        self.assertRaises(
            exceptions.InvalidImageFormatError, self.thumbnailer.get_thumbnail, opts
        )

    def test_extensions(self):
        self.ext_thumbnailer.thumbnail_extension = 'png'
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(path.splitext(thumb.name)[1], '.png')

        self.ext_thumbnailer.thumbnail_preserve_extensions = ('foo',)
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(path.splitext(thumb.name)[1], '.png')

        self.ext_thumbnailer.thumbnail_preserve_extensions = True
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(path.splitext(thumb.name)[1], '.jpg')

        self.ext_thumbnailer.thumbnail_preserve_extensions = ('foo', 'jpg')
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(path.splitext(thumb.name)[1], '.jpg')

    def test_output_extension_fallback(self):
        filename = self.create_image(self.storage, 'noext')
        thumbnailer = files.get_thumbnailer(self.storage, filename)
        thumbnailer.thumbnail_storage = self.storage
        thumbnailer.thumbnail_preserve_extensions = True
        self.assertEqual(thumbnailer.get_output_extension({}), 'jpg')
        thumb = thumbnailer.get_thumbnail({'size': (100, 100)})
        self.assertEqual(path.splitext(thumb.name)[1], '.jpg')

        self.ext_thumbnailer.thumbnail_extension = ''
        self.assertEqual(self.ext_thumbnailer.get_output_extension({}), 'jpg')

    def test_format_option_extension(self):
        self.ext_thumbnailer.thumbnail_extension = 'png'
        self.ext_thumbnailer.thumbnail_preserve_extensions = True
        for value, ext in (
            ('webp', '.webp'),
            ('avif', '.avif'),
            ('jpeg', '.jpg'),
            ('JPG', '.jpg'),
        ):
            thumb = self.ext_thumbnailer.get_thumbnail(
                {'size': (100, 100), 'format': value}
            )
            self.assertEqual(path.splitext(thumb.name)[1], ext)

    def test_format_option_webp_image(self):
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100), 'format': 'webp'})
        with Image.open(thumb.path) as im:
            self.assertEqual(im.format, 'WEBP')

    @unittest.skipUnless(features.check('avif'), 'AVIF not supported by Pillow')
    def test_format_option_avif_image(self):
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100), 'format': 'avif'})
        with Image.open(thumb.path) as im:
            self.assertEqual(im.format, 'AVIF')

    def test_format_option_invalid(self):
        with self.assertRaises(ValueError):
            self.ext_thumbnailer.get_thumbnail({'size': (100, 100), 'format': 'gif'})

    def _saved_quality(self, thumbnailer, options):
        """
        Generate a thumbnail and return its name and the quality passed to
        ``engine.save_pil_image`` (``None`` if not passed).
        """
        with mock.patch.object(
            engine, 'save_pil_image', wraps=engine.save_pil_image
        ) as save:
            thumb = thumbnailer.get_thumbnail(options)
        return thumb.name, save.call_args.kwargs.get('quality')

    def test_default_quality(self):
        name, quality = self._saved_quality(self.ext_thumbnailer, {'size': (100, 100)})
        self.assertIn('_q76', name)
        self.assertEqual(quality, 76)

    def test_quality_per_format(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {
            'JPEG': {'quality': 76},
            'WEBP': {'quality': 80, 'method': 6},
            'AVIF': {'quality': 61},
        }
        formats = [('jpeg', 76), ('webp', 80)]
        if features.check('avif'):
            formats.append(('avif', 61))
        for fmt, expected in formats:
            name, quality = self._saved_quality(
                self.ext_thumbnailer, {'size': (100, 100), 'format': fmt}
            )
            self.assertIn(f'_q{expected}.', name)
            self.assertEqual(quality, expected)

    def test_quality_per_format_from_extension(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {
            'JPEG': {'quality': 76},
            'WEBP': {'quality': 80},
        }
        self.ext_thumbnailer.thumbnail_extension = 'webp'
        name, quality = self._saved_quality(self.ext_thumbnailer, {'size': (100, 100)})
        self.assertIn('_q80.webp', name)
        self.assertEqual(quality, 80)

    def test_quality_option_overrides_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'WEBP': {'quality': 80}}
        name, quality = self._saved_quality(
            self.ext_thumbnailer, {'size': (100, 100), 'format': 'webp', 'quality': 50}
        )
        self.assertIn('_q50.webp', name)
        self.assertEqual(quality, 50)

    def test_default_options_quality_overrides_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'WEBP': {'quality': 80}}
        settings.THUMBNAIL_DEFAULT_OPTIONS = {'quality': 40}
        name, quality = self._saved_quality(
            self.ext_thumbnailer, {'size': (100, 100), 'format': 'webp'}
        )
        self.assertIn('_q40.webp', name)
        self.assertEqual(quality, 40)

    def test_quality_without_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'JPEG': {'quality': 76}}
        name, quality = self._saved_quality(
            self.ext_thumbnailer, {'size': (100, 100), 'format': 'webp'}
        )
        self.assertNotIn('_q', name)
        self.assertTrue(name.endswith('.100x100.webp'), name)
        self.assertIsNone(quality)

    def test_quality_none_uses_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'WEBP': {'quality': 80}}
        for options in (
            {'size': (100, 100), 'format': 'webp', 'quality': None},
            ThumbnailOptions({'size': (100, 100), 'format': 'webp', 'quality': None}),
        ):
            opts = self.ext_thumbnailer.resolve_quality(
                self.ext_thumbnailer.get_options(options)
            )
            self.assertEqual(opts['quality'], 80)
            name = self.ext_thumbnailer.get_thumbnail_name(options)
            self.assertTrue(name.endswith('_q80.webp'), name)

    def test_quality_none_without_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {}
        for options in (
            {'size': (100, 100), 'quality': None},
            ThumbnailOptions({'size': (100, 100), 'quality': None}),
        ):
            name = self.ext_thumbnailer.get_thumbnail_name(options)
            self.assertTrue(name.endswith('.100x100.jpg'), name)

    def test_quality_of_preserved_png(self):
        self.transparent_thumbnailer.thumbnail_preserve_extensions = ('png',)
        name, quality = self._saved_quality(
            self.transparent_thumbnailer, {'size': (100, 100)}
        )
        self.assertTrue(name.endswith('.100x100.png'), name)
        self.assertIsNone(quality)

    def test_quality_transparent_uses_transparency_format(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {
            'JPEG': {'quality': 76},
            'WEBP': {'quality': 80},
        }
        self.transparent_thumbnailer.thumbnail_transparency_extension = 'webp'
        name, quality = self._saved_quality(
            self.transparent_thumbnailer, {'size': (100, 100)}
        )
        self.assertTrue(name.endswith('_q80.webp'), name)
        self.assertEqual(quality, 80)
        thumb = self.transparent_thumbnailer.get_existing_thumbnail({'size': (100, 100)})
        self.assertEqual(thumb.name, name)
        self.assertEqual(thumb.thumbnail_options['quality'], 80)
        # The opaque variant still uses the regular format's default.
        self.assertTrue(
            self.transparent_thumbnailer.get_thumbnail_name(
                {'size': (100, 100)}
            ).endswith('_q76.jpg')
        )

    def test_quality_transparent_png(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'JPEG': {'quality': 76}}
        self.transparent_thumbnailer.thumbnail_transparency_extension = 'png'
        name, quality = self._saved_quality(
            self.transparent_thumbnailer, {'size': (100, 100)}
        )
        self.assertTrue(name.endswith('.100x100.png'), name)
        self.assertIsNone(quality)

    def test_resolve_quality_thumbnail_options_instance(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'WEBP': {'quality': 80}}
        options = ThumbnailOptions({'size': (100, 100), 'format': 'webp'})
        opts = self.ext_thumbnailer.resolve_quality(
            self.ext_thumbnailer.get_options(options)
        )
        self.assertEqual(opts['quality'], 80)
        self.assertNotIn('quality', options)

    def _alias_quality(self, alias_options, **thumbnailer_kwargs):
        """
        Generate the ``q`` alias with ``alias_options`` and return its name
        and the quality passed to ``engine.save_pil_image``.
        """
        aliases.set('q', alias_options)
        self.addCleanup(aliases.populate_from_settings)
        with mock.patch.object(
            engine, 'save_pil_image', wraps=engine.save_pil_image
        ) as save:
            thumb = self.ext_thumbnailer['q']
        return thumb.name, save.call_args.kwargs.get('quality')

    def test_alias_quality_overrides_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {'JPEG': {'quality': 76}}
        name, quality = self._alias_quality({'size': (100, 100), 'quality': 50})
        self.assertIn('_q50.jpg', name)
        self.assertEqual(quality, 50)

    def test_alias_quality_overrides_default_options(self):
        settings.THUMBNAIL_DEFAULT_OPTIONS = {'quality': 40}
        name, quality = self._alias_quality({'size': (100, 100), 'quality': 50})
        self.assertIn('_q50.jpg', name)
        self.assertEqual(quality, 50)

    def test_alias_format_uses_format_default(self):
        settings.THUMBNAIL_IMAGE_SAVE_OPTIONS = {
            'JPEG': {'quality': 76},
            'WEBP': {'quality': 80},
        }
        name, quality = self._alias_quality({'size': (100, 100), 'format': 'webp'})
        self.assertIn('_q80.webp', name)
        self.assertEqual(quality, 80)

    def test_subsampling(self):
        samplings = {
            0: (1, 1, 1, 1, 1, 1),
            1: (2, 1, 1, 1, 1, 1),
            2: (2, 2, 1, 1, 1, 1),
        }
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100)})
        with Image.open(thumb.path) as im:
            self.assertNotIn('ss', thumb.name)
            sampling = im.layer[0][1:3] + im.layer[1][1:3] + im.layer[2][1:3]
            self.assertEqual(sampling, samplings[2])

        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100), 'subsampling': 1})
        with Image.open(thumb.path) as im:
            self.assertIn('ss1', thumb.name)
            sampling = im.layer[0][1:3] + im.layer[1][1:3] + im.layer[2][1:3]
            self.assertEqual(sampling, samplings[1])

        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100), 'subsampling': 0})
        with Image.open(thumb.path) as im:
            self.assertIn('ss0', thumb.name)
            sampling = im.layer[0][1:3] + im.layer[1][1:3] + im.layer[2][1:3]
            self.assertEqual(sampling, samplings[0])

    def test_default_subsampling(self):
        settings.THUMBNAIL_DEFAULT_OPTIONS = {'subsampling': 1}
        thumb = self.ext_thumbnailer.get_thumbnail({'size': (100, 100)})
        with Image.open(thumb.path) as im:
            self.assertIn('ss1', thumb.name)
            sampling = im.layer[0][1:3] + im.layer[1][1:3] + im.layer[2][1:3]
            self.assertEqual(sampling, (2, 1, 1, 1, 1, 1))

    @unittest.skipIf(
        'easy_thumbnails.optimize' not in settings.INSTALLED_APPS,
        'optimize app not installed',
    )
    def test_postprocessor(self):
        """Use a mock image optimizing post processor doing nothing"""
        settings.THUMBNAIL_OPTIMIZE_COMMAND = {
            'png': f'{TESTS_DIR}/mockoptim.py {{filename}}'
        }
        with LogCapture() as logcap:
            self.ext_thumbnailer.thumbnail_extension = 'png'
            self.ext_thumbnailer.get_thumbnail({'size': (10, 10)})
            actual = tuple(logcap.actual())[-1]
            self.assertEqual(actual[0], 'easy_thumbnails.optimize')
            self.assertEqual(actual[1], 'INFO')
            self.assertRegex(actual[2], r'^.+/mockoptim\.py [^ ]+ returned nothing$')

    @unittest.skipIf(
        'easy_thumbnails.optimize' not in settings.INSTALLED_APPS,
        'optimize app not installed',
    )
    @unittest.skipIf(LogCapture is None, 'testfixtures not installed')
    def test_postprocessor_fail(self):
        """Use a mock image optimizing post processor doing nothing"""
        settings.THUMBNAIL_OPTIMIZE_COMMAND = {
            'png': f'{TESTS_DIR}/mockoptim_fail.py {{filename}}'
        }
        with LogCapture() as logcap:
            self.ext_thumbnailer.thumbnail_extension = 'png'
            self.ext_thumbnailer.get_thumbnail({'size': (10, 10)})
            actual = tuple(logcap.actual())[-1]
            self.assertEqual(actual[0], 'easy_thumbnails.optimize')
            self.assertEqual(actual[1], 'ERROR')
            self.assertRegex(actual[2], r'^Command .+returned non-zero exit status 1.*$')

    def test_USE_TZ(self):
        settings.USE_TZ = True
        self.thumbnailer.get_thumbnail({'size': (10, 20)})

        settings.USE_TZ = False
        self.thumbnailer.get_thumbnail({'size': (20, 40)})

    def test_thumbnailfile_options(self):
        opts = {'size': (50, 50), 'crop': True, 'upscale': True}
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual(
            thumb.thumbnail_options,
            self.thumbnailer.resolve_quality(self.thumbnailer.get_options(opts)),
        )
        self.assertEqual(thumb.thumbnail_options['quality'], 76)

    def test_get_thumbnail_name(self):
        opts = {'size': (50, 50), 'crop': 'smart', 'upscale': True, 'target': (10, 10)}
        self.assertEqual(
            self.thumbnailer.get_thumbnail_name(opts),
            'test.jpg.50x50_q76_crop-smart_target-10,10_upscale.jpg',
        )

    def test_get_thumbnail_name_strips_location_prefix_only(self):
        location = self.thumbnailer.source_storage.location
        self.thumbnailer.name = f'{location}/sub{location}/test.jpg'
        self.assertEqual(
            self.thumbnailer.get_thumbnail_name({'size': (50, 50)}),
            f'sub{location}/test.jpg.50x50_q76.jpg'.lstrip('/'),
        )

    def test_default_options_setting(self):
        settings.THUMBNAIL_DEFAULT_OPTIONS = {'crop': True}
        opts = {'size': (50, 50)}
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual((thumb.width, thumb.height), (50, 50))

    def test_dimensions_of_cached_image(self):
        opts = {'size': (50, 50)}
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual((thumb.width, thumb.height), (50, 38))
        # Now the thumb has been created, check that retrieving this still
        # gives access to the dimensions.
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual((thumb.width, thumb.height), (50, 38))

    def test_cached_dimensions_of_cached_image(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        opts = {'size': (50, 50)}
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual((thumb.width, thumb.height), (50, 38))
        # Now the thumb has been created, check that dimensions are in the
        # database.
        dimensions = models.ThumbnailDimensions.objects.all()[0]
        self.assertEqual(
            (thumb.width, thumb.height), (dimensions.width, dimensions.height)
        )

    def test_thumb_hash_custom_hasher(self):
        settings.THUMBNAIL_HASHER = 'tests.test_files.fake_hasher'
        self.assertIsNone(self.thumbnailer.get_thumb_hash())
        self.thumbnailer.get_thumbnail({'size': (50, 50)})
        source = models.Source.objects.get()
        self.assertEqual(source.thumb_hash, 'fake-800x600')
        self.assertEqual(self.thumbnailer.get_thumb_hash(), 'fake-800x600')

    def test_thumb_hash_disabled(self):
        settings.THUMBNAIL_HASHER = None
        self.thumbnailer.get_thumbnail({'size': (50, 50)})
        self.assertEqual(models.Source.objects.get().thumb_hash, '')

    def get_file_source_thumbnailer(self):
        source = BytesIO()
        Image.new('RGB', (800, 600)).save(source, 'JPEG')
        source.seek(0)
        thumbnailer = files.get_thumbnailer(source, 'test.jpg')
        thumbnailer.thumbnail_storage = self.storage
        return thumbnailer

    def test_file_source(self):
        settings.THUMBNAIL_HASHER = 'tests.test_files.fake_hasher'
        thumbnailer = self.get_file_source_thumbnailer()
        self.assertTrue(thumbnailer.remote_source)
        opts = {'size': (50, 50)}
        thumb = thumbnailer.get_thumbnail(opts)
        self.assertEqual(thumb.name, 'test.jpg.50x50_q76.jpg')
        self.assertTrue(self.storage.exists(thumb.name))
        # No cache is used, so the thumbnail is never found as existing.
        self.assertIsNone(thumbnailer.get_existing_thumbnail(opts))
        self.assertIsNone(thumbnailer.get_thumbnail(opts, generate=False))
        self.assertIsNone(thumbnailer.get_thumb_hash())
        self.assertEqual(models.Source.objects.count(), 0)
        self.assertEqual(models.Thumbnail.objects.count(), 0)

    def test_file_source_cache_dimensions(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        thumbnailer = self.get_file_source_thumbnailer()
        thumb = thumbnailer.get_thumbnail({'size': (50, 50)})
        self.assertEqual((thumb.width, thumb.height), (50, 38))
        self.assertEqual(models.ThumbnailDimensions.objects.count(), 0)

    def test_remote_cached_dimensions_queries(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        opts = {'size': (50, 50)}
        thumb = self.remote_thumbnailer.get_thumbnail(opts)
        # Trigger dimension caching.
        thumb.height  # noqa: B018
        # Get thumb again (which now has cached dimensions).
        thumb = self.remote_thumbnailer.get_thumbnail(opts)
        with self.assertNumQueries(0):
            self.assertEqual(thumb.width, 50)

    def _prefetch_queries(self, thumbnailer):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        options_list = [{'size': (50, 50)}, {'size': (30, 30)}]
        for opts in options_list:
            thumbnailer.get_thumbnail(opts)
        # use a fresh thumbnailer without cached source or dimensions
        storage = thumbnailer.thumbnail_storage
        thumbnailer = files.get_thumbnailer(storage, thumbnailer.name)
        thumbnailer.thumbnail_storage = storage
        with self.assertNumQueries(1):
            thumbnailer.prefetch_thumbnails(options_list)
        with self.assertNumQueries(0):
            thumbs = [thumbnailer.get_thumbnail(opts) for opts in options_list]
            sizes = [(thumb.width, thumb.height) for thumb in thumbs]
        self.assertEqual(sizes, [(50, 38), (30, 22)])

    def test_prefetch_thumbnails(self):
        self._prefetch_queries(self.thumbnailer)

    def test_remote_prefetch_thumbnails(self):
        self._prefetch_queries(self.remote_thumbnailer)

    def test_prefetch_thumbnails_generates_missing(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        self.remote_thumbnailer.get_thumbnail({'size': (50, 50)})
        thumbnailer = files.get_thumbnailer(self.remote_storage, 'test.jpg')
        thumbnailer.thumbnail_storage = self.remote_storage
        options_list = [{'size': (50, 50)}, {'size': (30, 30)}]
        thumbnailer.prefetch_thumbnails(options_list)
        thumbs = [thumbnailer.get_thumbnail(opts) for opts in options_list]
        self.assertEqual([(t.width, t.height) for t in thumbs], [(50, 38), (30, 22)])
        # the generated thumbnail is not served from the (stale) prefetch
        self.assertEqual(models.Thumbnail.objects.count(), 2)
        thumb = thumbnailer.get_thumbnail({'size': (30, 30)})
        self.assertEqual((thumb.width, thumb.height), (30, 22))

    def test_remote_transparent_thumbnail_queries(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        opts = {'size': (50, 50)}
        filename = self.create_image(
            self.remote_storage, 'transparent.png', image_mode='RGBA', image_format='PNG'
        )

        def get_thumbnailer():
            thumbnailer = files.get_thumbnailer(self.remote_storage, filename)
            thumbnailer.thumbnail_storage = self.remote_storage
            return thumbnailer

        created = get_thumbnailer().get_thumbnail(opts)
        self.assertTrue(created.name.endswith('.png'))

        thumbnailer = get_thumbnailer()
        # jpg name (missing), png name (existing) and source in one query
        with self.assertNumQueries(1):
            thumb = thumbnailer.get_thumbnail(opts)
        self.assertEqual(thumb.name, created.name)
        with self.assertNumQueries(0):
            self.assertEqual((thumb.width, thumb.height), (50, 38))
            self.assertEqual(thumbnailer.get_thumbnail(opts).name, created.name)

    def test_remote_missing_thumbnail_is_generated(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        thumbnailer = self.remote_thumbnailer
        self.assertIsNone(thumbnailer.get_existing_thumbnail({'size': (50, 50)}))
        thumb = thumbnailer.get_thumbnail({'size': (50, 50)})
        self.assertEqual((thumb.width, thumb.height), (50, 38))
        # the stale "missing" entry was dropped when the thumbnail was saved
        self.assertIsNotNone(thumbnailer.get_existing_thumbnail({'size': (50, 50)}))

    def test_prefetch_aliases(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        aliases.set('small', {'size': (50, 50)})
        aliases.set('tiny', {'size': (30, 30)})
        self.addCleanup(aliases.populate_from_settings)
        for alias in ('small', 'tiny'):
            self.remote_thumbnailer.get_thumbnail({**aliases.get(alias), 'ALIAS': alias})
        thumbnailer = files.get_thumbnailer(self.remote_storage, 'test.jpg')
        thumbnailer.thumbnail_storage = self.remote_storage
        with self.assertNumQueries(1):
            thumbnailer.prefetch_aliases(['small', 'tiny'])
        with self.assertNumQueries(0):
            thumbs = [thumbnailer[alias] for alias in ('small', 'tiny')]
            sizes = [(thumb.width, thumb.height) for thumb in thumbs]
        self.assertEqual(sizes, [(50, 38), (30, 22)])
        with self.assertRaises(KeyError):
            thumbnailer.prefetch_aliases(['unknown'])

    def test_add_dimension_cache(self):
        settings.THUMBNAIL_CACHE_DIMENSIONS = True
        opts = {'size': (50, 50)}
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual((thumb.width, thumb.height), (50, 38))
        # Delete the created dimensions.
        models.ThumbnailDimensions.objects.all().delete()
        # Now access the thumbnail again.
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual(models.ThumbnailDimensions.objects.count(), 0)
        thumb.height  # noqa: B018
        dimensions = models.ThumbnailDimensions.objects.get()
        # and make sure they match when fetched again.
        thumb = self.thumbnailer.get_thumbnail(opts)
        self.assertEqual(
            (thumb.width, thumb.height), (dimensions.width, dimensions.height)
        )

        # close the filefield (cause unclosed file ResourceWarning)
        thumb.close()

    def test_thumbnail_created_signal(self):

        def signal_handler(sender, **kwargs):
            sender.signal_received = True

        signals.thumbnail_created.connect(signal_handler)
        try:
            thumb = self.thumbnailer.get_thumbnail({'size': (10, 20)})
            self.assertTrue(hasattr(thumb, 'signal_received'))
        finally:
            signals.thumbnail_created.disconnect(signal_handler)

    def test_passive_thumbnailer(self):
        options = {'size': (10, 10)}

        # Explicitly using the generate=False option on get_thumbnail won't
        # generate a missing thumb.
        thumb = self.thumbnailer.get_thumbnail(options, generate=False)
        self.assertEqual(thumb, None)

        # If the thumbnailer has generate=False, get_thumbnail won't generate a
        # missing thumb by default.
        self.thumbnailer.generate = False
        thumb = self.thumbnailer.get_thumbnail(options)
        self.assertEqual(thumb, None)

        # If the thumbnailer has generate=False, get_thumbnail with
        # generate=True will stiff force generation a missing thumb.
        thumb = self.thumbnailer.get_thumbnail(options, generate=True)
        self.assertTrue(thumb)

        # If the thumbnailer has generate=False, get_thumbnail will still
        # return existing thumbnails.
        thumb = self.thumbnailer.get_thumbnail(options)
        self.assertTrue(thumb)

        # Explicitly using the generate=False option on get_thumbnail will
        # still return existing thumbnails.
        thumb = self.thumbnailer.get_thumbnail(options, generate=False)
        self.assertTrue(thumb)

    def test_thumbnail_missed_signal(self):

        def signal_handler(sender, **kwargs):
            sender.missed_signal = kwargs.get('options')

        signals.thumbnail_missed.connect(signal_handler)
        try:
            # Standard generation doesn't trigger signal.
            self.thumbnailer.get_thumbnail({'size': (100, 100)})
            self.assertFalse(hasattr(self.thumbnailer, 'missed_signal'))
            # Retrieval doesn't trigger signal.
            self.thumbnailer.get_thumbnail({'size': (100, 100)}, generate=False)
            self.assertFalse(hasattr(self.thumbnailer, 'missed_signal'))
            # A thumbnail miss does trigger it.
            options = {'size': (10, 20)}
            thumb = self.thumbnailer.get_thumbnail(options, generate=False)
            self.assertEqual(thumb, None)
            self.assertEqual(
                self.thumbnailer.missed_signal, self.thumbnailer.get_options(options)
            )
        finally:
            signals.thumbnail_created.disconnect(signal_handler)

    def test_progressive_encoding(self):
        thumb = self.thumbnailer.generate_thumbnail({'size': (99, 99), 'crop': True})
        with Image.open(thumb) as thumb_image:
            self.assertFalse(utils.is_progressive(thumb_image))

        thumb = self.thumbnailer.generate_thumbnail({'size': (1, 100), 'crop': True})
        with Image.open(thumb) as thumb_image:
            self.assertTrue(utils.is_progressive(thumb_image))
        thumb = self.thumbnailer.generate_thumbnail({'size': (100, 1), 'crop': True})
        with Image.open(thumb) as thumb_image:
            self.assertTrue(utils.is_progressive(thumb_image))
        thumb = self.thumbnailer.generate_thumbnail({'size': (200, 200)})
        with Image.open(thumb) as thumb_image:
            self.assertTrue(utils.is_progressive(thumb_image))

    def test_no_progressive_encoding(self):
        settings.THUMBNAIL_PROGRESSIVE = False
        thumb = self.thumbnailer.generate_thumbnail({'size': (200, 200)})
        with Image.open(thumb) as thumb_image:
            self.assertFalse(utils.is_progressive(thumb_image))


class FakeSourceGenerator:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, source, **kwargs):
        if self.fail:
            raise ValueError('Fake source generator failed')
        return source


class EngineTest(TestCase):
    def setUp(self):
        self.source = BytesIO(b'file-contents')

    def test_single_fail(self):
        source_generators = [FakeSourceGenerator(fail=True)]
        self.assertRaises(
            ValueError,
            engine.generate_source_image,
            self.source,
            {},
            source_generators,
            fail_silently=False,
        )

    def test_single_silent_fail(self):
        source_generators = [FakeSourceGenerator(fail=True)]
        image = engine.generate_source_image(self.source, {}, source_generators)
        self.assertEqual(image, None)

    def test_multiple_fail(self):
        source_generators = [
            FakeSourceGenerator(fail=True),
            FakeSourceGenerator(fail=True),
        ]
        self.assertRaises(
            engine.NoSourceGenerator,
            engine.generate_source_image,
            self.source,
            {},
            source_generators,
            fail_silently=False,
        )

    def test_multiple_silent_fail(self):
        source_generators = [
            FakeSourceGenerator(fail=True),
            FakeSourceGenerator(fail=True),
        ]
        image = engine.generate_source_image(self.source, {}, source_generators)
        self.assertEqual(image, None)
