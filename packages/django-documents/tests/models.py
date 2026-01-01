"""Test models for django-documents tests."""

from django.db import models


class Organization(models.Model):
    """Test organization model for document attachment."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name


class Invoice(models.Model):
    """Test invoice model for document attachment."""

    number = models.CharField(max_length=50)
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invoices',
    )

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return f"Invoice {self.number}"
