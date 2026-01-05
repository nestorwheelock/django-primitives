"""Tests for DiveLog overlay pattern (effective values).

Tests that DiveLog inherits values from Dive when personal override is null.
This is the "inheritance-by-null" / overlay pattern.
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

from django_parties.models import Organization, Person
from django_geo.models import Place


User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staff@diveshop.com",
        email="staff@diveshop.com",
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
        name="The Wall",
        place=place,
        max_depth_meters=40,
        difficulty="advanced",
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
        price_per_diver=Decimal("120.00"),
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
        actual_end=excursion.departure_time + timedelta(minutes=80),
        max_depth_meters=35,
        bottom_time_minutes=45,
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
        certification_level="aow",
        total_dives=50,
    )


@pytest.fixture
def assignment(db, dive, diver):
    """Create a dive assignment."""
    return DiveAssignment.objects.create(
        dive=dive,
        diver=diver,
        role="diver",
        status="on_boat",
    )


@pytest.fixture
def dive_log(db, dive, diver, assignment):
    """Create a dive log with null override fields."""
    return DiveLog.objects.create(
        dive=dive,
        diver=diver,
        assignment=assignment,
        # All override fields null - should inherit from Dive
        max_depth_meters=None,
        bottom_time_minutes=None,
    )


@pytest.mark.django_db
class TestDiveLogEffectiveValues:
    """Tests for DiveLog effective value properties (overlay pattern)."""

    def test_effective_max_depth_inherits_from_dive(self, dive_log, dive):
        """When max_depth_meters is null, effective_max_depth returns Dive value."""
        assert dive_log.max_depth_meters is None
        assert dive.max_depth_meters == 35
        assert dive_log.effective_max_depth == 35

    def test_effective_max_depth_uses_override(self, dive_log, dive):
        """When max_depth_meters is set, effective_max_depth returns personal value."""
        dive_log.max_depth_meters = Decimal("28.5")
        dive_log.save()

        assert dive_log.effective_max_depth == Decimal("28.5")
        assert dive.max_depth_meters == 35  # Dive unchanged

    def test_effective_bottom_time_inherits_from_dive(self, dive_log, dive):
        """When bottom_time_minutes is null, effective_bottom_time returns Dive value."""
        assert dive_log.bottom_time_minutes is None
        assert dive.bottom_time_minutes == 45
        assert dive_log.effective_bottom_time == 45

    def test_effective_bottom_time_uses_override(self, dive_log, dive):
        """When bottom_time_minutes is set, effective_bottom_time returns personal value."""
        dive_log.bottom_time_minutes = 38
        dive_log.save()

        assert dive_log.effective_bottom_time == 38
        assert dive.bottom_time_minutes == 45  # Dive unchanged

    def test_air_consumed_bar_calculation(self, dive_log):
        """air_consumed_bar returns difference when both values present."""
        dive_log.air_start_bar = 200
        dive_log.air_end_bar = 50
        dive_log.save()

        assert dive_log.air_consumed_bar == 150

    def test_air_consumed_bar_returns_none_when_incomplete(self, dive_log):
        """air_consumed_bar returns None when start or end is missing."""
        dive_log.air_start_bar = 200
        dive_log.air_end_bar = None
        dive_log.save()

        assert dive_log.air_consumed_bar is None

        dive_log.air_start_bar = None
        dive_log.air_end_bar = 50
        dive_log.save()

        assert dive_log.air_consumed_bar is None

    def test_is_verified_false_when_not_verified(self, dive_log):
        """is_verified returns False when verified_at is None."""
        assert dive_log.verified_at is None
        assert dive_log.is_verified is False

    def test_is_verified_true_when_verified(self, dive_log):
        """is_verified returns True when verified_at is set."""
        dive_log.verified_at = timezone.now()
        dive_log.save()

        assert dive_log.is_verified is True

    def test_personal_override_zero_is_valid(self, dive_log, dive):
        """A personal override of 0 should be used, not fallback to Dive."""
        # Zero is a valid override value (e.g., 0 depth for a dive computer error)
        # But in practice depth should be > 0, so we test bottom_time
        # Actually, let's just test that non-null values are used
        dive_log.max_depth_meters = Decimal("0.0")
        dive_log.save()

        # Zero should be returned, not fallback
        # Note: This depends on implementation - truthy check vs None check
        # Correct implementation checks `is not None`
        assert dive_log.effective_max_depth == Decimal("0.0")


@pytest.mark.django_db
class TestDiveLogMixedOverrides:
    """Tests for DiveLog with partial overrides."""

    def test_mixed_overrides_depth_set_time_inherited(self, dive, diver, assignment):
        """DiveLog can override depth but inherit time."""
        dive_log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            assignment=assignment,
            max_depth_meters=Decimal("25.0"),  # Override
            bottom_time_minutes=None,  # Inherit
        )

        assert dive_log.effective_max_depth == Decimal("25.0")
        assert dive_log.effective_bottom_time == dive.bottom_time_minutes

    def test_mixed_overrides_time_set_depth_inherited(self, dive, diver, assignment):
        """DiveLog can override time but inherit depth."""
        dive_log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            assignment=assignment,
            max_depth_meters=None,  # Inherit
            bottom_time_minutes=30,  # Override
        )

        assert dive_log.effective_max_depth == dive.max_depth_meters
        assert dive_log.effective_bottom_time == 30

    def test_all_overrides_set(self, dive, diver, assignment):
        """DiveLog with all overrides set uses personal values."""
        dive_log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            assignment=assignment,
            max_depth_meters=Decimal("20.0"),
            bottom_time_minutes=25,
        )

        assert dive_log.effective_max_depth == Decimal("20.0")
        assert dive_log.effective_bottom_time == 25

    def test_inherits_when_dive_values_null(self, excursion, dive_site, diver, staff_user):
        """When Dive has no actual values, effective values are None."""
        # Dive with no actual results logged
        dive = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=2,
            planned_start=excursion.departure_time + timedelta(hours=2),
            # No actual_*, max_depth, bottom_time
        )
        assignment = DiveAssignment.objects.create(
            dive=dive, diver=diver, role="diver", status="on_boat"
        )
        dive_log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            assignment=assignment,
        )

        # Both Dive and DiveLog have None
        assert dive.max_depth_meters is None
        assert dive_log.max_depth_meters is None
        assert dive_log.effective_max_depth is None
