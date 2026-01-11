"""Test models for django-communication tests."""

import uuid

from django.db import models


class TestBooking(models.Model):
    """Simple model to test GenericForeignKey linking."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=50)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.reference
