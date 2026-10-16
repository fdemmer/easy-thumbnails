from unittest import TestCase

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from easy_thumbnails import engine, processors


def create_image(mode='RGB', size=(800, 600)):
    image = Image.new(mode, size, (255, 255, 255))
    draw = ImageDraw.Draw(image)
    x_bit, y_bit = size[0] // 10, size[1] // 10
    draw.rectangle((x_bit, y_bit * 2, x_bit * 7, y_bit * 3), 'red')
    draw.rectangle((x_bit * 2, y_bit, x_bit * 3, y_bit * 8), 'red')
    return image


class ScaleAndCropTest(TestCase):
    def assertImagesEqual(self, im1, im2, msg=None):
        if im1.size != im2.size or (
            ImageChops.difference(im1, im2).getbbox() is not None
        ):
            raise self.failureException(msg or 'The two images were not identical')

    def test_scale(self):
        image = create_image()

        scaled = processors.scale_and_crop(image, (100, 100))
        self.assertEqual(scaled.size, (100, 75))

        not_scaled = processors.scale_and_crop(image, (1000, 1000))
        self.assertEqual(not_scaled.size, (800, 600))

        upscaled = processors.scale_and_crop(image, (1000, 1000), upscale=True)
        self.assertEqual(upscaled.size, (1000, 750))

    def test_crop(self):
        image = create_image()

        both_cropped = processors.scale_and_crop(image, (100, 100), crop=True)
        self.assertEqual(both_cropped.size, (100, 100))

        not_cropped = processors.scale_and_crop(image, (1000, 1000), crop=True)
        self.assertEqual(not_cropped.size, (800, 600))

        x_cropped = processors.scale_and_crop(image, (600, 600), crop=True)
        expected = image.crop([100, 0, 700, 600])
        self.assertImagesEqual(x_cropped, expected)

        y_cropped = processors.scale_and_crop(image, (1000, 100), crop=True)
        expected = image.crop([0, 250, 800, 350])
        self.assertImagesEqual(y_cropped, expected)

    def test_crop_corner(self):
        image = create_image()

        tl_crop = processors.scale_and_crop(image, (100, 600), crop='0,0')
        expected = image.crop([0, 0, 100, 600])
        self.assertImagesEqual(tl_crop, expected)

        br_crop = processors.scale_and_crop(image, (100, 600), crop='-0,-0')
        expected = image.crop([700, 0, 800, 600])
        self.assertImagesEqual(br_crop, expected)

        x_offset_crop = processors.scale_and_crop(image, (150, 600), crop='10,-10')
        expected = image.crop([15, 0, 165, 600])

        self.assertImagesEqual(x_offset_crop, expected)

        y_offset_crop = processors.scale_and_crop(image, (800, 150), crop='10,-10')
        expected = image.crop([0, 435, 800, 585])
        self.assertImagesEqual(y_offset_crop, expected)

        only_x_crop = processors.scale_and_crop(image, (100, 600), crop='0,')
        expected = image.crop([0, 0, 100, 600])
        self.assertImagesEqual(only_x_crop, expected)

        only_y_crop = processors.scale_and_crop(image, (800, 100), crop=',0')
        expected = image.crop([0, 0, 800, 100])
        self.assertImagesEqual(only_y_crop, expected)

    def test_crop_smart(self):
        image = create_image()

        smart_crop = processors.scale_and_crop(image, (600, 600), crop='smart')
        expected = image.crop([78, 0, 678, 600])
        self.assertImagesEqual(smart_crop, expected)

    def test_crop_scale(self):
        image = create_image(size=(200, 400))

        scaled = processors.scale_and_crop(image, (100, 100), crop='scale')
        self.assertEqual(scaled.size, (100, 200))

        scaled = processors.scale_and_crop(image, (600, 600), crop='scale')
        self.assertEqual(scaled.size, (200, 400))
        scaled = processors.scale_and_crop(image, (600, 600), crop='scale', upscale=True)
        self.assertEqual(scaled.size, (600, 1200))

    def test_one_dimension_scale(self):
        image = create_image()

        scaled = processors.scale_and_crop(image, (100, 0))
        self.assertEqual(scaled.size, (100, 75))
        scaled = processors.scale_and_crop(image, (0, 100))
        self.assertEqual(scaled.size, (133, 100))

    def test_one_dimension_crop(self):
        image = create_image()

        cropped = processors.scale_and_crop(image, (100, 0), crop=True)
        self.assertEqual(cropped.size, (100, 75))
        cropped = processors.scale_and_crop(image, (0, 100), crop=True)
        self.assertEqual(cropped.size, (133, 100))

    def test_croup_rounding(self):
        image = create_image(size=(2400, 3620))

        size = (110, 1000)
        cropped = processors.scale_and_crop(image, size, crop=True)
        self.assertEqual(cropped.size, size)

    def test_extreme_aspect_ratio_minimum_dimension(self):
        wide = create_image(size=(600, 1))
        scaled = processors.scale_and_crop(wide, (100, 100))
        self.assertEqual(scaled.size, (100, 1))

        tall = create_image(size=(1, 600))
        scaled = processors.scale_and_crop(tall, (100, 100))
        self.assertEqual(scaled.size, (1, 100))

        scaled = processors.scale_and_crop(wide, (100, 0))
        self.assertEqual(scaled.size, (100, 1))
        scaled = processors.scale_and_crop(tall, (0, 100))
        self.assertEqual(scaled.size, (1, 100))

        scaled = processors.scale_and_crop(wide, (100, 100), zoom=40)
        self.assertTrue(all(d >= 1 for d in scaled.size))

    def test_zoom_scale(self):
        image = create_image(size=(2400, 3620))

        size = (100, 100)
        scaled = processors.scale_and_crop(image, size, zoom=40)
        self.assertEqual(scaled.size, (66, 100))

    def test_zoom_crop(self):
        image = create_image(size=(2400, 3620))

        size = (110, 1000)
        cropped = processors.scale_and_crop(image, size, crop=True, zoom=40)
        self.assertEqual(cropped.size, size)

    def test_crop_target(self):
        image = create_image()

        # Try bottom right target.
        target = (95, 100)

        tl_crop = processors.scale_and_crop(
            image, size=(100, 600), crop=True, target=target
        )
        expected = image.crop([700, 0, 800, 600])
        self.assertImagesEqual(tl_crop, expected)

        tl_crop = processors.scale_and_crop(
            image, size=(800, 100), crop=True, target=target
        )
        expected = image.crop([0, 500, 800, 600])
        self.assertImagesEqual(tl_crop, expected)

        # Top left target.
        target = (0, 5)

        tl_crop = processors.scale_and_crop(
            image, size=(100, 600), crop=True, target=target
        )
        expected = image.crop([0, 0, 100, 600])
        self.assertImagesEqual(tl_crop, expected)

        tl_crop = processors.scale_and_crop(
            image, size=(800, 100), crop=True, target=target
        )
        expected = image.crop([0, 0, 800, 100])
        self.assertImagesEqual(tl_crop, expected)

    def test_crop_target_text(self):
        image = create_image()
        # Near centre target.
        target = '45,55'

        tl_crop = processors.scale_and_crop(
            image, size=(100, 600), crop=True, target=target
        )
        expected = image.crop([310, 0, 410, 600])
        self.assertImagesEqual(tl_crop, expected)

        tl_crop = processors.scale_and_crop(
            image, size=(800, 100), crop=True, target=target
        )
        expected = image.crop([0, 280, 800, 380])
        self.assertImagesEqual(tl_crop, expected)


