"""Tests for buddy services.

TDD: Tests written FIRST, services don't exist yet.
"""

import pytest
from django.db import IntegrityError
from django_parties.models import Person

from primitives_testbed.diveops.models import (
    BuddyIdentity,
    Contact,
    DiveTeam,
    DiveTeamMember,
)


@pytest.fixture
def person_alice(db):
    """Create Alice as a person."""
    return Person.objects.create(
        first_name="Alice",
        last_name="Diver",
        email="alice@example.com",
    )


@pytest.fixture
def person_bob(db):
    """Create Bob as a person."""
    return Person.objects.create(
        first_name="Bob",
        last_name="Ocean",
        email="bob@example.com",
    )


@pytest.fixture
def person_charlie(db):
    """Create Charlie as a person."""
    return Person.objects.create(
        first_name="Charlie",
        last_name="Reef",
        email="charlie@example.com",
    )


@pytest.fixture
def contact_dana(person_alice, db):
    """Create Dana as an unregistered contact."""
    return Contact.objects.create(
        created_by=person_alice,
        display_name="Dana Deep",
        email="dana@example.com",
    )


# =============================================================================
# get_or_create_identity Tests
# =============================================================================

@pytest.mark.django_db
class TestGetOrCreateIdentity:
    """Tests for get_or_create_identity service."""

    def test_creates_identity_for_person(self, person_alice):
        """Creates BuddyIdentity for a Person."""
        from primitives_testbed.diveops.services import get_or_create_identity

        identity, created = get_or_create_identity(person=person_alice)
        assert created is True
        assert identity.person == person_alice
        assert identity.contact is None

    def test_gets_existing_identity_for_person(self, person_alice):
        """Returns existing BuddyIdentity for a Person."""
        from primitives_testbed.diveops.services import get_or_create_identity

        identity1, created1 = get_or_create_identity(person=person_alice)
        identity2, created2 = get_or_create_identity(person=person_alice)
        assert created1 is True
        assert created2 is False
        assert identity1.pk == identity2.pk

    def test_creates_identity_for_contact(self, contact_dana):
        """Creates BuddyIdentity for a Contact."""
        from primitives_testbed.diveops.services import get_or_create_identity

        identity, created = get_or_create_identity(contact=contact_dana)
        assert created is True
        assert identity.contact == contact_dana
        assert identity.person is None

    def test_gets_existing_identity_for_contact(self, contact_dana):
        """Returns existing BuddyIdentity for a Contact."""
        from primitives_testbed.diveops.services import get_or_create_identity

        identity1, created1 = get_or_create_identity(contact=contact_dana)
        identity2, created2 = get_or_create_identity(contact=contact_dana)
        assert created1 is True
        assert created2 is False
        assert identity1.pk == identity2.pk

    def test_raises_if_both_provided(self, person_alice, contact_dana):
        """Raises ValueError if both person and contact provided."""
        from primitives_testbed.diveops.services import get_or_create_identity

        with pytest.raises(ValueError):
            get_or_create_identity(person=person_alice, contact=contact_dana)

    def test_raises_if_neither_provided(self):
        """Raises ValueError if neither person nor contact provided."""
        from primitives_testbed.diveops.services import get_or_create_identity

        with pytest.raises(ValueError):
            get_or_create_identity()


# =============================================================================
# add_buddy_pair Tests
# =============================================================================

@pytest.mark.django_db
class TestAddBuddyPair:
    """Tests for add_buddy_pair service."""

    def test_creates_team_with_two_persons(self, person_alice, person_bob):
        """Creates buddy pair team with two registered Persons."""
        from primitives_testbed.diveops.services import add_buddy_pair

        team = add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        assert team.pk is not None
        assert team.team_type == "buddy"
        assert team.members.count() == 2

    def test_creates_team_with_person_and_contact_data(self, person_alice):
        """Creates buddy pair with new Contact from input data."""
        from primitives_testbed.diveops.services import add_buddy_pair

        team = add_buddy_pair(
            me_person=person_alice,
            friend_data={"display_name": "Eve Explorer", "email": "eve@example.com"},
        )
        assert team.pk is not None
        assert team.members.count() == 2
        # Should have created a Contact
        contacts = Contact.objects.filter(display_name="Eve Explorer")
        assert contacts.count() == 1

    def test_sets_created_by(self, person_alice, person_bob):
        """Team created_by is set to me_person."""
        from primitives_testbed.diveops.services import add_buddy_pair

        team = add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        assert team.created_by == person_alice

    def test_prevents_self_add(self, person_alice):
        """Cannot add yourself as your own buddy."""
        from primitives_testbed.diveops.services import add_buddy_pair

        with pytest.raises(ValueError):
            add_buddy_pair(me_person=person_alice, friend_person=person_alice)

    def test_returns_existing_pair_if_exists(self, person_alice, person_bob):
        """Returns existing team if pair already exists."""
        from primitives_testbed.diveops.services import add_buddy_pair

        team1 = add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        team2 = add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        assert team1.pk == team2.pk


# =============================================================================
# create_buddy_group Tests
# =============================================================================

