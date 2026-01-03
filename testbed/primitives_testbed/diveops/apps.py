"""Django app configuration for diveops."""

from django.apps import AppConfig


class DiveopsConfig(AppConfig):
    """App configuration for dive operations."""

    name = "primitives_testbed.diveops"
    verbose_name = "Dive Operations"
    default_auto_field = "django.db.models.BigAutoField"
