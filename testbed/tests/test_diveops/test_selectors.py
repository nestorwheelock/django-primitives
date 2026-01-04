"""Tests for diveops selectors module."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from primitives_testbed.diveops.models import (
    Booking,
    DiverProfile,
    DiveSite,
    DiveTrip,
)
from primitives_testbed.diveops.selectors import (
    get_booking,
    get_diver_profile,
    list_diver_bookings,
    list_dive_sites,
    list_shop_trips,
    list_upcoming_trips,
)

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(username="staff", password="test", is_staff=True)


@pytest.fixture
def dive_shop(db):
    """Create a dive shop organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Test Dive Shop",
        org_type="dive_shop",
    )


@pytest.fixture
def dive_site_place(db):
    """Create a Place for a dive site."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Test Reef Location",
        latitude=Decimal("25.123456"),
        longitude=Decimal("-80.123456"),
    )


@pytest.fixture
def dive_site(db, dive_site_place):
    """Create a dive site."""
    return DiveSite.objects.create(
        name="Test Reef",
        description="A test dive site",
        place=dive_site_place,
        max_depth_meters=30,
        min_certification_level=None,
        is_active=True,
    )


@pytest.fixture
def another_dive_site_place(db):
    """Create a Place for another dive site."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Deep Wall Location",
        latitude=Decimal("25.234567"),
        longitude=Decimal("-80.234567"),
    )


@pytest.fixture
def another_dive_site(db, another_dive_site_place):
    """Create another dive site."""
    return DiveSite.objects.create(
        name="Deep Wall",
        description="A deep dive site",
        place=another_dive_site_place,
        max_depth_meters=40,
        min_certification_level=None,
        is_active=True,
    )


@pytest.fixture
def person(db):
    """Create a person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="John",
        last_name="Diver",
        email="john@example.com",
    )


@pytest.fixture
def diver(db, person):
    """Create a diver profile."""
    return DiverProfile.objects.create(
        person=person,
        medical_clearance_valid_until=date.today() + timedelta(days=365),
        total_dives=50,
    )


@pytest.fixture
def dive_trip(db, dive_shop, dive_site, staff_user):
    """Create an upcoming dive trip."""
    return DiveTrip.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        departure_time=timezone.now() + timedelta(days=7),
        return_time=timezone.now() + timedelta(days=7, hours=6),
        max_divers=10,
        price_per_diver=Decimal("100.00"),
        status="scheduled",
        created_by=staff_user,
    )


@pytest.fixture
def another_dive_shop(db):
    """Create another dive shop."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Another Dive Shop",
        org_type="dive_shop",
    )


@pytest.mark.django_db
class TestListUpcomingTrips:
    """Tests for list_upcoming_trips selector."""

    def test_returns_upcoming_trips(self, dive_trip):
        """Selector returns upcoming trips."""
        trips = list_upcoming_trips()
        assert len(trips) == 1
        assert trips[0].pk == dive_trip.pk

    def test_excludes_past_trips(self, dive_shop, dive_site, staff_user):
        """Past trips are excluded."""
        DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() - timedelta(days=1),
            return_time=timezone.now() - timedelta(hours=18),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="completed",
            created_by=staff_user,
        )
        trips = list_upcoming_trips()
        assert len(trips) == 0

    def test_excludes_cancelled_trips(self, dive_shop, dive_site, staff_user):
        """Cancelled trips are excluded."""
        DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=7),
            return_time=timezone.now() + timedelta(days=7, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="cancelled",
            created_by=staff_user,
        )
        trips = list_upcoming_trips()
        assert len(trips) == 0

    def test_filters_by_dive_shop(self, dive_trip, dive_shop, dive_site, another_dive_shop, staff_user):
        """Can filter by dive shop."""
        # Create trip at another shop
        DiveTrip.objects.create(
            dive_shop=another_dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=7),
            return_time=timezone.now() + timedelta(days=7, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="scheduled",
            created_by=staff_user,
        )
        trips = list_upcoming_trips(dive_shop=dive_shop)
        assert len(trips) == 1
        assert trips[0].dive_shop == dive_shop

    def test_filters_by_dive_site(self, dive_trip, dive_shop, dive_site, another_dive_site, staff_user):
        """Can filter by dive site."""
        # Create trip at another site
        DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=another_dive_site,
            departure_time=timezone.now() + timedelta(days=8),
            return_time=timezone.now() + timedelta(days=8, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="scheduled",
            created_by=staff_user,
        )
        trips = list_upcoming_trips(dive_site=dive_site)
        assert len(trips) == 1
        assert trips[0].dive_site == dive_site

    def test_filters_by_min_spots(self, dive_trip, diver, dive_shop, dive_site, staff_user):
        """Can filter by minimum available spots."""
        Booking.objects.create(
            excursion=dive_trip,
            diver=diver,
            booked_by=staff_user,
            status="confirmed",
        )
        # Trip has 9 spots available (10 max - 1 booked)
        trips = list_upcoming_trips(min_spots=10)
        assert len(trips) == 0

        trips = list_upcoming_trips(min_spots=9)
        assert len(trips) == 1

    def test_respects_limit(self, dive_shop, dive_site, staff_user):
        """Respects the limit parameter."""
        for i in range(5):
            DiveTrip.objects.create(
                dive_shop=dive_shop,
                dive_site=dive_site,
                departure_time=timezone.now() + timedelta(days=i + 1),
                return_time=timezone.now() + timedelta(days=i + 1, hours=6),
                max_divers=10,
                price_per_diver=Decimal("100.00"),
                status="scheduled",
                created_by=staff_user,
            )
        trips = list_upcoming_trips(limit=3)
        assert len(trips) == 3


