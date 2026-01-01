"""Django settings for django-sequence tests."""

SECRET_KEY = 'test-secret-key-not-for-production'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django_sequence',
    'tests',
]

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
