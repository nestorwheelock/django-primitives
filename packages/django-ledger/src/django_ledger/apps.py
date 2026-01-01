"""Django app configuration for django-ledger."""

from django.apps import AppConfig


class DjangoLedgerConfig(AppConfig):
    """App configuration for django-ledger."""

    name = 'django_ledger'
    verbose_name = 'Django Ledger'
    default_auto_field = 'django.db.models.BigAutoField'
