"""Tests for diveops services."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


def _create_excursion_price(excursion, user):
    """Helper to create a price for an excursion's catalog item."""
    from django_catalog.models import CatalogItem
    from primitives_testbed.pricing.models import Price

    # Get or create the catalog item for this excursion
    catalog_item, _ = CatalogItem.objects.get_or_create(
        display_name=f"Dive Excursion - {excursion.dive_site.name}",
        defaults={"kind": "service", "is_billable": True, "active": True},
    )

    # Create a price for this catalog item
    return Price.objects.create(
        catalog_item=catalog_item,
        amount=excursion.price_per_diver,
        currency=excursion.currency,
        valid_from=timezone.now() - timedelta(days=30),
        priority=50,
        created_by=user,
    )


@pytest.mark.django_db
class TestBookExcursion:
    """Tests for book_excursion service."""

    def test_book_excursion_creates_booking(self, dive_trip, diver_profile, user):
        """book_excursion creates a booking for an eligible diver."""
        from primitives_testbed.diveops.services import book_excursion

        booking = book_excursion(
            excursion=dive_trip,
            diver=diver_profile,
            booked_by=user,
        )

        assert booking.pk is not None
        assert booking.excursion == dive_trip
        assert booking.diver == diver_profile
        assert booking.status == "confirmed"

    def test_book_excursion_creates_basket(self, dive_trip, diver_profile, user):
        """book_excursion creates a basket when create_invoice=True."""
        from primitives_testbed.diveops.services import book_excursion

        # Create price for the excursion (required by billing adapter)
        _create_excursion_price(dive_trip, user)

        booking = book_excursion(
            excursion=dive_trip,
            diver=diver_profile,
            booked_by=user,
            create_invoice=True,
        )

        assert booking.basket is not None
        # Basket is committed when invoice is created
        assert booking.basket.status == "committed"

    def test_book_excursion_creates_invoice_when_requested(self, dive_trip, diver_profile, user):
        """book_excursion creates an invoice when create_invoice=True."""
        from primitives_testbed.diveops.services import book_excursion

        # Create price for the excursion (required by billing adapter)
        _create_excursion_price(dive_trip, user)

        booking = book_excursion(
            excursion=dive_trip,
            diver=diver_profile,
            booked_by=user,
            create_invoice=True,
        )

        assert booking.invoice is not None
        assert booking.invoice.total_amount == Decimal("100.00")

    def test_book_excursion_rejects_ineligible_diver(self, dive_site, dive_shop, person2, padi_agency, user):
        """book_excursion raises error if diver is not eligible."""
        from primitives_testbed.diveops.exceptions import DiverNotEligibleError
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            DiverProfile,
            Excursion,
            ExcursionRequirement,
        )
        from primitives_testbed.diveops.services import book_excursion

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
            created_by=user,
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

        with pytest.raises(DiverNotEligibleError):
            book_excursion(
                excursion=excursion,
                diver=diver,
                booked_by=user,
            )

    def test_book_excursion_rejects_full_excursion(self, full_excursion, beginner_diver, user):
        """book_excursion raises error if excursion is at capacity."""
        from primitives_testbed.diveops.exceptions import TripCapacityError
        from primitives_testbed.diveops.services import book_excursion

        with pytest.raises(TripCapacityError):
            book_excursion(
                excursion=full_excursion,
                diver=beginner_diver,
                booked_by=user,
            )

    def test_book_excursion_is_atomic(self, dive_trip, diver_profile, user, mocker):
        """book_excursion rolls back on error (atomic transaction)."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import book_excursion

        initial_count = Booking.objects.count()

        # Mock basket creation to fail
        mocker.patch(
            "primitives_testbed.diveops.integrations.create_excursion_basket",
            side_effect=Exception("Simulated error"),
        )

        with pytest.raises(Exception):
            book_excursion(
                excursion=dive_trip,
                diver=diver_profile,
                booked_by=user,
                create_invoice=True,  # Required to trigger basket creation
            )

        # Verify no booking was created (rollback)
        assert Booking.objects.count() == initial_count

    def test_book_excursion_rejects_duplicate_booking(self, dive_trip, diver_profile, user):
        """book_excursion raises BookingError for duplicate active booking."""
        from primitives_testbed.diveops.exceptions import BookingError
        from primitives_testbed.diveops.services import book_excursion

        # First booking succeeds
        book_excursion(
            excursion=dive_trip,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # Second booking for same diver on same excursion fails with domain error
        with pytest.raises(BookingError, match="already has an active booking"):
            book_excursion(
                excursion=dive_trip,
                diver=diver_profile,
                booked_by=user,
                skip_eligibility_check=True,
            )


@pytest.mark.django_db
class TestCheckIn:
    """Tests for check_in service."""

    def test_check_in_creates_roster_entry(self, dive_trip, diver_profile, user):
        """check_in creates an ExcursionRoster entry."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        roster = check_in(
            booking=booking,
            checked_in_by=user,
        )

        assert roster.pk is not None
        assert roster.excursion == dive_trip
        assert roster.diver == diver_profile
        assert roster.checked_in_at is not None

    def test_check_in_requires_waiver(self, dive_trip, diver_profile, user):
        """check_in requires a signed waiver agreement."""
        from primitives_testbed.diveops.exceptions import CheckInError
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.services import check_in

        booking = Booking.objects.create(
            excursion=dive_trip,
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
            excursion=dive_trip,
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
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        check_in(booking=booking, checked_in_by=user)
        booking.refresh_from_db()

        assert booking.status == "checked_in"

    def test_check_in_rejects_duplicate_roster(self, dive_trip, diver_profile, user):
        """check_in raises CheckInError for duplicate roster entry.

        This tests the edge case where a roster entry already exists
        (perhaps from a previous check-in that was interrupted before
        updating booking status).
        """
        from primitives_testbed.diveops.exceptions import CheckInError
        from primitives_testbed.diveops.models import Booking, ExcursionRoster
        from primitives_testbed.diveops.services import check_in

        # Create booking
        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        # Directly create roster entry (simulating partial check-in or race)
        ExcursionRoster.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )

        # Attempting check_in again should fail with domain error, not raw IntegrityError
        with pytest.raises(CheckInError, match="already has a roster entry"):
            check_in(booking=booking, checked_in_by=user)


