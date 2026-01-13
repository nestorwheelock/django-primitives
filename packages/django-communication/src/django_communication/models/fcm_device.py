"""FCM Device model for Firebase Cloud Messaging push notifications."""

from django.conf import settings
from django.db import models

from django_basemodels import BaseModel


class DevicePlatform(models.TextChoices):
    """Device platform types."""

    ANDROID = "android", "Android"
    IOS = "ios", "iOS"
    WEB = "web", "Web"


class FCMDevice(BaseModel):
    """Firebase Cloud Messaging device registration.

    Each mobile device/browser that registers for FCM push notifications
    creates an FCMDevice record. A user can have multiple devices.

    The registration_id is the FCM token provided by Firebase SDK
    when the user grants notification permission.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fcm_devices",
        help_text="User who owns this device",
    )

    # FCM registration token (provided by Firebase SDK)
    registration_id = models.TextField(
        help_text="FCM registration token (device token)",
    )

    # Device info
    platform = models.CharField(
        max_length=10,
        choices=DevicePlatform.choices,
        default=DevicePlatform.ANDROID,
        help_text="Device platform",
    )
    device_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Unique device identifier (Android ID, IDFV, etc.)",
    )
    device_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Friendly device name (e.g., 'Pixel 7 Pro')",
    )
    app_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="App version (e.g., '1.0.0')",
    )

    # Status tracking
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this device is active for notifications",
    )
    last_successful_push = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last push was successfully sent",
    )
    failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive push failures (reset on success)",
    )

    class Meta:
        verbose_name = "FCM Device"
        verbose_name_plural = "FCM Devices"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "registration_id"],
                name="unique_user_fcm_token",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["registration_id"]),
            models.Index(fields=["platform", "is_active"]),
        ]

    def __str__(self):
        device = self.device_name or self.platform
        status = "active" if self.is_active else "inactive"
        return f"{self.user} - {device} ({status})"

    def mark_success(self):
        """Mark successful push delivery."""
        from django.utils import timezone

        self.last_successful_push = timezone.now()
        self.failure_count = 0
        self.save(update_fields=["last_successful_push", "failure_count", "updated_at"])

    def mark_failure(self):
        """Mark push failure. Deactivate after 5 consecutive failures."""
        self.failure_count += 1
        if self.failure_count >= 5:
            self.is_active = False
        self.save(update_fields=["failure_count", "is_active", "updated_at"])
