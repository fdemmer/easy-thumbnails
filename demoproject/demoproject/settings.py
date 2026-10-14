"""
Django settings for demoproject project.

For more information on this file, see
https://docs.djangoproject.com/en/stable/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/stable/ref/settings/
"""

from pathlib import Path

from django.utils.crypto import get_random_string


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_random_string(32)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'mainapp',
    'easy_thumbnails',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
    'easy_thumbnails': {
        'BACKEND': 'easy_thumbnails.storage.ThumbnailFileSystemStorage',
    },
}


THUMBNAIL_ALIASES = {
    'mainapp.TestImage.image': {
        'gallery': {
            'size': (320, 240),
            'crop': True,
            'upscale': True,
        },
        'gallery_webp': {
            'size': (320, 240),
            'crop': True,
            'upscale': True,
            'format': 'webp',
        },
        'gallery_avif': {
            'size': (320, 240),
            'crop': True,
            'upscale': True,
            'format': 'avif',
        },
        'gallery_2x': {
            'size': (640, 480),
            'crop': True,
            'upscale': True,
        },
        'gallery_2x_webp': {
            'size': (640, 480),
            'crop': True,
            'upscale': True,
            'format': 'webp',
        },
        'gallery_2x_avif': {
            'size': (640, 480),
            'crop': True,
            'upscale': True,
            'format': 'avif',
        },
    },
}
THUMBNAIL_BASEDIR = 'thumbs'
THUMBNAIL_CACHE_DIMENSIONS = True
THUMBNAIL_CHECK_CACHE_MISS = True
THUMBNAIL_DEBUG = DEBUG
THUMBNAIL_IMAGE_SAVE_OPTIONS = {
    'AVIF': {'quality': 61},
    'JPEG': {'quality': 76},
    'WEBP': {'quality': 80},
}
# THUMBNAIL_NAMER = 'easy_thumbnails.namers.alias_or_size'
THUMBNAIL_PRESERVE_EXTENSIONS = ['png']


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'demoproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'demoproject.wsgi.application'


# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # noqa: E501
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
