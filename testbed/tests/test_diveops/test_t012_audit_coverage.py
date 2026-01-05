"""T-012: Audit Coverage Verification

Comprehensive tests to verify all critical DiveOps operations emit
appropriate audit events with correct metadata.

Audit Requirements:
- All financial operations MUST have audit trail
- All state changes MUST be logged
- Metadata MUST include relevant IDs for traceability

Critical Operations to Audit:
1. Booking lifecycle (create, cancel, check-in)
2. Settlement lifecycle (revenue, refund, batch)
3. Eligibility overrides
4. Commission rules (if applicable)
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
        name=f"Audit Test Type {slug_suffix}",
        slug=f"audit-test-{uuid.uuid4().hex[:8]}",
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


# =============================================================================
# T-012: Booking Audit Coverage
# =============================================================================


@pytest.mark.django_db
class TestBookingAuditCoverage:
    """Verify booking operations emit correct audit events."""

    def test_booking_created_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """book_excursion emits BOOKING_CREATED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion

        excursion_type = create_test_excursion_type(padi_agency, "book1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        initial_count = AuditLog.objects.filter(
            action=Actions.BOOKING_CREATED
        ).count()

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # Verify audit event
        final_count = AuditLog.objects.filter(
            action=Actions.BOOKING_CREATED
        ).count()
        assert final_count == initial_count + 1

        audit_event = AuditLog.objects.filter(
            action=Actions.BOOKING_CREATED
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert "booking_id" in audit_event.metadata
        assert audit_event.metadata["booking_id"] == str(booking.pk)

    def test_booking_cancelled_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """cancel_booking emits BOOKING_CANCELLED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        excursion_type = create_test_excursion_type(padi_agency, "cancel1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        initial_count = AuditLog.objects.filter(
            action=Actions.BOOKING_CANCELLED
        ).count()

        cancel_booking(booking, cancelled_by=user)

        final_count = AuditLog.objects.filter(
            action=Actions.BOOKING_CANCELLED
        ).count()
        assert final_count == initial_count + 1

        audit_event = AuditLog.objects.filter(
            action=Actions.BOOKING_CANCELLED
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert "booking_id" in audit_event.metadata

    def test_diver_checked_in_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """check_in emits DIVER_CHECKED_IN audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion, check_in

        excursion_type = create_test_excursion_type(padi_agency, "checkin1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )
        booking.status = "confirmed"
        booking.save()

        initial_count = AuditLog.objects.filter(
            action=Actions.DIVER_CHECKED_IN
        ).count()

        check_in(booking, checked_in_by=user)

        final_count = AuditLog.objects.filter(
            action=Actions.DIVER_CHECKED_IN
        ).count()
        assert final_count == initial_count + 1


# =============================================================================
# T-012: Settlement Audit Coverage
# =============================================================================


@pytest.mark.django_db
class TestSettlementAuditCoverage:
    """Verify settlement operations emit correct audit events."""

    def test_revenue_settlement_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """create_revenue_settlement emits SETTLEMENT_POSTED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "settle1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )
        booking.status = "confirmed"
        booking.save()

        initial_count = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_POSTED
        ).count()

        settlement = create_revenue_settlement(booking=booking, processed_by=user)

        final_count = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_POSTED
        ).count()
        assert final_count == initial_count + 1

        audit_event = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_POSTED
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert "settlement_id" in audit_event.metadata
        assert "booking_id" in audit_event.metadata
        assert "amount" in audit_event.metadata

    def test_refund_settlement_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """create_refund_settlement emits REFUND_SETTLEMENT_POSTED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "refund1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )
        booking.status = "confirmed"
        booking.save()

        create_revenue_settlement(booking=booking, processed_by=user)

        initial_count = AuditLog.objects.filter(
            action=Actions.REFUND_SETTLEMENT_POSTED
        ).count()

        # Cancel with force to create refund
        cancel_booking(booking, cancelled_by=user, force_with_refund=True)

        final_count = AuditLog.objects.filter(
            action=Actions.REFUND_SETTLEMENT_POSTED
        ).count()
        assert final_count == initial_count + 1

    def test_settlement_run_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """run_settlement_batch emits SETTLEMENT_RUN_COMPLETED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "run1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )
        booking.status = "confirmed"
        booking.save()

        initial_count = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_RUN_COMPLETED
        ).count()

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        final_count = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_RUN_COMPLETED
        ).count()
        assert final_count == initial_count + 1

        audit_event = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_RUN_COMPLETED
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert "run_id" in audit_event.metadata
        assert "total_bookings" in audit_event.metadata
        assert "settled_count" in audit_event.metadata
        assert "total_amount" in audit_event.metadata


# =============================================================================
# T-012: Eligibility Override Audit Coverage
# =============================================================================


@pytest.mark.django_db
class TestEligibilityOverrideAuditCoverage:
    """Verify eligibility override operations emit correct audit events."""

    def test_eligibility_override_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """record_booking_eligibility_override emits BOOKING_ELIGIBILITY_OVERRIDDEN audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.models import Booking, CertificationLevel
        from primitives_testbed.diveops.eligibility_service import record_booking_eligibility_override

        # Create excursion type that requires certification
        cert_level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="advanced-override",
            name="Advanced Open Water",
            rank=3,
        )
        excursion_type = create_test_excursion_type(padi_agency, "override1")
        excursion_type.requires_cert = True
        excursion_type.min_certification_level = cert_level
        excursion_type.save()

        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        # Create booking directly (bypassing eligibility)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
            price_snapshot={"amount": "100.00", "currency": "USD"},
            price_amount=Decimal("100.00"),
            price_currency="USD",
        )

        initial_count = AuditLog.objects.filter(
            action=Actions.BOOKING_ELIGIBILITY_OVERRIDDEN
        ).count()

        override = record_booking_eligibility_override(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "advanced"},
            approver=user,
            reason="VIP customer with equivalent experience",
        )

        final_count = AuditLog.objects.filter(
            action=Actions.BOOKING_ELIGIBILITY_OVERRIDDEN
        ).count()
        assert final_count == initial_count + 1

        audit_event = AuditLog.objects.filter(
            action=Actions.BOOKING_ELIGIBILITY_OVERRIDDEN
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert "booking_id" in audit_event.metadata
        assert "diver_id" in audit_event.metadata
        assert "requirement_type" in audit_event.metadata
        assert "reason" in audit_event.metadata
        assert "approved_by_id" in audit_event.metadata


# =============================================================================
# T-012: Audit Metadata Completeness
# =============================================================================


@pytest.mark.django_db
class TestAuditMetadataCompleteness:
    """Verify audit events have complete metadata for traceability."""

    def test_booking_audit_includes_diver_and_excursion(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Booking audit events include diver and excursion IDs."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion

        excursion_type = create_test_excursion_type(padi_agency, "meta1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        audit_event = AuditLog.objects.filter(
            action=Actions.BOOKING_CREATED
        ).order_by("-created_at").first()

        assert audit_event is not None
        # Check for essential traceability fields
        assert "booking_id" in audit_event.metadata
        assert "diver_id" in audit_event.metadata
        assert "excursion_id" in audit_event.metadata

    def test_settlement_audit_includes_financial_details(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Settlement audit events include amount, currency, and IDs."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "meta2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )
        booking.status = "confirmed"
        booking.save()

        settlement = create_revenue_settlement(booking=booking, processed_by=user)

        audit_event = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_POSTED
        ).order_by("-created_at").first()

        assert audit_event is not None
        # Check for financial traceability
        assert "settlement_id" in audit_event.metadata
        assert "booking_id" in audit_event.metadata
        assert "amount" in audit_event.metadata
        assert "idempotency_key" in audit_event.metadata


# =============================================================================
# T-012: Audit Actor Tracking
# =============================================================================


@pytest.mark.django_db
class TestAuditActorTracking:
    """Verify audit events correctly track the actor (user) who performed the action."""

    def test_booking_audit_tracks_actor(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Booking audit event tracks the user who made the booking."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion

        excursion_type = create_test_excursion_type(padi_agency, "actor1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        audit_event = AuditLog.objects.filter(
            action=Actions.BOOKING_CREATED
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert audit_event.actor_user == user

    def test_settlement_audit_tracks_processor(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Settlement audit event tracks the user who processed it."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        excursion_type = create_test_excursion_type(padi_agency, "actor2")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )
        booking.status = "confirmed"
        booking.save()

        create_revenue_settlement(booking=booking, processed_by=user)

        audit_event = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_POSTED
        ).order_by("-created_at").first()

        assert audit_event is not None
        assert audit_event.actor_user == user


# =============================================================================
# T-012: Audit Immutability
# =============================================================================


@pytest.mark.django_db
class TestAuditImmutability:
    """Verify audit events cannot be modified after creation."""

    def test_audit_events_are_created_not_updated(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Each operation creates a new audit event (append-only)."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        excursion_type = create_test_excursion_type(padi_agency, "immut1")
        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)

        # Count before
        count_before = AuditLog.objects.count()

        # Create booking
        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        count_after_book = AuditLog.objects.count()
        assert count_after_book > count_before  # New event created

        # Cancel booking
        cancel_booking(booking, cancelled_by=user)

        count_after_cancel = AuditLog.objects.count()
        assert count_after_cancel > count_after_book  # Another new event

        # Both events exist - no updates, only appends
        assert AuditLog.objects.filter(action=Actions.BOOKING_CREATED).exists()
        assert AuditLog.objects.filter(action=Actions.BOOKING_CANCELLED).exists()
