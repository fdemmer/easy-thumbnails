============
WebP support
============

WebP is an image format employing both lossy and lossless compression,
typically producing smaller files than JPEG or PNG at comparable quality.
easy-thumbnails can generate WebP thumbnails natively, without any extra
configuration beyond a couple of settings.

Generating WebP thumbnails
===========================

The output format is chosen from the thumbnail's file extension. To make
WebP the default output format project-wide, set
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_EXTENSION`::

    THUMBNAIL_EXTENSION = 'webp'

If you only want to convert *some* sources to WebP (e.g. keep JPEG sources
as JPEG but re-encode PNGs losslessly), leave ``THUMBNAIL_EXTENSION`` at its
default and use
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_PRESERVE_EXTENSIONS`
instead::

    THUMBNAIL_PRESERVE_EXTENSIONS = ['webp']

This preserves WebP sources as WebP thumbnails while other formats still
fall back to ``THUMBNAIL_EXTENSION``.

Encoder options
================

WebP save options (such as ``quality`` or ``method``) are configured via
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_IMAGE_SAVE_OPTIONS`, which
already ships a default entry::

    THUMBNAIL_IMAGE_SAVE_OPTIONS = {
        'WEBP': {
            'quality': 85,
        },
    }

Any keyword accepted by Pillow's WebP plugin (e.g. ``lossless``, ``method``)
can be added here.

Browser support
================

All current browsers support WebP in ``<img>`` tags, so no fallback markup
(such as a ``<picture>`` element with a JPEG/PNG ``<source>``) is required.
