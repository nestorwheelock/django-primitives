"""Test models for django-encounters tests."""

from django.db import models


class Subject(models.Model):
    """
    Generic subject model for testing.

    In real usage, this could be Patient, Asset, Case, Project, etc.
    GenericFK allows encounters to attach to ANY model.
    """
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name
