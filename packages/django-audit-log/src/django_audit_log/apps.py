"""Django app configuration for django_audit_log."""
from django.apps import AppConfig


class DjangoAuditLogConfig(AppConfig):
    name = 'django_audit_log'
    label = 'django_audit_log'
    verbose_name = 'Audit Log'
    default_auto_field = 'django.db.models.UUIDField'
