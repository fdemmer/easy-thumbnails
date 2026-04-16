import os
import re
from pathlib import Path, PurePath

from easy_thumbnails.conf import settings


re_thumbnail_file = re.compile(
    r'(?P<source_filename>.+)_(?P<x>\d+)x(?P<y>\d+)'
    r'(?:_(?P<options>\w+))?_q(?P<quality>\d+)'
    r'(?:.[^.]+)?$'
)


def all_thumbnails(path, recursive=True, prefix=None, subdir=None):
    """
    Return a dictionary referencing all files which match the thumbnail format.

    Each key is a source image filename, relative to path.
    Each value is a list of dictionaries as explained in `thumbnails_for_file`.
    """
    if prefix is None:
        prefix = settings.THUMBNAIL_PREFIX
    if subdir is None:
        subdir = settings.THUMBNAIL_SUBDIR

    thumbnail_files = {}
    if not path.endswith('/'):
        path = f'{path}/'
    len_path = len(path)

    if recursive:
        all = os.walk(path)
    else:
        files = [p.name for p in Path(path).iterdir() if p.is_file()]
        all = [(path, [], files)]

    for dir_, subdirs, files in all:  # noqa: B007
        rel_dir = dir_[len_path:]
        for file in files:
            thumb = re_thumbnail_file.match(file)
            if not thumb:
                continue

            d = thumb.groupdict()
            source_filename = d.pop('source_filename')

            if prefix:
                source_file_path = PurePath(source_filename)
                source_filename = source_file_path.name
                # remove prefix from source_filename
                if source_filename.startswith(prefix):
                    plain_filename = source_filename[len(prefix) :]
                    source_filename = str(source_file_path.parent / plain_filename)
                else:
                    continue

            d['options'] = d['options'] and d['options'].split('_') or []
            if subdir and rel_dir.endswith(subdir):
                rel_dir = rel_dir[: -len(subdir)]

            # Corner-case bug: if the filename didn't have an extension but did
            # have an underscore, the last underscore will get converted to a
            # '.'.
            if m := re.match(r'(.*)_(.*)', source_filename):
                source_filename = '{}.{}'.format(*m.groups())

            filename = str(PurePath(rel_dir) / source_filename)
            thumbnail_file = thumbnail_files.setdefault(filename, [])
            d['filename'] = str(PurePath(dir_) / file)
            thumbnail_file.append(d)

    return thumbnail_files


def thumbnails_for_file(
    relative_source_path,
    root=None,
    basedir=None,
    subdir=None,
    prefix=None,
):
    """
    Return a list of dictionaries, one for each thumbnail belonging to the
    source image.

    The following list explains each key of the dictionary:

      `filename`  -- absolute thumbnail path
      `x` and `y` -- the size of the thumbnail
      `options`   -- list of options for this thumbnail
      `quality`   -- quality setting for this thumbnail
    """
    if root is None:
        root = settings.MEDIA_ROOT
    if prefix is None:
        prefix = settings.THUMBNAIL_PREFIX
    if subdir is None:
        subdir = settings.THUMBNAIL_SUBDIR
    if basedir is None:
        basedir = settings.THUMBNAIL_BASEDIR

    source_file_path = Path(relative_source_path)
    thumbs_path = Path(root) / basedir / source_file_path.parent / subdir
    if not thumbs_path.is_dir():
        return []

    files = all_thumbnails(str(thumbs_path), recursive=False, prefix=prefix, subdir='')
    return files.get(source_file_path.name, [])


def delete_thumbnails(
    relative_source_path,
    root=None,
    basedir=None,
    subdir=None,
    prefix=None,
):
    """
    Delete all thumbnails for a source image.
    """
    thumbs = thumbnails_for_file(relative_source_path, root, basedir, subdir, prefix)
    return _delete_using_thumbs_list(thumbs)


def _delete_using_thumbs_list(thumbs):
    deleted = 0
    for thumb_dict in thumbs:
        filename = thumb_dict['filename']
        try:
            Path(filename).unlink()
        except FileNotFoundError:
            pass
        else:
            deleted += 1
    return deleted


def delete_all_thumbnails(path, recursive=True):
    """
    Delete all files within a path which match the thumbnails pattern.

    By default, matching files from all sub-directories are also removed. To
    only remove from the path directory, set recursive=False.
    """
    total = 0
    for thumbs in all_thumbnails(path, recursive=recursive).values():
        total += _delete_using_thumbs_list(thumbs)
    return total
