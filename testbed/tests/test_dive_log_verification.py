"""Tests for DiveLog verification service.

Tests verify_dive_log() and update_dive_log() services.
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from primitives_testbed.diveops.models import (
    Dive,
    DiveAssignment,
    DiveLog,
    DiverProfile,
    DiveSite,
    Excursion,
)
from primitives_testbed.diveops.services import verify_dive_log, update_dive_log
from primitives_testbed.diveops.audit import Actions

from django_audit_log.models import AuditLog
from django_parties.models import Organization, Person
from django_geo.models import Place


User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for verification."""
    return User.objects.create_user(
        username="instructor@diveshop.com",
        email="instructor@diveshop.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def dive_shop(db):
    """Create a dive shop (Organization)."""
    return Organization.objects.create(
        name="Test Dive Shop",
    )


@pytest.fixture
def place(db):
    """Create a place for dive site."""
    return Place.objects.create(
        name="Reef Location",
        latitude=Decimal("17.5"),
        longitude=Decimal("-87.5"),
    )


@pytest.fixture
def dive_site(db, place):
    """Create a dive site."""
    return DiveSite.objects.create(
        name="Training Reef",
        place=place,
        max_depth_meters=18,
        difficulty="beginner",
    )


@pytest.fixture
def excursion(db, dive_shop, dive_site, staff_user):
    """Create an excursion."""
    departure = timezone.now() + timedelta(hours=1)
    return Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        departure_time=departure,
        return_time=departure + timedelta(hours=4),
        max_divers=6,
        price_per_diver=Decimal("90.00"),
        status="scheduled",
        created_by=staff_user,
    )


@pytest.fixture
def dive(db, excursion, dive_site):
    """Create a dive with logged results."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=1,
        planned_start=excursion.departure_time + timedelta(minutes=30),
        actual_start=excursion.departure_time + timedelta(minutes=35),
        actual_end=excursion.departure_time + timedelta(minutes=75),
        max_depth_meters=15,
        bottom_time_minutes=40,
    )


@pytest.fixture
def person(db):
    """Create a person."""
    return Person.objects.create(
        first_name="Student",
        last_name="Diver",
        email="student@example.com",
    )


@pytest.fixture
def diver(db, person):
    """Create a diver profile."""
    return DiverProfile.objects.create(
        person=person,
        certification_level="ow",
        total_dives=4,
    )


@pytest.fixture
def assignment(db, dive, diver):
    """Create a dive assignment."""
    return DiveAssignment.objects.create(
        dive=dive,
        diver=diver,
        role="student",
        status="on_boat",
    )


@pytest.fixture
def dive_log(db, dive, diver, assignment):
    """Create an unverified dive log."""
    return DiveLog.objects.create(
        dive=dive,
        diver=diver,
        assignment=assignment,
        dive_number=5,
    )


@pytest.mark.django_db
class TestVerifyDiveLog:
    """Tests for verify_dive_log service."""

    def test_sets_verified_by(self, dive_log, staff_user):
        """verify_dive_log sets verified_by to the actor."""
        assert dive_log.verified_by is None

        verify_dive_log(actor=staff_user, dive_log=dive_log)

        dive_log.refresh_from_db()
        assert dive_log.verified_by == staff_user

    def test_sets_verified_at(self, dive_log, staff_user):
        """verify_dive_log sets verified_at timestamp."""
        assert dive_log.verified_at is None

        before = timezone.now()
        verify_dive_log(actor=staff_user, dive_log=dive_log)

        dive_log.refresh_from_db()
        assert dive_log.verified_at is not None
        assert dive_log.verified_at >= before

    def test_is_verified_property_after_verification(self, dive_log, staff_user):
        """is_verified property returns True after verification."""
        assert dive_log.is_verified is False

        verify_dive_log(actor=staff_user, dive_log=dive_log)

        dive_log.refresh_from_db()
        assert dive_log.is_verified is True

    def test_emits_dive_log_verified_audit_event(self, dive_log, staff_user):
        """verify_dive_log emits DIVE_LOG_VERIFIED audit event."""
        verify_dive_log(actor=staff_user, dive_log=dive_log)

        audit = AuditLog.objects.filter(action=Actions.DIVE_LOG_VERIFIED).first()
        assert audit is not None
        assert audit.actor_user == staff_user

    def test_idempotent_verification(self, dive_log, staff_user):
        """Verifying twice updates the verifier but doesn't error."""
        verify_dive_log(actor=staff_user, dive_log=dive_log)
        first_verified_at = dive_log.verified_at

        # Verify again with different user
        staff_user2 = User.objects.create_user(
            username="instructor2@diveshop.com",
            email="instructor2@diveshop.com",
            password="testpass123",
            is_staff=True,
        )
        verify_dive_log(actor=staff_user2, dive_log=dive_log)

        dive_log.refresh_from_db()
        # Second verification overwrites
        assert dive_log.verified_by == staff_user2


