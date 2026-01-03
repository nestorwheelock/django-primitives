"""Django app configuration for checkin module."""

from django.apps import AppConfig


class CheckinConfig(AppConfig):
    """Configuration for check-in module."""

    name = "primitives_testbed.checkin"
    verbose_name = "Check-in"
    default_auto_field = "django.db.models.BigAutoField"
