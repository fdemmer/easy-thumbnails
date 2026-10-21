import tempfile
from io import BytesIO
from pathlib import Path
from unittest import TestCase

from PIL import Image, ImageCms

from easy_thumbnails import engine, exceptions, processors


class SaveTest(TestCase):
    def test_save_jpeg_rgba(self):
        source = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
        data = engine.save_pil_image(source, filename='test.jpg')
        with Image.open(data) as img:
            self.assertEqual(img.mode, 'RGB')

    def test_save_jpeg_la(self):
        source = Image.new('LA', (100, 100), (255, 0))
        data = engine.save_pil_image(source, filename='test.jpg')
        with Image.open(data) as img:
            self.assertEqual(img.mode, 'L')

    def test_save_with_icc_profile(self):
        source = Image.new('RGB', (100, 100), (255, 255, 255))
        profile = ImageCms.createProfile('sRGB')

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / 'source.jpg'

            source.save(tmp_path, icc_profile=ImageCms.ImageCmsProfile(profile).tobytes())
            source = Image.open(tmp_path)

            data = engine.save_pil_image(source, filename='xx.jpg', keep_icc_profile=True)
            img = Image.open(data)

            self.assertNotEqual(img.info.get('icc_profile'), None)


def create_animated_gif(durations=(40, 80, 120), size=(40, 30)):
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    frames = [Image.new('RGB', size, color) for color in colors[: len(durations)]]
    data = BytesIO()
    frames[0].save(
        data,
        format='GIF',
        save_all=True,
        append_images=frames[1:],
        duration=list(durations),
        loop=3,
    )
    data.seek(0)
    return Image.open(data)


class AnimatedTest(TestCase):
    def test_process_animated_image(self):
        source = create_animated_gif()
        frames, durations = engine.process_animated_image(
            source, {'size': (20, 20)}, [processors.scale_and_crop]
        )
        self.assertEqual(len(frames), 3)
        self.assertEqual(durations, [40, 80, 120])
        for frame in frames:
            self.assertEqual(frame.size, (20, 15))

    def test_process_animated_image_autocrop(self):
        source = create_animated_gif()
        with self.assertRaises(exceptions.EasyThumbnailsError):
            engine.process_animated_image(
                source, {'size': (20, 20), 'autocrop': True}, [processors.autocrop]
            )

    def test_save_animated_webp(self):
        source = create_animated_gif()
        frames, durations = engine.process_animated_image(
            source, {'size': (20, 20)}, [processors.scale_and_crop]
        )
        data = engine.save_pil_image(
            frames[0],
            filename='test.webp',
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=source.info['loop'],
        )
        with Image.open(data) as img:
            self.assertEqual(img.format, 'WEBP')
            self.assertTrue(img.is_animated)
            self.assertEqual(img.n_frames, 3)
            self.assertEqual(img.info['loop'], 3)
