import base64

from PIL import Image


def default(image):
    """
    Generate a `ThumbHash <https://evanw.github.io/thumbhash/>`_ of a PIL image.

    Returns the hash base64 encoded, or ``None`` if the ``thumbhash`` extra
    (``fast-thumbhash-rs``) is not installed or the image is not a PIL image
    (e.g. an SVG).
    """
    try:
        from thumbhash import rgba_to_thumb_hash
    except ImportError:
        return None
    if not isinstance(image, Image.Image):
        return None

    image = image.convert('RGBA')
    image.thumbnail((100, 100))
    width, height = image.size
    thumb_hash = rgba_to_thumb_hash(width, height, image.tobytes())
    return base64.b64encode(thumb_hash).decode('ascii')
