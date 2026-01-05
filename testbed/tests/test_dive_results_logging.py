"""Tests for dive results logging service.

Tests log_dive_results() service which:
- Updates Dive master record with actual results
- Sets logged_by and logged_at
- Auto-creates DiveLog entries for participating divers
- Is idempotent (calling twice doesn't duplicate logs)
- Emits DIVE_LOGGED audit event
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
from primitives_testbed.diveops.services import log_dive_results
from primitives_testbed.diveops.audit import Actions

from django_audit_log.models import AuditLog
from django_parties.models import Organization, Person
from django_geo.models import Place


User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user for logging."""
    return User.objects.create_user(
        username="guide@diveshop.com",
        email="guide@diveshop.com",
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
        name="Blue Hole Location",
        latitude=Decimal("17.3151"),
        longitude=Decimal("-87.5346"),
    )


@pytest.fixture
def dive_site(db, place):
    """Create a dive site."""
    return DiveSite.objects.create(
        name="Blue Hole",
        place=place,
        max_depth_meters=40,
        difficulty="intermediate",
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
        price_per_diver=Decimal("100.00"),
        status="scheduled",
        created_by=staff_user,
    )


@pytest.fixture
def dive(db, excursion, dive_site):
    """Create a dive within the excursion."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=1,
        planned_start=excursion.departure_time + timedelta(minutes=30),
        planned_duration_minutes=45,
    )


@pytest.fixture
def person1(db):
    """Create a person for diver 1."""
    return Person.objects.create(
        first_name="Alice",
        last_name="Diver",
        email="alice@example.com",
    )


@pytest.fixture
def person2(db):
    """Create a person for diver 2."""
    return Person.objects.create(
        first_name="Bob",
        last_name="Bubbles",
        email="bob@example.com",
    )


@pytest.fixture
def diver1(db, person1):
    """Create diver profile 1."""
    return DiverProfile.objects.create(
        person=person1,
        certification_level="ow",
        total_dives=25,
    )


@pytest.fixture
def diver2(db, person2):
    """Create diver profile 2."""
    return DiverProfile.objects.create(
        person=person2,
        certification_level="aow",
        total_dives=50,
    )


@pytest.fixture
def participating_assignment(db, dive, diver1):
    """Create an assignment that participated (on_boat status)."""
    return DiveAssignment.objects.create(
        dive=dive,
        diver=diver1,
        role="diver",
        status="on_boat",
    )


@pytest.fixture
def sat_out_assignment(db, dive, diver2):
    """Create an assignment that sat out."""
    return DiveAssignment.objects.create(
        dive=dive,
        diver=diver2,
        role="diver",
        status="sat_out",
    )


@pytest.mark.django_db
class TestLogDiveResults:
    """Tests for log_dive_results service."""

    def test_updates_dive_master_record(self, dive, staff_user):
        """log_dive_results updates Dive with actual results."""
        actual_start = timezone.now()
        actual_end = actual_start + timedelta(minutes=42)

        updated_dive = log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=actual_start,
            actual_end=actual_end,
            max_depth_meters=28,
            bottom_time_minutes=42,
            visibility_meters=15,
            water_temp_celsius=Decimal("26.5"),
            surface_conditions="calm",
            current="mild",
        )

        dive.refresh_from_db()
        assert dive.actual_start == actual_start
        assert dive.actual_end == actual_end
        assert dive.max_depth_meters == 28
        assert dive.bottom_time_minutes == 42
        assert dive.visibility_meters == 15
        assert dive.water_temp_celsius == Decimal("26.5")
        assert dive.surface_conditions == "calm"
        assert dive.current == "mild"

    def test_sets_logged_by_and_logged_at(self, dive, staff_user):
        """log_dive_results sets audit fields."""
        before = timezone.now()

        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        dive.refresh_from_db()
        assert dive.logged_by == staff_user
        assert dive.logged_at is not None
        assert dive.logged_at >= before

    def test_creates_dive_log_for_participating_assignment(
        self, dive, staff_user, participating_assignment
    ):
        """log_dive_results creates DiveLog for on_boat/surfaced/in_water assignments."""
        assert DiveLog.objects.count() == 0

        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        assert DiveLog.objects.count() == 1
        dive_log = DiveLog.objects.first()
        assert dive_log.dive == dive
        assert dive_log.diver == participating_assignment.diver
        assert dive_log.assignment == participating_assignment

    def test_does_not_create_dive_log_for_sat_out(
        self, dive, staff_user, sat_out_assignment
    ):
        """log_dive_results does NOT create DiveLog for sat_out assignments."""
        assert DiveLog.objects.count() == 0

        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        # No logs created for sat_out diver
        assert DiveLog.objects.count() == 0

    def test_creates_logs_for_multiple_participants(
        self, dive, staff_user, diver1, diver2
    ):
        """log_dive_results creates DiveLog for each participating diver."""
        # Create two participating assignments
        DiveAssignment.objects.create(
            dive=dive, diver=diver1, role="diver", status="on_boat"
        )
        DiveAssignment.objects.create(
            dive=dive, diver=diver2, role="guide", status="on_boat"
        )

        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        assert DiveLog.objects.count() == 2
        assert DiveLog.objects.filter(diver=diver1).exists()
        assert DiveLog.objects.filter(diver=diver2).exists()

    def test_is_idempotent(self, dive, staff_user, participating_assignment):
        """Calling log_dive_results twice doesn't duplicate DiveLogs."""
        kwargs = {
            "actor": staff_user,
            "dive": dive,
            "actual_start": timezone.now(),
            "actual_end": timezone.now() + timedelta(minutes=40),
            "max_depth_meters": 25,
        }

        # Call twice
        log_dive_results(**kwargs)
        log_dive_results(**kwargs)

        # Still only one DiveLog
        assert DiveLog.objects.count() == 1

    def test_assigns_dive_number_automatically(
        self, dive, staff_user, participating_assignment
    ):
        """log_dive_results auto-assigns dive_number based on diver's history."""
        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        dive_log = DiveLog.objects.first()
        assert dive_log.dive_number == 1  # First logged dive

    def test_emits_dive_logged_audit_event(self, dive, staff_user):
        """log_dive_results emits DIVE_LOGGED audit event."""
        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        audit = AuditLog.objects.filter(action=Actions.DIVE_LOGGED).first()
        assert audit is not None
        assert audit.actor_user == staff_user

    def test_participating_statuses(self, dive, staff_user, diver1, diver2):
        """Verify which statuses count as participated."""
        person3 = Person.objects.create(
            first_name="Charlie", last_name="Deep", email="charlie@example.com"
        )
        diver3 = DiverProfile.objects.create(
            person=person3, certification_level="dm", total_dives=100
        )

        # Create assignments with different statuses
        DiveAssignment.objects.create(
            dive=dive, diver=diver1, role="diver", status="in_water"
        )
        DiveAssignment.objects.create(
            dive=dive, diver=diver2, role="diver", status="surfaced"
        )
        DiveAssignment.objects.create(
            dive=dive, diver=diver3, role="guide", status="on_boat"
        )

        log_dive_results(
            actor=staff_user,
            dive=dive,
            actual_start=timezone.now(),
            actual_end=timezone.now() + timedelta(minutes=40),
            max_depth_meters=25,
        )

        # All three should have logs (in_water, surfaced, on_boat are participated)
        assert DiveLog.objects.count() == 3
