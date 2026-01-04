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
class TestExcursionListView:
    """Tests for ExcursionListView."""

    def test_excursion_list_requires_authentication(self, anonymous_client):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:excursion-list")
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_excursion_list_requires_staff(self, regular_client):
        """Non-staff users are denied access."""
        url = reverse("diveops:excursion-list")
        response = regular_client.get(url)

        # Should either redirect or return 403
        assert response.status_code in [302, 403]

    def test_excursion_list_accessible_by_staff(self, staff_client, dive_trip):
        """Staff users can access excursion list."""
        url = reverse("diveops:excursion-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "excursions" in response.context

    def test_excursion_list_shows_upcoming_excursions(self, staff_client, dive_trip, dive_shop, dive_site, user):
        """Excursion list shows only upcoming excursions."""
        from primitives_testbed.diveops.models import Excursion

        # Create a past excursion
        past_excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=timezone.now() - timedelta(days=1),
            return_time=timezone.now() - timedelta(days=1) + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            created_by=user,
        )

        url = reverse("diveops:excursion-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        excursions = response.context["excursions"]
        # Should include future excursion, not past excursion
        excursion_ids = [e.id for e in excursions]
        assert dive_trip.id in excursion_ids
        assert past_excursion.id not in excursion_ids

    def test_excursion_list_shows_booking_counts(self, staff_client, dive_trip, diver_profile, user):
        """Excursion list shows number of bookings per excursion."""
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        url = reverse("diveops:excursion-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        # The template should show booking counts
        assert b"1" in response.content or "1 booking" in str(response.content)

    def test_excursion_list_extends_staff_base(self, staff_client, dive_trip):
        """Excursion list template extends base_staff.html."""
        url = reverse("diveops:excursion-list")
        response = staff_client.get(url)

        # Should use staff base template
        assert response.status_code == 200
        # Template should be in the chain
        template_names = [t.name for t in response.templates]
        assert "diveops/staff/excursion_list.html" in template_names


@pytest.mark.django_db
class TestExcursionDetailView:
    """Tests for ExcursionDetailView."""

    def test_excursion_detail_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_excursion_detail_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_excursion_detail_accessible_by_staff(self, staff_client, dive_trip):
        """Staff users can access excursion detail."""
        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "excursion" in response.context

    def test_excursion_detail_shows_excursion_info(self, staff_client, dive_trip):
        """Excursion detail shows excursion information."""
        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert dive_trip.dive_site.name.encode() in response.content

    def test_excursion_detail_shows_roster(self, staff_client, dive_trip, diver_profile, user):
        """Excursion detail shows roster of checked-in divers."""
        from primitives_testbed.diveops.models import Booking, ExcursionRoster

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="checked_in",
            booked_by=user,
        )
        ExcursionRoster.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )

        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Should show diver name in roster
        assert diver_profile.person.first_name.encode() in response.content

    def test_excursion_detail_shows_bookings(self, staff_client, dive_trip, diver_profile, user):
        """Excursion detail shows all bookings."""
        from primitives_testbed.diveops.models import Booking

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "bookings" in response.context or b"booking" in response.content.lower()

    def test_excursion_detail_shows_spots_available(self, staff_client, dive_trip):
        """Excursion detail shows available spots."""
        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        # Max divers is 8, no bookings, so 8 spots available
        assert b"8" in response.content or "spots" in str(response.content).lower()

    def test_excursion_detail_404_for_invalid_id(self, staff_client):
        """Excursion detail returns 404 for non-existent excursion."""
        import uuid

        fake_id = uuid.uuid4()
        url = reverse("diveops:excursion-detail", kwargs={"pk": fake_id})
        response = staff_client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestURLPatterns:
    """Tests for diveops staff URL patterns."""

    def test_excursion_list_url_resolves(self):
        """Excursion list URL can be reversed."""
        url = reverse("diveops:excursion-list")
        assert url == "/staff/diveops/excursions/" or "/excursions/" in url

    def test_excursion_detail_url_resolves(self, dive_trip):
        """Excursion detail URL can be reversed."""
        url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        assert str(dive_trip.pk) in url


