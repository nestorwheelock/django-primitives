"""Django app configuration for invoicing module."""

from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    """Invoicing module app configuration."""

    name = "primitives_testbed.invoicing"
    verbose_name = "Invoicing"
    default_auto_field = "django.db.models.BigAutoField"
