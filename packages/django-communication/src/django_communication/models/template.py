"""Message template model for multi-channel content."""

from django.conf import settings
from django.db import models

from django_basemodels import BaseModel


class MessageType(models.TextChoices):
    """Message type determines default channel routing."""

    TRANSACTIONAL = "transactional", "Transactional"  # Confirmations, receipts
    REMINDER = "reminder", "Reminder"  # Day-of reminders
    ALERT = "alert", "Alert"  # Urgent notifications
    ANNOUNCEMENT = "announcement", "Announcement"  # Marketing, updates


class MessageTemplate(BaseModel):
    """Reusable message template with multi-channel support.

    Templates are identified by a unique key and can contain content
    for multiple channels. Template content uses Django template syntax.

    Usage:
        template = MessageTemplate.objects.get(key="booking_confirmation")
        # Use with services.send(template_key="booking_confirmation", ...)
    """

    key = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Unique identifier (e.g., 'booking_confirmation', 'day_of_reminder')",
    )
    name = models.CharField(
        max_length=200,
        help_text="Human-readable name",
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TRANSACTIONAL,
        help_text="Determines default channel routing",
    )

    # === Event-Driven Messaging ===
    event_type = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Event type that triggers this template (e.g., 'booking.confirmed', 'class.signup.started')",
    )

    # === Email Content ===
    email_subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Email subject line (Django template syntax)",
    )
    email_body_text = models.TextField(
        blank=True,
        help_text="Plain text email body (Django template syntax)",
    )
    email_body_html = models.TextField(
        blank=True,
        help_text="HTML email body (optional, Django template syntax)",
    )

    # === SMS Content ===
    sms_body = models.CharField(
        max_length=1600,  # Up to 10 SMS segments
        blank=True,
        help_text="SMS message content (Django template syntax)",
    )

    # === Metadata ===
    is_active = models.BooleanField(
        default=True,
        help_text="Only active templates can be used for sending",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_message_templates",
        help_text="User who last updated this template",
    )

    class Meta:
        verbose_name = "Message Template"
        verbose_name_plural = "Message Templates"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key}: {self.name}"

    def has_email_content(self) -> bool:
        """Check if template has email content defined."""
        return bool(self.email_subject and self.email_body_text)

    def has_sms_content(self) -> bool:
        """Check if template has SMS content defined."""
        return bool(self.sms_body)

    def get_available_channels(self) -> list[str]:
        """Return list of channels this template supports."""
        channels = []
        if self.has_email_content():
            channels.append("email")
        if self.has_sms_content():
            channels.append("sms")
        return channels
