# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

easy-thumbnails is a Django app that provides on-demand thumbnail generation with a database cache. It supports PIL/Pillow for raster images and svglib for SVG images.

## Commands

### Testing

Run the full test matrix (Python 3.9–3.14, Django 4.2–6.0, with/without SVG support):
```bash
just test
# or directly:
uvx --with tox-uv tox --parallel auto
```

Run a specific tox environment:
```bash
uvx --with tox-uv tox -e py39-dj42
```

Run a specific test module, class, or method via tox posargs:
```bash
uvx --with tox-uv tox -e py39-dj42 -- tests.test_engine
uvx --with tox-uv tox -e py39-dj42 -- tests.test_engine.EngineTest.test_scale_and_crop
```

### Linting

```bash
prek --all-files
# or just ruff:
uvx ruff check --fix src/easy_thumbnails/
```

### Docs

```bash
just docs   # builds HTML docs into docs/_build/html/
```

### Build & Publish

```bash
just build           # python -m build
just publish-test    # upload to TestPyPI
just publish         # upload to PyPI (requires clean working tree)
```

## Architecture

### Thumbnail generation pipeline

1. **`files.py`** — Entry point. `get_thumbnailer(obj)` returns a `Thumbnailer` instance. Calling `thumbnailer.get_thumbnail(options)` either returns a cached thumbnail or triggers generation. `ThumbnailerFieldFile` / `ThumbnailerImageFieldFile` are the Django field file classes used when `ThumbnailerField` or `ThumbnailerImageField` is on a model.

2. **`engine.py`** — Low-level image operations:
   - `generate_source_image()` — tries each source generator in sequence until one succeeds
   - `process_image()` — runs the PIL image through each processor in sequence
   - `save_pil_image()` / `save_svg_image()` — writes to a `BytesIO`/`StringIO`

3. **`source_generators.py`** — Convert the source file into a PIL `Image`. `pil_image` handles raster formats; `vil_image` handles SVG via the VIL wrapper. Configured via `THUMBNAIL_SOURCE_GENERATORS`.

4. **`processors.py`** — Functions that transform a PIL image: `colorspace`, `autocrop`, `scale_and_crop`, `filters`, `background`. Each accepts `**kwargs` matching `ThumbnailOptions`. Configured via `THUMBNAIL_PROCESSORS`.

5. **`options.py`** — `ThumbnailOptions` dict subclass that normalises option values (e.g. parses `"100x100"` into a `(100, 100)` tuple).

### Database cache

`models.py` defines three models:
- `Source` — one row per source file (identified by `storage_hash` + `name`)
- `Thumbnail` — one row per generated thumbnail, FK to `Source`
- `ThumbnailDimensions` — optional one-to-one, stores width/height to avoid remote storage reads (enabled by `THUMBNAIL_CACHE_DIMENSIONS = True`)

`thumbnail_exists()` in `files.py` compares source/thumbnail `modified` timestamps. For local storage it reads mtime from disk; for remote storage it uses the DB cache values.

### Settings

All settings live in `conf.py` as attributes on the `Settings` class (which extends `AppSettings`). Django project settings override defaults by setting `THUMBNAIL_*` in `settings.py`. The global `settings` singleton is imported as `from easy_thumbnails.conf import settings`.

### SVG support

`VIL/` (Virtual Image Library) is a thin PIL-compatible wrapper around svglib/reportlab. It is an optional dependency (`extras = svg` in `pyproject.toml`). `source_generators.vil_image` and `engine.save_svg_image` use it. SVG thumbnails are returned as SVG, not rasterized.

### Aliases

`alias.py` provides named option sets via `THUMBNAIL_ALIASES` in settings. Aliases can be scoped to a field, model, or app. The global `aliases` singleton is imported as `from easy_thumbnails.alias import aliases`. The `{% thumbnail %}` template tag and `Thumbnailer.__getitem__` both resolve aliases.

### Namers

`namers.py` provides four built-in filename strategies (`default`, `hashed`, `alias`, `source_hashed`). Configured via `THUMBNAIL_NAMER`. Custom namers receive `thumbnailer`, `source_filename`, `thumbnail_extension`, `thumbnail_options`, and `prepared_options` kwargs.

### Optimize app

`optimize/` is a separate Django app (`easy_thumbnails.optimize`) that connects to the `thumbnail_created` signal and runs configurable post-processors (e.g. jpegoptim, optipng) on newly generated thumbnails.

### Template tag

`templatetags/thumbnail.py` provides the `{% thumbnail source size [options] %}` tag. It calls `get_thumbnailer()` and `get_thumbnail()`, returning a `ThumbnailFile` usable as an `<img>` src.

## Test settings

Tests use an in-memory SQLite DB and a `TemporaryStorage` backend (defined in `tests/utils.py`). The `DJANGO_SETTINGS_MODULE` must be `tests.settings`.
