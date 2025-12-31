"""Audit log models for Django applications.

Provides a generic, B2B-grade audit log with:
- UUID primary keys
- Actor tracking (user + display snapshot)
- Model/object tracking with string snapshots
- Before/after change diffs (JSON)
- Request context (IP, user agent, request ID)
- Sensitivity classification (normal/high/critical)
- System action flag

NOTE: Audit logs are append-only. No soft delete - they're immutable records.
"""
import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Immutable audit log entry.

    Records who did what, when, where, and why for compliance and accountability.
    Audit logs are never deleted - they're the source of truth for auditors.
    """

    SENSITIVITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Timestamp (auto-populated, immutable)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Actor - who performed the action
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='django_audit_logs',
        help_text='User who performed the action (null for system actions)',
    )
    actor_display = models.CharField(
        max_length=200,
        blank=True,
        help_text='Snapshot of actor identity (email, name, etc.) for safety',
    )

    # Action - what was done
    action = models.CharField(
        max_length=50,
        db_index=True,
        help_text='Action type: create, update, delete, view, login, etc.',
    )

    # Target - what was affected
    model_label = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='Model label in app.model format (e.g., "emr.Encounter")',
    )
    object_id = models.CharField(
        max_length=50,
        blank=True,
        help_text='Primary key of affected object (UUID or integer as string)',
    )
    object_repr = models.CharField(
        max_length=200,
        blank=True,
        help_text='String representation of object at time of action',
    )

    # Changes - before/after diff
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Before/after field changes: {"field": {"old": x, "new": y}}',
    )

    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='Client IP address',
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text='Client user agent string',
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Request ID for correlation',
    )
    trace_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Distributed trace ID',
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional context (reason, ticket, etc.)',
    )
    sensitivity = models.CharField(
        max_length=20,
        choices=SENSITIVITY_CHOICES,
        default='normal',
        help_text='Data sensitivity classification',
    )
    is_system = models.BooleanField(
        default=False,
        help_text='True if action was performed by system (not a user)',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['actor_user', 'created_at']),
            models.Index(fields=['model_label', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['object_id', 'model_label']),
        ]

    def __str__(self):
        actor = self.actor_display or 'System'
        return f"{actor} {self.action} {self.model_label}"

    def save(self, *args, **kwargs):
        # Audit logs are append-only - prevent updates
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit logs are immutable and cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Audit logs should not be deleted
        raise ValueError("Audit logs are immutable and cannot be deleted")