class ColorspaceTest(TestCase):
    def test_standard(self):
        image = Image.new('RGB', (800, 600))
        processed = processors.colorspace(image)
        self.assertEqual(processed.mode, 'RGB')

        image = Image.new('L', (800, 600))
        processed = processors.colorspace(image)
        self.assertEqual(processed.mode, 'L')

    def test_transparent(self):
        image = Image.new('RGBA', (800, 600))
        processed = processors.colorspace(image)
        self.assertEqual(processed.mode, 'RGBA')

        image = Image.new('LA', (800, 600))
        processed = processors.colorspace(image)
        self.assertEqual(processed.mode, 'LA')

    def test_replace_alpha(self):
        image = Image.new('RGBA', (800, 600))
        self.assertEqual(image.load()[0, 0], (0, 0, 0, 0))
        processed = processors.colorspace(image, replace_alpha='#fefdfc')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.load()[0, 0], (254, 253, 252))

        image = Image.new('LA', (800, 600))
        self.assertEqual(image.load()[0, 0], (0, 0))
        processed = processors.colorspace(image, replace_alpha='#fefdfc')
        self.assertEqual(processed.mode, 'L')
        self.assertEqual(processed.load()[0, 0], 253)

    def test_bw(self):
        image = Image.new('RGB', (800, 600))
        processed = processors.colorspace(image, bw=True)
        self.assertEqual(processed.mode, 'L')

        image = Image.new('RGBA', (800, 600))
        processed = processors.colorspace(image, bw=True)
        self.assertEqual(processed.mode, 'LA')

        image = Image.new('L', (800, 600))
        processed = processors.colorspace(image, bw=True)
        self.assertEqual(processed.mode, 'L')

        image = Image.new('LA', (800, 600))
        processed = processors.colorspace(image, bw=True)
        self.assertEqual(processed.mode, 'LA')


