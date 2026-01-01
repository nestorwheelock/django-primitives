"""Test models for django-sequence tests."""

from django.db import models


class Organization(models.Model):
    """Test organization model for per-org sequence isolation."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name
