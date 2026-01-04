"""Tests for Excursion and Dive models.

Tests for the semantic refactor:
- Excursion: operational fulfillment (single calendar day), 1..N dives
- Dive: atomic loggable unit within an excursion
- Trip: commercial package (multi-day), 1..N excursions
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def dive_shop(db):
    """Create a dive shop organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Blue Water Divers",
        org_type="dive_shop",
    )


@pytest.fixture
def dive_site(db, staff_user):
    """Create a dive site."""
    from primitives_testbed.diveops.services import create_dive_site

    return create_dive_site(
        actor=staff_user,
        name="Coral Gardens",
        latitude=Decimal("20.5000"),
        longitude=Decimal("-87.0000"),
        max_depth_meters=25,
        difficulty="intermediate",
    )


@pytest.mark.django_db
class TestExcursionModel:
    """Tests for Excursion model (formerly DiveTrip)."""

    def test_excursion_creation(self, dive_shop, dive_site, staff_user):
        """Excursion can be created with required fields."""
        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
        )
        assert excursion.pk is not None
        assert excursion.status == "scheduled"

    def test_excursion_single_day_constraint(self, dive_shop, dive_site, staff_user):
        """Excursion departure and return must be same calendar day."""
        from primitives_testbed.diveops.models import Excursion

        today = timezone.now().replace(hour=8, minute=0)
        tomorrow = today + timedelta(days=1)

        excursion = Excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=today,
            return_time=tomorrow,  # Next day - should fail
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
        )

        with pytest.raises(ValidationError) as exc_info:
            excursion.full_clean()

        assert "same calendar day" in str(exc_info.value).lower()

    def test_excursion_return_after_departure(self, dive_shop, dive_site, staff_user):
        """Excursion return time must be after departure."""
        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        excursion = Excursion(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now - timedelta(hours=1),  # Before departure
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
        )

        with pytest.raises(IntegrityError):
            excursion.save()

    def test_excursion_can_be_standalone(self, dive_shop, dive_site, staff_user):
        """Excursion can exist without a Trip (walk-in bookings)."""
        from primitives_testbed.diveops.models import Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
            trip=None,  # No trip - standalone excursion
        )
        assert excursion.trip is None
        assert excursion.pk is not None

    def test_excursion_can_link_to_trip(self, dive_shop, dive_site, staff_user):
        """Excursion can be part of a Trip package."""
        from primitives_testbed.diveops.models import Excursion, Trip

        today = date.today()
        trip = Trip.objects.create(
            name="Weekend Dive Package",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today + timedelta(days=2),
            created_by=staff_user,
        )

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
            trip=trip,
        )
        assert excursion.trip == trip
        assert excursion in trip.excursions.all()

    def test_excursion_status_choices(self, dive_shop, dive_site, staff_user):
        """Excursion has correct status choices."""
        from primitives_testbed.diveops.models import Excursion

        assert Excursion.STATUS_CHOICES == [
            ("scheduled", "Scheduled"),
            ("boarding", "Boarding"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ]


@pytest.mark.django_db
class TestDiveModel:
    """Tests for Dive model (atomic loggable unit)."""

    def test_dive_creation(self, dive_shop, dive_site, staff_user):
        """Dive can be created within an excursion."""
        from primitives_testbed.diveops.models import Dive, Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
        )

        dive = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=now + timedelta(minutes=30),
        )
        assert dive.pk is not None
        assert dive.excursion == excursion
        assert dive.sequence == 1

    def test_dive_sequence_unique_per_excursion(self, dive_shop, dive_site, staff_user):
        """Dive sequence must be unique within excursion."""
        from primitives_testbed.diveops.models import Dive, Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
        )

        Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=now + timedelta(minutes=30),
        )

        # Second dive with same sequence should fail
        with pytest.raises(IntegrityError):
            Dive.objects.create(
                excursion=excursion,
                dive_site=dive_site,
                sequence=1,  # Duplicate
                planned_start=now + timedelta(hours=2),
            )

    def test_dive_can_log_actual_times(self, dive_shop, dive_site, staff_user):
        """Dive can record actual start/end times and metrics."""
        from primitives_testbed.diveops.models import Dive, Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
        )

        dive = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=now + timedelta(minutes=30),
            actual_start=now + timedelta(minutes=35),
            actual_end=now + timedelta(minutes=80),
            max_depth_meters=18,
            bottom_time_minutes=42,
        )
        assert dive.actual_start is not None
        assert dive.max_depth_meters == 18
        assert dive.bottom_time_minutes == 42

    def test_dive_belongs_to_excursion(self, dive_shop, dive_site, staff_user):
        """Dive must belong to an excursion."""
        from primitives_testbed.diveops.models import Dive

        with pytest.raises(IntegrityError):
            Dive.objects.create(
                excursion=None,  # Required
                dive_site=dive_site,
                sequence=1,
                planned_start=timezone.now(),
            )

    def test_multiple_dives_per_excursion(self, dive_shop, dive_site, staff_user):
        """Excursion can have multiple dives."""
        from primitives_testbed.diveops.models import Dive, Excursion

        now = timezone.now()
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=6),
            max_divers=12,
            price_per_diver=Decimal("200.00"),
            created_by=staff_user,
        )

        dive1 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=1,
            planned_start=now + timedelta(minutes=30),
        )
        dive2 = Dive.objects.create(
            excursion=excursion,
            dive_site=dive_site,
            sequence=2,
            planned_start=now + timedelta(hours=2),
        )

        assert excursion.dives.count() == 2
        assert list(excursion.dives.order_by("sequence")) == [dive1, dive2]


