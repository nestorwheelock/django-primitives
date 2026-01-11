"""Tests for conversation models and services."""

import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from django_communication.models import (
    Channel,
    Conversation,
    ConversationParticipant,
    ConversationStatus,
    Message,
    MessageDirection,
    ParticipantRole,
)
from django_communication.services.conversations import (
    create_conversation,
    ensure_conversation_participant,
    find_or_create_for_email,
    get_conversation_messages,
    get_customer_inbox,
    get_or_create_conversation_for_related,
    get_staff_inbox,
    mark_conversation_read,
    send_in_conversation,
)
from django_parties.models import Person

User = get_user_model()


@pytest.fixture
def customer(db):
    """Create a customer Person."""
    return Person.objects.create(
        first_name="Alice",
        last_name="Customer",
        email="alice@example.com",
        phone="+15551111111",
    )


@pytest.fixture
def customer2(db):
    """Create a second customer Person."""
    return Person.objects.create(
        first_name="Bob",
        last_name="Customer",
        email="bob@example.com",
        phone="+15552222222",
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password="testpass123",
    )


@pytest.fixture
def staff_person(db):
    """Create a Person for staff member."""
    return Person.objects.create(
        first_name="Staff",
        last_name="Member",
        email="staffperson@example.com",
    )


@pytest.fixture
def conversation(db, customer):
    """Create a basic conversation with customer."""
    return create_conversation(
        subject="Test Conversation",
        participants=[(customer, ParticipantRole.CUSTOMER)],
    )


@pytest.mark.django_db
class TestConversationParticipant:
    """Tests for ConversationParticipant model and constraints."""

    def test_unique_constraint_prevents_duplicates(self, conversation, customer):
        """Ensure no duplicate participants via database constraint."""
        # First participant already exists from fixture
        assert conversation.participants.count() == 1

        # Try to create duplicate via direct model creation
        with pytest.raises(IntegrityError):
            ConversationParticipant.objects.create(
                conversation=conversation,
                person=customer,
                role=ParticipantRole.CUSTOMER,
            )

    def test_ensure_participant_is_idempotent(self, conversation, customer):
        """Calling ensure_participant twice returns same participant."""
        # Get original participant count
        original_count = conversation.participants.count()

        # Call ensure_participant for existing participant
        participant1 = ensure_conversation_participant(
            conversation, customer, ParticipantRole.CUSTOMER
        )
        participant2 = ensure_conversation_participant(
            conversation, customer, ParticipantRole.CUSTOMER
        )

        # Should return same participant, not create new one
        assert participant1.pk == participant2.pk
        assert conversation.participants.count() == original_count

    def test_ensure_participant_creates_new_if_not_exists(self, conversation, customer2):
        """ensure_participant creates new participant if needed."""
        original_count = conversation.participants.count()

        participant = ensure_conversation_participant(
            conversation, customer2, ParticipantRole.CUSTOMER
        )

        assert participant.person == customer2
        assert conversation.participants.count() == original_count + 1

    def test_participant_roles(self, customer, staff_person):
        """Participants can have different roles."""
        conv = create_conversation(
            subject="Multi-role test",
            participants=[
                (customer, ParticipantRole.CUSTOMER),
                (staff_person, ParticipantRole.STAFF),
            ],
        )

        customer_part = conv.participants.get(person=customer)
        staff_part = conv.participants.get(person=staff_person)

        assert customer_part.role == ParticipantRole.CUSTOMER
        assert staff_part.role == ParticipantRole.STAFF


