import os

import django
import pytest
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": os.environ.get("POSTGRES_DB", "test_db"),
                    "USER": os.environ.get("POSTGRES_USER", "postgres"),
                    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
                    "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
                    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django_basemodels",
                "django_singleton",
                "django_cms_core",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            SECRET_KEY="test-secret-key-for-cms-core",
        )
    django.setup()


@pytest.fixture
def user(db):
    """Create a test user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def staff_user(db):
    """Create a test staff user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )
