# tests/conftest.py
"""
Pytest configuration for repo-level contract tests.
"""
import django
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY="test-secret-key-for-contract-tests",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                # Tier 0
                "django_basemodels",
                # Tier 1
                "django_parties",
                "django_rbac",
                "django_decisioning",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
    django.setup()
