"""Tests for diver profile selectors.

Tests the optimized queries for the staff diver detail view.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone

from django_parties.models import Organization, Person

from primitives_testbed.diveops.models import (
    Booking,
    CertificationLevel,
    DiverCertification,
    DiverProfile,
    DiverRelationship,
    DiveSite,
    EmergencyContact,
    Excursion,
    ExcursionRoster,
    ExcursionType,
)
from primitives_testbed.diveops.selectors import (
    calculate_age,
    get_diver_booking_history,
    get_diver_dive_history,
    get_diver_emergency_contacts,
    get_diver_medical_details,
    get_diver_normalized_contacts,
    get_diver_person_details,
    get_diver_relationships,
    get_diver_with_full_context,
)


@pytest.fixture
def person():
    """Create a test person."""
    return Person.objects.create(
        first_name="John",
        last_name="Diver",
        email="john@example.com",
        phone="+1-555-1234",
        date_of_birth=date(1985, 6, 15),
        preferred_name="Johnny",
        phone_is_mobile=True,
        phone_has_whatsapp=True,
        phone_can_receive_sms=True,
        address_line1="123 Ocean Drive",
        address_line2="Apt 4B",
        city="Miami",
        state="FL",
        postal_code="33139",
        country="USA",
        notes="Regular customer, prefers morning dives",
    )


@pytest.fixture
def diver(person):
    """Create a test diver profile."""
    return DiverProfile.objects.create(
        person=person,
        medical_clearance_date=date.today() - timedelta(days=90),
        medical_clearance_valid_until=date.today() + timedelta(days=275),
    )


@pytest.fixture
def dive_shop():
    """Create a test dive shop (Organization)."""
    return Organization.objects.create(
        name="Test Dive Shop",
        email="shop@example.com",
    )


@pytest.fixture
def dive_site():
    """Create a test dive site."""
    from django_geo.models import Place

    place = Place.objects.create(
        name="Blue Hole",
        latitude=Decimal("21.5"),
        longitude=Decimal("-86.5"),
    )
    return DiveSite.objects.create(
        name="Blue Hole",
        place=place,
        max_depth_meters=40,
    )


@pytest.fixture
def excursion_type():
    """Create a test excursion type."""
    return ExcursionType.objects.create(
        name="Two Tank Dive",
        slug="two-tank-dive",
        dive_mode=ExcursionType.DiveMode.BOAT,
        base_price=Decimal("150.00"),
    )


@pytest.fixture
def staff_user():
    """Create a staff user for created_by fields."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="teststaff",
        email="staff@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestCalculateAge:
    """Tests for calculate_age function."""

    def test_calculate_age_returns_correct_age(self):
        """Test age calculation for a past date."""
        dob = date(1985, 6, 15)
        age = calculate_age(dob)
        today = date.today()
        expected = today.year - 1985
        if (today.month, today.day) < (6, 15):
            expected -= 1
        assert age == expected

    def test_calculate_age_with_none(self):
        """Test that None returns None."""
        assert calculate_age(None) is None

    def test_calculate_age_birthday_today(self):
        """Test age calculation when birthday is today."""
        today = date.today()
        dob = date(today.year - 30, today.month, today.day)
        assert calculate_age(dob) == 30

    def test_calculate_age_birthday_tomorrow(self):
        """Test age calculation when birthday is tomorrow."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        dob = date(tomorrow.year - 30, tomorrow.month, tomorrow.day)
        assert calculate_age(dob) == 29


@pytest.mark.django_db
class TestGetDiverPersonDetails:
    """Tests for get_diver_person_details selector."""

    def test_returns_person_details_dataclass(self, person):
        """Test that selector returns PersonDetails dataclass."""
        details = get_diver_person_details(person)
        assert details.date_of_birth == date(1985, 6, 15)
        assert details.preferred_name == "Johnny"
        assert details.phone_is_mobile is True
        assert details.phone_has_whatsapp is True
        assert details.phone_can_receive_sms is True

    def test_returns_address_fields(self, person):
        """Test that address fields are populated."""
        details = get_diver_person_details(person)
        assert details.address_line1 == "123 Ocean Drive"
        assert details.address_line2 == "Apt 4B"
        assert details.city == "Miami"
        assert details.state == "FL"
        assert details.postal_code == "33139"
        assert details.country == "USA"
        assert details.has_address is True

    def test_has_address_false_when_no_address(self):
        """Test has_address is False when no address."""
        person = Person.objects.create(
            first_name="No",
            last_name="Address",
            email="no@address.com",
        )
        details = get_diver_person_details(person)
        assert details.has_address is False

    def test_age_calculation(self, person):
        """Test that age is calculated correctly."""
        details = get_diver_person_details(person)
        assert details.age is not None
        assert details.age > 0


@pytest.mark.django_db
class TestGetDiverMedicalDetails:
    """Tests for get_diver_medical_details selector."""

    def test_returns_medical_details_dataclass(self, diver):
        """Test that selector returns MedicalDetails dataclass."""
        details = get_diver_medical_details(diver)
        assert details.clearance_date == diver.medical_clearance_date
        assert details.valid_until == diver.medical_clearance_valid_until
        assert details.is_expired is False
        assert details.days_remaining is not None
        assert details.days_remaining > 0

    def test_expired_medical_clearance(self, diver):
        """Test detection of expired medical clearance."""
        diver.medical_clearance_valid_until = date.today() - timedelta(days=1)
        diver.save()
        details = get_diver_medical_details(diver)
        assert details.is_expired is True
        assert details.days_remaining is None

    def test_no_medical_clearance(self, person):
        """Test diver with no medical clearance."""
        diver = DiverProfile.objects.create(person=person)
        details = get_diver_medical_details(diver)
        assert details.clearance_date is None
        assert details.is_expired is False

    def test_clearance_date_without_valid_until(self, person):
        """Test that valid_until defaults to 1 year from clearance."""
        diver = DiverProfile.objects.create(
            person=person,
            medical_clearance_date=date.today() - timedelta(days=30),
        )
        details = get_diver_medical_details(diver)
        expected_valid_until = diver.medical_clearance_date + timedelta(days=365)
        assert details.valid_until == expected_valid_until


@pytest.mark.django_db
class TestGetDiverEmergencyContacts:
    """Tests for get_diver_emergency_contacts selector."""

    def test_returns_emergency_contacts(self, diver):
        """Test that emergency contacts are returned."""
        contact_person = Person.objects.create(
            first_name="Jane",
            last_name="Contact",
            email="jane@example.com",
            phone="+1-555-5678",
        )
        EmergencyContact.objects.create(
            diver=diver,
            contact_person=contact_person,
            relationship="spouse",
            priority=1,
        )
        contacts = get_diver_emergency_contacts(diver)
        assert len(contacts) == 1
        assert contacts[0].contact_person == contact_person
        assert contacts[0].relationship == "spouse"
        assert contacts[0].priority == 1

    def test_contacts_ordered_by_priority(self, diver):
        """Test that contacts are ordered by priority."""
        person1 = Person.objects.create(
            first_name="First",
            last_name="Contact",
            email="first@example.com",
        )
        person2 = Person.objects.create(
            first_name="Second",
            last_name="Contact",
            email="second@example.com",
        )
        EmergencyContact.objects.create(
            diver=diver,
            contact_person=person1,
            relationship="friend",
            priority=2,
        )
        EmergencyContact.objects.create(
            diver=diver,
            contact_person=person2,
            relationship="spouse",
            priority=1,
        )
        contacts = get_diver_emergency_contacts(diver)
        assert len(contacts) == 2
        assert contacts[0].priority == 1
        assert contacts[1].priority == 2

    def test_excludes_soft_deleted_contacts(self, diver):
        """Test that soft-deleted contacts are excluded."""
        contact_person = Person.objects.create(
            first_name="Deleted",
            last_name="Contact",
            email="deleted@example.com",
        )
        contact = EmergencyContact.objects.create(
            diver=diver,
            contact_person=contact_person,
            relationship="friend",
            priority=1,
        )
        contact.deleted_at = timezone.now()
        contact.save()
        contacts = get_diver_emergency_contacts(diver)
        assert len(contacts) == 0


@pytest.mark.django_db
class TestGetDiverRelationships:
    """Tests for get_diver_relationships selector."""

    def test_returns_relationships(self, diver):
        """Test that diver relationships are returned."""
        other_person = Person.objects.create(
            first_name="Buddy",
            last_name="Diver",
            email="buddy@example.com",
        )
        other_diver = DiverProfile.objects.create(person=other_person)
        DiverRelationship.objects.create(
            from_diver=diver,
            to_diver=other_diver,
            relationship_type="buddy",
            is_preferred_buddy=True,
        )
        relationships = get_diver_relationships(diver)
        assert len(relationships) == 1
        rel = relationships[0]
        assert rel["other_person"] == other_person
        assert rel["relationship_type"] == "buddy"
        assert rel["is_preferred_buddy"] is True

    def test_returns_bidirectional_relationships(self, diver):
        """Test that relationships from both directions are returned."""
        other_person = Person.objects.create(
            first_name="Other",
            last_name="Diver",
            email="other@example.com",
        )
        other_diver = DiverProfile.objects.create(person=other_person)
        DiverRelationship.objects.create(
            from_diver=other_diver,
            to_diver=diver,
            relationship_type="spouse",
        )
        relationships = get_diver_relationships(diver)
        assert len(relationships) == 1
        assert relationships[0]["other_person"] == other_person


@pytest.mark.django_db
class TestGetDiverBookingHistory:
    """Tests for get_diver_booking_history selector.

    Note: Full integration tests for booking history require complex fixtures
    (Booking requires booked_by, price, etc.). These tests verify basic
    query functionality. Full integration testing is done in view tests.
    """

    def test_returns_empty_for_diver_with_no_bookings(self, diver):
        """Test that empty list is returned for diver with no bookings."""
        bookings = get_diver_booking_history(diver)
        assert len(bookings) == 0


@pytest.mark.django_db
class TestGetDiverDiveHistory:
    """Tests for get_diver_dive_history selector.

    Note: Full integration tests for dive history require complex fixtures
    (ExcursionRoster requires booking, etc.). These tests verify basic
    query functionality. Full integration testing is done in view tests.
    """

    def test_returns_empty_for_diver_with_no_dives(self, diver):
        """Test that empty list is returned for diver with no dives."""
        history = get_diver_dive_history(diver)
        assert len(history) == 0


@pytest.mark.django_db
class TestGetDiverWithFullContext:
    """Tests for get_diver_with_full_context selector."""

    def test_returns_none_for_invalid_id(self):
        """Test that None is returned for non-existent diver."""
        result = get_diver_with_full_context(uuid4())
        assert result is None

    def test_returns_full_context(self, diver):
        """Test that full context dict is returned."""
        result = get_diver_with_full_context(diver.pk)
        assert result is not None
        assert result["diver"] == diver
        assert result["person"] == diver.person
        assert "person_details" in result
        assert "normalized_contacts" in result
        assert "emergency_contacts" in result
        assert "relationships" in result
        assert "booking_history" in result
        assert "dive_history" in result
        assert "medical_details" in result

    def test_excludes_soft_deleted_diver(self, diver):
        """Test that soft-deleted divers return None."""
        diver.deleted_at = timezone.now()
        diver.save()
        result = get_diver_with_full_context(diver.pk)
        assert result is None
