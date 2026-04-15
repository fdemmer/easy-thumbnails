import logging
import subprocess
from subprocess import check_output

from PIL import Image, UnidentifiedImageError

from django.core.files.base import ContentFile
from django.core.files.temp import NamedTemporaryFile

from easy_thumbnails.optimize.conf import settings


logger = logging.getLogger('easy_thumbnails.optimize')


def optimize_thumbnail(thumbnail):
    """Optimize thumbnail images by removing unnecessary data"""
    # Ignore remote storage backends.
    try:
        thumbnail_path = thumbnail.path
    except NotImplementedError:
        return

    # We can't use thumbnail.image.format directly because it's set to `None` for images
    # that have been created by running a method on an existing image. i.e. It's `None`
    # because of the thumnailing operations.
    # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.format
    #
    # Image.open() is lazy and the full file will not be read when determining the
    # format.
    # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open
    try:
        with Image.open(thumbnail_path) as img:
            # Use the lower case version of format to match the output of previously used
            # imghdr.what() (removed in Python 3.13).
            format = img.format.lower()
    except UnidentifiedImageError:
        return

    try:
        optimize_command = settings.THUMBNAIL_OPTIMIZE_COMMAND[format]
        if not optimize_command:
            return
    except (TypeError, KeyError, NotImplementedError):
        return
    storage = thumbnail.storage
    try:
        with NamedTemporaryFile() as temp_file:
            thumbnail.seek(0)
            temp_file.write(thumbnail.read())
            temp_file.flush()
            optimize_command = optimize_command.format(filename=temp_file.name)
            output = check_output(optimize_command, stderr=subprocess.STDOUT, shell=True)
            if output:
                logger.warning(f'{optimize_command} returned {output}')
            else:
                logger.info(f'{optimize_command} returned nothing')
            with open(temp_file.name, 'rb') as f:
                thumbnail.file = ContentFile(f.read())
                storage.delete(thumbnail.name)
                storage.save(thumbnail.name, thumbnail)
    except Exception as e:
        logger.error(e)
