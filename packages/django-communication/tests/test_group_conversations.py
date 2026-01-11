"""Tests for group conversation features."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from django_communication.models import (
    Channel,
    Conversation,
    ConversationParticipant,
    ConversationStatus,
    ParticipantRole,
)
from django_communication.services.conversations import (
    create_conversation,
    send_in_conversation,
)
from django_parties.models import Person

User = get_user_model()


@pytest.fixture
def alice(db):
    """Create first person."""
    return Person.objects.create(
        first_name="Alice",
        last_name="Diver",
        email="alice@example.com",
    )


@pytest.fixture
def bob(db):
    """Create second person."""
    return Person.objects.create(
        first_name="Bob",
        last_name="Buddy",
        email="bob@example.com",
    )


@pytest.fixture
def charlie(db):
    """Create third person."""
    return Person.objects.create(
        first_name="Charlie",
        last_name="Friend",
        email="charlie@example.com",
    )


@pytest.mark.django_db
class TestConversationType:
    """Tests for conversation type field."""

    def test_conversation_has_type_field(self, alice):
        """Conversation model has conversation_type field."""
        from django_communication.models import ConversationType

        conv = create_conversation(
            subject="Test",
            participants=[(alice, ParticipantRole.CUSTOMER)],
        )

        # Default should be DIRECT
        assert conv.conversation_type == ConversationType.DIRECT

    def test_conversation_type_choices(self):
        """ConversationType enum has expected choices."""
        from django_communication.models import ConversationType

        assert ConversationType.DIRECT == "direct"
        assert ConversationType.GROUP == "group"

    def test_conversation_title_field(self, alice):
        """Conversation model has title field for group names."""
        conv = Conversation.objects.create(
            title="Dive Buddies Chat",
            subject="",
        )
        assert conv.title == "Dive Buddies Chat"

    def test_conversation_created_by_person(self, alice):
        """Conversation model has created_by_person field."""
        conv = Conversation.objects.create(
            title="Test Group",
            created_by_person=alice,
        )
        assert conv.created_by_person == alice


@pytest.mark.django_db
class TestParticipantState:
    """Tests for participant state field."""

    def test_participant_has_state_field(self, alice):
        """ConversationParticipant has state field."""
        from django_communication.models import ParticipantState

        conv = create_conversation(
            subject="Test",
            participants=[(alice, ParticipantRole.CUSTOMER)],
        )
        participant = conv.participants.first()

        # Default should be ACTIVE
        assert participant.state == ParticipantState.ACTIVE

    def test_participant_state_choices(self):
        """ParticipantState enum has expected choices."""
        from django_communication.models import ParticipantState

        assert ParticipantState.ACTIVE == "active"
        assert ParticipantState.INVITED == "invited"
        assert ParticipantState.LEFT == "left"
        assert ParticipantState.REMOVED == "removed"

    def test_participant_joined_at_field(self, alice):
        """ConversationParticipant has joined_at field."""
        conv = create_conversation(
            subject="Test",
            participants=[(alice, ParticipantRole.CUSTOMER)],
        )
        participant = conv.participants.first()

        # Can set joined_at
        now = timezone.now()
        participant.joined_at = now
        participant.save()
        participant.refresh_from_db()
        assert participant.joined_at == now

    def test_participant_left_at_field(self, alice):
        """ConversationParticipant has left_at field."""
        conv = create_conversation(
            subject="Test",
            participants=[(alice, ParticipantRole.CUSTOMER)],
        )
        participant = conv.participants.first()

        # Can set left_at
        now = timezone.now()
        participant.left_at = now
        participant.save()
        participant.refresh_from_db()
        assert participant.left_at == now

    def test_participant_invited_by_field(self, alice, bob):
        """ConversationParticipant has invited_by field."""
        conv = create_conversation(
            subject="Test",
            participants=[(alice, ParticipantRole.CUSTOMER)],
        )
        participant = conv.participants.first()

        # Can set invited_by
        participant.invited_by = bob
        participant.save()
        participant.refresh_from_db()
        assert participant.invited_by == bob


@pytest.mark.django_db
class TestParticipantRoles:
    """Tests for expanded participant roles."""

    def test_owner_role_exists(self):
        """ParticipantRole includes OWNER."""
        assert ParticipantRole.OWNER == "owner"

    def test_admin_role_exists(self):
        """ParticipantRole includes ADMIN."""
        assert ParticipantRole.ADMIN == "admin"

    def test_member_role_exists(self):
        """ParticipantRole includes MEMBER."""
        assert ParticipantRole.MEMBER == "member"


@pytest.mark.django_db
class TestCreateGroupConversation:
    """Tests for create_group_conversation service."""

    def test_create_group_conversation_basic(self, alice, bob):
        """Create a group conversation with title and members."""
        from django_communication.models import ConversationType, ParticipantState
        from django_communication.services.conversations import create_group_conversation

        group = create_group_conversation(
            title="Dive Buddies",
            creator_person=alice,
            initial_members=[bob],
        )

        assert group.conversation_type == ConversationType.GROUP
        assert group.title == "Dive Buddies"
        assert group.created_by_person == alice

        # Creator should be owner with active state
        owner = group.participants.get(person=alice)
        assert owner.role == ParticipantRole.OWNER
        assert owner.state == ParticipantState.ACTIVE
        assert owner.joined_at is not None

        # Initial member should be invited (not active)
        member = group.participants.get(person=bob)
        assert member.role == ParticipantRole.MEMBER
        assert member.state == ParticipantState.INVITED
        assert member.invited_by == alice

    def test_create_group_with_multiple_members(self, alice, bob, charlie):
        """Create group with multiple initial members."""
        from django_communication.services.conversations import create_group_conversation

        group = create_group_conversation(
            title="Dive Trio",
            creator_person=alice,
            initial_members=[bob, charlie],
        )

        assert group.participants.count() == 3
        assert group.participants.filter(role=ParticipantRole.OWNER).count() == 1
        assert group.participants.filter(role=ParticipantRole.MEMBER).count() == 2

    def test_create_group_without_initial_members(self, alice):
        """Create group with just creator."""
        from django_communication.services.conversations import create_group_conversation

        group = create_group_conversation(
            title="Solo Start",
            creator_person=alice,
        )

        assert group.participants.count() == 1
        owner = group.participants.first()
        assert owner.person == alice
        assert owner.role == ParticipantRole.OWNER


@pytest.mark.django_db
class TestInviteParticipant:
    """Tests for invite_participant service."""

    def test_invite_participant_basic(self, alice, bob, charlie):
        """Owner can invite new participant."""
        from django_communication.models import ParticipantState
        from django_communication.services.conversations import (
            create_group_conversation,
            invite_participant,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
        )

        # Alice (owner) invites Bob
        participant = invite_participant(
            conversation=group,
            person=bob,
            invited_by=alice,
        )

        assert participant.person == bob
        assert participant.state == ParticipantState.INVITED
        assert participant.invited_by == alice
        assert participant.role == ParticipantRole.MEMBER

    def test_invite_requires_owner_or_admin(self, alice, bob, charlie):
        """Only owner/admin can invite."""
        from django_communication.models import ParticipantState
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            invite_participant,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
            initial_members=[bob],
        )

        # Bob accepts invite to become active member
        accept_invite(group, bob)

        # Bob (member) tries to invite Charlie - should fail
        with pytest.raises(PermissionError):
            invite_participant(
                conversation=group,
                person=charlie,
                invited_by=bob,
            )

    def test_invite_to_direct_conversation_fails(self, alice, bob):
        """Cannot invite to direct conversation."""
        from django_communication.services.conversations import invite_participant

        direct = create_conversation(
            subject="Direct chat",
            participants=[(alice, ParticipantRole.CUSTOMER)],
        )

        with pytest.raises(ValueError):
            invite_participant(
                conversation=direct,
                person=bob,
                invited_by=alice,
            )


@pytest.mark.django_db
class TestAcceptInvite:
    """Tests for accept_invite service."""

    def test_accept_invite_basic(self, alice, bob):
        """Invited participant can accept."""
        from django_communication.models import ParticipantState
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
            initial_members=[bob],
        )

        # Bob is invited
        bob_participant = group.participants.get(person=bob)
        assert bob_participant.state == ParticipantState.INVITED

        # Bob accepts
        updated = accept_invite(group, bob)

        assert updated.state == ParticipantState.ACTIVE
        assert updated.joined_at is not None

    def test_accept_invite_when_not_invited_fails(self, alice, bob):
        """Cannot accept if not invited."""
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
        )

        # Bob is not invited
        with pytest.raises(ValueError):
            accept_invite(group, bob)


@pytest.mark.django_db
class TestRemoveParticipant:
    """Tests for remove_participant service."""

    def test_remove_participant_basic(self, alice, bob):
        """Owner can remove participant."""
        from django_communication.models import ParticipantState
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            remove_participant,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)

        # Alice removes Bob
        removed = remove_participant(
            conversation=group,
            person=bob,
            removed_by=alice,
        )

        assert removed.state == ParticipantState.REMOVED
        assert removed.left_at is not None

    def test_remove_requires_owner_or_admin(self, alice, bob, charlie):
        """Only owner/admin can remove."""
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            remove_participant,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
            initial_members=[bob, charlie],
        )
        accept_invite(group, bob)
        accept_invite(group, charlie)

        # Bob (member) tries to remove Charlie - should fail
        with pytest.raises(PermissionError):
            remove_participant(
                conversation=group,
                person=charlie,
                removed_by=bob,
            )

    def test_cannot_remove_owner(self, alice, bob):
        """Cannot remove the owner."""
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            remove_participant,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)

        # Bob tries to remove Alice (owner) - should fail
        # First make Bob an admin
        bob_participant = group.participants.get(person=bob)
        bob_participant.role = ParticipantRole.ADMIN
        bob_participant.save()

        with pytest.raises(ValueError):
            remove_participant(
                conversation=group,
                person=alice,
                removed_by=bob,
            )


@pytest.mark.django_db
class TestLeaveConversation:
    """Tests for leave_conversation service."""

    def test_leave_conversation_basic(self, alice, bob):
        """Member can leave group."""
        from django_communication.models import ParticipantState
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            leave_conversation,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)

        # Bob leaves
        left = leave_conversation(group, bob)

        assert left.state == ParticipantState.LEFT
        assert left.left_at is not None

    def test_owner_cannot_leave(self, alice):
        """Owner cannot leave without transferring ownership."""
        from django_communication.services.conversations import (
            create_group_conversation,
            leave_conversation,
        )

        group = create_group_conversation(
            title="Test Group",
            creator_person=alice,
        )

        with pytest.raises(ValueError):
            leave_conversation(group, alice)


@pytest.mark.django_db
class TestSetConversationTitle:
    """Tests for set_conversation_title service."""

    def test_set_title_basic(self, alice):
        """Owner can change title."""
        from django_communication.services.conversations import (
            create_group_conversation,
            set_conversation_title,
        )

        group = create_group_conversation(
            title="Original Title",
            creator_person=alice,
        )

        updated = set_conversation_title(group, "New Title", alice)

        assert updated.title == "New Title"

    def test_set_title_requires_owner_or_admin(self, alice, bob):
        """Only owner/admin can change title."""
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            set_conversation_title,
        )

        group = create_group_conversation(
            title="Original",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)

        # Bob (member) tries to change title - should fail
        with pytest.raises(PermissionError):
            set_conversation_title(group, "Bob's Title", bob)


@pytest.mark.django_db
class TestCanSendMessage:
    """Tests for can_send_message service."""

    def test_active_participant_can_send(self, alice, bob):
        """Active participants can send messages."""
        from django_communication.services.conversations import (
            accept_invite,
            can_send_message,
            create_group_conversation,
        )

        group = create_group_conversation(
            title="Test",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)

        assert can_send_message(group, alice) is True
        assert can_send_message(group, bob) is True

    def test_invited_participant_cannot_send(self, alice, bob):
        """Invited (not accepted) participants cannot send."""
        from django_communication.services.conversations import (
            can_send_message,
            create_group_conversation,
        )

        group = create_group_conversation(
            title="Test",
            creator_person=alice,
            initial_members=[bob],
        )

        # Bob is invited but hasn't accepted
        assert can_send_message(group, bob) is False

    def test_left_participant_cannot_send(self, alice, bob):
        """Participants who left cannot send."""
        from django_communication.services.conversations import (
            accept_invite,
            can_send_message,
            create_group_conversation,
            leave_conversation,
        )

        group = create_group_conversation(
            title="Test",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)
        leave_conversation(group, bob)

        assert can_send_message(group, bob) is False

    def test_removed_participant_cannot_send(self, alice, bob):
        """Removed participants cannot send."""
        from django_communication.services.conversations import (
            accept_invite,
            can_send_message,
            create_group_conversation,
            remove_participant,
        )

        group = create_group_conversation(
            title="Test",
            creator_person=alice,
            initial_members=[bob],
        )
        accept_invite(group, bob)
        remove_participant(group, bob, alice)

        assert can_send_message(group, bob) is False

    def test_send_in_conversation_checks_permission(self, alice, bob):
        """send_in_conversation raises error for non-active participants."""
        from django_communication.services.conversations import (
            create_group_conversation,
            send_in_conversation,
        )

        group = create_group_conversation(
            title="Test",
            creator_person=alice,
            initial_members=[bob],
        )

        # Bob is invited but hasn't accepted
        with pytest.raises(PermissionError):
            send_in_conversation(group, bob, "Hello!")


@pytest.mark.django_db
class TestGetActiveParticipants:
    """Tests for get_active_participants service."""

    def test_returns_only_active(self, alice, bob, charlie):
        """Only returns participants with active state."""
        from django_communication.models import ParticipantState
        from django_communication.services.conversations import (
            accept_invite,
            create_group_conversation,
            get_active_participants,
            leave_conversation,
        )

        group = create_group_conversation(
            title="Test",
            creator_person=alice,
            initial_members=[bob, charlie],
        )
        accept_invite(group, bob)
        accept_invite(group, charlie)
        leave_conversation(group, charlie)

        active = list(get_active_participants(group))

        # Alice (owner) and Bob (active member) should be returned
        # Charlie (left) should not be returned
        assert len(active) == 2
        person_ids = [p.person_id for p in active]
        assert alice.pk in person_ids
        assert bob.pk in person_ids
        assert charlie.pk not in person_ids
