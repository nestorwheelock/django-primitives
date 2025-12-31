"""Test app configuration."""

from django.apps import AppConfig


class TestappConfig(AppConfig):
    """Configuration for test app."""

    name = 'tests.testapp'
    label = 'testapp'
    default_auto_field = 'django.db.models.BigAutoField'
