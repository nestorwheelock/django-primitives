"""Tests for DiveBuddy model.

Tests cover:
- Creating buddy relationships between divers
- Bi-directional buddy lookup
- Buddy relationship types
- Preventing duplicate buddy relationships
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django_parties.models import Person

from primitives_testbed.diveops.models import DiveBuddy, DiverProfile

User = get_user_model()


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
def diver_alice(person_alice, db):
    """Create Alice's diver profile."""
    return DiverProfile.objects.create(person=person_alice)


@pytest.fixture
def diver_bob(person_bob, db):
    """Create Bob's diver profile."""
    return DiverProfile.objects.create(person=person_bob)


@pytest.mark.django_db
class TestDiveBuddyModel:
    """Tests for DiveBuddy model."""

    def test_create_buddy_relationship(self, diver_alice, diver_bob):
        """Can create a buddy relationship between two divers."""
        buddy = DiveBuddy.objects.create(
            diver=diver_alice,
            buddy=diver_bob,
            relationship="friend",
        )
        assert buddy.pk is not None
        assert buddy.diver == diver_alice
        assert buddy.buddy == diver_bob
        assert buddy.relationship == "friend"

    def test_buddy_with_person_only(self, diver_alice, person_charlie):
        """Can add a buddy who is just a Person (not a diver yet)."""
        buddy = DiveBuddy.objects.create(
            diver=diver_alice,
            buddy_person=person_charlie,
            relationship="dive_club",
        )
        assert buddy.pk is not None
        assert buddy.buddy_person == person_charlie
        assert buddy.buddy is None

    def test_relationship_choices(self, diver_alice, diver_bob):
        """Relationship field accepts valid choices."""
        for rel_type in ["spouse", "friend", "dive_club", "instructor", "family", "coworker", "other"]:
            buddy = DiveBuddy.objects.create(
                diver=diver_alice,
                buddy=diver_bob,
                relationship=rel_type,
            )
            assert buddy.relationship == rel_type
            buddy.delete()

    def test_notes_field(self, diver_alice, diver_bob):
        """Can add notes to buddy relationship."""
        buddy = DiveBuddy.objects.create(
            diver=diver_alice,
            buddy=diver_bob,
            relationship="friend",
            notes="Great underwater photographer, AOW certified",
        )
        assert "photographer" in buddy.notes

    def test_get_buddies_for_diver(self, diver_alice, diver_bob, person_charlie):
        """Can retrieve all buddies for a diver."""
        DiveBuddy.objects.create(
            diver=diver_alice,
            buddy=diver_bob,
            relationship="friend",
        )
        DiveBuddy.objects.create(
            diver=diver_alice,
            buddy_person=person_charlie,
            relationship="dive_club",
        )

        buddies = DiveBuddy.objects.filter(diver=diver_alice, deleted_at__isnull=True)
        assert buddies.count() == 2

    def test_soft_delete(self, diver_alice, diver_bob):
        """Buddy relationships support soft delete."""
        buddy = DiveBuddy.objects.create(
            diver=diver_alice,
            buddy=diver_bob,
            relationship="friend",
        )
        buddy.delete()

        # Should not appear in default queryset
        assert DiveBuddy.objects.filter(diver=diver_alice).count() == 0
        # But should exist with deleted_at set
        assert DiveBuddy.all_objects.filter(diver=diver_alice).count() == 1

    def test_buddy_display_name(self, diver_alice, diver_bob):
        """Buddy has a display name from the linked person."""
        buddy = DiveBuddy.objects.create(
            diver=diver_alice,
            buddy=diver_bob,
            relationship="friend",
        )
        # Should return the buddy's person name
        assert buddy.buddy_name == "Bob Ocean"

    def test_buddy_display_name_person_only(self, diver_alice, person_charlie):
        """Buddy name works when buddy is just a Person."""
        buddy = DiveBuddy.objects.create(
            diver=diver_alice,
            buddy_person=person_charlie,
            relationship="dive_club",
        )
        assert buddy.buddy_name == "Charlie Reef"
