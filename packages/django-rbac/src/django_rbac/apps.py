"""Django app configuration for django-rbac."""

from django.apps import AppConfig


class DjangoRBACConfig(AppConfig):
    """App configuration for django-rbac."""

    name = 'django_rbac'
    verbose_name = 'Django RBAC'
    default_auto_field = 'django.db.models.BigAutoField'
