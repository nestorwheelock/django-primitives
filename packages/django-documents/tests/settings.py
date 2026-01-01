"""Django settings for django-documents tests."""

import os
import tempfile

SECRET_KEY = 'test-secret-key-for-django-documents'

DEBUG = True

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django_documents',
    'tests',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

USE_TZ = True
TIME_ZONE = 'UTC'

# File storage settings for tests
MEDIA_ROOT = tempfile.mkdtemp()
MEDIA_URL = '/media/'

# Document settings
DOCUMENTS_STORAGE_BACKEND = 'django.core.files.storage.FileSystemStorage'
DOCUMENTS_DEFAULT_RETENTION_DAYS = None
DOCUMENTS_CHECKSUM_ALGORITHM = 'sha256'

AUTH_USER_MODEL = 'auth.User'
