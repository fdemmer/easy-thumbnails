====================
Management Commands
====================

easy-thumbnails provides management commands to help maintain the
thumbnail database cache and files on disk.

.. _thumbnail_storages:

thumbnail storages
==================

**Usage**::

    python manage.py thumbnail storages

Lists every storage alias configured in Django's ``STORAGES`` setting
together with its computed storage hash, one ``<alias>: <storage_hash>``
line per storage.

This is useful for identifying which alias a ``Source.storage_hash``
value corresponds to, and as a prerequisite step before running
:ref:`thumbnail cleanup --delete-with-missing-storage
<thumbnail_cleanup>`.

Examples
--------

List all configured storages::

    python manage.py thumbnail storages

Example output::

    default: 275876e34cf609db8f4c1b0c56dfd4ba
    media: 1e5f5210a4bec7dc9a1c0e3c1c2e7f6d

.. _thumbnail_cleanup:

thumbnail cleanup
=================

**Usage**::

    python manage.py thumbnail cleanup [options]

Scans every ``Source`` record in the database and checks whether the
corresponding source image still exists on its configured storage backend.
For any source that is no longer present, the command:

1. Deletes each associated thumbnail files from disk.
2. Removes the ``Source`` record (and its associated ``Thumbnail`` records)
   from the database via cascade delete.

This is useful for keeping the database ``Source`` and ``Thumbnail`` records
consistent and reclaiming disk space after image files have been removed
outside of Django (e.g., direct filesystem deletion, storage bucket cleanup).

Options
-------

``--dry-run``
    Report what would be deleted without making any changes to the
    database or filesystem. The statistics summary is still printed at
    the end. Use this to audit the scope of a cleanup before committing.

``--last-n-days N``
    Restrict the scan to ``Source`` records whose ``modified`` date falls
    within the last *N* days (today inclusive). Records older than *N*
    days are left untouched. Default: ``0`` (scan all records).

    .. note::
       The ``modified`` field is updated each time a thumbnail is
       generated or retrieved for that source — not when the source file
       was originally uploaded. A source that was accessed recently may
       have a ``modified`` date much newer than its actual creation date.

``--path PREFIX``
    Restrict the scan to ``Source`` records whose stored name begins with
    *PREFIX*. This is a literal string prefix match against the name as
    stored in the database — not a filesystem glob.

    To target a directory, include a trailing slash::

        python manage.py thumbnail cleanup --path uploads/avatars/

``--delete-with-missing-storage``
    Delete ``Source`` records (and their associated ``Thumbnail`` records)
    whose stored storage hash cannot be matched to any alias currently in
    Django's ``STORAGES`` setting. This is useful after a storage backend
    has been removed from configuration, leaving behind orphaned rows that
    would otherwise be skipped.

    Can be combined with ``--dry-run`` to preview the count before
    deleting, and with ``--last-n-days`` or ``--path`` to limit scope.
    Use the :ref:`thumbnail storages <thumbnail_storages>` command to
    see which storage hashes are currently recognised.

    .. warning::
       Only use this flag if you are certain the unrecognised storage hash
       corresponds to a backend that has been intentionally removed. If a
       storage alias is temporarily missing due to a misconfiguration,
       running this flag will permanently delete the associated database
       records.

Examples
--------

Preview what would be cleaned up without making changes::

    python manage.py thumbnail cleanup --dry-run

Clean up only records modified in the last 7 days::

    python manage.py thumbnail cleanup --last-n-days 7

Restrict cleanup to a specific path prefix, silently::

    python manage.py thumbnail cleanup --path uploads/user_photos/ --verbosity 0

Preview how many sources reference a removed storage backend::

    python manage.py thumbnail cleanup --delete-with-missing-storage --dry-run

Remove all sources tied to a removed storage backend::

    python manage.py thumbnail cleanup --delete-with-missing-storage

Output
------