@pytest.mark.django_db
class TestTripModel:
    """Tests for Trip model (commercial package)."""

    def test_trip_creation(self, dive_shop, staff_user):
        """Trip can be created as multi-day package."""
        from primitives_testbed.diveops.models import Trip

        today = date.today()
        trip = Trip.objects.create(
            name="Weekend Dive Package",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today + timedelta(days=2),
            created_by=staff_user,
        )
        assert trip.pk is not None
        assert trip.status == "draft"

    def test_trip_multi_day_allowed(self, dive_shop, staff_user):
        """Trip can span multiple days."""
        from primitives_testbed.diveops.models import Trip

        today = date.today()
        trip = Trip.objects.create(
            name="Week-Long Expedition",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today + timedelta(days=7),
            created_by=staff_user,
        )
        assert (trip.end_date - trip.start_date).days == 7

    def test_trip_single_day_allowed(self, dive_shop, staff_user):
        """Trip can also be single day."""
        from primitives_testbed.diveops.models import Trip

        today = date.today()
        trip = Trip.objects.create(
            name="Day Trip Special",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today,  # Same day
            created_by=staff_user,
        )
        assert trip.start_date == trip.end_date

    def test_trip_end_must_be_after_start(self, dive_shop, staff_user):
        """Trip end date cannot be before start date."""
        from primitives_testbed.diveops.models import Trip

        today = date.today()
        trip = Trip(
            name="Invalid Trip",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today - timedelta(days=1),  # Before start
            created_by=staff_user,
        )

        with pytest.raises(IntegrityError):
            trip.save()

    def test_trip_contains_excursions(self, dive_shop, dive_site, staff_user):
        """Trip can contain multiple excursions."""
        from primitives_testbed.diveops.models import Excursion, Trip

        today = date.today()
        trip = Trip.objects.create(
            name="Multi-Dive Package",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today + timedelta(days=1),
            created_by=staff_user,
        )

        now = timezone.now()
        ex1 = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now,
            return_time=now + timedelta(hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
            trip=trip,
        )
        ex2 = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=now + timedelta(days=1),
            return_time=now + timedelta(days=1, hours=4),
            max_divers=12,
            price_per_diver=Decimal("150.00"),
            created_by=staff_user,
            trip=trip,
        )

        assert trip.excursions.count() == 2
        assert ex1 in trip.excursions.all()
        assert ex2 in trip.excursions.all()

    def test_trip_status_choices(self, dive_shop, staff_user):
        """Trip has correct status choices."""
        from primitives_testbed.diveops.models import Trip

        assert Trip.STATUS_CHOICES == [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ]

    def test_trip_can_link_to_catalog_item(self, dive_shop, staff_user):
        """Trip can be linked to a CatalogItem for commerce."""
        from django_catalog.models import CatalogItem

        from primitives_testbed.diveops.models import Trip

        catalog_item = CatalogItem.objects.create(
            display_name="Weekend Dive Package",
            kind="service",
            is_billable=True,
        )

        today = date.today()
        trip = Trip.objects.create(
            name="Weekend Package",
            dive_shop=dive_shop,
            start_date=today,
            end_date=today + timedelta(days=2),
            catalog_item=catalog_item,
            created_by=staff_user,
        )
        assert trip.catalog_item == catalog_item
