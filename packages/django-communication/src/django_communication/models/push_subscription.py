"""PushSubscription model for Web Push notifications."""

from django.db import models

from django_basemodels import BaseModel


class PushSubscription(BaseModel):
    """Web Push subscription for a Person's browser/device.

    Each browser/device that subscribes to push notifications creates
    a PushSubscription record. A Person can have multiple subscriptions
    (one per device).

    The endpoint, p256dh_key, and auth_key are provided by the browser
    when the user grants notification permission.
    """

    person = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        help_text="Person who owns this subscription",
    )

    # Web Push subscription data (from browser's PushSubscription object)
    endpoint = models.URLField(
        max_length=500,
        help_text="Push service endpoint URL",
    )
    p256dh_key = models.CharField(
        max_length=200,
        help_text="Public key for encryption (p256dh)",
    )
    auth_key = models.CharField(
        max_length=50,
        help_text="Auth secret for encryption",
    )

    # Device/browser info (for UI display)
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text="Browser user agent string",
    )
    device_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Friendly device name (e.g., 'Chrome on Windows')",
    )

    # Status tracking
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this subscription is active",
    )
    last_successful_push = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last push was successfully delivered",
    )
    failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive push failures (reset on success)",
    )

    class Meta:
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["person", "endpoint"],
                name="unique_person_endpoint",
            ),
        ]
        indexes = [
            models.Index(fields=["person", "is_active"]),
            models.Index(fields=["endpoint"]),
        ]

    def __str__(self):
        device = self.device_name or "Unknown device"
        status = "active" if self.is_active else "inactive"
        return f"{self.person} - {device} ({status})"
