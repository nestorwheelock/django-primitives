"""Test models for django-worklog tests."""

from django.db import models


class Task(models.Model):
    """A simple task model for testing context attachment."""

    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name


class Project(models.Model):
    """Another model to test context attachment with different types."""

    title = models.CharField(max_length=200)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.title
