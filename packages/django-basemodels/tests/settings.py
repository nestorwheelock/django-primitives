"""Minimal Django settings for running tests."""
SECRET_KEY = 'test-secret-key-not-for-production'
DEBUG = True

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'tests',  # Contains test models
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
