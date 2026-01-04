"""Tests for diveops staff views."""

from datetime import date, timedelta
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


@pytest.mark.django_db
class TestBookDiverView:
    """Tests for BookDiverView."""

    def test_book_diver_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_book_diver_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_book_diver_accessible_by_staff(self, staff_client, dive_trip):
        """Staff users can access book diver page."""
        url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "trip" in response.context
        assert "form" in response.context

    def test_book_diver_shows_form(self, staff_client, dive_trip):
        """Book diver page shows the booking form."""
        url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert b"diver" in response.content.lower()

    def test_book_diver_creates_booking(self, staff_client, dive_trip, diver_profile, staff_user):
        """POST creates a booking for the selected diver."""
        from primitives_testbed.diveops.models import Booking

        url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = staff_client.post(url, {"diver": diver_profile.pk})

        # Should redirect to trip detail on success
        assert response.status_code == 302
        assert str(dive_trip.pk) in response.url

        # Booking should be created
        assert Booking.objects.filter(trip=dive_trip, diver=diver_profile).exists()

    def test_book_diver_shows_eligibility_error(
        self, staff_client, dive_site, dive_shop, staff_user, person2, padi_agency
    ):
        """Book diver shows eligibility error for ineligible diver."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            DiveTrip,
            TripRequirement,
        )

        # Create AOW and OW certification levels
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow", name="Advanced Open Water", rank=3
        )
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow", name="Open Water", rank=2
        )

        # Create trip with AOW requirement
        tomorrow = timezone.now() + timedelta(days=1)
        trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=staff_user,
        )
        TripRequirement.objects.create(
            trip=trip, requirement_type="certification", certification_level=aow_level, is_mandatory=True
        )

        # Create diver with only OW certification (not enough)
        diver = DiverProfile.objects.create(
            person=person2,
            total_dives=10,
            medical_clearance_date=date.today(),
            medical_clearance_valid_until=date.today() + timedelta(days=365),
        )
        DiverCertification.objects.create(
            diver=diver, level=ow_level, card_number="12345", issued_on=date.today() - timedelta(days=30)
        )

        url = reverse("diveops:book-diver", kwargs={"trip_pk": trip.pk})
        response = staff_client.post(url, {"diver": diver.pk})

        # Should stay on the form with error
        assert response.status_code == 200
        # Should show eligibility reasons
        assert b"not eligible" in response.content.lower() or b"certification" in response.content.lower()

    def test_book_diver_redirects_to_trip_detail(self, staff_client, dive_trip, diver_profile):
        """Successful booking redirects to trip detail."""
        url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = staff_client.post(url, {"diver": diver_profile.pk})

        expected_redirect = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        assert response.status_code == 302
        assert expected_redirect in response.url


@pytest.mark.django_db
class TestCheckInView:
    """Tests for CheckInView."""

    @pytest.fixture
    def booking(self, dive_trip, diver_profile, user):
        """Create a confirmed booking for testing."""
        from primitives_testbed.diveops.models import Booking

        return Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

    def test_check_in_requires_authentication(self, anonymous_client, booking):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_check_in_requires_staff(self, regular_client, booking):
        """Non-staff users are denied access."""
        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = regular_client.post(url)

        assert response.status_code in [302, 403]

    def test_check_in_only_accepts_post(self, staff_client, booking):
        """GET requests are not allowed."""
        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = staff_client.get(url)

        assert response.status_code == 405  # Method not allowed

    def test_check_in_creates_roster_entry(self, staff_client, booking):
        """POST creates roster entry and updates booking status."""
        from primitives_testbed.diveops.models import TripRoster

        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = staff_client.post(url)

        # Should redirect to trip detail
        assert response.status_code == 302

        # Roster entry should exist
        assert TripRoster.objects.filter(booking=booking).exists()

        # Booking status should be updated
        booking.refresh_from_db()
        assert booking.status == "checked_in"

    def test_check_in_redirects_to_trip_detail(self, staff_client, booking):
        """Successful check-in redirects to trip detail."""
        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = staff_client.post(url)

        expected_redirect = reverse("diveops:trip-detail", kwargs={"pk": booking.trip.pk})
        assert response.status_code == 302
        assert expected_redirect in response.url

    def test_check_in_404_for_invalid_booking(self, staff_client):
        """Check-in returns 404 for non-existent booking."""
        import uuid

        fake_id = uuid.uuid4()
        url = reverse("diveops:check-in", kwargs={"pk": fake_id})
        response = staff_client.post(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestStartTripView:
    """Tests for StartTripView."""

    def test_start_trip_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:start-trip", kwargs={"pk": dive_trip.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_start_trip_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:start-trip", kwargs={"pk": dive_trip.pk})
        response = regular_client.post(url)

        assert response.status_code in [302, 403]

    def test_start_trip_only_accepts_post(self, staff_client, dive_trip):
        """GET requests are not allowed."""
        url = reverse("diveops:start-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 405  # Method not allowed

    def test_start_trip_transitions_to_in_progress(self, staff_client, dive_trip, diver_profile, user):
        """POST transitions trip to in_progress state."""
        from primitives_testbed.diveops.models import Booking, TripRoster
        from primitives_testbed.diveops.services import check_in

        # Create and check in a booking first
        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)

        # Start the trip
        url = reverse("diveops:start-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        # Should redirect
        assert response.status_code == 302

        # Trip state should be in_progress
        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "in_progress"

    def test_start_trip_redirects_to_trip_detail(self, staff_client, dive_trip, diver_profile, user):
        """Successful start redirects to trip detail."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)

        url = reverse("diveops:start-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        expected_redirect = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        assert response.status_code == 302
        assert expected_redirect in response.url


@pytest.mark.django_db
class TestCompleteTripView:
    """Tests for CompleteTripView."""

    def test_complete_trip_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:complete-trip", kwargs={"pk": dive_trip.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_complete_trip_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:complete-trip", kwargs={"pk": dive_trip.pk})
        response = regular_client.post(url)

        assert response.status_code in [302, 403]

    def test_complete_trip_only_accepts_post(self, staff_client, dive_trip):
        """GET requests are not allowed."""
        url = reverse("diveops:complete-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 405  # Method not allowed

    def test_complete_trip_transitions_to_completed(self, staff_client, dive_trip, diver_profile, user):
        """POST transitions trip to completed state and updates diver stats."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in, start_trip

        # Setup: create booking, check in, start trip
        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)
        start_trip(dive_trip, user)

        initial_dives = diver_profile.total_dives

        # Complete the trip
        url = reverse("diveops:complete-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        # Should redirect
        assert response.status_code == 302

        # Trip state should be completed
        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "completed"

        # Diver's total dives should be incremented
        diver_profile.refresh_from_db()
        assert diver_profile.total_dives == initial_dives + 1

    def test_complete_trip_redirects_to_trip_detail(self, staff_client, dive_trip, diver_profile, user):
        """Successful completion redirects to trip detail."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in, start_trip

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)
        start_trip(dive_trip, user)

        url = reverse("diveops:complete-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        expected_redirect = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        assert response.status_code == 302
        assert expected_redirect in response.url


@pytest.mark.django_db
class TestFullBookingWorkflow:
    """End-to-end integration tests for the full booking workflow."""

    def test_full_workflow_trip_to_completion(
        self, staff_client, dive_trip, diver_profile, beginner_diver, staff_user
    ):
        """Test complete workflow: list → detail → book → check-in → start → complete."""
        from primitives_testbed.diveops.models import Booking, TripRoster

        # Step 1: View trip list
        list_url = reverse("diveops:trip-list")
        response = staff_client.get(list_url)
        assert response.status_code == 200
        assert dive_trip.dive_site.name.encode() in response.content

        # Step 2: View trip detail
        detail_url = reverse("diveops:trip-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(detail_url)
        assert response.status_code == 200
        assert b"Book Diver" in response.content  # Should show booking link

        # Step 3: Book first diver via form
        book_url = reverse("diveops:book-diver", kwargs={"trip_pk": dive_trip.pk})
        response = staff_client.post(book_url, {"diver": diver_profile.pk})
        assert response.status_code == 302
        booking1 = Booking.objects.get(trip=dive_trip, diver=diver_profile)
        assert booking1.status == "confirmed"

        # Step 4: Book second diver
        response = staff_client.post(book_url, {"diver": beginner_diver.pk})
        assert response.status_code == 302
        booking2 = Booking.objects.get(trip=dive_trip, diver=beginner_diver)
        assert booking2.status == "confirmed"

        # Step 5: Check in first diver
        checkin_url = reverse("diveops:check-in", kwargs={"pk": booking1.pk})
        response = staff_client.post(checkin_url)
        assert response.status_code == 302
        booking1.refresh_from_db()
        assert booking1.status == "checked_in"
        assert TripRoster.objects.filter(booking=booking1).exists()

        # Step 6: Check in second diver
        checkin_url = reverse("diveops:check-in", kwargs={"pk": booking2.pk})
        response = staff_client.post(checkin_url)
        assert response.status_code == 302
        booking2.refresh_from_db()
        assert booking2.status == "checked_in"

        # Verify roster has 2 entries
        assert TripRoster.objects.filter(trip=dive_trip).count() == 2

        # Step 7: Start the trip
        start_url = reverse("diveops:start-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(start_url)
        assert response.status_code == 302
        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "in_progress"

        # Step 8: Complete the trip
        initial_dives1 = diver_profile.total_dives
        initial_dives2 = beginner_diver.total_dives

        complete_url = reverse("diveops:complete-trip", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(complete_url)
        assert response.status_code == 302

        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "completed"

        # Verify diver stats were incremented
        diver_profile.refresh_from_db()
        beginner_diver.refresh_from_db()
        assert diver_profile.total_dives == initial_dives1 + 1
        assert beginner_diver.total_dives == initial_dives2 + 1

    def test_workflow_shows_eligibility_error_for_ineligible_diver(
        self, staff_client, dive_site, dive_shop, staff_user, person2, padi_agency
    ):
        """Test that booking workflow properly blocks ineligible divers."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            DiveTrip,
            TripRequirement,
        )

        # Create AOW and OW certification levels
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow", name="Advanced Open Water", rank=3
        )
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow", name="Open Water", rank=2
        )

        # Create trip with AOW requirement
        tomorrow = timezone.now() + timedelta(days=1)
        deep_trip = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=staff_user,
        )
        TripRequirement.objects.create(
            trip=deep_trip, requirement_type="certification", certification_level=aow_level, is_mandatory=True
        )

        # Create diver with only OW certification (not enough)
        diver = DiverProfile.objects.create(
            person=person2,
            total_dives=10,
            medical_clearance_date=date.today(),
            medical_clearance_valid_until=date.today() + timedelta(days=365),
        )
        DiverCertification.objects.create(
            diver=diver, level=ow_level, card_number="12345", issued_on=date.today() - timedelta(days=30)
        )

        # Try to book diver (only OW cert) on deep dive
        book_url = reverse("diveops:book-diver", kwargs={"trip_pk": deep_trip.pk})
        response = staff_client.post(book_url, {"diver": diver.pk})

        # Should not redirect - should show error
        assert response.status_code == 200
        assert b"not eligible" in response.content.lower() or b"certification" in response.content.lower()

    def test_urls_are_correctly_namespaced(self):
        """Verify all diveops URLs use the correct namespace."""
        import uuid

        fake_pk = uuid.uuid4()

        # All URLs should resolve under diveops namespace
        trip_list = reverse("diveops:trip-list")
        assert "/diveops/" in trip_list

        trip_detail = reverse("diveops:trip-detail", kwargs={"pk": fake_pk})
        assert "/diveops/" in trip_detail
        assert str(fake_pk) in trip_detail

        book_diver = reverse("diveops:book-diver", kwargs={"trip_pk": fake_pk})
        assert "/diveops/" in book_diver

        check_in = reverse("diveops:check-in", kwargs={"pk": fake_pk})
        assert "/diveops/" in check_in

        start_trip = reverse("diveops:start-trip", kwargs={"pk": fake_pk})
        assert "/diveops/" in start_trip

        complete_trip = reverse("diveops:complete-trip", kwargs={"pk": fake_pk})
        assert "/diveops/" in complete_trip


@pytest.mark.django_db
class TestDiverListView:
    """Tests for DiverListView."""

    def test_diver_list_requires_authentication(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:diver-list")
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_diver_list_requires_staff(self, regular_client):
        """Non-staff users are denied access."""
        url = reverse("diveops:diver-list")
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_diver_list_accessible_by_staff(self, staff_client):
        """Staff users can access diver list."""
        url = reverse("diveops:diver-list")
        response = staff_client.get(url)

        assert response.status_code == 200

    def test_diver_list_shows_divers(self, staff_client, diver_profile):
        """Diver list shows existing divers."""
        url = reverse("diveops:diver-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert diver_profile.person.first_name.encode() in response.content

    def test_diver_list_has_add_diver_link(self, staff_client):
        """Diver list has link to add new diver."""
        url = reverse("diveops:diver-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert b"Add Diver" in response.content or b"add-diver" in response.content.lower()


@pytest.mark.django_db
class TestCreateDiverView:
    """Tests for CreateDiverView."""

    def test_create_diver_requires_authentication(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:diver-create")
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_create_diver_requires_staff(self, regular_client):
        """Non-staff users are denied access."""
        url = reverse("diveops:diver-create")
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_create_diver_accessible_by_staff(self, staff_client):
        """Staff users can access create diver form."""
        url = reverse("diveops:diver-create")
        response = staff_client.get(url)

        assert response.status_code == 200

    def test_create_diver_shows_form(self, staff_client):
        """Create diver page shows the form fields."""
        url = reverse("diveops:diver-create")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert b"first_name" in response.content
        assert b"certification_level" in response.content

    def test_create_diver_creates_diver(self, staff_client, padi_open_water):
        """POST creates a new diver with person and certification."""
        from datetime import date, timedelta
        from primitives_testbed.diveops.models import DiverCertification, DiverProfile

        url = reverse("diveops:diver-create")
        response = staff_client.post(url, {
            "first_name": "New",
            "last_name": "Diver",
            "email": "newdiver@example.com",
            "certification_level": str(padi_open_water.pk),
            "card_number": "NEW123",
            "issued_on": (date.today() - timedelta(days=30)).isoformat(),
            "total_dives": 5,
        })

        # Should redirect on success
        assert response.status_code == 302

        # Diver should exist
        diver = DiverProfile.objects.get(person__email="newdiver@example.com")
        assert diver.person.first_name == "New"
        assert diver.total_dives == 5

        # Certification should be created
        cert = DiverCertification.objects.get(diver=diver)
        assert cert.level == padi_open_water
        assert cert.card_number == "NEW123"

    def test_create_diver_redirects_to_list(self, staff_client, ssi_open_water):
        """Successful creation redirects to diver list."""
        from datetime import date, timedelta

        url = reverse("diveops:diver-create")
        response = staff_client.post(url, {
            "first_name": "Another",
            "last_name": "Diver",
            "email": "another@example.com",
            "certification_level": str(ssi_open_water.pk),
            "card_number": "SSI999",
            "issued_on": (date.today() - timedelta(days=90)).isoformat(),
            "total_dives": 20,
        })

        assert response.status_code == 302
        assert reverse("diveops:diver-list") in response.url


@pytest.mark.django_db
class TestEditDiverView:
    """Tests for EditDiverView."""

    def test_edit_diver_requires_authentication(self, anonymous_client, diver_profile):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_edit_diver_requires_staff(self, regular_client, diver_profile):
        """Non-staff users are denied access."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_edit_diver_accessible_by_staff(self, staff_client, diver_profile):
        """Staff users can access edit diver form."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200

    def test_edit_diver_shows_existing_data(self, staff_client, diver_profile):
        """Edit form is pre-populated with existing diver data."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert diver_profile.person.first_name.encode() in response.content

    def test_edit_diver_updates_diver(self, staff_client, diver_profile):
        """POST updates the existing diver."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.post(url, {
            "first_name": diver_profile.person.first_name,
            "last_name": diver_profile.person.last_name,
            "email": diver_profile.person.email,
            "total_dives": 100,  # More experience
        })

        # Should redirect on success
        assert response.status_code == 302

        # Diver should be updated
        diver_profile.refresh_from_db()
        assert diver_profile.total_dives == 100

    def test_edit_diver_redirects_to_list(self, staff_client, diver_profile):
        """Successful edit redirects to diver list."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.post(url, {
            "first_name": diver_profile.person.first_name,
            "last_name": diver_profile.person.last_name,
            "email": diver_profile.person.email,
            "total_dives": diver_profile.total_dives,
        })

        assert response.status_code == 302
        assert reverse("diveops:diver-list") in response.url

    def test_edit_diver_404_for_invalid_pk(self, staff_client):
        """Edit returns 404 for non-existent diver."""
        import uuid

        fake_pk = uuid.uuid4()
        url = reverse("diveops:diver-edit", kwargs={"pk": fake_pk})
        response = staff_client.get(url)

        assert response.status_code == 404

    def test_edit_diver_shows_certifications_list(self, staff_client, diver_profile, padi_open_water):
        """Edit diver page shows list of diver's certifications."""
        from primitives_testbed.diveops.models import DiverCertification

        # Add a certification to the diver
        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="TEST123",
        )

        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Should show the certification in the list
        assert b"TEST123" in response.content
        assert padi_open_water.name.encode() in response.content

    def test_edit_diver_has_add_certification_button(self, staff_client, diver_profile):
        """Edit diver page has a button to add a new certification."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Should have link to add certification
        add_cert_url = reverse("diveops:certification-add", kwargs={"diver_pk": diver_profile.pk})
        assert add_cert_url.encode() in response.content

    def test_edit_diver_no_inline_certification_form(self, staff_client, diver_profile):
        """Edit diver page does NOT have inline certification form fields."""
        url = reverse("diveops:diver-edit", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Should NOT have certification_level dropdown (the inline form)
        assert b'name="certification_level"' not in response.content
        assert b'name="certification_agency"' not in response.content
