====================
Management Commands
====================

easy-thumbnails provides management commands to help maintain the
thumbnail database cache and files on disk.

.. _thumbnail_cleanup:

thumbnail_cleanup
=================

**Usage**::

    python manage.py thumbnail_cleanup [options]

Scans every ``Source`` record in the database and checks whether the
corresponding source image still exists on its configured storage backend.
For any source that is no longer present, the command:

1. Deletes each associated thumbnail files from disk.
2. Removes the ``Source`` record (and its associated ``Thumbnail`` records)
   from the database via cascade delete.

This is useful for keeping the database thumbnail records consistent and
reclaiming disk space after source images have been removed outside of Django
(e.g., direct filesystem deletion, storage bucket cleanup, or bulk
database truncation).

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

        python manage.py thumbnail_cleanup --path uploads/avatars/

Examples
--------

Preview what would be cleaned up without making changes::

    python manage.py thumbnail_cleanup --dry-run

Clean up only records modified in the last 7 days::

    python manage.py thumbnail_cleanup --last-n-days 7

Restrict cleanup to a specific path prefix, silently::

    python manage.py thumbnail_cleanup --path uploads/user_photos/ --verbosity 0

Output
------

After the scan, the command always prints a statistics summary::

    2026-04-16 14:32 ------------------------------
    Sources checked:                          1024
    Source references deleted from DB:          37
    Thumbnails deleted from disk:               92
    (Completed in 4 seconds)

.. note::
   "Thumbnails deleted from disk" counts thumbnails whose database
   entries were removed. A thumbnail file that was already absent from
   disk is still counted if its database entry is cleaned up.

Caveats
-------

**Storage backend must be reachable.**
The command calls ``storage.exists()`` for each source path. If a
storage backend raises an exception (e.g., a transient network error
with a remote storage), the source is treated as *missing* and its
database records will be deleted. Ensure all configured storage backends
are reliably reachable before running against a large dataset.

**Unrecognised storage hashes are skipped.**
Each ``Source`` record stores a hash of the storage backend used when
it was saved. If that hash cannot be matched to any alias currently
in Django's ``STORAGES`` setting — for example, after a storage backend
has been removed — the source is skipped rather than deleted. A message
is printed to stdout. This means orphaned records from a removed storage
alias will silently accumulate until the alias is restored or the records
are cleaned up manually.

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
