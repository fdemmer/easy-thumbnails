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

Choosing the format per thumbnail
==================================

The ``format`` thumbnail option sets the output format for a single
thumbnail: ``webp``, ``avif`` or ``jpeg``. It takes precedence over
``THUMBNAIL_EXTENSION``, ``THUMBNAIL_TRANSPARENCY_EXTENSION`` and
``THUMBNAIL_PRESERVE_EXTENSIONS``::

    {% thumbnail person.photo 200x200 format="webp" %}

    thumbnailer.get_thumbnail({'size': (200, 200), 'format': 'webp'})

The option can also be used in
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_ALIASES`.

.. note::

   JPEG has no transparency support. Requesting ``format=jpeg`` for a source
   with an alpha channel discards the transparency; add ``replace_alpha`` (for
   example ``replace_alpha="#fff"``) to control the background color. WebP
   keeps transparency, so it is the better choice for transparent sources.

Checking supported formats
---------------------------

WebP and AVIF support depends on how Pillow was built (the official wheels
include both). To check what your installation supports::

    python -c "from PIL import features; print(features.check('webp'), features.check('avif'))"

``python -m PIL`` prints a full report of the supported codecs, features and
their library versions.

Encoder options
================

Additional WebP save options are configured via
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_IMAGE_SAVE_OPTIONS`, a
dictionary keyed by Pillow format name (``'WEBP'``, ``'JPEG'``). Every keyword
accepted by Pillow's `WebP plugin
<https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp>`_
can be set here and is passed to ``Image.save()`` for each WebP thumbnail.

Lossy compression (default)
---------------------------

WebP thumbnails are lossy unless configured otherwise. The ``quality`` (0-100,
higher is better and larger) is controlled like for JPEG: with the
``THUMBNAIL_QUALITY`` setting or the ``quality`` thumbnail option, for example
``{% thumbnail photo 200x200 format="webp" quality=70 %}``.

.. note::

   The ``quality`` thumbnail option is always passed explicitly when saving, so
   it takes precedence over a ``'quality'`` entry in
   ``THUMBNAIL_IMAGE_SAVE_OPTIONS``. Use ``THUMBNAIL_QUALITY`` (or
   ``THUMBNAIL_DEFAULT_OPTIONS``) to change the default quality.

Other useful lossy options are ``method`` (0-6, slower encoding gives smaller
files, Pillow's default is 4) and ``alpha_quality`` (0-100, quality of the
transparency layer)::

    THUMBNAIL_IMAGE_SAVE_OPTIONS = {
        'WEBP': {
            'method': 6,
        },
    }

Lossless compression
--------------------

To encode all WebP thumbnails losslessly, set ``lossless``::

    THUMBNAIL_IMAGE_SAVE_OPTIONS = {
        'WEBP': {
            'lossless': True,
        },
    }

In lossless mode ``quality`` no longer affects image fidelity (the image is
always pixel-exact), but trades encoding speed for file size: higher values
compress more slowly. Lossless WebP suits graphics, logos and screenshots;
for photographs it usually produces much larger files than lossy WebP.

``THUMBNAIL_IMAGE_SAVE_OPTIONS`` applies to *all* WebP thumbnails; there is no
per-thumbnail ``lossless`` switch.

Browser support
================

All current browsers support WebP in ``<img>`` tags, so no fallback markup
(such as a ``<picture>`` element with a JPEG/PNG ``<source>``) is required.