@pytest.mark.django_db
class TestUpdateDiveLog:
    """Tests for update_dive_log service."""

    def test_updates_personal_depth(self, dive_log, staff_user):
        """update_dive_log can update max_depth_meters."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            max_depth_meters=Decimal("12.5"),
        )

        dive_log.refresh_from_db()
        assert dive_log.max_depth_meters == Decimal("12.5")

    def test_updates_personal_bottom_time(self, dive_log, staff_user):
        """update_dive_log can update bottom_time_minutes."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            bottom_time_minutes=35,
        )

        dive_log.refresh_from_db()
        assert dive_log.bottom_time_minutes == 35

    def test_updates_air_consumption(self, dive_log, staff_user):
        """update_dive_log can update air start/end."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            air_start_bar=200,
            air_end_bar=60,
        )

        dive_log.refresh_from_db()
        assert dive_log.air_start_bar == 200
        assert dive_log.air_end_bar == 60

    def test_updates_equipment(self, dive_log, staff_user):
        """update_dive_log can update equipment fields."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            weight_kg=Decimal("8.0"),
            suit_type="5mm",
            tank_size_liters=12,
            nitrox_percentage=32,
        )

        dive_log.refresh_from_db()
        assert dive_log.weight_kg == Decimal("8.0")
        assert dive_log.suit_type == "5mm"
        assert dive_log.tank_size_liters == 12
        assert dive_log.nitrox_percentage == 32

    def test_updates_notes(self, dive_log, staff_user):
        """update_dive_log can update notes."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            notes="Saw a turtle! Great vis today.",
        )

        dive_log.refresh_from_db()
        assert dive_log.notes == "Saw a turtle! Great vis today."

    def test_updates_buddy_name(self, dive_log, staff_user):
        """update_dive_log can update buddy_name."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            buddy_name="John from California",
        )

        dive_log.refresh_from_db()
        assert dive_log.buddy_name == "John from California"

    def test_emits_dive_log_updated_audit_event(self, dive_log, staff_user):
        """update_dive_log emits DIVE_LOG_UPDATED audit event."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            notes="Updated notes",
        )

        audit = AuditLog.objects.filter(action=Actions.DIVE_LOG_UPDATED).first()
        assert audit is not None
        assert audit.actor_user == staff_user

    def test_audit_event_contains_changes(self, dive_log, staff_user):
        """Audit event contains tracked changes."""
        dive_log.notes = "Original notes"
        dive_log.save()

        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            notes="New notes",
        )

        audit = AuditLog.objects.filter(action=Actions.DIVE_LOG_UPDATED).first()
        assert audit is not None
        assert "notes" in audit.changes
        assert audit.changes["notes"]["old"] == "Original notes"
        assert audit.changes["notes"]["new"] == "New notes"

    def test_no_audit_when_no_changes(self, dive_log, staff_user):
        """No audit event when values don't actually change."""
        dive_log.notes = "Same notes"
        dive_log.save()

        # Try to update with same value
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            notes="Same notes",
        )

        # No audit event should be created
        audit_count = AuditLog.objects.filter(action=Actions.DIVE_LOG_UPDATED).count()
        assert audit_count == 0

    def test_multiple_fields_update(self, dive_log, staff_user):
        """update_dive_log can update multiple fields at once."""
        update_dive_log(
            actor=staff_user,
            dive_log=dive_log,
            max_depth_meters=Decimal("14.0"),
            bottom_time_minutes=38,
            air_start_bar=200,
            air_end_bar=70,
            notes="Great dive",
        )

        dive_log.refresh_from_db()
        assert dive_log.max_depth_meters == Decimal("14.0")
        assert dive_log.bottom_time_minutes == 38
        assert dive_log.air_start_bar == 200
        assert dive_log.air_end_bar == 70
        assert dive_log.notes == "Great dive"
