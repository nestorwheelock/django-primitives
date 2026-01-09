"""Tests for Buddy models: Contact, BuddyIdentity, DiveTeam, DiveTeamMember.

TDD: Tests written FIRST, models don't exist yet.
"""

import pytest
from django.db import IntegrityError
from django.db.utils import IntegrityError as DBIntegrityError
from django_parties.models import Person


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


# =============================================================================
# Contact Model Tests
# =============================================================================

@pytest.mark.django_db
class TestContactModel:
    """Tests for Contact model."""

    def test_contact_creation_with_email(self, person_alice):
        """Can create contact with email only."""
        from primitives_testbed.diveops.models import Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Charlie Reef",
            email="charlie@example.com",
        )
        assert contact.pk is not None
        assert contact.display_name == "Charlie Reef"
        assert contact.email == "charlie@example.com"
        assert contact.phone is None

    def test_contact_creation_with_phone(self, person_alice):
        """Can create contact with phone only."""
        from primitives_testbed.diveops.models import Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Dana Deep",
            phone="+1234567890",
        )
        assert contact.pk is not None
        assert contact.phone == "+1234567890"
        assert contact.email is None

    def test_contact_creation_with_both(self, person_alice):
        """Can create contact with both email and phone."""
        from primitives_testbed.diveops.models import Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Eve Explorer",
            email="eve@example.com",
            phone="+1234567890",
        )
        assert contact.email == "eve@example.com"
        assert contact.phone == "+1234567890"

    def test_contact_requires_email_or_phone(self, person_alice):
        """Contact without email AND phone should fail constraint."""
        from primitives_testbed.diveops.models import Contact

        with pytest.raises((IntegrityError, DBIntegrityError)):
            Contact.objects.create(
                created_by=person_alice,
                display_name="No Contact Info",
                email=None,
                phone=None,
            )

    def test_contact_status_default_new(self, person_alice):
        """Contact status defaults to 'new'."""
        from primitives_testbed.diveops.models import Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Frank Fisher",
            email="frank@example.com",
        )
        assert contact.status == "new"

    def test_contact_status_choices(self, person_alice):
        """Contact status can be set to valid choices."""
        from primitives_testbed.diveops.models import Contact

        for status in ["new", "invited", "accepted", "bounced", "opted_out"]:
            contact = Contact.objects.create(
                created_by=person_alice,
                display_name=f"Contact {status}",
                email=f"{status}@example.com",
                status=status,
            )
            assert contact.status == status

    def test_contact_linked_person_nullable(self, person_alice, person_bob):
        """Contact can have linked_person set later."""
        from primitives_testbed.diveops.models import Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Bob Ocean",
            email="bob@example.com",
        )
        assert contact.linked_person is None

        # Link to existing person
        contact.linked_person = person_bob
        contact.save()
        contact.refresh_from_db()
        assert contact.linked_person == person_bob

    def test_contact_soft_delete(self, person_alice):
        """Contact supports soft delete."""
        from primitives_testbed.diveops.models import Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Gary Gill",
            email="gary@example.com",
        )
        contact.delete()

        # Should not appear in default queryset
        assert Contact.objects.filter(pk=contact.pk).count() == 0
        # But should exist with deleted_at set
        assert Contact.all_objects.filter(pk=contact.pk).count() == 1


# =============================================================================
# BuddyIdentity Model Tests
# =============================================================================

@pytest.mark.django_db
class TestBuddyIdentityModel:
    """Tests for BuddyIdentity model."""

    def test_identity_with_person(self, person_alice):
        """Can create identity for a Person."""
        from primitives_testbed.diveops.models import BuddyIdentity

        identity = BuddyIdentity.objects.create(person=person_alice)
        assert identity.pk is not None
        assert identity.person == person_alice
        assert identity.contact is None

    def test_identity_with_contact(self, person_alice):
        """Can create identity for a Contact."""
        from primitives_testbed.diveops.models import BuddyIdentity, Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Henry Harbor",
            email="henry@example.com",
        )
        identity = BuddyIdentity.objects.create(contact=contact)
        assert identity.pk is not None
        assert identity.contact == contact
        assert identity.person is None

    def test_identity_requires_exactly_one(self, person_alice):
        """Identity must have exactly one of person or contact."""
        from primitives_testbed.diveops.models import BuddyIdentity, Contact

        # Neither set should fail
        with pytest.raises((IntegrityError, DBIntegrityError)):
            BuddyIdentity.objects.create(person=None, contact=None)

    def test_identity_cannot_have_both(self, person_alice, person_bob):
        """Identity cannot have both person AND contact."""
        from primitives_testbed.diveops.models import BuddyIdentity, Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Ivan Ice",
            email="ivan@example.com",
        )
        with pytest.raises((IntegrityError, DBIntegrityError)):
            BuddyIdentity.objects.create(person=person_bob, contact=contact)

    def test_identity_display_name_from_person(self, person_alice):
        """Identity display_name comes from Person."""
        from primitives_testbed.diveops.models import BuddyIdentity

        identity = BuddyIdentity.objects.create(person=person_alice)
        assert identity.display_name == "Alice Diver"

    def test_identity_display_name_from_contact(self, person_alice):
        """Identity display_name comes from Contact."""
        from primitives_testbed.diveops.models import BuddyIdentity, Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Jackie Jellyfish",
            email="jackie@example.com",
        )
        identity = BuddyIdentity.objects.create(contact=contact)
        assert identity.display_name == "Jackie Jellyfish"

    def test_identity_is_registered_true_for_person(self, person_alice):
        """is_registered is True for Person-based identity."""
        from primitives_testbed.diveops.models import BuddyIdentity

        identity = BuddyIdentity.objects.create(person=person_alice)
        assert identity.is_registered is True

    def test_identity_is_registered_false_for_contact(self, person_alice):
        """is_registered is False for Contact without linked_person."""
        from primitives_testbed.diveops.models import BuddyIdentity, Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Kyle Kelp",
            email="kyle@example.com",
        )
        identity = BuddyIdentity.objects.create(contact=contact)
        assert identity.is_registered is False

    def test_identity_is_registered_true_for_linked_contact(self, person_alice, person_bob):
        """is_registered is True for Contact with linked_person."""
        from primitives_testbed.diveops.models import BuddyIdentity, Contact

        contact = Contact.objects.create(
            created_by=person_alice,
            display_name="Bob Ocean",
            email="bob@example.com",
            linked_person=person_bob,
        )
        identity = BuddyIdentity.objects.create(contact=contact)
        assert identity.is_registered is True

    def test_identity_person_unique(self, person_alice):
        """Cannot create multiple identities for same Person."""
        from primitives_testbed.diveops.models import BuddyIdentity

        BuddyIdentity.objects.create(person=person_alice)
        with pytest.raises((IntegrityError, DBIntegrityError)):
            BuddyIdentity.objects.create(person=person_alice)


