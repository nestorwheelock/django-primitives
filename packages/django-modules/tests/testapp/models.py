"""Test models for django-modules tests."""

from django.db import models

from django_basemodels.models import BaseModel


class Organization(BaseModel):
    """Test organization model for module state tests."""

    name = models.CharField(max_length=200)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name