class AutocropTest(TestCase):
    def test_standard(self):
        processed = processors.autocrop(create_image(), autocrop=True)
        self.assertEqual(processed.size, (481, 421))


class BackgroundTest(TestCase):
    def test_basic(self):
        image = create_image()
        processed = processors.background(image, background='#fff', size=(800, 800))
        self.assertEqual(processed.size, (800, 800))

    def test_grayscale(self):
        image = create_image().convert('L')
        processed = processors.background(image, background='#fff', size=(800, 800))
        self.assertEqual(processed.size, (800, 800))
        self.assertEqual(processed.mode, 'L')

    def test_mode_alpha(self):
        image = create_image().convert('RGBA')
        processed = processors.background(image, background='#fff', size=(800, 800))
        self.assertEqual(processed.size, (800, 800))
        self.assertEqual(processed.mode, 'RGB')

        image = create_image().convert('LA')
        processed = processors.background(image, background='#fff', size=(800, 800))
        self.assertEqual(processed.size, (800, 800))
        self.assertEqual(processed.mode, 'L')


class ScaleAndCropCombinationTest(TestCase):
    def assertImagesEqual(self, im1, im2, msg=None):
        if im1.size != im2.size or (
            ImageChops.difference(im1, im2).getbbox() is not None
        ):
            raise self.failureException(msg or 'The two images were not identical')

    def test_crop_zoom_target(self):
        image = create_image()
        # Zoom is applied before cropping, the focal point still decides the box.
        top_left = processors.scale_and_crop(
            image,
            (100, 100),
            crop=True,
            zoom=40,
            target=(0, 0),
        )
        bottom_right = processors.scale_and_crop(
            image,
            (100, 100),
            crop=True,
            zoom=40,
            target=(100, 100),
        )
        self.assertEqual(top_left.size, (100, 100))
        self.assertEqual(bottom_right.size, (100, 100))
        self.assertIsNotNone(ImageChops.difference(top_left, bottom_right).getbbox())

    def test_zoom_with_upscale(self):
        image = create_image(size=(50, 50))
        scaled = processors.scale_and_crop(
            image,
            (100, 100),
            zoom=40,
        )
        self.assertEqual(scaled.size, (50, 50))
        scaled = processors.scale_and_crop(
            image,
            (100, 100),
            zoom=40,
            upscale=True,
        )
        self.assertEqual(scaled.size, (100, 100))

    def test_zoom_one_dimension(self):
        image = create_image()
        scaled = processors.scale_and_crop(
            image,
            (100, 0),
            zoom=40,
        )
        self.assertEqual(scaled.size, (100, 75))

    def test_crop_edge_with_zoom(self):
        image = create_image()
        cropped = processors.scale_and_crop(
            image,
            (100, 100),
            crop='0,0',
            zoom=40,
        )
        self.assertEqual(cropped.size, (100, 100))

    def test_crop_edge_overrides_target(self):
        image = create_image()
        # The edge offset decides the axis it names, the target is ignored there.
        cropped = processors.scale_and_crop(
            image,
            (100, 600),
            crop='0,',
            target=(100, 100),
        )
        self.assertImagesEqual(cropped, image.crop([0, 0, 100, 600]))

    def test_crop_edge_keeps_target_for_unnamed_axis(self):
        image = create_image()
        cropped = processors.scale_and_crop(
            image, (100, 600), crop=',0', target=(100, 100)
        )
        self.assertImagesEqual(cropped, image.crop([700, 0, 800, 600]))

    def test_crop_edge_empty_uses_target(self):
        image = create_image()
        cropped = processors.scale_and_crop(
            image,
            (100, 600),
            crop=',',
            target=(100, 100),
        )
        self.assertImagesEqual(cropped, image.crop([700, 0, 800, 600]))

    def test_crop_edge_offset_is_percent_of_target_size(self):
        # Pitfall: the offset is a percentage of the requested thumbnail size,
        # not of the source image or of the cropped-off remainder.
        image = create_image()
        cropped = processors.scale_and_crop(
            image,
            (100, 600),
            crop='200,',
        )
        self.assertImagesEqual(cropped, image.crop([200, 0, 300, 600]))

    def test_crop_edge_offset_is_clamped(self):
        image = create_image()
        cropped = processors.scale_and_crop(
            image,
            (100, 600),
            crop='1000,',
        )
        self.assertImagesEqual(cropped, image.crop([700, 0, 800, 600]))
        cropped = processors.scale_and_crop(
            image,
            (100, 600),
            crop='-1000,',
        )
        self.assertImagesEqual(cropped, image.crop([0, 0, 100, 600]))

    def test_crop_smart_single_axis(self):
        image = create_image()
        cropped = processors.scale_and_crop(
            image,
            (800, 100),
            crop='smart',
        )
        self.assertEqual(cropped.size, (800, 100))

    def test_crop_smart_with_zoom(self):
        image = create_image()
        cropped = processors.scale_and_crop(
            image,
            (100, 100),
            crop='smart',
            zoom=40,
        )
        self.assertEqual(cropped.size, (100, 100))

    def test_crop_upscale(self):
        image = create_image(size=(50, 40))
        cropped = processors.scale_and_crop(
            image,
            (100, 100),
            crop=True,
        )
        self.assertEqual(cropped.size, (50, 40))
        cropped = processors.scale_and_crop(
            image,
            (100, 100),
            crop=True,
            upscale=True,
        )
        self.assertEqual(cropped.size, (100, 100))

    def test_crop_one_dimension_with_upscale(self):
        image = create_image(size=(50, 40))
        scaled = processors.scale_and_crop(
            image,
            (100, 0),
            upscale=True,
        )
        self.assertEqual(scaled.size, (100, 80))

    def test_invalid_target_is_ignored(self):
        image = create_image()
        centered = processors.scale_and_crop(
            image,
            (100, 600),
            crop=True,
        )
        for target in ('abc', '-5,5', '1,2,3', (None, None), ',', None):
            cropped = processors.scale_and_crop(
                image,
                (100, 600),
                crop=True,
                target=target,
            )
            self.assertImagesEqual(cropped, centered, msg=repr(target))

    def test_target_partial(self):
        image = create_image()
        # A missing value defaults to 50%.
        for target in (',0', (None, 0)):
            cropped = processors.scale_and_crop(
                image,
                (800, 100),
                crop=True,
                target=target,
            )
            self.assertImagesEqual(cropped, image.crop([0, 0, 800, 100]))

    def test_target_without_crop_has_no_effect(self):
        image = create_image()
        plain = processors.scale_and_crop(image, (100, 100))
        targeted = processors.scale_and_crop(
            image,
            (100, 100),
            target=(0, 0),
        )
        self.assertImagesEqual(plain, targeted)

    def test_crop_scale_with_zoom_exceeds_size(self):
        # Pitfall: crop="scale" never crops, so zoom enlarges the result
        # beyond the requested size.
        image = create_image()
        scaled = processors.scale_and_crop(
            image,
            (100, 100),
            crop='scale',
            zoom=40,
        )
        self.assertGreater(scaled.size[0], 100)
        self.assertGreater(scaled.size[1], 100)

    def test_size_zero_zero(self):
        # Pitfall: no dimension to derive the scale from, result is 1x1.
        scaled = processors.scale_and_crop(create_image(), (0, 0))
        self.assertEqual(scaled.size, (1, 1))

    def test_crop_never_enlarges_without_upscale(self):
        image = create_image(size=(50, 50))
        for kwargs in ({'crop': True}, {'crop': 'smart'}, {'crop': '0,0'}):
            result = processors.scale_and_crop(image, (100, 100), **kwargs)
            self.assertEqual(result.size, (50, 50), msg=repr(kwargs))