@pytest.mark.django_db
class TestConversation:
    """Tests for Conversation model and core operations."""

    def test_send_updates_last_message_at(self, conversation, customer):
        """Sending message updates conversation timestamp."""
        # Initially no last_message_at
        assert conversation.last_message_at is None

        # Send a message
        before_send = timezone.now()
        message = send_in_conversation(
            conversation=conversation,
            sender_person=customer,
            body_text="Hello!",
        )
        after_send = timezone.now()

        # Refresh from DB
        conversation.refresh_from_db()

        # last_message_at should be updated
        assert conversation.last_message_at is not None
        assert before_send <= conversation.last_message_at <= after_send

    def test_mark_read_updates_unread_count(self, conversation, customer, customer2):
        """Mark read clears unread count for participant."""
        # Add second participant
        ensure_conversation_participant(conversation, customer2)

        # Send messages from customer2
        send_in_conversation(conversation, customer2, "Message 1")
        send_in_conversation(conversation, customer2, "Message 2")
        send_in_conversation(conversation, customer2, "Message 3")

        # Customer (original) has unread messages
        unread = conversation.get_unread_count_for(customer)
        assert unread == 3

        # Mark as read
        mark_conversation_read(conversation, customer)

        # Now should be 0
        unread_after = conversation.get_unread_count_for(customer)
        assert unread_after == 0

    def test_get_or_create_related_is_stable(self, db, customer, booking):
        """Multiple calls with same related object return same conversation."""
        # First call creates
        conv1, created1 = get_or_create_conversation_for_related(
            related_object=booking,
            participants=[(customer, ParticipantRole.CUSTOMER)],
            subject="Booking inquiry",
        )
        assert created1 is True

        # Second call finds existing
        conv2, created2 = get_or_create_conversation_for_related(
            related_object=booking,
            participants=[(customer, ParticipantRole.CUSTOMER)],
            subject="Different subject",  # Should be ignored
        )
        assert created2 is False
        assert conv1.pk == conv2.pk

    def test_conversation_lifecycle(self, conversation, staff_user):
        """Test close, archive, reopen operations."""
        assert conversation.status == ConversationStatus.ACTIVE

        # Close
        conversation.close(user=staff_user)
        assert conversation.status == ConversationStatus.CLOSED
        assert conversation.closed_at is not None
        assert conversation.closed_by_user == staff_user

        # Reopen
        conversation.reopen()
        assert conversation.status == ConversationStatus.ACTIVE
        assert conversation.closed_at is None
        assert conversation.closed_by_user is None

        # Archive
        conversation.archive()
        assert conversation.status == ConversationStatus.ARCHIVED

    def test_create_conversation_with_related_object(self, db, customer, booking):
        """Conversation can be linked to related object."""
        conv = create_conversation(
            subject="Booking question",
            participants=[(customer, ParticipantRole.CUSTOMER)],
            related_object=booking,
        )

        assert conv.related_object == booking
        assert str(conv.related_object_id) == str(booking.pk)

    def test_send_sets_sender_person(self, conversation, customer):
        """send_in_conversation sets sender_person on message."""
        message = send_in_conversation(
            conversation=conversation,
            sender_person=customer,
            body_text="Test message",
        )

        assert message.sender_person == customer
        assert message.conversation == conversation


