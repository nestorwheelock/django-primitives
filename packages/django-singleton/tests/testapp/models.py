"""Test models for django-singleton tests."""

from django.db import models

from django_singleton.models import SingletonModel


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
