from django.apps import AppConfig


class DjangoSingletonConfig(AppConfig):
    name = "django_singleton"
    verbose_name = "Singleton"
    default_auto_field = "django.db.models.BigAutoField"
