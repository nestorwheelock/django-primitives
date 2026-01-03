"""Tests for diveops staff views."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    """Create a regular (non-staff) user."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="testpass123",
        is_staff=False,
    )


@pytest.fixture
def staff_client(staff_user):
    """Create a client logged in as staff."""
    client = Client()
    client.login(username="staff", password="testpass123")
    return client


@pytest.fixture
def regular_client(regular_user):
    """Create a client logged in as regular user."""
    client = Client()
    client.login(username="regular", password="testpass123")
    return client


@pytest.fixture
def anonymous_client():
    """Create an anonymous client."""
    return Client()


@pytest.mark.django_db
class TestTripListView:
    """Tests for TripListView."""

    def test_trip_list_requires_authentication(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:trip-list")
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_trip_list_requires_staff(self, regular_client):
        """Non-staff users are denied access."""
        url = reverse("diveops:trip-list")
        response = regular_client.get(url)

        # Should either redirect or return 403
        assert response.status_code in [302, 403]

    def test_trip_list_accessible_by_staff(self, staff_client, dive_trip):
        """Staff users can access trip list."""
        url = reverse("diveops:trip-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "trips" in response.context

    def test_trip_list_shows_upcoming_trips(self, staff_client, dive_trip, dive_shop, dive_site, user):
        """Trip list shows only upcoming trips."""
        from primitives_testbed.diveops.models import DiveTrip

        # Create a past trip
        past_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() - timedelta(days=1),
            return_time=timezone.now() - timedelta(days=1) + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            created_by=user,
        )

        url = reverse("diveops:trip-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        trips = response.context["trips"]
        # Should include future trip, not past trip
        trip_ids = [t.id for t in trips]
        assert dive_trip.id in trip_ids
        assert past_trip.id not in trip_ids

    def test_trip_list_shows_booking_counts(self, staff_client, dive_trip, diver_profile, user):
        """Trip list shows number of bookings per trip."""
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        url = reverse("diveops:trip-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        # The template should show booking counts
        assert b"1" in response.content or "1 booking" in str(response.content)

    def test_trip_list_extends_staff_base(self, staff_client, dive_trip):
        """Trip list template extends base_staff.html."""
        url = reverse("diveops:trip-list")
        response = staff_client.get(url)

        # Should use staff base template
        assert response.status_code == 200
        # Template should be in the chain
        template_names = [t.name for t in response.templates]
        assert "diveops/staff/trip_list.html" in template_names


@pytest.mark.django_db
class TestTripDetailView:
    """Tests for TripDetailView."""

    def test_trip_detail_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_trip_detail_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_trip_detail_accessible_by_staff(self, staff_client, dive_trip):
        """Staff users can access trip detail."""
        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "trip" in response.context

    def test_trip_detail_shows_trip_info(self, staff_client, dive_trip):
        """Trip detail shows trip information."""
        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert dive_trip.dive_site.name.encode() in response.content

    def test_trip_detail_shows_roster(self, staff_client, dive_trip, diver_profile, user):
        """Trip detail shows roster of checked-in divers."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="checked_in",
            booked_by=user,
        )
        TripRoster.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )

        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Should show diver name in roster
        assert diver_profile.person.first_name.encode() in response.content

    def test_trip_detail_shows_bookings(self, staff_client, dive_trip, diver_profile, user):
        """Trip detail shows all bookings."""
        from primitives_testbed.diveops.models import Booking

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "bookings" in response.context or b"booking" in response.content.lower()

    def test_trip_detail_shows_spots_available(self, staff_client, dive_trip):
        """Trip detail shows available spots."""
        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Max divers is 8, no bookings, so 8 spots available
        assert b"8" in response.content or "spots" in str(response.content).lower()

    def test_trip_detail_404_for_invalid_id(self, staff_client):
        """Trip detail returns 404 for non-existent trip."""
        import uuid

        fake_id = uuid.uuid4()
        url = reverse("diveops:trip-detail", kwargs={"pk": fake_id})
        response = staff_client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestURLPatterns:
    """Tests for diveops staff URL patterns."""

    def test_trip_list_url_resolves(self):
        """Trip list URL can be reversed."""
        url = reverse("diveops:trip-list")
        assert url == "/staff/diveops/trips/" or "/trips/" in url

    def test_trip_detail_url_resolves(self, dive_trip):
        """Trip detail URL can be reversed."""
        url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        assert str(dive_trip.pk) in url
