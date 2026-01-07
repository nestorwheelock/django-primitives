import django
import os
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY="test-secret-key-for-ai-services",
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
                "django_singleton",
                "django_ai_services",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
    django.setup()
