"""Django app configuration for django-geo."""
from django.apps import AppConfig


class DjangoGeoConfig(AppConfig):
    """App configuration for django-geo."""

    name = 'django_geo'
    verbose_name = 'Django Geo'
    default_auto_field = 'django.db.models.BigAutoField'
