============
Installation
============

This fork requires Python 3.9+ and Django 4.2+. Image manipulation is
handled by `Pillow`__ (a fork of the Python Imaging Library / PIL), which is
installed automatically as a dependency.

.. __: https://python-pillow.org/


Installing easy-thumbnails
==========================

Install the package from `PyPI`__ with pip::

    pip install fdemmer-easy-thumbnails

.. __: https://pypi.python.org/pypi/fdemmer-easy-thumbnails/

To also thumbnail SVG images, install with the ``svg`` extra, which pulls
in ``svglib`` and ``reportlab``::

    pip install fdemmer-easy-thumbnails[svg]

See :doc:`ref/svg` for details on SVG support.


Configuring your project
========================

In your Django project's settings module, add easy-thumbnails to your
``INSTALLED_APPS`` setting::

    INSTALLED_APPS = (
        ...
        'easy_thumbnails',
    )

Run ``python manage.py migrate easy_thumbnails``.

You're done! You'll want to head on over now to the
:doc:`usage documentation <usage>`.