# =============================================================================
# DiveTeam Model Tests
# =============================================================================

@pytest.mark.django_db
class TestDiveTeamModel:
    """Tests for DiveTeam model."""

    def test_dive_team_creation(self, person_alice):
        """Can create a DiveTeam."""
        from primitives_testbed.diveops.models import DiveTeam

        team = DiveTeam.objects.create(created_by=person_alice)
        assert team.pk is not None

    def test_dive_team_type_default_buddy(self, person_alice):
        """DiveTeam defaults to 'buddy' type."""
        from primitives_testbed.diveops.models import DiveTeam

        team = DiveTeam.objects.create(created_by=person_alice)
        assert team.team_type == "buddy"

    def test_dive_team_name_optional(self, person_alice):
        """DiveTeam name is optional (blank for pairs)."""
        from primitives_testbed.diveops.models import DiveTeam

        team = DiveTeam.objects.create(created_by=person_alice)
        assert team.name == ""

        team_with_name = DiveTeam.objects.create(
            created_by=person_alice,
            name="Weekend Warriors",
        )
        assert team_with_name.name == "Weekend Warriors"

    def test_dive_team_is_active_default(self, person_alice):
        """DiveTeam is_active defaults to True."""
        from primitives_testbed.diveops.models import DiveTeam

        team = DiveTeam.objects.create(created_by=person_alice)
        assert team.is_active is True

    def test_dive_team_soft_delete(self, person_alice):
        """DiveTeam supports soft delete."""
        from primitives_testbed.diveops.models import DiveTeam

        team = DiveTeam.objects.create(created_by=person_alice)
        team.delete()

        assert DiveTeam.objects.filter(pk=team.pk).count() == 0
        assert DiveTeam.all_objects.filter(pk=team.pk).count() == 1


# =============================================================================
# DiveTeamMember Model Tests
# =============================================================================

@pytest.mark.django_db
class TestDiveTeamMemberModel:
    """Tests for DiveTeamMember model."""

    def test_team_member_creation(self, person_alice, person_bob):
        """Can create a DiveTeamMember."""
        from primitives_testbed.diveops.models import BuddyIdentity, DiveTeam, DiveTeamMember

        team = DiveTeam.objects.create(created_by=person_alice)
        identity = BuddyIdentity.objects.create(person=person_alice)

        member = DiveTeamMember.objects.create(team=team, identity=identity)
        assert member.pk is not None
        assert member.team == team
        assert member.identity == identity

    def test_unique_team_member_constraint(self, person_alice):
        """Cannot add same identity to team twice."""
        from primitives_testbed.diveops.models import BuddyIdentity, DiveTeam, DiveTeamMember

        team = DiveTeam.objects.create(created_by=person_alice)
        identity = BuddyIdentity.objects.create(person=person_alice)

        DiveTeamMember.objects.create(team=team, identity=identity)
        with pytest.raises((IntegrityError, DBIntegrityError)):
            DiveTeamMember.objects.create(team=team, identity=identity)

    def test_team_member_notes_optional(self, person_alice):
        """DiveTeamMember notes is optional."""
        from primitives_testbed.diveops.models import BuddyIdentity, DiveTeam, DiveTeamMember

        team = DiveTeam.objects.create(created_by=person_alice)
        identity = BuddyIdentity.objects.create(person=person_alice)

        member = DiveTeamMember.objects.create(team=team, identity=identity)
        assert member.notes == ""

        member.notes = "Great dive buddy, AOW certified"
        member.save()
        member.refresh_from_db()
        assert "AOW certified" in member.notes

    def test_team_member_role_optional(self, person_alice):
        """DiveTeamMember role is optional."""
        from primitives_testbed.diveops.models import BuddyIdentity, DiveTeam, DiveTeamMember

        team = DiveTeam.objects.create(created_by=person_alice)
        identity = BuddyIdentity.objects.create(person=person_alice)

        member = DiveTeamMember.objects.create(team=team, identity=identity)
        assert member.role == ""