@pytest.mark.django_db
class TestCreateBuddyGroup:
    """Tests for create_buddy_group service."""

    def test_creates_group_with_3_members(self, person_alice, person_bob, person_charlie):
        """Creates buddy group with 3 members."""
        from primitives_testbed.diveops.services import create_buddy_group

        team = create_buddy_group(
            me_person=person_alice,
            friend_persons=[person_bob, person_charlie],
            name="Weekend Warriors",
        )
        assert team.pk is not None
        assert team.name == "Weekend Warriors"
        assert team.members.count() == 3

    def test_group_includes_creator(self, person_alice, person_bob, person_charlie):
        """Creator is automatically included in the group."""
        from primitives_testbed.diveops.services import create_buddy_group

        team = create_buddy_group(
            me_person=person_alice,
            friend_persons=[person_bob, person_charlie],
        )
        # Check alice is in the team
        alice_identity = BuddyIdentity.objects.get(person=person_alice)
        assert team.members.filter(identity=alice_identity).exists()


# =============================================================================
# list_buddy_pairs Tests
# =============================================================================

@pytest.mark.django_db
class TestListBuddyPairs:
    """Tests for list_buddy_pairs service."""

    def test_returns_pairs_for_person(self, person_alice, person_bob, person_charlie):
        """Returns buddy pairs (size=2) where person is a member."""
        from primitives_testbed.diveops.services import add_buddy_pair, list_buddy_pairs

        add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        add_buddy_pair(me_person=person_alice, friend_person=person_charlie)

        pairs = list_buddy_pairs(person_alice)
        assert len(pairs) == 2

    def test_returns_buddy_name_in_pair(self, person_alice, person_bob):
        """Each pair includes the buddy's name."""
        from primitives_testbed.diveops.services import add_buddy_pair, list_buddy_pairs

        add_buddy_pair(me_person=person_alice, friend_person=person_bob)

        pairs = list_buddy_pairs(person_alice)
        assert len(pairs) == 1
        assert pairs[0]["buddy_name"] == "Bob Ocean"

    def test_returns_is_registered_status(self, person_alice, person_bob):
        """Each pair includes is_registered status."""
        from primitives_testbed.diveops.services import add_buddy_pair, list_buddy_pairs

        add_buddy_pair(me_person=person_alice, friend_person=person_bob)

        pairs = list_buddy_pairs(person_alice)
        assert pairs[0]["is_registered"] is True

    def test_excludes_groups_size_3_plus(self, person_alice, person_bob, person_charlie):
        """list_buddy_pairs excludes groups with 3+ members."""
        from primitives_testbed.diveops.services import (
            add_buddy_pair,
            create_buddy_group,
            list_buddy_pairs,
        )

        add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        create_buddy_group(
            me_person=person_alice,
            friend_persons=[person_bob, person_charlie],
            name="Trio",
        )

        pairs = list_buddy_pairs(person_alice)
        # Should only have 1 pair, not the group
        assert len(pairs) == 1


# =============================================================================
# list_buddy_groups Tests
# =============================================================================

@pytest.mark.django_db
class TestListBuddyGroups:
    """Tests for list_buddy_groups service."""

    def test_returns_groups_size_3_plus(self, person_alice, person_bob, person_charlie):
        """Returns buddy groups (size>=3) where person is a member."""
        from primitives_testbed.diveops.services import create_buddy_group, list_buddy_groups

        create_buddy_group(
            me_person=person_alice,
            friend_persons=[person_bob, person_charlie],
            name="Trio",
        )

        groups = list_buddy_groups(person_alice)
        assert len(groups) == 1
        assert groups[0]["name"] == "Trio"

    def test_excludes_pairs(self, person_alice, person_bob, person_charlie):
        """list_buddy_groups excludes pairs (size=2)."""
        from primitives_testbed.diveops.services import (
            add_buddy_pair,
            create_buddy_group,
            list_buddy_groups,
        )

        add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        create_buddy_group(
            me_person=person_alice,
            friend_persons=[person_bob, person_charlie],
            name="Trio",
        )

        groups = list_buddy_groups(person_alice)
        # Should only have 1 group, not the pair
        assert len(groups) == 1
        assert groups[0]["name"] == "Trio"


# =============================================================================
# remove_buddy Tests
# =============================================================================

@pytest.mark.django_db
class TestRemoveBuddy:
    """Tests for remove_buddy service."""

    def test_deletes_pair_when_removed(self, person_alice, person_bob):
        """Removing from a pair soft-deletes the whole team."""
        from primitives_testbed.diveops.services import add_buddy_pair, remove_buddy

        team = add_buddy_pair(me_person=person_alice, friend_person=person_bob)
        team_id = team.pk

        remove_buddy(me_person=person_alice, team_id=team_id)

        # Team should be soft-deleted
        assert DiveTeam.objects.filter(pk=team_id).count() == 0
        assert DiveTeam.all_objects.filter(pk=team_id).count() == 1

    def test_leaves_group_when_removed(self, person_alice, person_bob, person_charlie):
        """Removing from a group leaves the group (removes membership)."""
        from primitives_testbed.diveops.services import create_buddy_group, remove_buddy

        team = create_buddy_group(
            me_person=person_alice,
            friend_persons=[person_bob, person_charlie],
            name="Trio",
        )

        remove_buddy(me_person=person_alice, team_id=team.pk)

        # Team should still exist but without Alice
        team.refresh_from_db()
        assert team.members.count() == 2
        alice_identity = BuddyIdentity.objects.get(person=person_alice)
        assert not team.members.filter(identity=alice_identity).exists()
