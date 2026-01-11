"""Message model for logging all sent/received communications."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_basemodels import BaseModel

from .template import MessageType


class Channel(models.TextChoices):
    """Communication channels."""

    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    IN_APP = "in_app", "In-App Message"
    WHATSAPP = "whatsapp", "WhatsApp"
    PUSH = "push", "Web Push"


class MessageDirection(models.TextChoices):
    """Message direction."""

    OUTBOUND = "outbound", "Sent"
    INBOUND = "inbound", "Received"


class MessageStatus(models.TextChoices):
    """Message delivery status."""

    QUEUED = "queued", "Queued"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"


class Message(BaseModel):
    """Immutable log of a sent or received message.

    Every message sent through the system is recorded here for
    audit trail and delivery tracking. Messages are immutable
    after creation (except for status updates).
    """

    # === Conversation Link (optional for backwards compat) ===
    conversation = models.ForeignKey(
        "django_communication.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        help_text="Conversation this message belongs to",
    )

    # === Sender Identity (for stable UI) ===
    sender_person = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
        help_text="Person who sent this message",
    )

    # === Direction & Channel ===
    direction = models.CharField(
        max_length=10,
        choices=MessageDirection.choices,
        default=MessageDirection.OUTBOUND,
    )
    channel = models.CharField(
        max_length=20,  # Increased for longer channel names
        choices=Channel.choices,
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        blank=True,
    )

    # === Addressing ===
    from_address = models.CharField(
        max_length=255,
        help_text="Sender address (email or phone)",
    )
    to_address = models.CharField(
        max_length=255,
        help_text="Recipient address (email or phone)",
    )
    reply_to = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reply-to address (email only)",
    )

    # === Resolved Identity (for audit) ===
    recipient_locale = models.CharField(
        max_length=10,
        blank=True,
        help_text="Recipient's locale used for identity selection (e.g., 'en', 'es')",
    )
    profile = models.ForeignKey(
        "django_communication.MessageProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        help_text="Message profile used for sender identity",
    )

    # === Content ===
    subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Subject line (email only)",
    )
    body_text = models.TextField(
        help_text="Plain text content",
    )
    body_html = models.TextField(
        blank=True,
        help_text="HTML content (email only)",
    )

    # === Template Reference ===
    template = models.ForeignKey(
        "django_communication.MessageTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        help_text="Template used to generate this message",
    )

    # === Canned Response Reference (for audit) ===
    canned_response = models.ForeignKey(
        "django_communication.CannedResponse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        help_text="Canned response used to create this message",
    )
    canned_rendered_body = models.TextField(
        blank=True,
        help_text="Snapshot of rendered canned response at send time",
    )

    # === Status Tracking ===
    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.QUEUED,
    )
    provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Provider that sent this message (e.g., 'ses', 'twilio')",
    )
    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External message ID from provider",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error details if status is 'failed'",
    )

    # === Timestamps ===
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the message was sent",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When delivery was confirmed",
    )

    # === Email Threading (for future robust header-based threading) ===
    external_message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email Message-ID header value",
    )
    in_reply_to_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email In-Reply-To header value",
    )

    # === Related Object (GenericFK) ===
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Content type of related object",
    )
    related_object_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of related object (e.g., booking, excursion)",
    )
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["to_address"]),
            models.Index(fields=["direction", "created_at"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender_person"]),
        ]

    def __str__(self):
        return f"{self.channel}:{self.direction} to {self.to_address} ({self.status})"

    def mark_sent(self, provider: str, message_id: str = ""):
        """Update status to sent with provider info."""
        from django.utils import timezone

        self.status = MessageStatus.SENT
        self.provider = provider
        self.provider_message_id = message_id
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "provider", "provider_message_id", "sent_at", "updated_at"])

    def mark_failed(self, error: str, provider: str = ""):
        """Update status to failed with error details."""
        self.status = MessageStatus.FAILED
        self.provider = provider
        self.error_message = error
        self.save(update_fields=["status", "provider", "error_message", "updated_at"])

    def mark_delivered(self):
        """Update status to delivered."""
        from django.utils import timezone

        self.status = MessageStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])
