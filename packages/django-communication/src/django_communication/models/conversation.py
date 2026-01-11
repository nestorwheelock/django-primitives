"""Conversation model for grouping related messages."""

import re
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel


class ConversationStatus(models.TextChoices):
    """Conversation lifecycle status."""

    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"
    CLOSED = "closed", "Closed"


class Conversation(BaseModel):
    """Groups related messages between participants.

    A conversation is a thread of messages between a customer and staff.
    It consolidates multiple channels (email, SMS, in-app) into a single
    unified view for both customer portal and staff CRM.

    Key concepts:
    - One conversation can be linked to a related object (booking, order, etc.)
    - Messages across channels appear in chronological order
    - Staff can be assigned to conversations
    - Read tracking is per-participant via ConversationParticipant

    Usage:
        from django_communication.services.conversations import create_conversation

        conv = create_conversation(
            subject="Question about booking",
            participants=[(customer_person, "customer")],
        )
    """

    # === Identity ===
    subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Subject/title of conversation (often from email subject)",
    )
    normalized_subject = models.CharField(
        max_length=500,
        blank=True,
        db_index=True,
        help_text="Subject with Re:/Fwd: stripped for thread matching",
    )
    status = models.CharField(
        max_length=20,
        choices=ConversationStatus.choices,
        default=ConversationStatus.ACTIVE,
    )

    # === CRM Assignment (staff User) ===
    assigned_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
        help_text="Staff member responsible for this conversation",
    )

    # === Related Object (Context) ===
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Content type of related object (e.g., Booking)",
    )
    related_object_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of related object",
    )
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    # === Email Threading ===
    email_thread_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Email In-Reply-To/References header for threading",
    )

    # === Channel + Timing ===
    primary_channel = models.CharField(
        max_length=20,
        blank=True,
        help_text="Primary channel for this conversation (email, sms, in_app)",
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp of most recent message (denormalized for sorting)",
    )

    # === Lifecycle ===
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the conversation was closed",
    )
    closed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Staff who closed this conversation",
    )
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Staff who created this conversation",
    )

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-last_message_at"]),
            models.Index(fields=["assigned_to_user", "status", "-last_message_at"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
        ]

    def __str__(self):
        return f"Conversation: {self.subject or str(self.pk)[:8]}"

    def save(self, *args, **kwargs):
        """Auto-normalize subject on save."""
        if self.subject and not self.normalized_subject:
            self.normalized_subject = self.normalize_subject(self.subject)
        super().save(*args, **kwargs)

    def touch_last_message(self, message: "Message"):
        """Update last_message_at from a message."""
        self.last_message_at = message.created_at
        if not self.primary_channel and message.channel:
            self.primary_channel = message.channel
        self.save(update_fields=["last_message_at", "primary_channel", "updated_at"])

    def mark_read_for(self, person: "Person", at=None):
        """Mark conversation as read for a participant.

        Updates the participant's last_read_at to now (or specified time).
        """
        from .participant import ConversationParticipant

        at = at or timezone.now()
        ConversationParticipant.objects.filter(
            conversation=self,
            person=person,
        ).update(last_read_at=at)

    def get_unread_count_for(self, person: "Person") -> int:
        """Count unread messages for a participant.

        Returns count of messages created after participant's last_read_at.
        """
        from .participant import ConversationParticipant

        try:
            participant = self.participants.get(person=person)
            if participant.last_read_at is None:
                return self.messages.count()
            return self.messages.filter(created_at__gt=participant.last_read_at).count()
        except ConversationParticipant.DoesNotExist:
            return 0

    def close(self, user=None):
        """Close the conversation."""
        self.status = ConversationStatus.CLOSED
        self.closed_at = timezone.now()
        self.closed_by_user = user
        self.save(update_fields=["status", "closed_at", "closed_by_user", "updated_at"])

    def archive(self):
        """Archive the conversation."""
        self.status = ConversationStatus.ARCHIVED
        self.save(update_fields=["status", "updated_at"])

    def reopen(self):
        """Reopen a closed/archived conversation."""
        self.status = ConversationStatus.ACTIVE
        self.closed_at = None
        self.closed_by_user = None
        self.save(update_fields=["status", "closed_at", "closed_by_user", "updated_at"])

    @staticmethod
    def normalize_subject(subject: str) -> str:
        """Strip Re:, Fwd:, etc. from subject for thread matching.

        Handles common reply/forward prefixes in multiple languages:
        - English: Re:, Fwd:, Fw:
        - German: Aw:, Wg:
        - Spanish: Re:, Rv:
        - French: Re:, Tr:
        - Dutch: Antw:
        - Swedish: Sv:, Vb:
        """
        if not subject:
            return ""

        patterns = [
            r"^(re|fw|fwd|aw|wg|sv|antw|vs|rv|tr|vb):\s*",  # Common prefixes
            r"^\[.+?\]\s*",  # Mailing list prefixes like [list-name]
        ]

        normalized = subject.strip()
        for pattern in patterns:
            # Apply repeatedly to handle Re: Re: Re:
            while True:
                new_normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE).strip()
                if new_normalized == normalized:
                    break
                normalized = new_normalized

        return normalized[:500]  # Truncate to field length