@pytest.mark.django_db
class TestListDiverBookings:
    """Tests for list_diver_bookings selector."""

    def test_returns_diver_bookings(self, dive_trip, diver, staff_user):
        """Returns bookings for a diver."""
        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver,
            booked_by=staff_user,
            status="confirmed",
        )
        bookings = list_diver_bookings(diver)
        assert len(bookings) == 1
        assert bookings[0].pk == booking.pk

    def test_filters_by_status(self, dive_trip, diver, staff_user):
        """Can filter by status."""
        Booking.objects.create(
            excursion=dive_trip,
            diver=diver,
            booked_by=staff_user,
            status="confirmed",
        )
        bookings = list_diver_bookings(diver, status="cancelled")
        assert len(bookings) == 0

        bookings = list_diver_bookings(diver, status="confirmed")
        assert len(bookings) == 1

    def test_excludes_past_by_default(self, dive_shop, dive_site, diver, staff_user):
        """Excludes past trips by default."""
        past_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() - timedelta(days=7),
            return_time=timezone.now() - timedelta(days=7, hours=-6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="completed",
            created_by=staff_user,
        )
        Booking.objects.create(
            excursion=past_trip,
            diver=diver,
            booked_by=staff_user,
            status="checked_in",
        )
        bookings = list_diver_bookings(diver)
        assert len(bookings) == 0

    def test_includes_past_when_requested(self, dive_shop, dive_site, diver, staff_user):
        """Includes past trips when include_past=True."""
        past_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() - timedelta(days=7),
            return_time=timezone.now() - timedelta(days=7, hours=-6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="completed",
            created_by=staff_user,
        )
        Booking.objects.create(
            excursion=past_trip,
            diver=diver,
            booked_by=staff_user,
            status="checked_in",
        )
        bookings = list_diver_bookings(diver, include_past=True)
        assert len(bookings) == 1


@pytest.mark.django_db
class TestGetDiverProfile:
    """Tests for get_diver_profile selector."""

    def test_returns_profile_for_person(self, diver, person):
        """Returns diver profile for a person."""
        result = get_diver_profile(person)
        assert result is not None
        assert result.pk == diver.pk

    def test_returns_profile_for_person_id(self, diver, person):
        """Returns diver profile for a person ID."""
        result = get_diver_profile(person.pk)
        assert result is not None
        assert result.pk == diver.pk

    def test_returns_none_for_non_diver(self, db):
        """Returns None for person without diver profile."""
        from django_parties.models import Person

        person = Person.objects.create(
            first_name="Non",
            last_name="Diver",
            email="nondiver@example.com",
        )
        result = get_diver_profile(person)
        assert result is None


