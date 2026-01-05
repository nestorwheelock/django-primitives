"""Tests for DiveLog and DiveAssignment constraints.

Tests:
- Air constraint: air_end_bar < air_start_bar when both present
- Nitrox constraint: nitrox_percentage 21-40
- Unique constraints: (dive, diver) for both models
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
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
        name="Test Reef",
        place=place,
        max_depth_meters=25,
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
    """Create a dive."""
    return Dive.objects.create(
        excursion=excursion,
        dive_site=dive_site,
        sequence=1,
        planned_start=excursion.departure_time + timedelta(minutes=30),
        max_depth_meters=20,
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
def person2(db):
    """Create another person."""
    return Person.objects.create(
        first_name="Other",
        last_name="Diver",
        email="other@example.com",
    )


@pytest.fixture
def diver(db, person):
    """Create a diver profile."""
    return DiverProfile.objects.create(
        person=person,
        certification_level="ow",
        total_dives=20,
    )


@pytest.fixture
def diver2(db, person2):
    """Create another diver profile."""
    return DiverProfile.objects.create(
        person=person2,
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
        status="assigned",
    )


@pytest.mark.django_db
class TestDiveAssignmentUniqueConstraint:
    """Tests for DiveAssignment unique (dive, diver) constraint."""

    def test_unique_diver_per_dive(self, dive, diver, assignment):
        """Cannot create duplicate assignment for same diver on same dive."""
        with pytest.raises(IntegrityError):
            DiveAssignment.objects.create(
                dive=dive,
                diver=diver,
                role="guide",  # Different role
                status="assigned",
            )

    def test_same_diver_different_dives(self, excursion, dive_site, diver):
        """Same diver can be assigned to different dives."""
        dive1 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=excursion.departure_time + timedelta(minutes=30),
        )
        dive2 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=2,
            planned_start=excursion.departure_time + timedelta(hours=2),
        )

        # Both should succeed
        a1 = DiveAssignment.objects.create(
            dive=dive1, diver=diver, role="diver", status="assigned"
        )
        a2 = DiveAssignment.objects.create(
            dive=dive2, diver=diver, role="diver", status="assigned"
        )

        assert a1.pk is not None
        assert a2.pk is not None

    def test_different_divers_same_dive(self, dive, diver, diver2):
        """Different divers can be assigned to same dive."""
        a1 = DiveAssignment.objects.create(
            dive=dive, diver=diver, role="diver", status="assigned"
        )
        a2 = DiveAssignment.objects.create(
            dive=dive, diver=diver2, role="diver", status="assigned"
        )

        assert a1.pk is not None
        assert a2.pk is not None


@pytest.mark.django_db
class TestDiveLogUniqueConstraint:
    """Tests for DiveLog unique (dive, diver) constraint."""

    def test_unique_diver_per_dive(self, dive, diver, assignment):
        """Cannot create duplicate log for same diver on same dive."""
        DiveLog.objects.create(
            dive=dive,
            diver=diver,
            assignment=assignment,
        )

        with pytest.raises(IntegrityError):
            DiveLog.objects.create(
                dive=dive,
                diver=diver,
                # Different assignment or none
            )

    def test_same_diver_different_dives(self, excursion, dive_site, diver):
        """Same diver can have logs for different dives."""
        dive1 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=excursion.departure_time + timedelta(minutes=30),
        )
        dive2 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=2,
            planned_start=excursion.departure_time + timedelta(hours=2),
        )

        log1 = DiveLog.objects.create(dive=dive1, diver=diver)
        log2 = DiveLog.objects.create(dive=dive2, diver=diver)

        assert log1.pk is not None
        assert log2.pk is not None

    def test_different_divers_same_dive(self, dive, diver, diver2):
        """Different divers can have logs for same dive."""
        log1 = DiveLog.objects.create(dive=dive, diver=diver)
        log2 = DiveLog.objects.create(dive=dive, diver=diver2)

        assert log1.pk is not None
        assert log2.pk is not None


@pytest.mark.django_db
class TestDiveLogAirConstraint:
    """Tests for DiveLog air consumption constraint (end < start)."""

    def test_valid_air_values(self, dive, diver):
        """Valid air values (end < start) are accepted."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            air_start_bar=200,
            air_end_bar=50,
        )
        assert log.pk is not None

    def test_invalid_air_end_greater_than_start(self, dive, diver):
        """air_end_bar > air_start_bar violates constraint."""
        with pytest.raises(IntegrityError):
            DiveLog.objects.create(
                dive=dive,
                diver=diver,
                air_start_bar=100,
                air_end_bar=150,  # Invalid: end > start
            )

    def test_invalid_air_end_equals_start(self, dive, diver):
        """air_end_bar == air_start_bar violates constraint."""
        with pytest.raises(IntegrityError):
            DiveLog.objects.create(
                dive=dive,
                diver=diver,
                air_start_bar=100,
                air_end_bar=100,  # Invalid: end == start
            )

    def test_null_air_start_allowed(self, dive, diver):
        """Null air_start_bar is allowed."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            air_start_bar=None,
            air_end_bar=50,
        )
        assert log.pk is not None

    def test_null_air_end_allowed(self, dive, diver2):
        """Null air_end_bar is allowed."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver2,
            air_start_bar=200,
            air_end_bar=None,
        )
        assert log.pk is not None

    def test_both_air_null_allowed(self, excursion, dive_site, diver):
        """Both air values null is allowed."""
        # Use a separate dive to avoid unique constraint with other tests
        dive2 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=2,
            planned_start=excursion.departure_time + timedelta(hours=2),
        )
        log = DiveLog.objects.create(
            dive=dive2,
            diver=diver,
            air_start_bar=None,
            air_end_bar=None,
        )
        assert log.pk is not None


@pytest.mark.django_db
class TestDiveLogNitroxConstraint:
    """Tests for DiveLog nitrox percentage constraint (21-40)."""

    def test_valid_nitrox_21(self, dive, diver):
        """nitrox_percentage=21 (air) is valid."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            nitrox_percentage=21,
        )
        assert log.pk is not None

    def test_valid_nitrox_32(self, dive, diver):
        """nitrox_percentage=32 (EAN32) is valid."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            nitrox_percentage=32,
        )
        assert log.pk is not None

    def test_valid_nitrox_40(self, dive, diver):
        """nitrox_percentage=40 (max recreational) is valid."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            nitrox_percentage=40,
        )
        assert log.pk is not None

    def test_invalid_nitrox_below_21(self, dive, diver):
        """nitrox_percentage < 21 violates constraint."""
        with pytest.raises(IntegrityError):
            DiveLog.objects.create(
                dive=dive,
                diver=diver,
                nitrox_percentage=20,
            )

    def test_invalid_nitrox_above_40(self, dive, diver):
        """nitrox_percentage > 40 violates constraint."""
        with pytest.raises(IntegrityError):
            DiveLog.objects.create(
                dive=dive,
                diver=diver,
                nitrox_percentage=50,
            )

    def test_null_nitrox_allowed(self, dive, diver):
        """Null nitrox_percentage is allowed."""
        log = DiveLog.objects.create(
            dive=dive,
            diver=diver,
            nitrox_percentage=None,
        )
        assert log.pk is not None
