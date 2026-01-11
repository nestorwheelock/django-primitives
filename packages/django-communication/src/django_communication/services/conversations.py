"""Conversation services for managing threaded messaging.

This module provides the primary APIs for working with conversations:
- Creating conversations with participants
- Sending messages within conversations
- Managing read status
- Querying inboxes for staff and customers
"""

from datetime import datetime
from typing import Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone


def ensure_conversation_participant(
    conversation: "Conversation",
    person: "Person",
    role: str = None,
) -> "ConversationParticipant":
    """Get or create a participant. MUST be idempotent (no duplicates).

    This is the primary way to add participants to a conversation.
    If the participant already exists, returns the existing record.

    Args:
        conversation: The conversation to add participant to
        person: The Person to add as participant
        role: Role (customer, staff, system). Defaults to customer.

    Returns:
        ConversationParticipant instance (existing or new)
    """
    from ..models import ConversationParticipant, ParticipantRole

    if role is None:
        role = ParticipantRole.CUSTOMER

    participant, _ = ConversationParticipant.objects.get_or_create(
        conversation=conversation,
        person=person,
        defaults={"role": role},
    )
    return participant


@transaction.atomic
def create_conversation(
    subject: str = "",
    participants: list[tuple["Person", str]] = None,
    related_object: Any = None,
    assigned_to_user: "User" = None,
    created_by_user: "User" = None,
    primary_channel: str = "",
) -> "Conversation":
    """Create a new conversation with participants.

    Args:
        subject: Conversation subject/title
        participants: List of (person, role) tuples to add
        related_object: Optional object to link (e.g., Booking)
        assigned_to_user: Staff user to assign
        created_by_user: Staff user who created this
        primary_channel: Primary channel (email, sms, in_app)

    Returns:
        New Conversation instance with participants added
    """
    from ..models import Conversation

    # Create conversation
    conv = Conversation(
        subject=subject,
        assigned_to_user=assigned_to_user,
        created_by_user=created_by_user,
        primary_channel=primary_channel,
    )

    # Link related object if provided
    if related_object:
        conv.related_content_type = ContentType.objects.get_for_model(related_object)
        conv.related_object_id = str(related_object.pk)

    conv.save()

    # Add participants
    if participants:
        for person, role in participants:
            ensure_conversation_participant(conv, person, role)

    return conv


@transaction.atomic
def get_or_create_conversation_for_related(
    related_object: Any,
    participants: list[tuple["Person", str]] = None,
    subject: str = "",
) -> tuple["Conversation", bool]:
    """Find existing conversation for related object or create new.

    Useful when you want one conversation per booking, order, etc.

    Args:
        related_object: Object to link (e.g., Booking)
        participants: List of (person, role) tuples if creating new
        subject: Subject if creating new

    Returns:
        Tuple of (Conversation, created_bool)
    """
    from ..models import Conversation, ConversationStatus

    content_type = ContentType.objects.get_for_model(related_object)
    object_id = str(related_object.pk)

    # Try to find existing active conversation for this object
    existing = Conversation.objects.filter(
        related_content_type=content_type,
        related_object_id=object_id,
        status=ConversationStatus.ACTIVE,
    ).first()

    if existing:
        # Ensure participants are added
        if participants:
            for person, role in participants:
                ensure_conversation_participant(existing, person, role)
        return existing, False

    # Create new conversation
    conv = create_conversation(
        subject=subject,
        participants=participants,
        related_object=related_object,
    )
    return conv, True


