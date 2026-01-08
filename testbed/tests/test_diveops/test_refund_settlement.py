"""Tests for T-006: Refund Settlement (Idempotent).

This module tests refund settlement for cancelled bookings:
- Settlement creates SettlementRecord with type=refund and links to ledger
- Settlement is idempotent (same key returns same record)
- Settlement requires RefundDecision from cancellation
- Settlement only allowed for cancelled bookings
- Audit events emitted

INV-4: Idempotent settlement with ledger integration (refund variant)
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-006: Refund Settlement Tests
# =============================================================================


@pytest.mark.django_db
class TestRefundSettlementCreatesRecord:
    """Test: Refund settlement creates record and ledger transaction."""

    def test_refund_settlement_creates_record_and_ledger_tx(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """create_refund_settlement() creates SettlementRecord with linked transaction."""
        from django_ledger.models import Transaction

        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SettlementRecord,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        # Setup: Create booking with agreement for refund decision
        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_refund_ow", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Refund Test Dive",
            slug="refund-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("200.00"),
            currency="USD",
        )

        # Schedule far in future for full refund
        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("200.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,  # Need agreement for refund policy
        )

        # Confirm and settle revenue first
        booking.status = "confirmed"
        booking.save()
        create_revenue_settlement(booking=booking, processed_by=user)

        # Cancel booking - this creates RefundDecision
        cancellation_result = cancel_booking(booking, cancelled_by=user)
        booking.refresh_from_db()

        initial_settlement_count = SettlementRecord.objects.filter(
            settlement_type="refund"
        ).count()
        initial_tx_count = Transaction.objects.count()

        # Act: Create refund settlement
        settlement = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )

        # Assert: SettlementRecord created
        assert (
            SettlementRecord.objects.filter(settlement_type="refund").count()
            == initial_settlement_count + 1
        )
        assert settlement.booking == booking
        assert settlement.amount == cancellation_result.refund_decision.refund_amount
        assert settlement.currency == cancellation_result.refund_decision.currency
        assert settlement.settlement_type == "refund"

        # Assert: Transaction created and linked
        assert Transaction.objects.count() == initial_tx_count + 1
        assert settlement.transaction is not None
        assert settlement.transaction.posted_at is not None

    def test_refund_transaction_is_balanced(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Refund settlement creates balanced transaction (debits == credits)."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_refund_bal", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Refund Balance Test",
            slug="refund-balance-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("150.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )

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

        cancellation_result = cancel_booking(booking, cancelled_by=user)

        settlement = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )

        # Verify transaction is balanced
        entries = settlement.transaction.entries.all()
        debits = sum(e.amount for e in entries if e.entry_type == "debit")
        credits = sum(e.amount for e in entries if e.entry_type == "credit")
        assert debits == credits
        assert debits == cancellation_result.refund_decision.refund_amount


@pytest.mark.django_db
class TestRefundSettlementIdempotency:
    """Test: Refund settlement is idempotent."""

    def test_refund_settlement_is_idempotent(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Calling create_refund_settlement twice returns same record."""
        from django_ledger.models import Transaction

        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SettlementRecord,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_idemp_ref", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Idempotent Refund Test",
            slug="idempotent-refund-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

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

        cancellation_result = cancel_booking(booking, cancelled_by=user)

        # First call
        settlement1 = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )

        refund_count_after_first = SettlementRecord.objects.filter(
            settlement_type="refund"
        ).count()
        tx_count_after_first = Transaction.objects.count()

        # Second call - should return same record
        settlement2 = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )

        # Assert: Same record returned
        assert settlement2.pk == settlement1.pk
        assert settlement2.idempotency_key == settlement1.idempotency_key

        # Assert: No new records created
        assert (
            SettlementRecord.objects.filter(settlement_type="refund").count()
            == refund_count_after_first
        )
        assert Transaction.objects.count() == tx_count_after_first


