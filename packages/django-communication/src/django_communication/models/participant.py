"""ConversationParticipant model for conversation membership and read tracking."""

from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel


class ParticipantRole(models.TextChoices):
    """Role of participant in conversation."""

    # CRM roles (for direct/support conversations)
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff"
    SYSTEM = "system", "System"  # For automated messages

    # Group chat roles
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


class ParticipantState(models.TextChoices):
    """Membership state in conversation."""

    ACTIVE = "active", "Active"
    INVITED = "invited", "Invited"
    LEFT = "left", "Left"
    REMOVED = "removed", "Removed"


class ConversationParticipant(BaseModel):
    """Links a Person to a Conversation with role and read tracking.

    Person is the ONLY identity reference. Staff users should have
    corresponding Person records to participate in conversations.

    Tracks:
    - Who is part of a conversation
    - Their role (customer vs staff)
    - When they last read the conversation
    - Whether they want notifications

    Usage:
        from django_communication.services.conversations import ensure_conversation_participant

        # Add customer to conversation (idempotent)
        participant = ensure_conversation_participant(
            conversation=conv,
            person=customer,
            role=ParticipantRole.CUSTOMER,
        )

        # Mark as read
        participant.mark_read()

        # Check unread
        unread = participant.unread_count
    """

    conversation = models.ForeignKey(
        "django_communication.Conversation",
        on_delete=models.CASCADE,
        related_name="participants",
    )
    person = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="conversation_participations",
        help_text="Person participating in conversation",
    )
    role = models.CharField(
        max_length=20,
        choices=ParticipantRole.choices,
        default=ParticipantRole.CUSTOMER,
    )

    # === Membership State (for group chats) ===
    state = models.CharField(
        max_length=20,
        choices=ParticipantState.choices,
        default=ParticipantState.ACTIVE,
        db_index=True,
        help_text="Participant membership state",
    )
    joined_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When participant joined/accepted",
    )
    left_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When participant left or was removed",
    )
    invited_by = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations_sent",
        help_text="Person who invited this participant",
    )

    # === Read Tracking ===
    last_read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When participant last read the conversation",
    )

    # === Notification Preferences ===
    notifications_enabled = models.BooleanField(
        default=True,
        help_text="Whether to notify this participant of new messages",
    )

    class Meta:
        verbose_name = "Conversation Participant"
        verbose_name_plural = "Conversation Participants"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "person"],
                name="unique_conversation_person",
            ),
        ]
        indexes = [
            models.Index(fields=["conversation", "person"]),
            models.Index(fields=["person", "-last_read_at"]),
            models.Index(fields=["conversation", "role"]),
            models.Index(fields=["conversation", "state"]),
            models.Index(fields=["person", "state"]),
        ]

    def __str__(self):
        person_name = getattr(self.person, "full_name", str(self.person))
        return f"{person_name} ({self.role}) in {self.conversation}"

    def mark_read(self, at=None):
        """Update last_read_at to now or specified time."""
        self.last_read_at = at or timezone.now()
        self.save(update_fields=["last_read_at", "updated_at"])

    @property
    def unread_count(self) -> int:
        """Count of unread messages in this conversation for this participant.

        Only counts messages NOT sent by this participant (messages from others
        that this participant needs to read).
        """
        # Exclude messages sent by this participant
        others_messages = self.conversation.messages.exclude(
            sender_person=self.person
        )
        if self.last_read_at is None:
            return others_messages.count()
        return others_messages.filter(
            created_at__gt=self.last_read_at
        ).count()

    @property
    def has_unread(self) -> bool:
        """Whether there are any unread messages from others."""
        # Exclude messages sent by this participant
        others_messages = self.conversation.messages.exclude(
            sender_person=self.person
        )
        if self.last_read_at is None:
            return others_messages.exists()
        return others_messages.filter(
            created_at__gt=self.last_read_at
        ).exists()