class ColorspaceCombinationTest(TestCase):
    def test_bw_with_replace_alpha(self):
        image = Image.new('RGBA', (10, 10))
        processed = processors.colorspace(image, bw=True, replace_alpha='#fff')
        self.assertEqual(processed.mode, 'L')
        self.assertEqual(processed.getpixel((0, 0)), 255)

    def test_replace_alpha_opaque_image(self):
        image = Image.new('RGBA', (10, 10), (1, 2, 3, 255))
        processed = processors.colorspace(image, replace_alpha='#fff')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((0, 0)), (1, 2, 3))

    def test_replace_alpha_ignored_without_transparency(self):
        image = Image.new('RGB', (10, 10), (1, 2, 3))
        processed = processors.colorspace(image, replace_alpha='#fff')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((0, 0)), (1, 2, 3))

    def test_replace_alpha_blends_partial_transparency(self):
        image = Image.new('RGBA', (10, 10), (0, 0, 0, 128))
        processed = processors.colorspace(image, replace_alpha='#fff')
        self.assertEqual(processed.mode, 'RGB')
        value = processed.getpixel((0, 0))[0]
        self.assertTrue(120 <= value <= 135, value)

    def test_palette_and_cmyk_become_rgb(self):
        self.assertEqual(processors.colorspace(Image.new('P', (4, 4))).mode, 'RGB')
        self.assertEqual(processors.colorspace(Image.new('CMYK', (4, 4))).mode, 'RGB')

    def test_palette_with_transparency(self):
        image = Image.new('P', (4, 4))
        image.info['transparency'] = 0
        self.assertEqual(processors.colorspace(image).mode, 'RGBA')
        processed = processors.colorspace(image, replace_alpha='#fff')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((0, 0)), (255, 255, 255))

    def test_16_bit_grayscale(self):
        image = Image.new('I', (4, 4), 40000)
        processed = processors.colorspace(image)
        self.assertEqual(processed.mode, 'L')
        self.assertEqual(processed.getpixel((0, 0)), 40000 // 256)

    def test_16_bit_grayscale_bw(self):
        processed = processors.colorspace(Image.new('I', (4, 4), 256), bw=True)
        self.assertEqual(processed.mode, 'L')


class AutocropCombinationTest(TestCase):
    def test_disabled(self):
        image = create_image()
        self.assertEqual(processors.autocrop(image).size, (800, 600))
        self.assertEqual(processors.autocrop(image, autocrop=False).size, (800, 600))

    def test_all_white_is_unchanged(self):
        image = Image.new('RGB', (10, 10), 'white')
        self.assertEqual(processors.autocrop(image, autocrop=True).size, (10, 10))

    def test_off_white_is_not_trimmed(self):
        # Pitfall: only pure white (255) counts as whitespace.
        image = Image.new('RGB', (10, 10), (254, 254, 254))
        self.assertEqual(processors.autocrop(image, autocrop=True).size, (10, 10))

    def test_transparent_border_is_trimmed(self):
        image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        image.paste((255, 0, 0, 255), (20, 30, 60, 70))
        for mode in ('RGBA', 'LA'):
            processed = processors.autocrop(image.convert(mode), autocrop=True)
            self.assertEqual(processed.size, (40, 40))
            self.assertEqual(processed.mode, mode)

    def test_grayscale(self):
        processed = processors.autocrop(create_image().convert('L'), autocrop=True)
        self.assertEqual(processed.size, (481, 421))

    def test_white_content_on_transparent_is_lost(self):
        # Pitfall: transparent areas are treated like white, so white content
        # on a transparent background is trimmed away with it.
        image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        image.paste((255, 255, 255, 255), (20, 30, 60, 70))
        processed = processors.autocrop(image, autocrop=True)
        self.assertEqual(processed.size, (100, 100))


class FiltersTest(TestCase):
    def test_no_options_is_noop(self):
        image = create_image()
        self.assertIs(processors.filters(image), image)

    def test_sharpen_and_detail_change_pixels(self):
        image = create_image()
        for kwargs in ({'sharpen': True}, {'detail': True}):
            processed = processors.filters(image, **kwargs)
            self.assertEqual(processed.size, image.size)
            self.assertEqual(processed.mode, image.mode)

    def test_both_filters(self):
        image = create_image()
        both = processors.filters(image, detail=True, sharpen=True)
        expected = image.filter(ImageFilter.DETAIL).filter(ImageFilter.SHARPEN)
        self.assertEqual(ImageChops.difference(both, expected).getbbox(), None)

    def test_modes_are_preserved(self):
        for mode in ('RGB', 'RGBA', 'L', 'LA'):
            image = create_image().convert(mode)
            processed = processors.filters(image, sharpen=True, detail=True)
            self.assertEqual(processed.mode, mode)


class BackgroundCombinationTest(TestCase):
    def test_without_background_is_noop(self):
        image = create_image()
        self.assertIs(processors.background(image, size=(1000, 1000)), image)

    def test_zero_dimension_is_noop(self):
        # Pitfall: a size with a zero (unbounded) dimension cannot be padded.
        image = create_image()
        for size in ((0, 1000), (1000, 0), (0, 0)):
            self.assertIs(
                processors.background(image, size=size, background='#fff'), image
            )

    def test_larger_image_is_noop(self):
        image = create_image()
        processed = processors.background(image, size=(100, 100), background='#fff')
        self.assertIs(processed, image)

    def test_image_is_centered(self):
        image = Image.new('RGB', (10, 10), 'blue')
        processed = processors.background(image, size=(20, 30), background='#f00')
        self.assertEqual(processed.size, (20, 30))
        self.assertEqual(processed.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(processed.getpixel((5, 10)), (0, 0, 255))
        self.assertEqual(processed.getpixel((14, 19)), (0, 0, 255))
        self.assertEqual(processed.getpixel((19, 29)), (255, 0, 0))

    def test_transparency_is_replaced_by_background(self):
        image = Image.new('RGBA', (10, 10))
        processed = processors.background(image, size=(20, 20), background='#f00')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((10, 10)), (255, 0, 0))

    def test_replace_alpha_option_does_not_conflict(self):
        # All thumbnail options are passed to every processor, including
        # replace_alpha, which is also what background uses internally.
        image = Image.new('RGBA', (10, 10))
        processed = processors.background(
            image, size=(20, 20), background='#f00', replace_alpha='#00f'
        )
        self.assertEqual(processed.getpixel((10, 10)), (255, 0, 0))

    def test_transparent_padding_is_not_possible(self):
        # Pitfall: the alpha part of the color is ignored, the result is opaque.
        image = Image.new('RGBA', (10, 10), (0, 0, 255, 255))
        processed = processors.background(image, size=(20, 20), background='#0000')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((0, 0)), (0, 0, 0))

    def test_overflow_on_one_axis_is_cropped(self):
        # Pitfall: the image only needs to be smaller on one axis to be padded,
        # the other axis is then cropped around the center.
        image = Image.new('RGB', (100, 100), 'blue')
        image.paste('green', (0, 0, 100, 10))
        processed = processors.background(image, size=(200, 50), background='#f00')
        self.assertEqual(processed.size, (200, 50))
        self.assertEqual(processed.getpixel((100, 0)), (0, 0, 255))
        self.assertEqual(processed.getpixel((0, 25)), (255, 0, 0))

    def test_bw_option_is_honored(self):
        processed = processors.background(
            create_image(), size=(1000, 1000), background='#fff', bw=True
        )
        self.assertEqual(processed.mode, 'L')

    def test_named_color(self):
        processed = processors.background(
            create_image(), size=(1000, 1000), background='red'
        )
        self.assertEqual(processed.getpixel((0, 0)), (255, 0, 0))


