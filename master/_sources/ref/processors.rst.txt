================
Image Processors
================

Easy thumbnails generates thumbnail images by passing the source image through
a series of image processors. Each processor may alter the image, often
dependent on the options it receives.

This makes the system very flexible, as the processors an image passes through
can be defined in :attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_PROCESSORS`
and even overridden by an individual :class:`easy_thumbnails.files.Thumbnailer`
(via the :attr:`~easy_thumbnails.files.Thumbnailer.thumbnail_processors`
attribute).

Built-in processors
===================

Following is a list of the built-in processors, along with the thumbnail
options which they use.

.. automodule:: easy_thumbnails.processors
   :members:


Option combinations and pitfalls
================================

All options are passed to every processor and the processors run in order (see
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_PROCESSORS`), so the result of
an option depends on what ran before it. These combinations are covered by
``tests/test_pixel_processors.py``.

``size``
    - A zero in ``size`` leaves that dimension unbounded. ``size=(0, 0)`` has
      nothing to derive a scale from and gives a 1x1 image.
    - :func:`~easy_thumbnails.processors.background` needs both dimensions and
      does nothing if one is zero.

``crop``
    - Without ``upscale`` a smaller source is never enlarged, so the result
      can be smaller than ``size`` even with ``crop`` (``background`` can pad
      it to the exact size).
    - ``crop="scale"`` never crops. Combined with ``zoom`` the result is
      larger than ``size``.
    - The ``W,H`` offsets are a percentage of the requested thumbnail size (not
      of the source) and are limited to the available overflow. For ``W,H``
      the ``target`` option only applies to an axis that has no offset, e.g.
      ``crop=",0"``.
    - An empty ``crop=","`` is the same as ``crop=True``.

``target``
    - Only used when the image is cropped, otherwise it has no effect.
    - Invalid values (``"abc"``, ``"-5,5"``, ``"1,2,3"``) are silently ignored
      and the image is centered. Use ``None`` or an empty part for the default
      of 50%.

``zoom``
    - Without ``crop`` the image is scaled to fit ``size`` and then cropped to
      that size, so ``zoom`` implies cropping.
    - Is limited by ``upscale`` like any other scaling: a source smaller than
      ``size`` is not zoomed in unless ``upscale`` is set.

``autocrop``
    - Runs before scaling, so ``crop`` and ``size`` apply to the trimmed image
      (and its aspect ratio).
    - Only pure white (``#fff``) is whitespace; off-white borders are kept.
      Transparent areas count as white, so white content on a transparent
      background is trimmed as well.

``replace_alpha`` and ``background``
    - ``background`` also replaces transparency with its color, even without
      ``replace_alpha``, but only if padding is needed. If both are set,
      ``replace_alpha`` is applied first by
      :func:`~easy_thumbnails.processors.colorspace`, so the image is flat
      before it is padded.
    - ``background`` cannot pad with transparency. The result is always opaque
      and the alpha part of a color like ``#0000`` is ignored (black border).
    - ``bw`` is passed through to ``background``, so a padded image is
      grayscale as well.
    - ``background`` pads whenever the image is smaller than ``size`` on *one*
      axis, and crops around the center on the other axis if the image is
      larger there.

Custom processors
=================

You can replace or leave out any default processor as suits your needs.
Following is an explanation of how to create and activate a custom processor.

When defining the
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_PROCESSORS` setting, remember
that this is the order through which the processors are run. The image received
by a processor is the output of the previous processor.

Create the processor
--------------------

First create a processor like this::

    def whizzbang_processor(image, bang=False, **kwargs):
        """
        Whizz bang the source image.

        """
        if bang:
            image = whizz(image)
        return image

The first argument for a processor is the source image.

All other arguments are keyword arguments which relate to the list of options
received by the thumbnail generator (including ``size`` and ``quality``).
Ensure you list all arguments which could be used (giving them a default value
of ``False``), as the processors arguments are introspected to generate a list
of valid options.

You must also use ``**kwargs`` at the end of your argument list because all
options used to generate the thumbnail are passed to processors, not just the
ones defined.

Whether a processor actually modifies the image or not, they must always return
an image.

Use the processor
-----------------

Next, add the processor to
:attr:`~easy_thumbnails.conf.Settings.THUMBNAIL_PROCESSORS` in your settings
module::

    from easy_thumbnails.conf import Settings as easy_thumbnails_defaults

    THUMBNAIL_PROCESSORS = easy_thumbnails_defaults.THUMBNAIL_PROCESSORS + (
        'wb_project.thumbnail_processors.whizzbang_processor',
    )
