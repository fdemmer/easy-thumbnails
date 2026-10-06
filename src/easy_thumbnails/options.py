from easy_thumbnails.conf import settings


OUTPUT_FORMATS = ('jpg', 'webp', 'avif')

# Chroma subsampling constants for JPEG used by Pillow
JPEG_CSS_444 = 0
JPEG_CSS_422 = 1
JPEG_CSS_420 = 2


class ThumbnailOptions(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.THUMBNAIL_DEFAULT_OPTIONS:
            for key, value in settings.THUMBNAIL_DEFAULT_OPTIONS.items():
                self.setdefault(key, value)
        self.setdefault('quality', settings.THUMBNAIL_QUALITY)
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
        The second item is the quality (``'q85'``).
        It gets an ``ss`` part with the subsampling, if it is not the default
        (``'q85ss0'``). The default is 4:2:0, which Pillow indicates with
        ``subsampling=2``.

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
