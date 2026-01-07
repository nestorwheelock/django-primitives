"""Test models for django-singleton tests."""

from django.db import models

from django_singleton.models import SingletonModel
from django_singleton.mixins import EnvFallbackMixin


class SiteSettings(SingletonModel):
    """Test singleton with custom fields."""

    site_name = models.CharField(max_length=100, default="My Site")
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        app_label = "testapp"


class TaxSettings(SingletonModel):
    """Another singleton to test independence."""

    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    class Meta:
        app_label = "testapp"


class APISettings(EnvFallbackMixin, SingletonModel):
    """Test singleton with environment variable fallback."""

    api_key = models.CharField(max_length=255, blank=True)
    secret_key = models.CharField(max_length=255, blank=True)
    base_url = models.CharField(max_length=255, blank=True, default="")

    ENV_FALLBACKS = {
        "api_key": "TEST_API_KEY",
        "secret_key": "TEST_SECRET_KEY",
        # base_url intentionally has no fallback
    }

    class Meta:
        app_label = "testapp"
