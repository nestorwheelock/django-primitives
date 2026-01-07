"""Django settings for django-questionnaires tests."""

SECRET_KEY = "test-secret-key-for-django-questionnaires"

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_basemodels",
    "django_questionnaires",
    "tests",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

AUTH_USER_MODEL = "auth.User"
