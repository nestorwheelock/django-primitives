"""Tests for PartyRelationship-based forms.

Tests the EmergencyContactForm and DiverRelationshipForm that create
PartyRelationship + DiverRelationshipMeta instead of legacy models.
"""

import pytest
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from django_parties.models import PartyRelationship, Person

from primitives_testbed.diveops.forms import DiverRelationshipForm, EmergencyContactForm
from primitives_testbed.diveops.models import DiverProfile, DiverRelationshipMeta


@pytest.fixture
def person():
    """Create a test person."""
    return Person.objects.create(
        first_name="John",
        last_name="Diver",
        email="john@example.com",
    )


@pytest.fixture
def diver(person):
    """Create a test diver profile."""
    return DiverProfile.objects.create(person=person)


@pytest.fixture
def other_person():
    """Create another person for relationships."""
    return Person.objects.create(
        first_name="Jane",
        last_name="Contact",
        email="jane@example.com",
        phone="+1-555-1234",
    )


@pytest.fixture
def other_diver(other_person):
    """Create another diver for buddy relationships."""
    return DiverProfile.objects.create(person=other_person)


@pytest.fixture
def staff_user():
    """Create a staff user."""
    User = get_user_model()
    return User.objects.create_user(
        username="teststaff",
        email="staff@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestEmergencyContactFormValidation:
    """Tests for EmergencyContactForm validation."""

    def test_requires_either_existing_or_new_name(self, diver):
        """Must select existing person OR provide first/last name."""
        form = EmergencyContactForm(
            data={
                "relationship": "spouse",
                "priority": 1,
            },
            diver=diver,
        )
        assert not form.is_valid()
        assert "Select an existing contact or enter first and last name" in str(
            form.errors
        )

    def test_rejects_both_existing_and_new_name(self, diver, other_person):
        """Cannot select existing AND provide new name."""
        form = EmergencyContactForm(
            data={
                "existing_person": other_person.pk,
                "first_name": "New",
                "last_name": "Person",
                "relationship": "spouse",
                "priority": 1,
            },
            diver=diver,
        )
        assert not form.is_valid()
        assert "Select an existing contact OR enter a new name" in str(form.errors)

    def test_accepts_existing_person_only(self, diver, other_person):
        """Valid when selecting existing person."""
        form = EmergencyContactForm(
            data={
                "existing_person": other_person.pk,
                "relationship": "spouse",
                "priority": 1,
            },
            diver=diver,
        )
        assert form.is_valid(), form.errors

    def test_accepts_new_name_only(self, diver):
        """Valid when providing new name."""
        form = EmergencyContactForm(
            data={
                "first_name": "New",
                "last_name": "Person",
                "phone": "+1-555-9999",
                "relationship": "friend",
                "priority": 1,
            },
            diver=diver,
        )
        assert form.is_valid(), form.errors

    def test_requires_last_name_with_first_name(self, diver):
        """Must provide both first and last name for new contacts."""
        form = EmergencyContactForm(
            data={
                "first_name": "Only",
                "relationship": "friend",
                "priority": 1,
            },
            diver=diver,
        )
        assert not form.is_valid()

    def test_excludes_diver_from_queryset(self, diver):
        """Diver cannot be their own emergency contact."""
        form = EmergencyContactForm(diver=diver)
        queryset = form.fields["existing_person"].queryset
        assert diver.person not in queryset


@pytest.mark.django_db
class TestEmergencyContactFormSave:
    """Tests for EmergencyContactForm.save()."""

    def test_creates_party_relationship_for_existing_person(
        self, diver, other_person, staff_user
    ):
        """Creates PartyRelationship when using existing person."""
        form = EmergencyContactForm(
            data={
                "existing_person": other_person.pk,
                "relationship": "spouse",
                "priority": 1,
                "notes": "Primary contact",
            },
            diver=diver,
        )
        assert form.is_valid(), form.errors
        result = form.save(actor=staff_user)

        assert isinstance(result, PartyRelationship)
        assert result.from_person == diver.person
        assert result.to_person == other_person
        assert result.relationship_type == "emergency_contact"
        assert result.title == "spouse"
        assert result.is_primary is True

    def test_creates_person_for_new_contact(self, diver, staff_user):
        """Creates new Person when providing name fields."""
        form = EmergencyContactForm(
            data={
                "first_name": "New",
                "last_name": "Contact",
                "phone": "+1-555-9999",
                "email": "new@example.com",
                "relationship": "friend",
                "priority": 2,
            },
            diver=diver,
        )
        assert form.is_valid(), form.errors
        result = form.save(actor=staff_user)

        # Should create the PartyRelationship
        assert isinstance(result, PartyRelationship)

        # Should create the Person
        contact = result.to_person
        assert contact.first_name == "New"
        assert contact.last_name == "Contact"
        assert contact.phone == "+1-555-9999"
        assert contact.email == "new@example.com"

    def test_creates_diver_relationship_meta(self, diver, other_person, staff_user):
        """Creates DiverRelationshipMeta with priority and notes."""
        form = EmergencyContactForm(
            data={
                "existing_person": other_person.pk,
                "relationship": "parent",
                "priority": 2,
                "notes": "Available after 6pm",
            },
            diver=diver,
        )
        assert form.is_valid(), form.errors
        result = form.save(actor=staff_user)

        # Check DiverRelationshipMeta was created
        meta = DiverRelationshipMeta.objects.get(party_relationship=result)
        assert meta.priority == 2
        assert meta.notes == "Available after 6pm"


@pytest.mark.django_db
class TestDiverRelationshipFormValidation:
    """Tests for DiverRelationshipForm validation."""

    def test_prevents_self_relationship(self, diver):
        """Cannot create relationship with yourself."""
        form = DiverRelationshipForm(
            data={
                "related_person": str(diver.person.pk),
                "relationship_type": "buddy",
            },
            from_diver=diver,
        )
        # Queryset should exclude self
        assert diver.person not in form.fields["related_person"].queryset

    def test_prevents_duplicate_relationship(self, diver, other_person, staff_user):
        """Cannot create duplicate relationship of same type."""
        # Create first relationship
        PartyRelationship.objects.create(
            from_person=diver.person,
            to_person=other_person,
            relationship_type="buddy",
            is_active=True,
        )

        # Try to create duplicate
        form = DiverRelationshipForm(
            data={
                "related_person": other_person.pk,
                "relationship_type": "buddy",
            },
            from_diver=diver,
        )
        assert not form.is_valid()
        assert "already exists" in str(form.errors)

    def test_allows_different_relationship_type(self, diver, other_person, staff_user):
        """Can create relationship of different type with same person."""
        # Create buddy relationship
        PartyRelationship.objects.create(
            from_person=diver.person,
            to_person=other_person,
            relationship_type="buddy",
            is_active=True,
        )

        # Create spouse relationship (different type)
        form = DiverRelationshipForm(
            data={
                "related_person": other_person.pk,
                "relationship_type": "spouse",
            },
            from_diver=diver,
        )
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestDiverRelationshipFormSave:
    """Tests for DiverRelationshipForm.save()."""

    def test_creates_party_relationship(self, diver, other_person, staff_user):
        """Creates PartyRelationship with correct data."""
        form = DiverRelationshipForm(
            data={
                "related_person": other_person.pk,
                "relationship_type": "buddy",
                "is_preferred_buddy": True,
                "notes": "Same certification level",
            },
            from_diver=diver,
        )
        assert form.is_valid(), form.errors
        result = form.save(actor=staff_user)

        assert isinstance(result, PartyRelationship)
        assert result.from_person == diver.person
        assert result.to_person == other_person
        assert result.relationship_type == "buddy"
        assert result.is_primary is True  # is_preferred_buddy = True

    def test_creates_diver_relationship_meta(self, diver, other_person, staff_user):
        """Creates DiverRelationshipMeta with dive-specific fields."""
        form = DiverRelationshipForm(
            data={
                "related_person": other_person.pk,
                "relationship_type": "buddy",
                "is_preferred_buddy": True,
                "notes": "Both advanced open water",
            },
            from_diver=diver,
        )
        assert form.is_valid(), form.errors
        result = form.save(actor=staff_user)

        meta = DiverRelationshipMeta.objects.get(party_relationship=result)
        assert meta.is_preferred_buddy is True
        assert meta.notes == "Both advanced open water"
