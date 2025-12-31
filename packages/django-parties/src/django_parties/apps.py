"""Django app configuration for django_parties."""
from django.apps import AppConfig


class DjangoPartiesConfig(AppConfig):
    """Configuration for the Django Parties app."""

    name = "django_parties"
    label = "django_parties"
    verbose_name = "Parties"

    def ready(self):
        """Run when the app is ready."""
        pass
