"""Django Catalog app configuration."""

from django.apps import AppConfig


class DjangoCatalogConfig(AppConfig):
    """Configuration for django-catalog app."""

    name = "django_catalog"
    verbose_name = "Order Catalog"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Perform startup tasks when Django loads the app."""
        pass
