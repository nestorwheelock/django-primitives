"""Models for django-worklog."""

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class WorklogBaseModel(models.Model):
    """Base model with UUID PK and timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class WorkSession(WorklogBaseModel):
    """
    A work session tracking when a user started and stopped working on something.

    Key invariants:
    - One active session per user (stopped_at IS NULL)
    - All timestamps are server-side
    - duration_seconds is derived, immutable once set
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="work_sessions",
    )

    # GenericFK for context attachment to any model
    context_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    context_object_id = models.CharField(max_length=255)
    context = GenericForeignKey("context_content_type", "context_object_id")

    # Server-side timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    # Optional metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "stopped_at"]),
            models.Index(fields=["context_content_type", "context_object_id"]),
        ]

    def __str__(self):
        status = "active" if self.stopped_at is None else "stopped"
        return f"WorkSession({self.user.username}, {status}, {self.pk})"