@pytest.mark.django_db
class TestBookDiverView:
    """Tests for BookDiverView."""

    def test_book_diver_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = anonymous_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_book_diver_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = regular_client.get(url)

        assert response.status_code in [302, 403]

    def test_book_diver_accessible_by_staff(self, staff_client, dive_trip):
        """Staff users can access book diver page."""
        url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "excursion" in response.context
        assert "form" in response.context

    def test_book_diver_shows_form(self, staff_client, dive_trip):
        """Book diver page shows the booking form."""
        url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert b"diver" in response.content.lower()

    def test_book_diver_creates_booking(self, staff_client, dive_trip, diver_profile, staff_user):
        """POST creates a booking for the selected diver."""
        from primitives_testbed.diveops.models import Booking

        url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = staff_client.post(url, {"diver": diver_profile.pk})

        # Should redirect to excursion detail on success
        assert response.status_code == 302
        assert str(dive_trip.pk) in response.url

        # Booking should be created
        assert Booking.objects.filter(excursion=dive_trip, diver=diver_profile).exists()

    def test_book_diver_shows_eligibility_error(
        self, staff_client, dive_site, dive_shop, staff_user, person2, padi_agency
    ):
        """Book diver shows eligibility error for ineligible diver."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            Excursion,
            ExcursionRequirement,
        )

        # Create AOW and OW certification levels
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow", name="Advanced Open Water", rank=3
        )
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow", name="Open Water", rank=2
        )

        # Create excursion with AOW requirement
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=staff_user,
        )
        ExcursionRequirement.objects.create(
            excursion=excursion, requirement_type="certification", certification_level=aow_level, is_mandatory=True
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

        url = reverse("diveops:book-diver", kwargs={"excursion_pk": excursion.pk})
        response = staff_client.post(url, {"diver": diver.pk})

        # Should stay on the form with error
        assert response.status_code == 200
        # Should show eligibility reasons
        assert b"not eligible" in response.content.lower() or b"certification" in response.content.lower()

    def test_book_diver_redirects_to_excursion_detail(self, staff_client, dive_trip, diver_profile):
        """Successful booking redirects to excursion detail."""
        url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = staff_client.post(url, {"diver": diver_profile.pk})

        expected_redirect = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
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
            excursion=dive_trip,
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
        from primitives_testbed.diveops.models import ExcursionRoster

        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = staff_client.post(url)

        # Should redirect to excursion detail
        assert response.status_code == 302

        # Roster entry should exist
        assert ExcursionRoster.objects.filter(booking=booking).exists()

        # Booking status should be updated
        booking.refresh_from_db()
        assert booking.status == "checked_in"

    def test_check_in_redirects_to_excursion_detail(self, staff_client, booking):
        """Successful check-in redirects to excursion detail."""
        url = reverse("diveops:check-in", kwargs={"pk": booking.pk})
        response = staff_client.post(url)

        expected_redirect = reverse("diveops:excursion-detail", kwargs={"pk": booking.excursion.pk})
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
class TestStartExcursionView:
    """Tests for StartExcursionView."""

    def test_start_excursion_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:start-excursion", kwargs={"pk": dive_trip.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_start_excursion_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:start-excursion", kwargs={"pk": dive_trip.pk})
        response = regular_client.post(url)

        assert response.status_code in [302, 403]

    def test_start_excursion_only_accepts_post(self, staff_client, dive_trip):
        """GET requests are not allowed."""
        url = reverse("diveops:start-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 405  # Method not allowed

    def test_start_excursion_transitions_to_in_progress(self, staff_client, dive_trip, diver_profile, user):
        """POST transitions excursion to in_progress state."""
        from primitives_testbed.diveops.models import Booking, ExcursionRoster
        from primitives_testbed.diveops.services import check_in

        # Create and check in a booking first
        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)

        # Start the excursion
        url = reverse("diveops:start-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        # Should redirect
        assert response.status_code == 302

        # Excursion state should be in_progress
        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "in_progress"

    def test_start_excursion_redirects_to_excursion_detail(self, staff_client, dive_trip, diver_profile, user):
        """Successful start redirects to excursion detail."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)

        url = reverse("diveops:start-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        expected_redirect = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        assert response.status_code == 302
        assert expected_redirect in response.url


@pytest.mark.django_db
class TestCompleteExcursionView:
    """Tests for CompleteExcursionView."""

    def test_complete_excursion_requires_authentication(self, anonymous_client, dive_trip):
        """Anonymous users are redirected to login."""
        url = reverse("diveops:complete-excursion", kwargs={"pk": dive_trip.pk})
        response = anonymous_client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_complete_excursion_requires_staff(self, regular_client, dive_trip):
        """Non-staff users are denied access."""
        url = reverse("diveops:complete-excursion", kwargs={"pk": dive_trip.pk})
        response = regular_client.post(url)

        assert response.status_code in [302, 403]

    def test_complete_excursion_only_accepts_post(self, staff_client, dive_trip):
        """GET requests are not allowed."""
        url = reverse("diveops:complete-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(url)

        assert response.status_code == 405  # Method not allowed

    def test_complete_excursion_transitions_to_completed(self, staff_client, dive_trip, diver_profile, user):
        """POST transitions excursion to completed state and updates diver stats."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in, start_excursion

        # Setup: create booking, check in, start excursion
        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)
        start_excursion(dive_trip, user)

        initial_dives = diver_profile.total_dives

        # Complete the excursion
        url = reverse("diveops:complete-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        # Should redirect
        assert response.status_code == 302

        # Excursion state should be completed
        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "completed"

        # Diver's total dives should be incremented
        diver_profile.refresh_from_db()
        assert diver_profile.total_dives == initial_dives + 1

    def test_complete_excursion_redirects_to_excursion_detail(self, staff_client, dive_trip, diver_profile, user):
        """Successful completion redirects to excursion detail."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in, start_excursion

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )
        check_in(booking, user)
        start_excursion(dive_trip, user)

        url = reverse("diveops:complete-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(url)

        expected_redirect = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        assert response.status_code == 302
        assert expected_redirect in response.url


@pytest.mark.django_db
class TestFullBookingWorkflow:
    """End-to-end integration tests for the full booking workflow."""

    def test_full_workflow_excursion_to_completion(
        self, staff_client, dive_trip, diver_profile, beginner_diver, staff_user
    ):
        """Test complete workflow: list → detail → book → check-in → start → complete."""
        from primitives_testbed.diveops.models import Booking, ExcursionRoster

        # Step 1: View excursion list
        list_url = reverse("diveops:excursion-list")
        response = staff_client.get(list_url)
        assert response.status_code == 200
        assert dive_trip.dive_site.name.encode() in response.content

        # Step 2: View excursion detail
        detail_url = reverse("diveops:excursion-detail", kwargs={"pk": dive_trip.pk})
        response = staff_client.get(detail_url)
        assert response.status_code == 200
        assert b"Book Diver" in response.content  # Should show booking link

        # Step 3: Book first diver via form
        book_url = reverse("diveops:book-diver", kwargs={"excursion_pk": dive_trip.pk})
        response = staff_client.post(book_url, {"diver": diver_profile.pk})
        assert response.status_code == 302
        booking1 = Booking.objects.get(excursion=dive_trip, diver=diver_profile)
        assert booking1.status == "confirmed"

        # Step 4: Book second diver
        response = staff_client.post(book_url, {"diver": beginner_diver.pk})
        assert response.status_code == 302
        booking2 = Booking.objects.get(excursion=dive_trip, diver=beginner_diver)
        assert booking2.status == "confirmed"

        # Step 5: Check in first diver
        checkin_url = reverse("diveops:check-in", kwargs={"pk": booking1.pk})
        response = staff_client.post(checkin_url)
        assert response.status_code == 302
        booking1.refresh_from_db()
        assert booking1.status == "checked_in"
        assert ExcursionRoster.objects.filter(booking=booking1).exists()

        # Step 6: Check in second diver
        checkin_url = reverse("diveops:check-in", kwargs={"pk": booking2.pk})
        response = staff_client.post(checkin_url)
        assert response.status_code == 302
        booking2.refresh_from_db()
        assert booking2.status == "checked_in"

        # Verify roster has 2 entries
        assert ExcursionRoster.objects.filter(excursion=dive_trip).count() == 2

        # Step 7: Start the excursion
        start_url = reverse("diveops:start-excursion", kwargs={"pk": dive_trip.pk})
        response = staff_client.post(start_url)
        assert response.status_code == 302
        dive_trip.refresh_from_db()
        assert dive_trip.encounter.state == "in_progress"

        # Step 8: Complete the excursion
        initial_dives1 = diver_profile.total_dives
        initial_dives2 = beginner_diver.total_dives

        complete_url = reverse("diveops:complete-excursion", kwargs={"pk": dive_trip.pk})
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
            Excursion,
            ExcursionRequirement,
        )

        # Create AOW and OW certification levels
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow", name="Advanced Open Water", rank=3
        )
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow", name="Open Water", rank=2
        )

        # Create excursion with AOW requirement
        tomorrow = timezone.now() + timedelta(days=1)
        deep_excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=staff_user,
        )
        ExcursionRequirement.objects.create(
            excursion=deep_excursion, requirement_type="certification", certification_level=aow_level, is_mandatory=True
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
        book_url = reverse("diveops:book-diver", kwargs={"excursion_pk": deep_excursion.pk})
        response = staff_client.post(book_url, {"diver": diver.pk})

        # Should not redirect - should show error
        assert response.status_code == 200
        assert b"not eligible" in response.content.lower() or b"certification" in response.content.lower()

    def test_urls_are_correctly_namespaced(self):
        """Verify all diveops URLs use the correct namespace."""
        import uuid

        fake_pk = uuid.uuid4()

        # All URLs should resolve under diveops namespace
        excursion_list = reverse("diveops:excursion-list")
        assert "/diveops/" in excursion_list

        excursion_detail = reverse("diveops:excursion-detail", kwargs={"pk": fake_pk})
        assert "/diveops/" in excursion_detail
        assert str(fake_pk) in excursion_detail

        book_diver = reverse("diveops:book-diver", kwargs={"excursion_pk": fake_pk})
        assert "/diveops/" in book_diver

        check_in = reverse("diveops:check-in", kwargs={"pk": fake_pk})
        assert "/diveops/" in check_in

        start_excursion = reverse("diveops:start-excursion", kwargs={"pk": fake_pk})
        assert "/diveops/" in start_excursion

        complete_excursion = reverse("diveops:complete-excursion", kwargs={"pk": fake_pk})
        assert "/diveops/" in complete_excursion


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


@pytest.mark.django_db
class TestDashboardView:
    """Tests for the staff dashboard view."""

    def test_dashboard_requires_staff(self, anonymous_client):
        """Dashboard requires staff authentication."""
        url = reverse("diveops:dashboard")
        response = anonymous_client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_dashboard_accessible_to_staff(self, staff_client):
        """Staff users can access the dashboard."""
        url = reverse("diveops:dashboard")
        response = staff_client.get(url)
        assert response.status_code == 200

    def test_dashboard_shows_upcoming_excursions(self, staff_client, dive_trip):
        """Dashboard displays upcoming excursions."""
        url = reverse("diveops:dashboard")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "upcoming_excursions" in response.context
        assert "upcoming_excursions_count" in response.context

    def test_dashboard_shows_diver_count(self, staff_client, diver_profile):
        """Dashboard displays diver count."""
        url = reverse("diveops:dashboard")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "diver_count" in response.context
        assert response.context["diver_count"] >= 1

    def test_dashboard_shows_todays_excursions(self, staff_client):
        """Dashboard displays today's excursions context."""
        url = reverse("diveops:dashboard")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "todays_excursions" in response.context

    def test_dashboard_shows_pending_bookings(self, staff_client):
        """Dashboard displays pending bookings count."""
        url = reverse("diveops:dashboard")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "pending_bookings_count" in response.context


@pytest.mark.django_db
class TestDiverDetailView:
    """Tests for the diver detail view."""

    def test_diver_detail_requires_staff(self, anonymous_client, diver_profile):
        """Diver detail requires staff authentication."""
        url = reverse("diveops:diver-detail", kwargs={"pk": diver_profile.pk})
        response = anonymous_client.get(url)
        assert response.status_code == 302

    def test_diver_detail_accessible_to_staff(self, staff_client, diver_profile):
        """Staff can access diver detail."""
        url = reverse("diveops:diver-detail", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)
        assert response.status_code == 200

    def test_diver_detail_shows_certifications(self, staff_client, diver_profile):
        """Diver detail shows certifications in context."""
        url = reverse("diveops:diver-detail", kwargs={"pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "certifications" in response.context

    def test_diver_detail_404_for_invalid_pk(self, staff_client):
        """Diver detail returns 404 for invalid PK."""
        import uuid
        url = reverse("diveops:diver-detail", kwargs={"pk": uuid.uuid4()})
        response = staff_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestAddCertificationView:
    """Tests for adding certifications."""

    def test_add_certification_requires_staff(self, anonymous_client, diver_profile):
        """Add certification requires staff authentication."""
        url = reverse("diveops:certification-add", kwargs={"diver_pk": diver_profile.pk})
        response = anonymous_client.get(url)
        assert response.status_code == 302

    def test_add_certification_form_displayed(self, staff_client, diver_profile, padi_agency):
        """Add certification form is displayed."""
        url = reverse("diveops:certification-add", kwargs={"diver_pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert "diver" in response.context
        assert response.context["is_create"] is True

    def test_add_certification_shows_agencies(self, staff_client, diver_profile, padi_agency):
        """Add certification shows available agencies."""
        url = reverse("diveops:certification-add", kwargs={"diver_pk": diver_profile.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "agencies" in response.context

    def test_add_certification_submit(self, staff_client, diver_profile, padi_open_water):
        """Add certification via POST."""
        url = reverse("diveops:certification-add", kwargs={"diver_pk": diver_profile.pk})
        data = {
            "diver": diver_profile.pk,
            "level": padi_open_water.pk,
            "card_number": "TEST123",
            "issued_on": date.today().isoformat(),
        }
        response = staff_client.post(url, data)

        # Should redirect to diver detail on success
        assert response.status_code == 302
        assert str(diver_profile.pk) in response.url


@pytest.mark.django_db
class TestEditCertificationView:
    """Tests for editing certifications."""

    @pytest.fixture
    def certification(self, diver_profile, padi_open_water, staff_user):
        """Create a certification for testing."""
        from primitives_testbed.diveops.models import DiverCertification

        return DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="EDIT123",
            issued_on=date.today(),
        )

    def test_edit_certification_requires_staff(self, anonymous_client, certification):
        """Edit certification requires staff authentication."""
        url = reverse("diveops:certification-edit", kwargs={"pk": certification.pk})
        response = anonymous_client.get(url)
        assert response.status_code == 302

    def test_edit_certification_form_displayed(self, staff_client, certification):
        """Edit certification form is displayed."""
        url = reverse("diveops:certification-edit", kwargs={"pk": certification.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "form" in response.context

    def test_edit_certification_submit(self, staff_client, certification):
        """Edit certification via POST updates the certification."""
        url = reverse("diveops:certification-edit", kwargs={"pk": certification.pk})
        data = {
            "diver": certification.diver.pk,
            "level": certification.level.pk,
            "card_number": "UPDATED123",
            "issued_on": date.today().isoformat(),
        }
        response = staff_client.post(url, data)

        # Should redirect to diver detail on success
        assert response.status_code == 302
        assert str(certification.diver.pk) in response.url

        # Certification should be updated
        certification.refresh_from_db()
        assert certification.card_number == "UPDATED123"

    def test_edit_certification_context_has_agencies(self, staff_client, certification, padi_agency):
        """Edit certification context includes agencies."""
        url = reverse("diveops:certification-edit", kwargs={"pk": certification.pk})
        response = staff_client.get(url)

        assert response.status_code == 200
        assert "agencies" in response.context
        assert response.context["is_create"] is False


@pytest.mark.django_db
class TestDeleteCertificationView:
    """Tests for deleting certifications."""

    @pytest.fixture
    def certification(self, diver_profile, padi_open_water):
        """Create a certification for testing."""
        from primitives_testbed.diveops.models import DiverCertification

        return DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="DELETE123",
            issued_on=date.today(),
        )

    def test_delete_certification_requires_staff(self, anonymous_client, certification):
        """Delete certification requires staff authentication."""
        url = reverse("diveops:certification-delete", kwargs={"pk": certification.pk})
        response = anonymous_client.post(url)
        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_delete_certification_requires_post(self, staff_client, certification):
        """Delete certification only accepts POST."""
        url = reverse("diveops:certification-delete", kwargs={"pk": certification.pk})
        response = staff_client.get(url)
        assert response.status_code == 405  # Method not allowed

    def test_delete_certification_soft_deletes(self, staff_client, certification):
        """Delete certification soft-deletes the record."""
        url = reverse("diveops:certification-delete", kwargs={"pk": certification.pk})
        response = staff_client.post(url)

        # Should redirect to diver detail
        assert response.status_code == 302
        assert str(certification.diver.pk) in response.url

        # Certification should be soft-deleted
        certification.refresh_from_db()
        assert certification.deleted_at is not None


@pytest.mark.django_db
class TestVerifyCertificationView:
    """Tests for verifying/unverifying certifications."""

    @pytest.fixture
    def certification(self, diver_profile, padi_open_water):
        """Create an unverified certification for testing."""
        from primitives_testbed.diveops.models import DiverCertification

        return DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="VERIFY123",
            issued_on=date.today(),
            is_verified=False,
        )

    def test_verify_certification_requires_staff(self, anonymous_client, certification):
        """Verify certification requires staff authentication."""
        url = reverse("diveops:certification-verify", kwargs={"pk": certification.pk})
        response = anonymous_client.post(url)
        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_verify_certification_requires_post(self, staff_client, certification):
        """Verify certification only accepts POST."""
        url = reverse("diveops:certification-verify", kwargs={"pk": certification.pk})
        response = staff_client.get(url)
        assert response.status_code == 405  # Method not allowed

    def test_verify_certification_verifies_unverified(self, staff_client, certification):
        """POST verifies an unverified certification."""
        assert certification.is_verified is False

        url = reverse("diveops:certification-verify", kwargs={"pk": certification.pk})
        response = staff_client.post(url)

        # Should redirect to diver detail
        assert response.status_code == 302
        assert str(certification.diver.pk) in response.url

        # Certification should now be verified
        certification.refresh_from_db()
        assert certification.is_verified is True

    def test_verify_certification_unverifies_verified(self, staff_client, certification, staff_user):
        """POST unverifies a verified certification."""
        # First verify it
        certification.is_verified = True
        certification.verified_by = staff_user
        certification.save()

        url = reverse("diveops:certification-verify", kwargs={"pk": certification.pk})
        response = staff_client.post(url)

        # Should redirect to diver detail
        assert response.status_code == 302

        # Certification should now be unverified
        certification.refresh_from_db()
        assert certification.is_verified is False

    def test_verify_shows_error_on_certification_error(self, staff_client, certification):
        """Verify view shows error message when CertificationError raised (lines 433-434)."""
        from unittest.mock import patch

        from primitives_testbed.diveops.exceptions import CertificationError

        url = reverse("diveops:certification-verify", kwargs={"pk": certification.pk})

        # Mock at services module since it's imported inside the view method
        with patch(
            "primitives_testbed.diveops.services.verify_certification",
            side_effect=CertificationError("Test error message"),
        ):
            response = staff_client.post(url, follow=True)

        # Should redirect to diver detail with error message
        assert response.status_code == 200  # After redirect
        # Check error message in response
        messages_list = list(response.context.get("messages", []))
        assert len(messages_list) > 0
        assert any("Test error message" in str(m) for m in messages_list)


@pytest.mark.django_db
class TestAuditLogView:
    """Tests for AuditLogView (lines 450-458)."""

    def test_audit_log_requires_staff(self, anonymous_client):
        """Audit log requires staff authentication."""
        url = reverse("diveops:audit-log")
        response = anonymous_client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url or "/accounts/login/" in response.url

    def test_audit_log_accessible_by_staff(self, staff_client):
        """Staff can access audit log view."""
        url = reverse("diveops:audit-log")
        response = staff_client.get(url)
        assert response.status_code == 200

    def test_audit_log_shows_entries(self, staff_client, staff_user, diver_profile, padi_open_water):
        """Audit log shows audit entries."""
        from primitives_testbed.diveops.services import add_certification

        # Create a certification to generate audit log entry
        add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=staff_user,
            card_number="AUDIT123",
            issued_on=date.today(),
        )

        url = reverse("diveops:audit-log")
        response = staff_client.get(url)

        # Should have entries in context
        assert response.status_code == 200
        assert "entries" in response.context
        assert "page_title" in response.context
        assert response.context["page_title"] == "Audit Log"

    def test_audit_log_entries_ordered_newest_first(self, staff_client, staff_user, diver_profile, padi_open_water, padi_advanced):
        """Audit log entries are ordered newest first."""
        from primitives_testbed.diveops.services import add_certification

        # Create multiple certifications to generate multiple audit entries
        add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=staff_user,
            card_number="FIRST123",
            issued_on=date.today(),
        )
        add_certification(
            diver=diver_profile,
            level=padi_advanced,
            added_by=staff_user,
            card_number="SECOND456",
            issued_on=date.today(),
        )

        url = reverse("diveops:audit-log")
        response = staff_client.get(url)

        assert response.status_code == 200
        entries = response.context["entries"]
        assert len(entries) >= 2
        # Newest should be first (higher created_at)
        if len(entries) >= 2:
            assert entries[0].created_at >= entries[1].created_at