# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(up to 2.x, version numbers were not strictly semantic).

## Unreleased

- Add `thumbnail purge` management command to delete thumbnails (files and
  database records) while keeping `Source` records, optionally filtered by
  `--include`/`--exclude` and `--alias`.


## [3.1.3] - 2026-10-06

- Fix no-op `exclude` filter for empty/null `FileField` values in the
  `thumbnail` management command.
- Fix thumbnail names removing the storage location from anywhere in the
  source path instead of only from its start.
- Fix `get_storage_hash()` hashing `builtins.object` for lazy storages that
  were not yet set up (e.g. `default_storage`), producing a wrong hash.
- The source distribution now includes the `demoproject` (not the wheel).


## [3.1.2] - 2026-10-03

- `thumbnail storages` output is now column-aligned and includes the
  storage class name.
- Refactor `thumbnail cleanup`: Source deletion is batched via
  `itertools.batched` (backported for Python < 3.12), messages are reworded,
  and `-v2` logs each storage existence check.
- Remove unused `dimensions` argument from `database_get_image_dimensions()`.
- Fix `thumbnail storages` command to show all storages, even when
  multiple aliases share the same storage hash.
- Fix `ThumbnailerFieldFile.delete_thumbnails()` ignoring the
  `source_cache` argument.


## [3.1.1] - 2026-07-26

- Update documentation links to the new GitHub Pages site.
- Drop the unused Read the Docs config.


## [3.1.0] - 2026-07-26

- Add `thumbnail storages` subcommand: lists each configured storage's
  alias and storage hash.
- Add `thumbnail cleanup --delete-with-missing-storage` option: deletes
  `Source` records whose storage hash no longer matches any alias
  configured in Django's `STORAGES` setting.
- Add `thumbnail source_files` subcommand: lists file paths stored in
  every `ThumbnailerImageField` across installed apps, with `--summary`,
  `--include`, and `--exclude` options for filtering by app/model/field.
- Add `thumbnail source_cleanup` subcommand: deletes orphaned `Source`
  records whose `(storage_hash, name)` no longer matches any
  `ThumbnailerImageField` value.
- Rename the `thumbnail_cleanup` management command to a `cleanup`
  subcommand of a new, unified `thumbnail` management command. Update any
  `python manage.py thumbnail_cleanup` invocations to
  `python manage.py thumbnail cleanup`.
- Fix SVG thumbnails rendering at 0.75x the requested size when `svglib` >= 2.0
  is installed: `VIL.Image` now writes explicit `pt` units on SVG
  `width`/`height` attributes instead of unitless values, whose
  interpretation changed between svglib versions.


## [3.0.1] - 2026-05-04

- Refactor `ThumbnailCollectionCleaner.clean_up` to reduce McCabe complexity
  by extracting `_build_query`, `_process_source`, and `_delete_thumbnail`.
- Fix `thumbnail_cleanup`: storage errors during source existence check no
  longer cause false-positive deletion of thumbnails.


## [3.0.0] - 2026-04-16

- Fork published as `fdemmer-easy-thumbnails` on PyPI.
- Add support for Django 5.2 and 6.0, Python 3.13 and 3.14.
- Add `thumbnail_cleanup` management command documentation.
- Major modernization: migrated to `src/` layout, `pyproject.toml`-only
  build configuration, pytest, uv/tox, and pathlib.
- Drop support for Python < 3.9 and Django < 4.2.


## [2.10.2] - 2025-02-11

- Remove experimental support for animated image formats due to problems with
  MPO (Multi-Picture Format) images.


## [2.10.1] - 2025-01-25

- Fix for non-filesystem storage (regression in 26e8f9f of 2.8.5).


## [2.10] - 2024-09-11

- Add support for Django 5.1.
- Experimental support for animated image formats. See documentation for more infos.
- Drop support for Python 3.8.
- Drop support for Django 4.1 and earlier.
- Fix #642: Do not scale images (SVG) without size information.
- Fix #366: Keep ICC profile when saving image, if present.


## [2.9] - 2024-07-25

- Add support for Django 4.2 storages (mandatory in Django 5.1).


## [2.8.5] - 2023-01-09

- Fix regression introduced in version 2.8.4. Argument `quality` is not removed for images
  of type `.webp`.


## [2.8.4] - 2022-12-19

- Replace deprecated Pillow constants with newer counterparts. Check
  https://pillow.readthedocs.io/en/stable/releasenotes/9.1.0.html#deprecations for details.
- Fix problem when thumbnailing images of type TIFF. PIL's `TiffImagePlugin` doesn't
  like argument `quality`.


## [2.8.3] - 2022-08-02

- Fix regression in library detection introduced in version 2.8.2.


## [2.8.2] - 2022-07-31

- Installation of easy-thumbnails now optionally depends on the reportlab library.


## [2.8.1] - 2022-01-20

- Add support for Django 4.
- New `THUMBNAIL_IMAGE_SAVE_OPTIONS` setting.
- Fix #587: Uploading SVG Images to S3 storage.


## [2.8.0] - 2021-11-03

- Add support for thumbnailing SVG images. This is done by adding an emulation layer named VIL,
  which aims to be compatible with PIL. All thumbnailing operations, such as scaling and cropping
  behave like pixel images.
- Remove configuration directives `THUMBNAIL_HIGH_RESOLUTION` and `THUMBNAIL_HIGHRES_INFIX`
  from easy-thumbnails setting directives.


## [2.7.2] - 2021-10-17

- Add support for Django 3.2 and Python 3.10.
- In management command `thumbnail_cleanup`, replace `print` statements
  with `stdout.write`.
- Use Python format strings wherever possible.
- Fix #563: Do not close image after loading content.


## [2.7.1] - 2020-11-23

