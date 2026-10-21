=========
ThumbHash
=========

Each ``Source`` record has a ``thumb_hash`` field, which holds a short string
that can be used to render a blurred placeholder while the real image loads.
By default it is a `ThumbHash <https://evanw.github.io/thumbhash/>`_, base64
encoded.

Install the ``thumbhash`` extra (see :doc:`install`) to enable the default
hasher. Without it, ``thumb_hash`` stays empty.

The hash is generated when the first thumbnail of a source image is created and
is available through ``Thumbnailer.get_thumb_hash()``. For sources that
already have thumbnails, generate the missing hashes with
:ref:`thumbnail thumb_hash <thumbnail_thumb_hash>`.

Custom hashers
==============

Set :attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_HASHER` to the dotted path
of a function that takes the PIL source image and returns a string (at most 64
characters) or ``None``::

    THUMBNAIL_HASHER = 'myapp.hashers.blurhash'

Set it to ``None`` to disable hashing.

.. autofunction:: easy_thumbnails.hashers.default