@pytest.mark.django_db
class TestRefundSettlementRequiresRefundDecision:
    """Test: Refund settlement requires RefundDecision."""

    def test_refund_settlement_requires_refund_decision(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Settlement creation fails if no refund_decision provided."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_no_dec", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="No Decision Test",
            slug="no-decision-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # Cancel without agreement (no refund decision)
        cancel_booking(booking, cancelled_by=user)
        booking.refresh_from_db()

        with pytest.raises(ValueError, match="refund_decision"):
            create_refund_settlement(
                booking=booking,
                refund_decision=None,
                processed_by=user,
            )


@pytest.mark.django_db
class TestRefundSettlementRequiresCancelledBooking:
    """Test: Refund settlement only allowed for cancelled bookings."""

    def test_refund_settlement_disallowed_for_confirmed_booking(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Settlement creation fails if booking is not cancelled."""
        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
            RefundDecision,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_refund_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_not_canc", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Not Cancelled Test",
            slug="not-cancelled-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )
        booking.status = "confirmed"
        booking.save()

        # Create a fake refund decision
        fake_decision = RefundDecision(
            refund_amount=Decimal("100.00"),
            refund_percent=100,
            original_amount=Decimal("100.00"),
            currency="USD",
            hours_before_departure=168,
            policy_tier_applied={"hours_before": 48, "refund_percent": 100},
            reason="Test refund",
        )

        with pytest.raises(ValueError, match="cancelled"):
            create_refund_settlement(
                booking=booking,
                refund_decision=fake_decision,
                processed_by=user,
            )


@pytest.mark.django_db
class TestRefundSettlementZeroAmount:
    """Test: Zero refund amount is handled correctly."""

    def test_zero_refund_does_not_create_settlement(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """No settlement created if refund amount is zero."""
        from primitives_testbed.diveops.cancellation_policy import RefundDecision
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SettlementRecord,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_zero", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Zero Refund Test",
            slug="zero-refund-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        # Schedule very soon for no refund
        soon = timezone.now() + timedelta(hours=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=soon,
            return_time=soon + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # Cancel without confirming first (to avoid revenue settlement issues)
        cancel_booking(booking, cancelled_by=user)
        booking.refresh_from_db()

        # Create zero refund decision
        zero_decision = RefundDecision(
            refund_amount=Decimal("0.00"),
            refund_percent=0,
            original_amount=Decimal("100.00"),
            currency="USD",
            hours_before_departure=1,
            policy_tier_applied={"hours_before": 0, "refund_percent": 0},
            reason="No refund - too late",
        )

        initial_count = SettlementRecord.objects.filter(settlement_type="refund").count()

        # Should return None for zero refund
        result = create_refund_settlement(
            booking=booking,
            refund_decision=zero_decision,
            processed_by=user,
        )

        assert result is None
        assert (
            SettlementRecord.objects.filter(settlement_type="refund").count()
            == initial_count
        )


@pytest.mark.django_db
class TestRefundSettlementAuditEvent:
    """Test: Refund settlement emits audit event."""

    def test_audit_event_emitted(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Settlement creation emits REFUND_SETTLEMENT_POSTED audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_audit_ref", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Audit Refund Test",
            slug="audit-refund-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

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

        cancellation_result = cancel_booking(booking, cancelled_by=user)

        initial_audit_count = AuditLog.objects.count()

        settlement = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )

        # Check audit event
        assert AuditLog.objects.count() > initial_audit_count

        refund_event = AuditLog.objects.filter(
            action=Actions.REFUND_SETTLEMENT_POSTED
        ).first()
        assert refund_event is not None
        assert "booking_id" in refund_event.metadata
        assert "settlement_id" in refund_event.metadata
        # `amount` is the refund amount from the settlement record
        assert "amount" in refund_event.metadata
        assert "refund_percent" in refund_event.metadata
        assert "original_amount" in refund_event.metadata


@pytest.mark.django_db
class TestRefundIdempotencyKeyFormat:
    """Test: Refund idempotency key format is deterministic."""

    def test_refund_idempotency_key_format(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Idempotency key follows format: {booking_id}:refund:1"""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_key_ref", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Key Refund Test",
            slug="key-refund-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

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

        cancellation_result = cancel_booking(booking, cancelled_by=user)
        booking.refresh_from_db()

        settlement = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )

        expected_key = f"{booking.pk}:refund:1"
        assert settlement.idempotency_key == expected_key


@pytest.mark.django_db
class TestRefundReversesRevenue:
    """Test: Refund settlement reverses revenue entries."""

    def test_refund_reverses_revenue_direction(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Refund creates opposite entries: DR Revenue, CR Receivable."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_refund_settlement,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_reverse", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Reverse Test",
            slug="reverse-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        future = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=future,
            return_time=future + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )
        booking.status = "confirmed"
        booking.save()

        # Revenue settlement: DR Receivable, CR Revenue
        revenue_settlement = create_revenue_settlement(booking=booking, processed_by=user)
        revenue_entries = list(revenue_settlement.transaction.entries.all())

        # Find entry types from revenue
        revenue_debit = [e for e in revenue_entries if e.entry_type == "debit"][0]
        revenue_credit = [e for e in revenue_entries if e.entry_type == "credit"][0]

        cancellation_result = cancel_booking(booking, cancelled_by=user)

        # Refund settlement: DR Revenue, CR Receivable (opposite)
        refund_settlement = create_refund_settlement(
            booking=booking,
            refund_decision=cancellation_result.refund_decision,
            processed_by=user,
        )
        refund_entries = list(refund_settlement.transaction.entries.all())

        # Verify refund reverses the direction
        refund_debit = [e for e in refund_entries if e.entry_type == "debit"][0]
        refund_credit = [e for e in refund_entries if e.entry_type == "credit"][0]

        # Debit should now be on revenue account (was credit)
        assert refund_debit.account.account_type == "revenue"
        # Credit should now be on receivable account (was debit)
        assert refund_credit.account.account_type == "receivable"