@pytest.mark.django_db
class TestListDiveSites:
    """Tests for list_dive_sites selector."""

    def test_returns_active_sites(self, dive_site):
        """Returns active dive sites."""
        sites = list_dive_sites()
        assert len(sites) == 1
        assert sites[0].pk == dive_site.pk

    def test_excludes_inactive_sites(self, db):
        """Excludes inactive sites by default."""
        from django_geo.models import Place

        place = Place.objects.create(
            name="Inactive Site Location",
            latitude=Decimal("25.345678"),
            longitude=Decimal("-80.345678"),
        )
        DiveSite.objects.create(
            name="Inactive Site",
            description="Closed",
            place=place,
            max_depth_meters=20,
            is_active=False,
        )
        sites = list_dive_sites()
        assert len(sites) == 0

    def test_can_filter_by_certification_level(self, dive_site, another_dive_site, padi_agency):
        """Can filter by certification level FK."""
        from primitives_testbed.diveops.models import CertificationLevel

        # Create certification levels
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow_test", name="Open Water", rank=2
        )
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_test", name="Advanced Open Water", rank=3
        )

        # Update sites with certification requirements
        dive_site.min_certification_level = ow_level
        dive_site.save()
        another_dive_site.min_certification_level = aow_level
        another_dive_site.save()

        # Test: sites requiring OW or less (rank <= 2)
        sites = list_dive_sites(max_certification_rank=2)
        assert len(sites) == 1
        assert sites[0].name == "Test Reef"

    def test_returns_inactive_when_requested(self, db):
        """Returns inactive sites when is_active=False."""
        from django_geo.models import Place

        place = Place.objects.create(
            name="Inactive Site Location",
            latitude=Decimal("25.345678"),
            longitude=Decimal("-80.345678"),
        )
        inactive = DiveSite.objects.create(
            name="Inactive Site",
            description="Closed",
            place=place,
            max_depth_meters=20,
            is_active=False,
        )
        sites = list_dive_sites(is_active=False)
        assert len(sites) == 1
        assert sites[0].pk == inactive.pk


@pytest.mark.django_db
class TestListShopTrips:
    """Tests for list_shop_trips selector."""

    def test_returns_shop_trips(self, dive_trip, dive_shop):
        """Returns trips for a dive shop."""
        trips = list_shop_trips(dive_shop)
        assert len(trips) == 1
        assert trips[0].pk == dive_trip.pk

    def test_filters_by_status(self, dive_shop, dive_site, staff_user):
        """Can filter by status."""
        DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=7),
            return_time=timezone.now() + timedelta(days=7, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="cancelled",
            created_by=staff_user,
        )
        trips = list_shop_trips(dive_shop, status="cancelled")
        assert len(trips) == 1
        assert trips[0].status == "cancelled"

    def test_filters_by_from_date(self, dive_shop, dive_site, staff_user):
        """Can filter by from_date."""
        early_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=1),
            return_time=timezone.now() + timedelta(days=1, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="scheduled",
            created_by=staff_user,
        )
        late_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=10),
            return_time=timezone.now() + timedelta(days=10, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="scheduled",
            created_by=staff_user,
        )
        trips = list_shop_trips(dive_shop, from_date=timezone.now() + timedelta(days=5))
        assert len(trips) == 1
        assert trips[0].pk == late_trip.pk

    def test_filters_by_to_date(self, dive_shop, dive_site, staff_user):
        """Can filter by to_date."""
        early_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=1),
            return_time=timezone.now() + timedelta(days=1, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="scheduled",
            created_by=staff_user,
        )
        late_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() + timedelta(days=10),
            return_time=timezone.now() + timedelta(days=10, hours=6),
            max_divers=10,
            price_per_diver=Decimal("100.00"),
            status="scheduled",
            created_by=staff_user,
        )
        trips = list_shop_trips(dive_shop, to_date=timezone.now() + timedelta(days=5))
        assert len(trips) == 1
        assert trips[0].pk == early_trip.pk


@pytest.mark.django_db
class TestGetBooking:
    """Tests for get_booking selector."""

    def test_returns_booking_with_related_data(self, dive_trip, diver, staff_user):
        """Returns booking with related data prefetched."""
        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver,
            booked_by=staff_user,
            status="confirmed",
        )
        result = get_booking(booking.pk)
        assert result is not None
        assert result.pk == booking.pk
        # Check related data is prefetched
        assert result.trip.dive_shop is not None
        assert result.diver.person is not None

    def test_returns_none_for_invalid_id(self, db):
        """Returns None for invalid booking ID."""
        import uuid

        result = get_booking(uuid.uuid4())
        assert result is None