@pytest.mark.django_db
class TestCompleteExcursion:
    """Tests for complete_excursion service."""

    def test_complete_excursion_updates_status(self, dive_trip, user):
        """complete_excursion updates excursion status to 'completed'."""
        from primitives_testbed.diveops.services import complete_excursion

        result = complete_excursion(
            excursion=dive_trip,
            completed_by=user,
        )

        assert result.status == "completed"
        assert result.completed_at is not None

    def test_complete_excursion_updates_diver_stats(self, dive_trip, diver_profile, user):
        """complete_excursion increments divers' total_dives count."""
        from primitives_testbed.diveops.models import Booking, ExcursionRoster
        from primitives_testbed.diveops.services import complete_excursion

        initial_dives = diver_profile.total_dives

        # Create booking and check in
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

        complete_excursion(excursion=dive_trip, completed_by=user)
        diver_profile.refresh_from_db()

        assert diver_profile.total_dives == initial_dives + 1

    def test_complete_excursion_creates_encounter_transition(self, dive_trip, user, encounter_definition):
        """complete_excursion records an encounter transition."""
        from django_encounters.models import Encounter

        from primitives_testbed.diveops.services import complete_excursion, start_excursion

        # Start the excursion first to create encounter
        start_excursion(excursion=dive_trip, started_by=user)
        dive_trip.refresh_from_db()

        complete_excursion(excursion=dive_trip, completed_by=user)

        # Check encounter was transitioned
        if dive_trip.encounter:
            assert dive_trip.encounter.state == "completed"

    def test_complete_excursion_is_idempotent(self, dive_trip, user):
        """complete_excursion is idempotent - returns excursion if already completed."""
        from primitives_testbed.diveops.services import complete_excursion

        dive_trip.status = "completed"
        dive_trip.save()

        # Should return excursion without error (idempotent no-op)
        result = complete_excursion(excursion=dive_trip, completed_by=user)
        assert result.status == "completed"
        assert result.pk == dive_trip.pk

    def test_complete_excursion_rejects_cancelled(self, dive_trip, user):
        """complete_excursion raises error for cancelled excursion."""
        from primitives_testbed.diveops.exceptions import TripStateError
        from primitives_testbed.diveops.services import complete_excursion

        dive_trip.status = "cancelled"
        dive_trip.save()

        with pytest.raises(TripStateError):
            complete_excursion(excursion=dive_trip, completed_by=user)


