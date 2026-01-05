"""T-011: Booking Financial State Enforcement

Tests for financial state rules on bookings:
- INV-5: Cannot cancel settled booking without refund
- Booking.is_settled property tracks revenue settlement
- Booking.has_refund property tracks refund settlement
- Soft delete blocked for settled bookings
- Status transitions respect financial state

Financial State Rules:
1. Unsettled booking → can cancel freely
2. Settled booking → must have refund settlement before/during cancel
3. Settled booking → cannot be soft-deleted
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


def create_test_excursion_type(padi_agency, slug_suffix=""):
    """Helper to create a valid ExcursionType for tests."""
    from primitives_testbed.diveops.models import CertificationLevel, ExcursionType
    import uuid

    cert_level, _ = CertificationLevel.objects.get_or_create(
        agency=padi_agency,
        code=f"ow-{uuid.uuid4().hex[:6]}",
        defaults={"name": "Open Water", "rank": 1},
    )

    return ExcursionType.objects.create(
        name=f"Financial State Test Type {slug_suffix}",
        slug=f"financial-state-{uuid.uuid4().hex[:8]}",
        dive_mode="boat",
        time_of_day="day",
        max_depth_meters=18,
        base_price=Decimal("100.00"),
        currency="USD",
    )


def create_test_excursion(dive_shop, dive_site, user, excursion_type, days_offset=7):
    """Helper to create a valid Excursion for tests."""
    from primitives_testbed.diveops.models import Excursion

    departure = timezone.now() + timedelta(days=days_offset)
    return_time = departure + timedelta(hours=4)

    return Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        excursion_type=excursion_type,
        departure_time=departure,
        return_time=return_time,
        max_divers=10,
        price_per_diver=Decimal("100.00"),
        currency="USD",
        status="scheduled",
        created_by=user,
    )


def create_confirmed_booking(excursion, diver_profile, user, create_agreement=False):
    """Helper to create a confirmed booking."""
    from primitives_testbed.diveops.services import book_excursion

    booking = book_excursion(
        excursion=excursion,
        diver=diver_profile,
        booked_by=user,
        skip_eligibility_check=True,
        create_agreement=create_agreement,
    )
    booking.status = "confirmed"
    booking.save()
    return booking


# =============================================================================
# T-011: Booking Financial State Properties
# =============================================================================


@pytest.mark.django_db
class TestBookingIsSettledProperty:
    """Test: Booking.is_settled property."""

    def test_is_settled_false_when_no_settlement(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """is_settled returns False when no revenue settlement exists."""
        excursion_type = create_test_excursion_type(padi_agency, "settled1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        assert booking.is_settled is False

    def test_is_settled_true_when_revenue_settlement_exists(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """is_settled returns True when revenue settlement exists."""
        from primitives_testbed.diveops.services import create_revenue_settlement

        excursion_type = create_test_excursion_type(padi_agency, "settled2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        create_revenue_settlement(booking=booking, processed_by=user)

        assert booking.is_settled is True


@pytest.mark.django_db
class TestBookingHasRefundProperty:
    """Test: Booking.has_refund property."""

    def test_has_refund_false_when_no_refund_settlement(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """has_refund returns False when no refund settlement exists."""
        excursion_type = create_test_excursion_type(padi_agency, "refund1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        assert booking.has_refund is False

    def test_has_refund_true_when_refund_settlement_exists(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """has_refund returns True when refund settlement exists."""
        from primitives_testbed.diveops.services import (
            cancel_booking,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "refund2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user, create_agreement=True)

        # Settle revenue first
        create_revenue_settlement(booking=booking, processed_by=user)

        # Cancel with force_with_refund=True to auto-create refund
        result = cancel_booking(booking, cancelled_by=user, force_with_refund=True)
        booking.refresh_from_db()

        assert booking.has_refund is True


# =============================================================================
# T-011: Cancel Booking Financial State Enforcement (INV-5)
# =============================================================================


@pytest.mark.django_db
class TestCancelBookingFinancialState:
    """Test: cancel_booking enforces financial state rules (INV-5)."""

    def test_cancel_unsettled_booking_allowed(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Cancelling an unsettled booking is allowed."""
        from primitives_testbed.diveops.services import cancel_booking

        excursion_type = create_test_excursion_type(padi_agency, "cancel1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        # Should succeed - booking is not settled
        result = cancel_booking(booking, cancelled_by=user)
        booking.refresh_from_db()

        assert booking.status == "cancelled"

    def test_cancel_settled_booking_blocked_without_refund(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Cancelling a settled booking without refund raises error (INV-5)."""
        from primitives_testbed.diveops.services import (
            cancel_booking,
            create_revenue_settlement,
        )
        from primitives_testbed.diveops.exceptions import BookingError

        excursion_type = create_test_excursion_type(padi_agency, "cancel2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        # Settle the booking
        create_revenue_settlement(booking=booking, processed_by=user)

        # Should fail - booking is settled but no refund settlement
        with pytest.raises(BookingError, match="settled.*refund"):
            cancel_booking(booking, cancelled_by=user)

    def test_cancel_settled_booking_allowed_with_force_flag(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Cancelling a settled booking with force=True creates refund automatically."""
        from primitives_testbed.diveops.models import SettlementRecord
        from primitives_testbed.diveops.services import (
            cancel_booking,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "cancel3")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user, create_agreement=True)

        # Settle the booking
        create_revenue_settlement(booking=booking, processed_by=user)

        # Cancel with force=True - should create refund settlement automatically
        result = cancel_booking(booking, cancelled_by=user, force_with_refund=True)
        booking.refresh_from_db()

        assert booking.status == "cancelled"
        # Refund settlement should exist
        assert SettlementRecord.objects.filter(
            booking=booking, settlement_type="refund"
        ).exists()


# =============================================================================
# T-011: Soft Delete Financial State Enforcement
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteFinancialState:
    """Test: Soft delete blocked for settled bookings."""

    def test_soft_delete_allowed_for_unsettled_booking(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Soft deleting an unsettled booking is allowed."""
        from primitives_testbed.diveops.models import Booking

        excursion_type = create_test_excursion_type(padi_agency, "delete1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)
        booking_id = booking.pk

        # Soft delete should work
        booking.delete()

        # Should be excluded from default queryset
        assert not Booking.objects.filter(pk=booking_id).exists()
        # But still in all_objects
        assert Booking.all_objects.filter(pk=booking_id).exists()

    def test_soft_delete_blocked_for_settled_booking(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Soft deleting a settled booking raises error."""
        from primitives_testbed.diveops.services import create_revenue_settlement
        from primitives_testbed.diveops.exceptions import BookingError

        excursion_type = create_test_excursion_type(padi_agency, "delete2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        # Settle the booking
        create_revenue_settlement(booking=booking, processed_by=user)

        # Soft delete should be blocked
        with pytest.raises(BookingError, match="settlement.*cannot.*delete"):
            booking.delete()


# =============================================================================
# T-011: Booking Financial State Method
# =============================================================================


@pytest.mark.django_db
class TestBookingFinancialStateMethod:
    """Test: Booking.get_financial_state() method."""

    def test_financial_state_unsettled(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """get_financial_state returns 'unsettled' when no settlements."""
        excursion_type = create_test_excursion_type(padi_agency, "state1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        assert booking.get_financial_state() == "unsettled"

    def test_financial_state_settled(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """get_financial_state returns 'settled' when revenue settlement exists."""
        from primitives_testbed.diveops.services import create_revenue_settlement

        excursion_type = create_test_excursion_type(padi_agency, "state2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        create_revenue_settlement(booking=booking, processed_by=user)

        assert booking.get_financial_state() == "settled"

    def test_financial_state_refunded(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """get_financial_state returns 'refunded' when refund settlement exists."""
        from primitives_testbed.diveops.services import (
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "state3")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user, create_agreement=True)

        create_revenue_settlement(booking=booking, processed_by=user)
        result = cancel_booking(booking, cancelled_by=user, force_with_refund=True)
        booking.refresh_from_db()

        assert booking.get_financial_state() == "refunded"


# =============================================================================
# T-011: Audit Events for Financial State Changes
# =============================================================================


@pytest.mark.django_db
class TestFinancialStateAudit:
    """Test: Financial state enforcement emits audit events."""

    def test_blocked_cancellation_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Blocked cancellation attempt emits audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.services import (
            cancel_booking,
            create_revenue_settlement,
        )
        from primitives_testbed.diveops.exceptions import BookingError

        excursion_type = create_test_excursion_type(padi_agency, "audit1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = create_confirmed_booking(excursion, diver_profile, user)

        create_revenue_settlement(booking=booking, processed_by=user)

        # Count blocked events before attempt
        blocked_count_before = AuditLog.objects.filter(
            action="booking_cancellation_blocked"
        ).count()

        with pytest.raises(BookingError):
            cancel_booking(booking, cancelled_by=user)

        # Audit event should be emitted for blocked action
        blocked_count_after = AuditLog.objects.filter(
            action="booking_cancellation_blocked"
        ).count()
        assert blocked_count_after > blocked_count_before

        audit_event = AuditLog.objects.filter(
            action="booking_cancellation_blocked"
        ).first()
        assert audit_event is not None
        assert "settled" in audit_event.metadata.get("reason", "")