@pytest.mark.django_db
class TestEmailThreading:
    """Tests for email threading heuristics."""

    def test_heuristic_subject_matching(self, db, customer):
        """Re: and Fwd: are stripped for matching."""
        # Test normalization - strips prefixes but preserves case
        assert Conversation.normalize_subject("Hello") == "Hello"
        assert Conversation.normalize_subject("Re: Hello") == "Hello"
        assert Conversation.normalize_subject("RE: Hello") == "Hello"
        assert Conversation.normalize_subject("Fwd: Hello") == "Hello"
        assert Conversation.normalize_subject("FWD: Hello") == "Hello"
        assert Conversation.normalize_subject("Re: Fwd: Re: Hello") == "Hello"
        assert Conversation.normalize_subject("Re:Re:Re: Hello") == "Hello"
        assert Conversation.normalize_subject("  Re:   Hello  ") == "Hello"

    def test_subject_threading_finds_existing(self, db, customer):
        """find_or_create_for_email matches by normalized subject."""
        # Create initial conversation
        conv1, created1 = find_or_create_for_email(
            from_email="alice@example.com",
            subject="Question about booking",
            from_person=customer,
        )
        assert created1 is True

        # Reply should match existing
        conv2, created2 = find_or_create_for_email(
            from_email="alice@example.com",
            subject="Re: Question about booking",
            from_person=customer,
        )
        assert created2 is False
        assert conv1.pk == conv2.pk

    def test_thread_id_matching(self, db, customer):
        """Exact thread_id match wins over subject matching."""
        thread_id = "<msg123@example.com>"

        # Create conversation with thread ID
        conv1, created1 = find_or_create_for_email(
            from_email="alice@example.com",
            subject="Original Subject",
            email_thread_id=thread_id,
            from_person=customer,
        )
        assert created1 is True

        # Reply with thread ID should match even with different subject
        conv2, created2 = find_or_create_for_email(
            from_email="alice@example.com",
            subject="Completely Different Subject",
            email_thread_id=thread_id,
            from_person=customer,
        )
        assert created2 is False
        assert conv1.pk == conv2.pk

    def test_different_sender_creates_new_conversation(self, db, customer, customer2):
        """Different sender email creates new conversation."""
        conv1, created1 = find_or_create_for_email(
            from_email="alice@example.com",
            subject="Test Subject",
            from_person=customer,
        )

        # Different email, same subject creates new conversation
        conv2, created2 = find_or_create_for_email(
            from_email="bob@example.com",
            subject="Test Subject",
            from_person=customer2,
        )

        assert created1 is True
        assert created2 is True
        assert conv1.pk != conv2.pk


@pytest.mark.django_db
class TestInbox:
    """Tests for inbox queries."""

    def test_staff_inbox_filters(self, db, customer, customer2, staff_user, staff_person):
        """mine/unassigned/all filters work correctly."""
        # Create staff user 2
        staff_user2 = User.objects.create_user(
            username="staffuser2",
            email="staff2@example.com",
            password="testpass123",
        )

        # Conversation assigned to staff_user
        conv_mine = create_conversation(
            subject="Assigned to me",
            participants=[(customer, ParticipantRole.CUSTOMER)],
            assigned_to_user=staff_user,
        )

        # Conversation unassigned
        conv_unassigned = create_conversation(
            subject="Unassigned",
            participants=[(customer2, ParticipantRole.CUSTOMER)],
        )

        # Conversation assigned to someone else
        conv_other = create_conversation(
            subject="Assigned to other",
            participants=[(customer, ParticipantRole.CUSTOMER)],
            assigned_to_user=staff_user2,
        )

        # Test "mine" scope
        mine_inbox = get_staff_inbox(staff_user, scope="mine")
        mine_ids = list(mine_inbox.values_list("pk", flat=True))
        assert conv_mine.pk in mine_ids
        assert conv_unassigned.pk not in mine_ids
        assert conv_other.pk not in mine_ids

        # Test "unassigned" scope
        unassigned_inbox = get_staff_inbox(staff_user, scope="unassigned")
        unassigned_ids = list(unassigned_inbox.values_list("pk", flat=True))
        assert conv_mine.pk not in unassigned_ids
        assert conv_unassigned.pk in unassigned_ids
        assert conv_other.pk not in unassigned_ids

        # Test "all" scope
        all_inbox = get_staff_inbox(staff_user, scope="all")
        all_ids = list(all_inbox.values_list("pk", flat=True))
        assert conv_mine.pk in all_ids
        assert conv_unassigned.pk in all_ids
        assert conv_other.pk in all_ids

    def test_customer_inbox_only_shows_participated(self, db, customer, customer2):
        """Customer only sees their conversations."""
        # Conversation with customer1
        conv1 = create_conversation(
            subject="Customer 1 conversation",
            participants=[(customer, ParticipantRole.CUSTOMER)],
        )

        # Conversation with customer2
        conv2 = create_conversation(
            subject="Customer 2 conversation",
            participants=[(customer2, ParticipantRole.CUSTOMER)],
        )

        # Conversation with both
        conv3 = create_conversation(
            subject="Both customers",
            participants=[
                (customer, ParticipantRole.CUSTOMER),
                (customer2, ParticipantRole.CUSTOMER),
            ],
        )

        # Customer1's inbox
        inbox1 = get_customer_inbox(customer)
        inbox1_ids = list(inbox1.values_list("pk", flat=True))
        assert conv1.pk in inbox1_ids
        assert conv2.pk not in inbox1_ids
        assert conv3.pk in inbox1_ids

        # Customer2's inbox
        inbox2 = get_customer_inbox(customer2)
        inbox2_ids = list(inbox2.values_list("pk", flat=True))
        assert conv1.pk not in inbox2_ids
        assert conv2.pk in inbox2_ids
        assert conv3.pk in inbox2_ids

    def test_inbox_has_unread_count(self, db, customer, customer2):
        """Customer inbox includes unread count."""
        conv = create_conversation(
            subject="Test unread",
            participants=[
                (customer, ParticipantRole.CUSTOMER),
                (customer2, ParticipantRole.CUSTOMER),
            ],
        )

        # Customer2 sends messages
        send_in_conversation(conv, customer2, "Message 1")
        send_in_conversation(conv, customer2, "Message 2")

        # Customer1's inbox should show unread count
        inbox = get_customer_inbox(customer)
        conv_from_inbox = inbox.get(pk=conv.pk)
        assert conv_from_inbox.unread_count == 2

    def test_staff_inbox_status_filter(self, db, customer, staff_user):
        """Staff inbox can filter by status."""
        # Active conversation
        conv_active = create_conversation(
            subject="Active",
            participants=[(customer, ParticipantRole.CUSTOMER)],
            assigned_to_user=staff_user,
        )

        # Closed conversation
        conv_closed = create_conversation(
            subject="Closed",
            participants=[(customer, ParticipantRole.CUSTOMER)],
            assigned_to_user=staff_user,
        )
        conv_closed.close(user=staff_user)

        # Test active filter
        active_inbox = get_staff_inbox(staff_user, status="active")
        active_ids = list(active_inbox.values_list("pk", flat=True))
        assert conv_active.pk in active_ids
        assert conv_closed.pk not in active_ids

        # Test closed filter
        closed_inbox = get_staff_inbox(staff_user, status="closed")
        closed_ids = list(closed_inbox.values_list("pk", flat=True))
        assert conv_active.pk not in closed_ids
        assert conv_closed.pk in closed_ids


