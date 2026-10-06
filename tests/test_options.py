from django.test import TestCase
from django.test.utils import override_settings

from easy_thumbnails.options import JPEG_CSS_444, ThumbnailOptions


class PreparedOptions(TestCase):
    def prepared(self, **kwargs):
        kwargs.setdefault('size', (100, 50))
        kwargs.setdefault('quality', 80)
        return ThumbnailOptions(kwargs).prepared_options()

    def test_default_size_and_quality(self):
        self.assertEqual(self.prepared(), ['100x50', 'q80'])

    def test_default_subsampling_omitted(self):
        self.assertEqual(self.prepared(), ['100x50', 'q80'])

    def test_size_and_quality(self):
        self.assertEqual(
            self.prepared(size=(600, 0), quality=95),
            ['600x0', 'q95'],
        )

    def test_subsampling(self):
        self.assertEqual(
            self.prepared(subsampling=JPEG_CSS_444),
            ['100x50', 'q80ss0'],
        )

    def test_boolean_option(self):
        self.assertEqual(
            self.prepared(crop=True),
            ['100x50', 'q80', 'crop'],
        )

    def test_falsy_values_skipped(self):
        self.assertEqual(
            self.prepared(crop=False, upscale=None, bw=0),
            ['100x50', 'q80'],
        )

    def test_string_option(self):
        self.assertEqual(
            self.prepared(crop='smart'),
            ['100x50', 'q80', 'crop-smart'],
        )

    def test_sequence_option(self):
        self.assertEqual(
            self.prepared(target=(20, 30)),
            ['100x50', 'q80', 'target-20,30'],
        )
        self.assertEqual(
            self.prepared(target=(20, None)),
            ['100x50', 'q80', 'target-20,None'],
        )
        self.assertEqual(
            self.prepared(target='20,30'),
            ['100x50', 'q80', 'target-20,30'],
        )
        self.assertEqual(
            self.prepared(target=',30'),
            ['100x50', 'q80', 'target-,30'],
        )
        self.assertEqual(
            self.prepared(crop='-10,-0'),
            ['100x50', 'q80', 'crop--10,-0'],
        )

    def test_non_iterable_option(self):
        self.assertEqual(
            self.prepared(sharpen=3),
            ['100x50', 'q80', 'sharpen-3'],
        )

    def test_options_sorted(self):
        self.assertEqual(
            self.prepared(upscale=True, crop=True, bw=True),
            ['100x50', 'q80', 'bw', 'crop', 'upscale'],
        )

    def test_uppercase_keys_ignored(self):
        self.assertEqual(
            self.prepared(ALIAS='very_large', crop=True),
            ['100x50', 'q80', 'crop'],
        )

    def test_format_option_ignored(self):
        self.assertEqual(
            self.prepared(format='jpeg'),
            ['100x50', 'q80'],
        )

    @override_settings(THUMBNAIL_DEFAULT_OPTIONS={'crop': True})
    def test_default_options_setting(self):
        self.assertEqual(
            self.prepared(),
            ['100x50', 'q80', 'crop'],
        )


class FormatNormalization(TestCase):
    def test_normalized(self):
        for value, expected in [
            ('jpeg', 'jpg'),
            ('.JPEG', 'jpg'),
            ('WebP', 'webp'),
            ('.avif', 'avif'),
        ]:
            options = ThumbnailOptions({'size': (1, 1), 'format': value})
            self.assertEqual(options['format'], expected)

    def test_unsupported(self):
        with self.assertRaises(ValueError):
            ThumbnailOptions({'size': (1, 1), 'format': 'gif'})