@transaction.atomic
def send_in_conversation(
    conversation: "Conversation",
    sender_person: "Person",
    body_text: str,
    body_html: str = "",
    channel: str = None,
    direction: str = None,
    subject: str = "",
) -> "Message":
    """Send a message within an existing conversation.

    This is the primary way to add messages to a conversation.
    - Updates conversation.last_message_at
    - Ensures sender is a participant
    - Sets sender_person on Message
    - Marks as read for sender

    Args:
        conversation: Conversation to add message to
        sender_person: Person sending the message
        body_text: Plain text content
        body_html: HTML content (optional)
        channel: Channel (defaults to in_app)
        direction: Direction (defaults to outbound for staff, inbound for customer)
        subject: Subject line (for email)

    Returns:
        New Message instance
    """
    from ..models import (
        Channel,
        Message,
        MessageDirection,
        MessageStatus,
        ParticipantRole,
    )

    # Default channel to in_app
    if channel is None:
        channel = Channel.IN_APP

    # Ensure sender is a participant
    participant = ensure_conversation_participant(
        conversation, sender_person, ParticipantRole.CUSTOMER
    )

    # Determine direction based on participant role if not specified
    if direction is None:
        if participant.role == ParticipantRole.STAFF:
            direction = MessageDirection.OUTBOUND
        else:
            direction = MessageDirection.INBOUND

    # Create message
    message = Message.objects.create(
        conversation=conversation,
        sender_person=sender_person,
        direction=direction,
        channel=channel,
        from_address=sender_person.email or str(sender_person.pk),
        to_address="",  # In-app messages don't have explicit recipient
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        status=MessageStatus.DELIVERED,  # In-app is instant
        sent_at=timezone.now(),
        delivered_at=timezone.now(),
    )

    # Update conversation timestamp
    conversation.touch_last_message(message)

    # Mark as read for sender
    conversation.mark_read_for(sender_person)

    return message


def mark_conversation_read(
    conversation: "Conversation",
    person: "Person",
    at: datetime = None,
) -> None:
    """Mark conversation as read for a person.

    Args:
        conversation: Conversation to mark read
        person: Person who read the conversation
        at: Timestamp to mark (defaults to now)
    """
    conversation.mark_read_for(person, at=at)


def find_or_create_for_email(
    from_email: str,
    subject: str,
    email_thread_id: str = None,
    related_object: Any = None,
    from_person: "Person" = None,
) -> tuple["Conversation", bool]:
    """Find conversation by email thread or create new.

    Threading logic:
    1. Match by email_thread_id (if provided)
    2. Match by normalized_subject + participant email
    3. Create new if no match

    Args:
        from_email: Email address of sender
        subject: Email subject
        email_thread_id: In-Reply-To or References header
        related_object: Optional related object
        from_person: Person who sent the email (if known)

    Returns:
        Tuple of (Conversation, created_bool)
    """
    from ..models import Conversation, ConversationStatus, ParticipantRole

    # Normalize subject
    normalized = Conversation.normalize_subject(subject)

    # 1. Try email thread ID first (most reliable)
    if email_thread_id:
        conv = Conversation.objects.filter(
            email_thread_id=email_thread_id,
            status=ConversationStatus.ACTIVE,
        ).first()
        if conv:
            # Ensure sender is participant
            if from_person:
                ensure_conversation_participant(conv, from_person, ParticipantRole.CUSTOMER)
            return conv, False

    # 2. Try normalized subject + participant email match
    if from_email and normalized:
        conv = Conversation.objects.filter(
            normalized_subject=normalized,
            participants__person__email__iexact=from_email,
            status=ConversationStatus.ACTIVE,
        ).first()
        if conv:
            if from_person:
                ensure_conversation_participant(conv, from_person, ParticipantRole.CUSTOMER)
            return conv, False

    # 3. Create new conversation
    participants = []
    if from_person:
        participants.append((from_person, ParticipantRole.CUSTOMER))

    conv = create_conversation(
        subject=subject,
        participants=participants,
        related_object=related_object,
        primary_channel="email",
    )

    # Set email threading fields
    conv.email_thread_id = email_thread_id or ""
    conv.normalized_subject = normalized
    conv.save(update_fields=["email_thread_id", "normalized_subject", "updated_at"])

    return conv, True


