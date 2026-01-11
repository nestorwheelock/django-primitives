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
from django.db.models import Count, Max, OuterRef, Q, Subquery, Value
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

    For group conversations, sender must be an active participant.

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

    Raises:
        PermissionError: If sender is not an active participant (for group conversations)
    """
    from ..models import (
        Channel,
        ConversationType,
        Message,
        MessageDirection,
        MessageStatus,
        ParticipantRole,
    )

    # For group conversations, check if sender can send
    if conversation.conversation_type == ConversationType.GROUP:
        if not can_send_message(conversation, sender_person):
            raise PermissionError("Only active participants can send messages")

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


@transaction.atomic
def send_system_message(
    conversation: "Conversation",
    body_text: str,
    event_type: str = "",
    metadata: dict = None,
) -> "Message":
    """Send a system-generated message with no sender person.

    Used for flow events, status updates, and other automated messages.
    System messages are displayed distinctly in the UI.

    Args:
        conversation: Conversation to add message to
        body_text: Message content
        event_type: Type of event (e.g., 'flow_started', 'agreement_signed')
        metadata: Optional metadata dict to store with the message

    Returns:
        New Message instance
    """
    from ..models import Channel, Message, MessageDirection, MessageStatus

    # Create system message
    message = Message.objects.create(
        conversation=conversation,
        sender_person=None,  # System message - no sender
        direction=MessageDirection.SYSTEM,
        channel=Channel.IN_APP,
        from_address="system",
        to_address="",
        subject=event_type,  # Store event type in subject for querying
        body_text=body_text,
        body_html="",
        status=MessageStatus.DELIVERED,
        sent_at=timezone.now(),
        delivered_at=timezone.now(),
    )

    # Update conversation timestamp
    conversation.touch_last_message(message)

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
    from django.db.models import Value
    from django.db.models.functions import Coalesce, Concat

    from ..models import (
        Conversation,
        ConversationParticipant,
        ConversationStatus,
        Message,
        MessageDirection,
        ParticipantRole,
    )

    # Try to get staff Person for unread tracking
    # Person doesn't have a direct user FK, so we match by email
    staff_person = None
    try:
        from django_parties.models import Person
        from django.db.models import Q

        if user.email:
            staff_person = Person.objects.filter(
                email=user.email, deleted_at__isnull=True
            ).first()

        # Fallback: try matching by name if no email match
        if not staff_person and user.first_name and user.last_name:
            staff_person = Person.objects.filter(
                Q(first_name=user.first_name, last_name=user.last_name),
                deleted_at__isnull=True,
            ).first()
    except Exception:
        pass

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
    ).order_by("created_at").select_related("person")

    qs = qs.annotate(
        customer_person_id=Subquery(customer_participant.values("person_id")[:1]),
        customer_name=Subquery(
            customer_participant.annotate(
                full_name=Concat(
                    "person__first_name",
                    Value(" "),
                    "person__last_name",
                )
            ).values("full_name")[:1]
        ),
    )

    # Annotate unread_count for staff
    if staff_person:
        # Get staff's last_read_at for each conversation
        staff_participant = ConversationParticipant.objects.filter(
            conversation=OuterRef("pk"),
            person=staff_person,
        )

        # Count inbound messages since staff's last_read_at
        # If staff hasn't read, count all inbound messages
        qs = qs.annotate(
            staff_last_read=Subquery(staff_participant.values("last_read_at")[:1]),
        )

        # Count unread inbound + system messages
        # Use epoch (1970-01-01) as fallback when staff hasn't read,
        # so all messages will be counted as unread
        from zoneinfo import ZoneInfo
        epoch = datetime(1970, 1, 1, tzinfo=ZoneInfo("UTC"))

        unread_messages = Message.objects.filter(
            conversation=OuterRef("pk"),
            direction__in=[MessageDirection.INBOUND, MessageDirection.SYSTEM],
            # If staff_last_read is NULL, fall back to epoch so all messages are "after"
            created_at__gt=Coalesce(OuterRef("staff_last_read"), Value(epoch)),
        )

        qs = qs.annotate(
            unread_count=Coalesce(
                Subquery(
                    unread_messages.values("conversation").annotate(
                        cnt=Count("id")
                    ).values("cnt")[:1]
                ),
                Value(0),
            )
        )
    else:
        # No staff person, can't track unread
        qs = qs.annotate(unread_count=Value(0))

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


# =============================================================================
# GROUP CONVERSATION SERVICES
# =============================================================================


@transaction.atomic
def create_group_conversation(
    title: str,
    creator_person: "Person",
    initial_members: list["Person"] = None,
) -> "Conversation":
    """Create a new group conversation.

    The creator becomes the owner. Other members are added as invited.

    Args:
        title: Title for the group conversation
        creator_person: Person who creates and owns the group
        initial_members: Optional list of Persons to invite

    Returns:
        New group Conversation instance
    """
    from ..models import (
        Conversation,
        ConversationType,
        ConversationParticipant,
        ParticipantRole,
        ParticipantState,
    )

    # Create the group conversation
    conv = Conversation.objects.create(
        conversation_type=ConversationType.GROUP,
        title=title,
        created_by_person=creator_person,
        subject=title,  # Use title as subject for consistency
    )

    # Add creator as owner with active state
    ConversationParticipant.objects.create(
        conversation=conv,
        person=creator_person,
        role=ParticipantRole.OWNER,
        state=ParticipantState.ACTIVE,
        joined_at=timezone.now(),
    )

    # Invite other members
    if initial_members:
        for member in initial_members:
            if member.pk != creator_person.pk:  # Don't re-add creator
                ConversationParticipant.objects.create(
                    conversation=conv,
                    person=member,
                    role=ParticipantRole.MEMBER,
                    state=ParticipantState.INVITED,
                    invited_by=creator_person,
                )

    return conv


@transaction.atomic
def invite_participant(
    conversation: "Conversation",
    person: "Person",
    invited_by: "Person",
) -> "ConversationParticipant":
    """Invite a person to a group conversation.

    Only owner or admin can invite.

    Args:
        conversation: The group conversation
        person: Person to invite
        invited_by: Person doing the inviting (must be owner/admin)

    Returns:
        ConversationParticipant for the invited person

    Raises:
        ValueError: If conversation is not a group
        PermissionError: If inviter lacks permission
    """
    from ..models import ConversationType, ConversationParticipant, ParticipantRole, ParticipantState

    # Must be a group conversation
    if conversation.conversation_type != ConversationType.GROUP:
        raise ValueError("Can only invite to group conversations")

    # Check permission
    if not _has_admin_permission(conversation, invited_by):
        raise PermissionError("Only owner or admin can invite participants")

    # Check if already a participant
    existing = ConversationParticipant.objects.filter(
        conversation=conversation,
        person=person,
    ).first()

    if existing:
        # If they left or were removed, re-invite them
        if existing.state in (ParticipantState.LEFT, ParticipantState.REMOVED):
            existing.state = ParticipantState.INVITED
            existing.invited_by = invited_by
            existing.left_at = None
            existing.save(update_fields=["state", "invited_by", "left_at", "updated_at"])
            return existing
        # Already active or invited
        return existing

    # Create new invitation
    return ConversationParticipant.objects.create(
        conversation=conversation,
        person=person,
        role=ParticipantRole.MEMBER,
        state=ParticipantState.INVITED,
        invited_by=invited_by,
    )


@transaction.atomic
def add_participant(
    conversation: "Conversation",
    person: "Person",
    added_by: "Person",
    role: str = None,
) -> "ConversationParticipant":
    """Force-add a person to a group conversation as active participant.

    This bypasses the invitation flow and immediately makes them active.
    Intended for staff use when they need to loop someone in immediately.

    Only owner or admin can add.

    Args:
        conversation: The group conversation
        person: Person to add
        added_by: Person doing the adding (must be owner/admin)
        role: Role for the new participant (defaults to member)

    Returns:
        ConversationParticipant for the added person

    Raises:
        ValueError: If conversation is not a group
        PermissionError: If adder lacks permission
    """
    from ..models import ConversationType, ConversationParticipant, ParticipantRole, ParticipantState

    if role is None:
        role = ParticipantRole.MEMBER

    # Must be a group conversation
    if conversation.conversation_type != ConversationType.GROUP:
        raise ValueError("Can only add participants to group conversations")

    # Check permission
    if not _has_admin_permission(conversation, added_by):
        raise PermissionError("Only owner or admin can add participants")

    # Check if already a participant
    existing = ConversationParticipant.objects.filter(
        conversation=conversation,
        person=person,
    ).first()

    if existing:
        # If they're not active, make them active
        if existing.state != ParticipantState.ACTIVE:
            existing.state = ParticipantState.ACTIVE
            existing.joined_at = timezone.now()
            existing.left_at = None
            existing.save(update_fields=["state", "joined_at", "left_at", "updated_at"])
        return existing

    # Create new active participant
    return ConversationParticipant.objects.create(
        conversation=conversation,
        person=person,
        role=role,
        state=ParticipantState.ACTIVE,
        joined_at=timezone.now(),
        invited_by=added_by,
    )


@transaction.atomic
def accept_invite(
    conversation: "Conversation",
    person: "Person",
) -> "ConversationParticipant":
    """Accept an invitation to a group conversation.

    Args:
        conversation: The group conversation
        person: Person accepting the invitation

    Returns:
        Updated ConversationParticipant

    Raises:
        ValueError: If not invited
    """
    from ..models import ConversationParticipant, ParticipantState

    try:
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            person=person,
        )
    except ConversationParticipant.DoesNotExist:
        raise ValueError("Not invited to this conversation")

    if participant.state != ParticipantState.INVITED:
        raise ValueError("No pending invitation")

    participant.state = ParticipantState.ACTIVE
    participant.joined_at = timezone.now()
    participant.save(update_fields=["state", "joined_at", "updated_at"])

    return participant


@transaction.atomic
def remove_participant(
    conversation: "Conversation",
    person: "Person",
    removed_by: "Person",
    purge_history: bool = False,
) -> "ConversationParticipant | None":
    """Remove a participant from a group conversation.

    Only owner or admin can remove. Cannot remove owner.

    Args:
        conversation: The group conversation
        person: Person to remove
        removed_by: Person doing the removing (must be owner/admin)
        purge_history: If True, hard-deletes the participant record so they
            lose all access to the conversation. If False (default), sets
            state to REMOVED so they retain read-only access to messages
            up to their removal time.

    Returns:
        Updated ConversationParticipant, or None if purge_history=True

    Raises:
        PermissionError: If remover lacks permission
        ValueError: If trying to remove owner or person is not a participant
    """
    from ..models import ConversationParticipant, ParticipantRole, ParticipantState

    # Check permission
    if not _has_admin_permission(conversation, removed_by):
        raise PermissionError("Only owner or admin can remove participants")

    try:
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            person=person,
        )
    except ConversationParticipant.DoesNotExist:
        raise ValueError("Person is not a participant")

    # Cannot remove owner
    if participant.role == ParticipantRole.OWNER:
        raise ValueError("Cannot remove the owner")

    if purge_history:
        # Hard delete - they lose all access to the conversation
        participant.delete()
        return None
    else:
        # Soft remove - they keep read-only access to history
        participant.state = ParticipantState.REMOVED
        participant.left_at = timezone.now()
        participant.save(update_fields=["state", "left_at", "updated_at"])
        return participant


@transaction.atomic
def leave_conversation(
    conversation: "Conversation",
    person: "Person",
) -> "ConversationParticipant":
    """Leave a group conversation.

    Owner cannot leave without transferring ownership.

    Args:
        conversation: The group conversation
        person: Person leaving

    Returns:
        Updated ConversationParticipant

    Raises:
        ValueError: If owner tries to leave or not a participant
    """
    from ..models import ConversationParticipant, ParticipantRole, ParticipantState

    try:
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            person=person,
        )
    except ConversationParticipant.DoesNotExist:
        raise ValueError("Not a participant")

    # Owner cannot leave
    if participant.role == ParticipantRole.OWNER:
        raise ValueError("Owner cannot leave the conversation")

    # Must be active to leave
    if participant.state != ParticipantState.ACTIVE:
        raise ValueError("Not an active participant")

    participant.state = ParticipantState.LEFT
    participant.left_at = timezone.now()
    participant.save(update_fields=["state", "left_at", "updated_at"])

    return participant


@transaction.atomic
def set_conversation_title(
    conversation: "Conversation",
    title: str,
    changed_by: "Person",
) -> "Conversation":
    """Update the title of a group conversation.

    Only owner or admin can change title.

    Args:
        conversation: The group conversation
        title: New title
        changed_by: Person making the change (must be owner/admin)

    Returns:
        Updated Conversation

    Raises:
        PermissionError: If person lacks permission
    """
    if not _has_admin_permission(conversation, changed_by):
        raise PermissionError("Only owner or admin can change title")

    conversation.title = title
    conversation.subject = title  # Keep subject in sync
    conversation.save(update_fields=["title", "subject", "updated_at"])

    return conversation


def can_send_message(
    conversation: "Conversation",
    person: "Person",
) -> bool:
    """Check if a person can send messages in a conversation.

    For group conversations, only active participants can send.
    For direct conversations, any participant can send.

    Args:
        conversation: The conversation
        person: Person to check

    Returns:
        True if person can send messages
    """
    from ..models import ConversationType, ConversationParticipant, ParticipantState

    if conversation.conversation_type == ConversationType.DIRECT:
        # Direct: any participant
        return ConversationParticipant.objects.filter(
            conversation=conversation,
            person=person,
        ).exists()

    # Group: must be active participant
    return ConversationParticipant.objects.filter(
        conversation=conversation,
        person=person,
        state=ParticipantState.ACTIVE,
    ).exists()


def get_active_participants(
    conversation: "Conversation",
) -> models.QuerySet:
    """Get all active participants in a conversation.

    Args:
        conversation: The conversation

    Returns:
        QuerySet of ConversationParticipant with state=active
    """
    from ..models import ConversationParticipant, ParticipantState

    return ConversationParticipant.objects.filter(
        conversation=conversation,
        state=ParticipantState.ACTIVE,
    ).select_related("person")


def _has_admin_permission(conversation: "Conversation", person: "Person") -> bool:
    """Check if person has owner or admin role in conversation.

    Args:
        conversation: The conversation
        person: Person to check

    Returns:
        True if person is owner or admin
    """
    from ..models import ConversationParticipant, ParticipantRole, ParticipantState

    return ConversationParticipant.objects.filter(
        conversation=conversation,
        person=person,
        role__in=[ParticipantRole.OWNER, ParticipantRole.ADMIN],
        state=ParticipantState.ACTIVE,
    ).exists()
