"""Test models for django-notes tests."""

from django.db import models


class Organization(models.Model):
    """Test organization model."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name


class Project(models.Model):
    """Test project model for note attachment."""

    name = models.CharField(max_length=100)
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='projects',
    )

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name


class Task(models.Model):
    """Test task model for note attachment."""

    title = models.CharField(max_length=200)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
    )

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.title
