"""Test models for django-catalog tests."""

from django.db import models


class Encounter(models.Model):
    """Simple encounter model for testing catalog."""

    patient_name = models.CharField(max_length=200)
    status = models.CharField(max_length=50, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'testapp'

    def __str__(self):
        return f"Encounter: {self.patient_name}"
