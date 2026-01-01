"""Pytest configuration for django-geo tests."""
import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for pytest."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'django_geo',
            ],
            DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
            USE_TZ=True,
        )
    django.setup()
