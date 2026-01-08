"""Entitlement grant model.

Tracks which users have which entitlements, enabling access to
paywall content in the CMS.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class EntitlementGrant(models.Model):
    """Records a user's entitlement to access protected content.

    Entitlements are granted when:
    - A user purchases a product that includes entitlements (via fulfillment)
    - A staff member manually grants access

    Attributes:
        user: The user who has this entitlement
        code: The entitlement code (e.g., 'content:owd-courseware')
        source_type: How the entitlement was granted ('invoice', 'manual')
        source_id: Reference to the source (invoice ID, ticket ID, etc.)
        starts_at: When the entitlement becomes active (null = immediate)
        ends_at: When the entitlement expires (null = permanent)
        created_at: When this grant was created
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entitlement_grants",
    )
    code = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Entitlement code (e.g., 'content:owd-courseware')",
    )

    # Source tracking
    source_type = models.CharField(
        max_length=20,
        choices=[
            ("invoice", "Invoice/Purchase"),
            ("manual", "Manual Grant"),
        ],
        default="manual",
    )
    source_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Reference to source (invoice ID, etc.)",
    )

    # Validity period
    starts_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When entitlement becomes active (null = immediate)",
    )
    ends_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When entitlement expires (null = permanent)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "entitlement grant"
        verbose_name_plural = "entitlement grants"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "code"]),
            models.Index(fields=["code", "ends_at"]),
        ]

    def __str__(self):
        return f"{self.user} -> {self.code}"

    def is_active(self, at=None):
        """Check if this entitlement is currently active.

        Args:
            at: Point in time to check (default: now)

        Returns:
            True if entitlement is active at the given time
        """
        at = at or timezone.now()

        # Check start time
        if self.starts_at and at < self.starts_at:
            return False

        # Check end time
        if self.ends_at and at >= self.ends_at:
            return False

        return True
