import base64
import unittest

from PIL import Image

from easy_thumbnails import hashers


try:
    import thumbhash
except ImportError:
    thumbhash = None


class DefaultHasherTest(unittest.TestCase):
    def test_non_pil_image(self):
        self.assertIsNone(hashers.default(object()))

    @unittest.skipIf(thumbhash is None, 'requires the thumbhash extra')
    def test_thumbhash(self):
        image = Image.new('RGB', (400, 200), (255, 0, 0))
        result = hashers.default(image)
        self.assertLessEqual(len(result), 64)
        w, h, rgba = thumbhash.thumb_hash_to_rgba(base64.b64decode(result))
        self.assertGreater(w, h)
        # the source image is not modified
        self.assertEqual(image.size, (400, 200))
