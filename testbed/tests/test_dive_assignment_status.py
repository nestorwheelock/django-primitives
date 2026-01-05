"""Tests for dive assignment status transitions.

Tests update_diver_status() service which:
- Updates DiveAssignment.status
- Sets timestamps on transitions (entered_water_at, surfaced_at)
- Emits DIVER_STATUS_CHANGED audit event
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from primitives_testbed.diveops.models import (
    Dive,
    DiveAssignment,
    DiverProfile,
    DiveSite,
    Excursion,
)
from primitives_testbed.diveops.services import update_diver_status
from primitives_testbed.diveops.audit import Actions

from django_audit_log.models import AuditLog
from django_parties.models import Organization, Person
from django_geo.models import Place


User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="dm@diveshop.com",
        email="dm@diveshop.com",
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
        name="Coral Garden",
        place=place,
        max_depth_meters=25,
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
        max_divers=8,
        price_per_diver=Decimal("80.00"),
        status="scheduled",
        created_by=staff_user,
    )


@pytest.fixture
def dive(db, excursion, dive_site):
    """Create a dive."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=1,
        planned_start=excursion.departure_time + timedelta(minutes=30),
    )


@pytest.fixture
def person(db):
    """Create a person."""
    return Person.objects.create(
        first_name="Test",
        last_name="Diver",
        email="test@example.com",
    )


@pytest.fixture
def diver(db, person):
    """Create a diver profile."""
    return DiverProfile.objects.create(
        person=person,
        certification_level="ow",
        total_dives=10,
    )


@pytest.fixture
def assignment(db, dive, diver):
    """Create a dive assignment."""
    return DiveAssignment.objects.create(
        dive=dive,
        diver=diver,
        role="diver",
        status="assigned",
    )


@pytest.mark.django_db
class TestUpdateDiverStatus:
    """Tests for update_diver_status service."""

    def test_updates_status(self, assignment, staff_user):
        """update_diver_status changes assignment status."""
        assert assignment.status == "assigned"

        updated = update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="briefed",
        )

        assignment.refresh_from_db()
        assert assignment.status == "briefed"
        assert updated.status == "briefed"

    def test_sets_entered_water_at_on_in_water(self, assignment, staff_user):
        """Transition to in_water sets entered_water_at timestamp."""
        assert assignment.entered_water_at is None

        before = timezone.now()
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="in_water",
        )

        assignment.refresh_from_db()
        assert assignment.entered_water_at is not None
        assert assignment.entered_water_at >= before

    def test_sets_surfaced_at_on_surfaced(self, assignment, staff_user):
        """Transition to surfaced sets surfaced_at timestamp."""
        # First go in water
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="in_water",
        )

        assert assignment.surfaced_at is None

        before = timezone.now()
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="surfaced",
        )

        assignment.refresh_from_db()
        assert assignment.surfaced_at is not None
        assert assignment.surfaced_at >= before

    def test_does_not_overwrite_entered_water_at(self, assignment, staff_user):
        """entered_water_at is only set once (first transition to in_water)."""
        # First transition to in_water
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="in_water",
        )
        assignment.refresh_from_db()
        first_timestamp = assignment.entered_water_at

        # Transition away and back
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="surfaced",
        )
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="in_water",
        )

        assignment.refresh_from_db()
        # Original timestamp preserved
        assert assignment.entered_water_at == first_timestamp

    def test_does_not_overwrite_surfaced_at(self, assignment, staff_user):
        """surfaced_at is only set once (first transition to surfaced)."""
        # Get in water then surface
        update_diver_status(
            actor=staff_user, assignment=assignment, new_status="in_water"
        )
        update_diver_status(
            actor=staff_user, assignment=assignment, new_status="surfaced"
        )
        assignment.refresh_from_db()
        first_timestamp = assignment.surfaced_at

        # Transition to on_boat and back to surfaced
        update_diver_status(
            actor=staff_user, assignment=assignment, new_status="on_boat"
        )
        update_diver_status(
            actor=staff_user, assignment=assignment, new_status="surfaced"
        )

        assignment.refresh_from_db()
        # Original timestamp preserved
        assert assignment.surfaced_at == first_timestamp

    def test_emits_diver_status_changed_audit_event(self, assignment, staff_user):
        """update_diver_status emits DIVER_STATUS_CHANGED audit event."""
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="briefed",
        )

        audit = AuditLog.objects.filter(action=Actions.DIVER_STATUS_CHANGED).first()
        assert audit is not None
        assert audit.actor_user == staff_user

    def test_audit_event_contains_status_change(self, assignment, staff_user):
        """Audit event contains old and new status in changes."""
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="gearing_up",
        )

        audit = AuditLog.objects.filter(action=Actions.DIVER_STATUS_CHANGED).first()
        assert audit is not None
        assert audit.changes.get("status") == {"old": "assigned", "new": "gearing_up"}

    def test_full_status_progression(self, assignment, staff_user):
        """Test typical status progression through a dive."""
        statuses = ["briefed", "gearing_up", "in_water", "surfaced", "on_boat"]

        for status in statuses:
            update_diver_status(
                actor=staff_user,
                assignment=assignment,
                new_status=status,
            )
            assignment.refresh_from_db()
            assert assignment.status == status

        # Verify timestamps were set
        assert assignment.entered_water_at is not None
        assert assignment.surfaced_at is not None

    def test_sat_out_status(self, assignment, staff_user):
        """Test transitioning to sat_out status."""
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="briefed",
        )
        update_diver_status(
            actor=staff_user,
            assignment=assignment,
            new_status="sat_out",
        )

        assignment.refresh_from_db()
        assert assignment.status == "sat_out"
        # No water timestamps for sat_out
        assert assignment.entered_water_at is None
        assert assignment.surfaced_at is None
