import hashlib
import inspect
import math
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager

from PIL import Image

from django.core.files.storage import storages
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import LazyObject, empty
from django.utils.module_loading import import_string

from easy_thumbnails.conf import settings


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
        if storage._wrapped is empty:
            storage._setup()
        storage = storage._wrapped
    if not isinstance(storage, str):
        storage_cls = storage.__class__
        storage = f'{storage_cls.__module__}.{storage_cls.__name__}'
    return md5_not_used_for_security(storage.encode('utf8')).hexdigest()


def get_storages():
    """
    Return an (alias, class name, storage hash) tuple for each configured storage.
    """
    return [
        (alias, type(storage := storages[alias]).__name__, get_storage_hash(storage))
        for alias in settings.STORAGES
    ]


def get_storage_hash_map():
    """
    Return a dict mapping each configured storage hash to its alias.
    """
    return {storage_hash: alias for alias, _, storage_hash in get_storages()}


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


def q_has_value(field):
    """
    Return a Q object matching rows where `field` has an actual value
    (excludes both the empty string and NULL).
    """
    return ~(Q(**{field.name: ''}) | Q(**{f'{field.name}__isnull': True}))


def queryset_iterator(query, chunk_size=2000):
    """
    Iterate over a queryset in chunks using keyset pagination on the primary
    key, which avoids the cost of large OFFSETs and keeps memory use bounded.

    https://use-the-index-luke.com/sql/partial-results/fetch-next-page
    """
    threshold = new_threshold = 0
    query = query.order_by('pk')
    while True:
        chunk = query.filter(pk__gt=threshold)[:chunk_size].iterator(chunk_size)
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