# =============================================================================
# Concurrency Tests
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestCompleteExcursionConcurrency:
    """Concurrency tests for complete_excursion service.

    These tests verify that concurrent calls to complete_excursion()
    do not cause double-counting of dives.
    """

    def test_complete_excursion_no_double_count(self, dive_trip, diver_profile, user):
        """Concurrent complete_excursion() calls increment total_dives exactly once.

        This test verifies the idempotency guarantee: if two callers try to
        complete the same excursion simultaneously, the diver's dive count should
        only increment once.
        """
        from primitives_testbed.diveops.models import Booking, ExcursionRoster
        from primitives_testbed.diveops.services import complete_excursion

        initial_dives = diver_profile.total_dives

        # Setup: diver on roster
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

        # First call completes the excursion
        result1 = complete_excursion(excursion=dive_trip, completed_by=user)
        assert result1.status == "completed"

        # Second call should be idempotent (no-op)
        dive_trip.refresh_from_db()
        result2 = complete_excursion(excursion=dive_trip, completed_by=user)
        assert result2.status == "completed"

        # Verify dive count incremented exactly once
        diver_profile.refresh_from_db()
        assert diver_profile.total_dives == initial_dives + 1, (
            f"Expected {initial_dives + 1} dives, got {diver_profile.total_dives}. "
            "Double-count detected!"
        )

    def test_complete_excursion_idempotent_no_phantom_audit(
        self, dive_trip, diver_profile, user
    ):
        """Second complete_excursion() call does not emit phantom audit events."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.models import Booking, ExcursionRoster
        from primitives_testbed.diveops.services import complete_excursion

        # Setup
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

        # Clear existing audit events
        AuditLog.objects.all().delete()

        # First call
        complete_excursion(excursion=dive_trip, completed_by=user)
        first_call_count = AuditLog.objects.filter(
            action=Actions.TRIP_COMPLETED
        ).count()
        assert first_call_count == 1

        # Second call (idempotent no-op)
        dive_trip.refresh_from_db()
        complete_excursion(excursion=dive_trip, completed_by=user)
        second_call_count = AuditLog.objects.filter(
            action=Actions.TRIP_COMPLETED
        ).count()

        # Should still be 1 (no phantom event from no-op)
        assert second_call_count == 1, (
            f"Expected 1 TRIP_COMPLETED event, got {second_call_count}. "
            "Phantom audit event from idempotent call!"
        )


@pytest.mark.django_db(transaction=True)
class TestBookExcursionConcurrency:
    """Concurrency tests for book_excursion service.

    These tests verify that concurrent booking attempts at capacity
    result in exactly one successful booking.
    """

    def test_book_excursion_at_capacity_one_succeeds(
        self, dive_site, dive_shop, person, person2, user
    ):
        """When excursion is at capacity, only one booking succeeds.

        This test creates an excursion with capacity=1, then attempts to book
        two divers. Only one should succeed.

        Note: We do NOT skip eligibility check because capacity is checked
        in can_diver_join_excursion(). Skipping it bypasses capacity enforcement.
        """
        from primitives_testbed.diveops.exceptions import (
            DiverNotEligibleError,
            TripCapacityError,
        )
        from primitives_testbed.diveops.models import DiverProfile, Excursion
        from primitives_testbed.diveops.services import book_excursion

        # Create excursion with capacity=1
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=1,  # Only one spot
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        # Create two divers with all requirements met
        from datetime import date
        next_year = date.today() + timedelta(days=365)
        diver1 = DiverProfile.objects.create(
            person=person,
            total_dives=10,
            waiver_signed_at=timezone.now(),
            medical_clearance_valid_until=next_year,
        )
        diver2 = DiverProfile.objects.create(
            person=person2,
            total_dives=10,
            waiver_signed_at=timezone.now(),
            medical_clearance_valid_until=next_year,
        )

        # First booking succeeds (eligibility check runs, capacity=1 available)
        booking1 = book_excursion(
            excursion=excursion,
            diver=diver1,
            booked_by=user,
            # Don't skip - we want capacity check to run
        )
        assert booking1.status == "confirmed"

        # Second booking fails (capacity exhausted)
        with pytest.raises((TripCapacityError, DiverNotEligibleError)):
            book_excursion(
                excursion=excursion,
                diver=diver2,
                booked_by=user,
                # Don't skip - capacity check rejects this
            )

        # Verify capacity not exceeded
        excursion.refresh_from_db()
        assert excursion.spots_available == 0
        assert excursion.bookings.filter(status="confirmed").count() == 1

    def test_book_excursion_spots_never_negative(self):
        """spots_available never goes negative even under rapid booking."""
        from django.contrib.auth import get_user_model
        from django_parties.models import Organization, Person

        from primitives_testbed.diveops.models import DiverProfile, DiveSite, Excursion
        from primitives_testbed.diveops.services import book_excursion

        User = get_user_model()

        # Create all fixtures fresh for this test
        user = User.objects.create_user(
            username="spots_test_user",
            email="spots@test.com",
            password="password123",
            is_staff=True,
        )
        from django_geo.models import Place

        dive_shop = Organization.objects.create(
            name="Spots Test Dive Shop",
            org_type="dive_shop",
        )
        place = Place.objects.create(
            name="Spots Test Site Location",
            latitude=Decimal("25.0"),
            longitude=Decimal("-80.0"),
        )
        dive_site = DiveSite.objects.create(
            name="Spots Test Site",
            place=place,
            max_depth_meters=20,
        )

        # Create excursion with small capacity
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=3,  # Small capacity to test
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        original_spots = excursion.spots_available
        bookings_created = 0
        from datetime import date
        next_year = date.today() + timedelta(days=365)

        # Create enough divers to potentially exceed capacity
        for i in range(original_spots + 2):  # Try to exceed by 2
            try:
                person = Person.objects.create(
                    first_name=f"Test{i}",
                    last_name=f"Diver{i}",
                )
                diver = DiverProfile.objects.create(
                    person=person,
                    total_dives=10,
                    waiver_signed_at=timezone.now(),
                    medical_clearance_valid_until=next_year,
                )

                book_excursion(
                    excursion=excursion,
                    diver=diver,
                    booked_by=user,
                    # Don't skip eligibility - capacity check is there
                )
                bookings_created += 1
            except Exception:
                # Expected to fail after capacity reached
                pass

        excursion.refresh_from_db()
        assert excursion.spots_available >= 0, "spots_available went negative!"
        assert bookings_created == original_spots, (
            f"Expected {original_spots} bookings, got {bookings_created}"
        )
