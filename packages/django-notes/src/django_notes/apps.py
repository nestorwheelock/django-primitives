"""Django app configuration for django-notes."""

from django.apps import AppConfig


class DjangoNotesConfig(AppConfig):
    """App configuration for django-notes."""

    name = 'django_notes'
    verbose_name = 'Django Notes'
    default_auto_field = 'django.db.models.BigAutoField'