- Add support for Django 3.1.


## [2.7.0] - 2019-12-15

- Add support for Django 3.0.
- Drop support for Python 2.
- Drop support for Django < 1.11.
- Drop support for Django 2.0, 2.1.


## [2.6.0] - 2019-02-03

- Add testing for Django 2.2 (no code changes required).


## [2.5.0] - 2017-10-31

- Support Django versions up to 1.11. Version 2.0 is in beta.
- Remove all references to South migrations.
- Fix pickle/unpickle machinery. The ThumbnailerField fields no longer
  generated thumbnails.


## [2.4.2] - 2017-09-14

- Supported Django versions are now 1.8 or 1.10+, Python 2.7 minimum.
- Fix IOError saving JPEG files with transparency on Pillow 4.2+.
- Fix #450, #473: fixed int/string is not a callable in management command.
- Fix #456: Delete method of ThumbnailerFieldFile is called twice.


## [2.4.1] - 2017-04-05

- Add `easy_thumbnails_tags` template tag mirror to allow multiple
  thumbnailer libraries to coexist happily.
- New minimum requirement of Django 1.4 or 1.7+.
- Upgrades to avoid deprecation warnings.
- Django 1.8+ compatibility for `thumbnail_cleanup` command.
- Limit pillow to its final compatible version when on Python 2.6.
- Fix EXIF orientation to use transpose.
- Fix app settings not working in Django 1.11.
- Fix a bad conditional check causing incorrect behaviour in autocropping
  transparent images.
- Fix tests.


## [2.3] - 2015-12-11

- New `Alias` namer.
- Allow `HIGH_RESOLUTION` argument on thumbnail template tag.
- Add a `data_uri` filter to allow rendering of an image inline as a data
  uri.
- Avoid a potential concurrency issue with creating the cache.
- Remove some vestigial processor arguments.
- Fix incorrect use of select_related for source thumbnail model.
- Add logic to correctly handle thumbnail images on deferred models (e.g. when
  using `.only()`).


## [2.2.1] - 2014-12-30

- Option `zoom` can also be used by itself, without combining it with
  `crop`.


## [2.2] - 2014-10-04

- Fix migrations for Django 1.7 final.
- Fix contain bad image EXIFs being able to still raise an exception.


## [2.1] - 2014-08-13

- JPEG files can now be saved with progressive encoding. By default, any image
  with a dimension larger than 100px will be saved progressively. Configured
  with the `THUMBNAILER_PROGRESSIVE` setting.
- Fix Python 3.4 installation issue.
- Avoid an OverflowError due to invalid EXIF data.
- Fix bug causing JPEG images to be saved without optimization.


## [2.0.1] - 2014-04-26

- Fix packaging issue with old south migrations.


## [2.0] - 2014-04-25

- Add `target` option to the scale_and_crop processor, allowing for image
  focal points when cropping (or zooming) an image.
- Add a THUMBNAIL_NAMER option which takes a function used to customize
  the thumbnail filename.
- New `subsampling` option to reduce color subsampling of JPEG images,
  providing sharper color borders for a small increase in file size.
- Use Django 1.7 migrations. Thanks Trey Hunner.
  **Note**: if using South, read the installation docs for required settings
  changes.
- Make ThumbnailerImageField.resize_source reflect change in extension.
- Reimplementation of the `thumbnail_cleanup` command. Thanks Jørgen
  Abrahamsen.
- More efficient thumbnail default storage. Thanks Sandip Agarwal.


## [1.5] - 2014-03-05

- Optional postprocessor for image optimization. Thanks Jacob Rief!
- Thumbnail dimensions can now optionally be cached. Thanks David Novakovic.
- New `zoom` option to generate a thumbnail of a source image with a
  percentage clipped off each side.
- New `background` source processor that can add a border color to ensure
  scaled images fit within the exact dimensions given.
- Added configuration option to specify the infix used for high resolution
  image handling.
- Better support for multiple source generators.
- Update method used to check for modification dates of source and thumbnail
  images. Thanks Ben Roberts.
- Better thumbnail_high_resolution handling, including the ability to switch on
  and off explicitly with a `HIGH_RESOLUTION` thumbnail option.
- More remote storages optimization.


## [1.4] - 2013-09-23

- Allow the `{% thumbnail %}` tag to also accept aliases. Thanks Simon Meers!
- Considerable speed up for remote storages by reducing queries.
  Brent O'Connor spent a lot of time debugging this, so thank you epicserve!
- Make `replace_alpha` actually work correctly.
- Fix exception being raised when image exists in cache but doesn't
  actually exist in the storage.
- Fix Python 2.5 compatibility.


## [1.3] - 2013-06-17

- Add the ability to generate retina quality thumbnails in addition to the
  standard ones (off by default).
- Some more Django 1.5 fixes.
- Fix an issue with `Thumbnail.url` not working correctly.


## [1.2] - 2013-01-23

- Django 1.5 compatibility.
- Fix a problem with the `ImageClearableFileInput` widget.


## [1.1] - 2012-08-29

- Add a way to avoid generating thumbnails if they don't exist already (with
  a signal to deal with them elsewhere).
- Add a `thumbnailer_passive` filter to allow templates to use the
  non-generating thumbnails functionality when dealing with aliases.


## [1.0.3] - 2012-05-30

- Change the exception to catch from 1.0.2 to IOError.


## [1.0.2] - 2012-05-29

- Catch an OSError exception when trying to get the EXIF data of a touchy
  image.


## [1.0.1] - 2012-05-23

- Introduce a `thumbnail_created` signal.
- Fix a Django 1.2 backwards incompatibility in `easy_thumbnails.conf`.


## [1.0] - 2012-05-07

- Introduction of aliased thumbnails.
- Start of sane versioning numbers.