class ProcessorPipelineTest(TestCase):
    """
    Run the default processors in sequence with combined options.
    """

    def process(self, image, **options):
        return engine.process_image(image, options)

    def test_fit_and_pad(self):
        processed = self.process(create_image(), size=(100, 100), background='#fff')
        self.assertEqual(processed.size, (100, 100))

    def test_crop_fills_size_so_background_is_noop(self):
        image = create_image()
        processed = self.process(image, size=(100, 100), crop=True, background='#0f0')
        self.assertEqual(processed.size, (100, 100))
        self.assertNotIn((0, 255, 0), processed.getdata())

    def test_crop_smaller_than_size_gets_padded(self):
        # Without upscale a small image is not enlarged by crop, background
        # then pads it to the requested size.
        image = create_image(size=(50, 50))
        processed = self.process(image, size=(100, 100), crop=True, background='#f00')
        self.assertEqual(processed.size, (100, 100))
        self.assertEqual(processed.getpixel((0, 0)), (255, 0, 0))

    def test_upscale_with_background(self):
        image = create_image(size=(50, 25))
        processed = self.process(image, size=(100, 100), upscale=True, background='#fff')
        self.assertEqual(processed.size, (100, 100))

    def test_zoom_without_crop_with_background(self):
        processed = self.process(
            create_image(size=(2400, 3620)),
            size=(100, 100),
            zoom=40,
            background='#fff',
        )
        self.assertEqual(processed.size, (100, 100))

    def test_autocrop_before_scale(self):
        # Autocrop runs first, so the crop is relative to the trimmed image.
        processed = self.process(
            create_image(), size=(100, 100), autocrop=True, crop=True
        )
        self.assertEqual(processed.size, (100, 100))
        fitted = self.process(create_image(), size=(100, 100), autocrop=True)
        self.assertEqual(fitted.size, (100, 88))

    def test_transparent_source_all_options(self):
        image = Image.new('RGBA', (400, 300), (0, 0, 0, 0))
        image.paste((0, 0, 255, 255), (100, 100, 300, 200))
        processed = self.process(
            image,
            size=(100, 100),
            autocrop=True,
            replace_alpha='#fff',
            bw=True,
            sharpen=True,
            detail=True,
            crop='smart',
            target='50,50',
            zoom=10,
            background='#fff',
        )
        self.assertEqual(processed.size, (100, 100))
        self.assertEqual(processed.mode, 'L')

    def test_transparency_kept_without_replace_alpha(self):
        image = Image.new('RGBA', (400, 300), (0, 0, 0, 0))
        processed = self.process(image, size=(100, 100), sharpen=True)
        self.assertEqual(processed.mode, 'RGBA')

    def test_background_replaces_alpha(self):
        image = Image.new('RGBA', (400, 300), (0, 0, 0, 0))
        # Pitfall: background flattens transparency even without replace_alpha.
        processed = self.process(image, size=(100, 100), background='#f00')
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((50, 50)), (255, 0, 0))
        processed = self.process(
            image, size=(100, 100), background='#f00', replace_alpha='#00f'
        )
        self.assertEqual(processed.mode, 'RGB')
        self.assertEqual(processed.getpixel((50, 50)), (0, 0, 255))
        self.assertEqual(processed.getpixel((0, 0)), (255, 0, 0))

    def test_unknown_options_are_ignored(self):
        processed = self.process(create_image(), size=(100, 100), whizzbang=True)
        self.assertEqual(processed.size, (100, 75))
