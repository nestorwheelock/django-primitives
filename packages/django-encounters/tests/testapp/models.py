"""Test models for django-encounters tests."""

import uuid

from django.db import models


class Subject(models.Model):
    """
    Generic subject model for testing with integer PK.

    In real usage, this could be Patient, Asset, Case, Project, etc.
    GenericFK allows encounters to attach to ANY model.
    """
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name


class UUIDSubject(models.Model):
    """
    Subject model with UUID primary key for testing GenericFK with UUID subjects.

    This tests that Encounter.subject_id supports UUID primary keys,
    which is the standard pattern in django-primitives (via BaseModel).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name
