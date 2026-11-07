from importlib import import_module


def is_available() -> bool:
    """
    Returns True if SVG support should be available.
    """
    try:
        # must really import it, the module exists without the optional dependencies
        import_module('easy_thumbnails.VIL.Image')
    except ImportError:
        return False
    return True