After the scan, the command always prints a statistics summary::

    2026-04-16 14:32 ------------------------------
    Sources checked:                          1024
    Sources with missing storage deleted:       12
    Source references deleted from DB:          37
    Thumbnails deleted from disk:               92
    (Completed in 4 seconds)

.. note::
   "Thumbnails deleted from disk" counts thumbnails whose database
   entries were removed. A thumbnail file that was already absent from
   disk is still counted if its database entry is cleaned up.

.. note::
   "Sources with missing storage deleted" is only non-zero when
   ``--delete-with-missing-storage`` is passed.

Caveats
-------

**Storage backend must be reachable.**
The command calls ``storage.exists()`` for each source path. If a
storage backend raises an exception (e.g., a transient network error
with a remote storage), the source is treated as *missing* and its
database records will be deleted. Ensure all configured storage backends
are reliably reachable before running against a large dataset.

**Unrecognised storage hashes are skipped by default.**
Each ``Source`` record stores a hash of the storage backend used when
it was saved. If that hash cannot be matched to any alias currently
in Django's ``STORAGES`` setting — for example, after a storage backend
has been removed — the source is skipped rather than deleted. A message
is printed to stdout. Pass ``--delete-with-missing-storage`` to delete
these records instead.

**No signals are fired.**
The command deletes ``Source`` and ``Thumbnail`` records directly via
``QuerySet.delete()``. Any ``pre_delete`` or ``post_delete`` signal
handlers attached to those models in your project will not be called.

**Orphaned thumbnail files are not removed.**
If a thumbnail file exists on disk but its ``Source`` record has already
been deleted from the database, the command will not find or remove it.
The command only works from the database outward, not from the filesystem
inward.

**Requires Django 4.2+ ``STORAGES`` configuration.**
The command reads ``settings.STORAGES`` directly. Projects still using
the legacy ``DEFAULT_FILE_STORAGE`` string setting will encounter an
error.

.. _thumbnail_source_files:

thumbnail source_files
======================

**Usage**::

    python manage.py thumbnail source_files [options]

Lists the file paths currently stored in every ``ThumbnailerImageField``
across all installed apps. Useful for auditing which source images are
tracked and for feeding into other tools.

Options
-------

``-s`` / ``--summary``
    Instead of printing one path per line, print the count of non-empty
    values for each field, one field per line, followed by a total on
    stderr.

``--include SPEC``
    Restrict output to fields matching *SPEC*. *SPEC* can be:

    - ``app`` — matches all fields in the named app
    - ``app.model`` — matches all fields on the named model
    - ``app.model.field`` — matches a specific field

    Wildcards (``*``, ``?``) are supported in each component.
    May be repeated to include multiple specs.

``--exclude SPEC``
    Exclude fields matching *SPEC* from output. Same format as
    ``--include``. May be repeated.

Examples
--------

List every source path::

    python manage.py thumbnail source_files

Count per field (summary mode)::

    python manage.py thumbnail source_files --summary

Restrict to a single app::

    python manage.py thumbnail source_files --include myapp

.. _thumbnail_source_cleanup:

thumbnail source_cleanup
========================

**Usage**::

    python manage.py thumbnail source_cleanup [options]

Compares every ``Source`` record in the database against the current
values stored in ``ThumbnailerImageField`` columns across all installed
apps. Any ``Source`` whose ``(storage_hash, name)`` pair does not match
a field value is considered orphaned and deleted.

This is useful after a ``ThumbnailerImageField`` is removed or renamed,
or after rows are deleted directly from the database, leaving ``Source``
records with no corresponding model field value.

.. note::
   Deleting a ``Source`` record cascades to its associated ``Thumbnail``
   records in the database, but does **not** remove thumbnail files from
   storage.

Options
-------

``--dry-run``
    Print the name of each ``Source`` record that would be deleted,
    without making any changes to the database.

Examples
--------

Preview what would be removed::

    python manage.py thumbnail source_cleanup --dry-run

Remove all orphaned ``Source`` records::

    python manage.py thumbnail source_cleanup
