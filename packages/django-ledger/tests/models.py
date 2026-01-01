"""Test models for django-ledger tests."""

from django.db import models


class Organization(models.Model):
    """Test organization model (account owner)."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name


class Customer(models.Model):
    """Test customer model (account owner)."""

    name = models.CharField(max_length=100)
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='customers',
    )

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name
