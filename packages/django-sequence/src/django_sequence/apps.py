"""Django app configuration for django-sequence."""

from django.apps import AppConfig


class DjangoSequenceConfig(AppConfig):
    """App configuration for django-sequence."""

    name = 'django_sequence'
    verbose_name = 'Django Sequence'
    default_auto_field = 'django.db.models.BigAutoField'
