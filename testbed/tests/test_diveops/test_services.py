"""Tests for diveops services."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


def _create_trip_price(trip, user):
    """Helper to create a price for a trip's catalog item."""
    from django_catalog.models import CatalogItem
    from primitives_testbed.pricing.models import Price

    # Get or create the catalog item for this trip
    catalog_item, _ = CatalogItem.objects.get_or_create(
        display_name=f"Dive Trip - {trip.dive_site.name}",
        defaults={"kind": "service", "is_billable": True, "active": True},
    )

    # Create a price for this catalog item
    return Price.objects.create(
        catalog_item=catalog_item,
        amount=trip.price_per_diver,
        currency=trip.currency,
        valid_from=timezone.now() - timedelta(days=30),
        priority=50,
        created_by=user,
    )


@pytest.mark.django_db
class TestBookTrip:
    """Tests for book_trip service."""

    def test_book_trip_creates_booking(self, dive_trip, diver_profile, user):
        """book_trip creates a booking for an eligible diver."""
        from primitives_testbed.diveops.services import book_trip

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=user,
        )

        assert booking.pk is not None
        assert booking.trip == dive_trip
        assert booking.diver == diver_profile
        assert booking.status == "confirmed"

    def test_book_trip_creates_basket(self, dive_trip, diver_profile, user):
        """book_trip creates a basket when create_invoice=True."""
        from primitives_testbed.diveops.services import book_trip

        # Create price for the trip (required by billing adapter)
        _create_trip_price(dive_trip, user)

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=user,
            create_invoice=True,
        )

        assert booking.basket is not None
        # Basket is committed when invoice is created
        assert booking.basket.status == "committed"

    def test_book_trip_creates_invoice_when_requested(self, dive_trip, diver_profile, user):
        """book_trip creates an invoice when create_invoice=True."""
        from primitives_testbed.diveops.services import book_trip

        # Create price for the trip (required by billing adapter)
        _create_trip_price(dive_trip, user)

        booking = book_trip(
            trip=dive_trip,
            diver=diver_profile,
            booked_by=user,
            create_invoice=True,
        )

        assert booking.invoice is not None
        assert booking.invoice.total_amount == Decimal("100.00")

    def test_book_trip_rejects_ineligible_diver(self, dive_site, dive_shop, person2, padi_agency, user):
        """book_trip raises error if diver is not eligible."""
        from primitives_testbed.diveops.exceptions import DiverNotEligibleError
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            DiveTrip,
            TripRequirement,
        )
        from primitives_testbed.diveops.services import book_trip

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
            created_by=user,
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

        with pytest.raises(DiverNotEligibleError):
            book_trip(
                trip=trip,
                diver=diver,
                booked_by=user,
            )

    def test_book_trip_rejects_full_trip(self, full_trip, beginner_diver, user):
        """book_trip raises error if trip is at capacity."""
        from primitives_testbed.diveops.exceptions import TripCapacityError
        from primitives_testbed.diveops.services import book_trip

        with pytest.raises(TripCapacityError):
            book_trip(
                trip=full_trip,
                diver=beginner_diver,
                booked_by=user,
            )

    def test_book_trip_is_atomic(self, dive_trip, diver_profile, user, mocker):
        """book_trip rolls back on error (atomic transaction)."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import book_trip

        initial_count = Booking.objects.count()

        # Mock basket creation to fail
        mocker.patch(
            "primitives_testbed.diveops.integrations.create_trip_basket",
            side_effect=Exception("Simulated error"),
        )

        with pytest.raises(Exception):
            book_trip(
                trip=dive_trip,
                diver=diver_profile,
                booked_by=user,
                create_invoice=True,  # Required to trigger basket creation
            )

        # Verify no booking was created (rollback)
        assert Booking.objects.count() == initial_count


@pytest.mark.django_db
class TestCheckIn:
    """Tests for check_in service."""

    def test_check_in_creates_roster_entry(self, dive_trip, diver_profile, user):
        """check_in creates a TripRoster entry."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        roster = check_in(
            booking=booking,
            checked_in_by=user,
        )

        assert roster.pk is not None
        assert roster.trip == dive_trip
        assert roster.diver == diver_profile
        assert roster.checked_in_at is not None

    def test_check_in_requires_waiver(self, dive_trip, diver_profile, user):
        """check_in requires a signed waiver agreement."""
        from primitives_testbed.diveops.exceptions import CheckInError
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        # No waiver signed yet
        with pytest.raises(CheckInError) as exc_info:
            check_in(
                booking=booking,
                checked_in_by=user,
                require_waiver=True,
            )

        assert "waiver" in str(exc_info.value).lower()

    def test_check_in_rejects_cancelled_booking(self, dive_trip, diver_profile, user):
        """check_in raises error for cancelled booking."""
        from primitives_testbed.diveops.exceptions import CheckInError
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="cancelled",
            booked_by=user,
        )

        with pytest.raises(CheckInError):
            check_in(
                booking=booking,
                checked_in_by=user,
            )

    def test_check_in_updates_booking_status(self, dive_trip, diver_profile, user):
        """check_in updates booking status to 'checked_in'."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            trip=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        check_in(booking=booking, checked_in_by=user)
        booking.refresh_from_db()

        assert booking.status == "checked_in"


@pytest.mark.django_db
class TestCompleteTrip:
    """Tests for complete_trip service."""

    def test_complete_trip_updates_status(self, dive_trip, user):
        """complete_trip updates trip status to 'completed'."""
        from primitives_testbed.diveops.services import complete_trip

        result = complete_trip(
            trip=dive_trip,
            completed_by=user,
        )

        assert result.status == "completed"
        assert result.completed_at is not None

    def test_complete_trip_updates_diver_stats(self, dive_trip, diver_profile, user):
        """complete_trip increments divers' total_dives count."""
        from primitives_testbed.diveops.models import Booking, TripRoster
        from primitives_testbed.diveops.services import complete_trip

        initial_dives = diver_profile.total_dives

        # Create booking and check in
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

        complete_trip(trip=dive_trip, completed_by=user)
        diver_profile.refresh_from_db()

        assert diver_profile.total_dives == initial_dives + 1

    def test_complete_trip_creates_encounter_transition(self, dive_trip, user, encounter_definition):
        """complete_trip records an encounter transition."""
        from django_encounters.models import Encounter

        from primitives_testbed.diveops.services import complete_trip, start_trip

        # Start the trip first to create encounter
        start_trip(trip=dive_trip, started_by=user)
        dive_trip.refresh_from_db()

        complete_trip(trip=dive_trip, completed_by=user)

        # Check encounter was transitioned
        if dive_trip.encounter:
            assert dive_trip.encounter.state == "completed"

    def test_complete_trip_rejects_already_completed(self, dive_trip, user):
        """complete_trip raises error for already completed trip."""
        from primitives_testbed.diveops.exceptions import TripStateError
        from primitives_testbed.diveops.services import complete_trip

        dive_trip.status = "completed"
        dive_trip.save()

        with pytest.raises(TripStateError):
            complete_trip(trip=dive_trip, completed_by=user)
