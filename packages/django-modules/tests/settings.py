"""Django settings for django-modules tests."""

SECRET_KEY = "test-secret-key-do-not-use-in-production"

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "tests.testapp",
    "django_basemodels",
    "django_modules",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True

# Configure swappable organization model for tests
MODULES_ORG_MODEL = "testapp.Organization"
