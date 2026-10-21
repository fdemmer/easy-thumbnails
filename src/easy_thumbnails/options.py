from easy_thumbnails.conf import settings


OUTPUT_FORMATS = ('jpg', 'webp', 'avif')

# Chroma subsampling constants for JPEG used by Pillow
JPEG_CSS_444 = 0
JPEG_CSS_422 = 1
JPEG_CSS_420 = 2


class ThumbnailOptions(dict):
    """
    A dictionary of thumbnail options (e.g. ``{'size': (100, 100), 'crop':
    True}``), as passed to the source generators, the processors and
    ``engine.save_pil_image``. :meth:`Thumbnailer.get_options
    <easy_thumbnails.files.Thumbnailer.get_options>` and the engine wrap plain
    dictionaries in it. See :doc:`/usage` and :doc:`processors` for the
    available options.

    On creation, it:

    * adds the entries of ``THUMBNAIL_DEFAULT_OPTIONS`` that aren't given,
    * sets ``subsampling`` to 4:2:0 (``JPEG_CSS_420``) if it isn't given,
    * normalizes ``format``: lowercased, without a leading ``.``, and ``jpeg``
      becomes ``jpg``. It must be one of ``OUTPUT_FORMATS`` (``jpg``,
      ``webp``, ``avif``), otherwise a ``ValueError`` is raised.

    It doesn't add a ``quality``; ``Thumbnailer.get_options`` adds the default
    quality of the output format from ``THUMBNAIL_IMAGE_SAVE_OPTIONS``. It
    doesn't parse a ``size`` string either (the ``{% thumbnail %}`` tag does).

    :meth:`prepared_options` turns the options into the parts of the thumbnail
    file name.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.THUMBNAIL_DEFAULT_OPTIONS:
            for key, value in settings.THUMBNAIL_DEFAULT_OPTIONS.items():
                self.setdefault(key, value)
        self.setdefault('subsampling', JPEG_CSS_420)
        if self.get('format'):
            self['format'] = self._normalize_format(self['format'])

    @staticmethod
    def _normalize_format(value):
        fmt = str(value).lower().lstrip('.')
        fmt = {'jpeg': 'jpg'}.get(fmt, fmt)
        if fmt not in OUTPUT_FORMATS:
            raise ValueError(
                f'Unsupported thumbnail format {value!r}, '
                f'expected one of: jpeg, webp, avif'
            )
        return fmt

    def prepared_options(self):
        """
        Return the options as a list of strings used to name the thumbnail.

        The first item is the size (``'100x50'``).
        The second item is the quality (``'q76'``).
        It gets an ``ss`` part with the subsampling, if it is not the default
        (``'q76ss0'``). The default is 4:2:0, which Pillow indicates with
        ``subsampling=2``.
        It is left out if there is neither a quality nor a non-default
        subsampling (e.g. for formats without a configured default quality).

        The remaining options follow in key order.
        A ``True`` value is added as ``key``.
        Any other value is added as ``key-value``.
        Sequences are comma-joined.

        Falsy values and uppercase keys are skipped, they don't affect the filename.
        The ``format`` key is skipped too: it already determines the file
        extension, so it is not repeated in the name.

        This is only used for naming: ``Thumbnailer.get_thumbnail_name`` joins
        the list with ``_`` for the ``%(opts)s`` basedir/subdir templates and
        passes it to the namer as ``prepared_options``.

        Image generation does not use it; the processors, source generators
        and ``engine.save_pil_image`` read the full options dict.

        The size must stay the first item, since the built-in ``source_hashed``
        namer relies on it!
        """
        hidden_keys = ['format', 'quality', 'size', 'subsampling']
        prepared_opts = ['{size[0]}x{size[1]}'.format(**self)]

        opts_text = ''
        if 'quality' in self:
            opts_text += 'q{quality}'.format(**self)
        if 'subsampling' in self and str(self['subsampling']) != f'{JPEG_CSS_420}':
            opts_text += 'ss{subsampling}'.format(**self)
        if opts_text:
            prepared_opts.append(opts_text)

        for key, value in sorted(self.items()):
            if key == key.upper():
                # Uppercase options aren't used by prepared options (a primary
                # use of prepared options is to generate the filename -- these
                # options don't alter the filename).
                continue
            if not value or key in hidden_keys:
                continue
            if value is True:
                prepared_opts.append(key)
                continue
            if not isinstance(value, str):
                try:
                    value = ','.join([str(item) for item in value])
                except TypeError:
                    value = str(value)
            prepared_opts.append(f'{key}-{value}')

        return prepared_opts