def get_staff_inbox(
    user: "User",
    status: str = "active",
    scope: str = "mine",
) -> models.QuerySet:
    """Get conversations for staff CRM inbox.

    Returns annotated queryset with:
    - last_message_preview
    - unread_count (for the user's Person)
    - customer_name (first non-staff participant)
    - awaiting_reply (last message was inbound)

    Args:
        user: Staff user
        status: Filter by status (active, archived, closed, all)
        scope: Filter scope (mine, unassigned, all)

    Returns:
        QuerySet of Conversation with annotations
    """
    from ..models import (
        Conversation,
        ConversationParticipant,
        ConversationStatus,
        Message,
        MessageDirection,
        ParticipantRole,
    )

    # Base queryset
    qs = Conversation.objects.all()

    # Status filter
    if status != "all":
        qs = qs.filter(status=status)

    # Scope filter
    if scope == "mine":
        qs = qs.filter(assigned_to_user=user)
    elif scope == "unassigned":
        qs = qs.filter(assigned_to_user__isnull=True)
    # "all" shows everything

    # Annotate with last message preview
    latest_message = Message.objects.filter(
        conversation=OuterRef("pk")
    ).order_by("-created_at")

    qs = qs.annotate(
        last_message_preview=Subquery(latest_message.values("body_text")[:1]),
        last_message_direction=Subquery(latest_message.values("direction")[:1]),
    )

    # Annotate awaiting_reply (last message was inbound)
    qs = qs.annotate(
        awaiting_reply=Q(last_message_direction=MessageDirection.INBOUND)
    )

    # Get customer name (first non-staff participant)
    customer_participant = ConversationParticipant.objects.filter(
        conversation=OuterRef("pk"),
        role=ParticipantRole.CUSTOMER,
    ).order_by("created_at")

    qs = qs.annotate(
        customer_person_id=Subquery(customer_participant.values("person_id")[:1]),
    )

    # Order by most recent
    qs = qs.order_by("-last_message_at", "-created_at")

    # Prefetch for efficiency
    qs = qs.select_related("assigned_to_user").prefetch_related(
        "participants__person"
    )

    return qs


def get_customer_inbox(
    person: "Person",
) -> models.QuerySet:
    """Get conversations for customer portal.

    Returns annotated queryset with:
    - last_message_preview
    - last_message_at
    - unread_count

    Args:
        person: Customer Person instance

    Returns:
        QuerySet of Conversation with annotations
    """
    from ..models import Conversation, ConversationParticipant, Message

    # Get conversations where person is participant
    qs = Conversation.objects.filter(
        participants__person=person
    )

    # Annotate with last message preview
    latest_message = Message.objects.filter(
        conversation=OuterRef("pk")
    ).order_by("-created_at")

    qs = qs.annotate(
        last_message_preview=Subquery(latest_message.values("body_text")[:1]),
    )

    # Annotate with unread count
    participant_last_read = ConversationParticipant.objects.filter(
        conversation=OuterRef("pk"),
        person=person,
    ).values("last_read_at")[:1]

    # Count messages after last_read_at
    qs = qs.annotate(
        participant_last_read_at=Subquery(participant_last_read),
    ).annotate(
        unread_count=Count(
            "messages",
            filter=Q(messages__created_at__gt=models.F("participant_last_read_at"))
            | Q(participant_last_read_at__isnull=True),
        )
    )

    # Order by most recent
    qs = qs.order_by("-last_message_at", "-created_at")

    return qs


def get_conversation_messages(
    conversation: "Conversation",
    limit: int = None,
    before: datetime = None,
) -> models.QuerySet:
    """Get messages in a conversation in chronological order.

    Args:
        conversation: Conversation to get messages from
        limit: Maximum number of messages (most recent)
        before: Only get messages before this timestamp

    Returns:
        QuerySet of Message in chronological order
    """
    qs = conversation.messages.all()

    if before:
        qs = qs.filter(created_at__lt=before)

    # Always order chronologically
    qs = qs.order_by("created_at")

    if limit:
        # Get the latest N messages, but still return in chronological order
        # This requires a subquery approach
        latest_ids = qs.order_by("-created_at").values("pk")[:limit]
        qs = qs.filter(pk__in=latest_ids).order_by("created_at")

    return qs.select_related("sender_person", "template")
