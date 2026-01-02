"""Django settings for django-catalog tests."""

SECRET_KEY = 'test-secret-key-do-not-use-in-production'

DEBUG = True

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'tests.testapp',
    'django_singleton',
    'django_decisioning',
    'django_catalog',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

USE_TZ = True

# Configure swappable encounter model for tests
CATALOG_ENCOUNTER_MODEL = 'testapp.Encounter'
