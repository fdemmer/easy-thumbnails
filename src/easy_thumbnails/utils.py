import hashlib
import inspect
import math
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager

from PIL import Image

from django.apps import apps
from django.utils import timezone
from django.utils.functional import LazyObject
from django.utils.module_loading import import_string

from easy_thumbnails.conf import settings
from easy_thumbnails.fields import ThumbnailerImageField


def image_entropy(im):
    """
    Calculate the entropy of an image. Used for "smart cropping".
    """
    if not isinstance(im, Image.Image):
        # Can only deal with PIL images. Fall back to a constant entropy.
        return 0
    hist = im.histogram()
    hist_size = float(sum(hist))
    hist = [h / hist_size for h in hist]
    return -sum([p * math.log(p, 2) for p in hist if p != 0])


def valid_processor_options(processors=None):
    """
    Return a list of unique valid options for a list of image processors
    (and/or source generators)
    """
    if processors is None:
        processors = [
            import_string(p)
            for p in tuple(settings.THUMBNAIL_PROCESSORS)
            + tuple(settings.THUMBNAIL_SOURCE_GENERATORS)
        ]
    valid_options = {'size', 'quality', 'subsampling'}
    for processor in processors:
        args = inspect.getfullargspec(processor)[0]
        # Add all arguments apart from the first (the source image).
        valid_options.update(args[1:])
    return list(valid_options)


def is_storage_local(storage):
    """
    Check to see if a file storage is local.
    """
    try:
        storage.path('test')
    except NotImplementedError:
        return False
    return True


def get_storage_hash(storage):
    """
    Return a hex string hash for a storage object (or string containing
    'full.path.ClassName' referring to a storage object).
    """
    # If storage is wrapped in a lazy object we need to get the real thing.
    if isinstance(storage, LazyObject):
        if storage._wrapped is None:
            storage._setup()
        storage = storage._wrapped
    if not isinstance(storage, str):
        storage_cls = storage.__class__
        storage = f'{storage_cls.__module__}.{storage_cls.__name__}'
    return md5_not_used_for_security(storage.encode('utf8')).hexdigest()


def is_transparent(image):
    """
    Check to see if an image is transparent.
    """
    if not isinstance(image, Image.Image):
        # Can only deal with PIL images, fall back to the assumption that that
        # it's not transparent.
        return False
    return image.mode in ('RGBA', 'LA') or (
        image.mode == 'P' and 'transparency' in image.info
    )


def is_progressive(image):
    """
    Check to see if an image is progressive.
    """
    if not isinstance(image, Image.Image):
        # Can only check PIL images for progressive encoding.
        return False
    return ('progressive' in image.info) or ('progression' in image.info)


def exif_orientation(im):
    """
    Rotate and/or flip an image to respect the image's EXIF orientation data.
    """
    # Check Pillow version and use right constant
    try:
        # Pillow >= 9.1.0
        Image__Transpose = Image.Transpose
    except AttributeError:
        # Pillow < 9.1.0
        Image__Transpose = Image

    try:
        exif = im._getexif()
    except Exception:
        # There are many ways that _getexif fails, we're just going to blanket
        # cover them all.
        exif = None
    if exif:
        orientation = exif.get(0x0112)
        if orientation == 2:
            im = im.transpose(Image__Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            im = im.transpose(Image__Transpose.ROTATE_180)
        elif orientation == 4:
            im = im.transpose(Image__Transpose.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            im = im.transpose(Image__Transpose.ROTATE_270).transpose(
                Image__Transpose.FLIP_LEFT_RIGHT
            )
        elif orientation == 6:
            im = im.transpose(Image__Transpose.ROTATE_270)
        elif orientation == 7:
            im = im.transpose(Image__Transpose.ROTATE_90).transpose(
                Image__Transpose.FLIP_LEFT_RIGHT
            )
        elif orientation == 8:
            im = im.transpose(Image__Transpose.ROTATE_90)
    return im


def get_modified_time(storage, name):
    """
    Get modified time from storage, ensuring the result is a timezone-aware
    datetime.
    """
    try:
        modified_time = storage.get_modified_time(name)
    except OSError:
        return 0
    except NotImplementedError:
        return None
    if modified_time and timezone.is_naive(modified_time):
        if getattr(settings, 'USE_TZ', False):
            default_timezone = timezone.get_default_timezone()
            return timezone.make_aware(modified_time, default_timezone)
    return modified_time


def md5_not_used_for_security(data):
    """
    Calculate a md5 hash of the given data, but explicitly mark it as not
    being used for security purposes. Without this flag FIPS compliant
    systems will raise an exception when used.
    """
    return hashlib.new('md5', data, usedforsecurity=False)


def sha1_not_used_for_security(data):
    """
    Calculate a sha1 hash of the given data, but explicitly mark it as not
    being used for security purposes. Without the flag FIPS compliant
    systems will raise an exception when used.
    """
    return hashlib.new('sha1', data, usedforsecurity=False)


def queryset_iterator(query, chunk_size=1000, order_by='pk'):
    """
    Iterate over `query` in chunks, avoiding the cost of a large OFFSET.

    Paginates using a `pk__gt` keyset cursor instead of OFFSET/LIMIT: each
    chunk of `chunk_size` rows is fetched ordered by `order_by` (defaults to
    `pk`; pass None to keep the queryset's own ordering), and the last row's
    pk becomes the cursor for the next chunk. Iteration stops once a chunk
    doesn't advance the cursor.

    https://use-the-index-luke.com/sql/partial-results/fetch-next-page
    """
    threshold = new_threshold = 0
    if order_by is not None:
        query = query.order_by(order_by)
    while True:
        chunk = query.filter(pk__gt=threshold)[:chunk_size].iterator()
        for row in chunk:
            new_threshold = row.pk
            yield row
        if threshold == new_threshold:
            break
        threshold = new_threshold


@contextmanager
def handle_broken_pipe() -> Generator[None, None, None]:
    """
    Prevent BrokenPipeError when the output stream is closed early, such as
    when piping to head.

    https://adamj.eu/tech/2025/07/20/python-fix-brokenpipeerror/
    """
    try:
        yield
        sys.stdout.flush()
    except BrokenPipeError:
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())


def collect_fields(field_class=ThumbnailerImageField):
    """
    Yield (model, field) pairs for every concrete model field of `field_class`.

    Walks all installed apps and their non-proxy, managed models, in
    alphabetical order by app label, model, and field name.
    """
    for app_config in sorted(apps.get_app_configs(), key=lambda a: a.label):
        for model in app_config.get_models():
            if model._meta.proxy or not model._meta.managed:
                continue
            for field in sorted(model._meta.get_fields(), key=lambda f: f.name):
                if isinstance(field, field_class):
                    yield model, field