@pytest.mark.django_db
class TestConversationMessages:
    """Tests for message retrieval."""

    def test_get_conversation_messages_chronological(self, conversation, customer):
        """Messages returned in chronological order."""
        msg1 = send_in_conversation(conversation, customer, "First")
        msg2 = send_in_conversation(conversation, customer, "Second")
        msg3 = send_in_conversation(conversation, customer, "Third")

        messages = list(get_conversation_messages(conversation))
        assert len(messages) == 3
        assert messages[0].pk == msg1.pk
        assert messages[1].pk == msg2.pk
        assert messages[2].pk == msg3.pk

    def test_get_conversation_messages_with_limit(self, conversation, customer):
        """Limit parameter returns most recent N messages."""
        for i in range(5):
            send_in_conversation(conversation, customer, f"Message {i}")

        messages = list(get_conversation_messages(conversation, limit=3))
        assert len(messages) == 3
        # Should be the last 3 messages in chronological order
        assert "Message 2" in messages[0].body_text
        assert "Message 3" in messages[1].body_text
        assert "Message 4" in messages[2].body_text

    def test_send_ensures_sender_is_participant(self, conversation, customer2):
        """Sending message adds sender as participant if not already."""
        # customer2 is not a participant
        assert not conversation.participants.filter(person=customer2).exists()

        # Send message
        send_in_conversation(conversation, customer2, "Hello!")

        # Now customer2 is a participant
        assert conversation.participants.filter(person=customer2).exists()

    def test_in_app_message_is_instant_delivery(self, conversation, customer):
        """In-app messages are marked as delivered immediately."""
        message = send_in_conversation(
            conversation, customer, "Instant message", channel=Channel.IN_APP
        )

        assert message.channel == Channel.IN_APP
        assert message.sent_at is not None
        assert message.delivered_at is not None
