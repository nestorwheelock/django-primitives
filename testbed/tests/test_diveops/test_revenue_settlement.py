"""Tests for T-005: Revenue Settlement (Idempotent).

This module tests revenue settlement for bookings:
- Settlement creates SettlementRecord and links to ledger transaction
- Settlement is idempotent (same key returns same record)
- Settlement requires price snapshot
- Settlement disallowed for cancelled bookings
- Audit events emitted

INV-4: Idempotent settlement with ledger integration
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-005: Revenue Settlement Tests
# =============================================================================


@pytest.mark.django_db
class TestRevenueSettlementCreatesRecord:
    """Test: Revenue settlement creates record and ledger transaction."""

    def test_revenue_settlement_creates_record_and_ledger_tx(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """create_revenue_settlement() creates SettlementRecord with linked transaction."""
        from django_ledger.models import Transaction

        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SettlementRecord,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        # Setup: Create booking with price snapshot
        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_settle_ow", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Settlement Test Dive",
            slug="settlement-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("150.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
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
        )

        # Confirm booking to allow settlement
        booking.status = "confirmed"
        booking.save()

        initial_settlement_count = SettlementRecord.objects.count()
        initial_tx_count = Transaction.objects.count()

        # Act: Create revenue settlement
        settlement = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        # Assert: SettlementRecord created
        assert SettlementRecord.objects.count() == initial_settlement_count + 1
        assert settlement.booking == booking
        assert settlement.amount == booking.price_amount
        assert settlement.currency == booking.price_currency
        assert settlement.settlement_type == "revenue"

        # Assert: Transaction created and linked
        assert Transaction.objects.count() == initial_tx_count + 1
        assert settlement.transaction is not None
        assert settlement.transaction.posted_at is not None  # Transaction is posted

    def test_transaction_is_balanced(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Revenue settlement creates balanced transaction (debits == credits)."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_balance", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Balance Test Dive",
            slug="balance-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("200.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
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
        )
        booking.status = "confirmed"
        booking.save()

        settlement = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        # Verify transaction is balanced
        entries = settlement.transaction.entries.all()
        debits = sum(e.amount for e in entries if e.entry_type == "debit")
        credits = sum(e.amount for e in entries if e.entry_type == "credit")
        assert debits == credits
        assert debits == Decimal("200.00")


@pytest.mark.django_db
class TestRevenueSettlementIdempotency:
    """Test: Revenue settlement is idempotent."""

    def test_revenue_settlement_is_idempotent(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Calling create_revenue_settlement twice returns same record."""
        from django_ledger.models import Transaction

        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SettlementRecord,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_idemp", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Idempotency Test Dive",
            slug="idempotency-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("175.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("175.00"),
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

        # First call
        settlement1 = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        settlement_count_after_first = SettlementRecord.objects.count()
        tx_count_after_first = Transaction.objects.count()

        # Second call - should return same record
        settlement2 = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        # Assert: Same record returned
        assert settlement2.pk == settlement1.pk
        assert settlement2.idempotency_key == settlement1.idempotency_key

        # Assert: No new records created
        assert SettlementRecord.objects.count() == settlement_count_after_first
        assert Transaction.objects.count() == tx_count_after_first


@pytest.mark.django_db
class TestRevenueSettlementRequiresPriceSnapshot:
    """Test: Revenue settlement requires price snapshot."""

    def test_revenue_settlement_requires_price_snapshot(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """Settlement creation fails if booking has no price_amount."""
        from primitives_testbed.diveops.models import Booking, Excursion
        from primitives_testbed.diveops.services import create_revenue_settlement

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=None,  # No type = no price snapshot
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        # Create booking directly without price snapshot
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot=None,
            price_amount=None,
            price_currency="",
        )

        with pytest.raises(ValueError, match="price"):
            create_revenue_settlement(
                booking=booking,
                processed_by=user,
            )


@pytest.mark.django_db
class TestRevenueSettlementDisallowedForCancelled:
    """Test: Revenue settlement disallowed for cancelled bookings."""

    def test_revenue_settlement_disallowed_for_cancelled_booking(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Settlement creation fails if booking is cancelled."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            cancel_booking,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_cancel", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Cancel Test Dive",
            slug="cancel-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
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

        # Cancel the booking
        cancel_booking(booking, cancelled_by=user)
        booking.refresh_from_db()

        with pytest.raises(ValueError, match="cancelled"):
            create_revenue_settlement(
                booking=booking,
                processed_by=user,
            )

    def test_settlement_allowed_for_confirmed_booking(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Settlement allowed for confirmed bookings."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SettlementRecord,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_confirm", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Confirm Test Dive",
            slug="confirm-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
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

        # Should succeed
        settlement = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        assert settlement is not None
        assert settlement.settlement_type == "revenue"


@pytest.mark.django_db
class TestRevenueSettlementAuditEvent:
    """Test: Revenue settlement emits audit event."""

    def test_audit_event_emitted(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Settlement creation emits SETTLEMENT_POSTED audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_audit_s", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Audit Settlement Dive",
            slug="audit-settlement-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("125.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("125.00"),
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

        initial_audit_count = AuditLog.objects.count()

        settlement = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        # Check audit event
        assert AuditLog.objects.count() > initial_audit_count

        settlement_event = AuditLog.objects.filter(
            action=Actions.SETTLEMENT_POSTED
        ).first()
        assert settlement_event is not None
        assert "booking_id" in settlement_event.metadata
        assert "settlement_id" in settlement_event.metadata
        assert "amount" in settlement_event.metadata
        assert "idempotency_key" in settlement_event.metadata


@pytest.mark.django_db
class TestSettlementRecordModel:
    """Test: SettlementRecord model has correct fields."""

    def test_settlement_record_has_required_fields(self, db):
        """SettlementRecord model has all required fields."""
        from primitives_testbed.diveops.models import SettlementRecord

        # Check field existence
        field_names = [f.name for f in SettlementRecord._meta.get_fields()]

        assert "booking" in field_names
        assert "idempotency_key" in field_names
        assert "amount" in field_names
        assert "currency" in field_names
        assert "transaction" in field_names
        assert "settlement_type" in field_names
        assert "processed_by" in field_names
        assert "settled_at" in field_names

    def test_idempotency_key_is_unique(self, db):
        """idempotency_key has unique constraint."""
        from primitives_testbed.diveops.models import SettlementRecord

        field = SettlementRecord._meta.get_field("idempotency_key")
        assert field.unique is True


@pytest.mark.django_db
class TestIdempotencyKeyFormat:
    """Test: Idempotency key format is deterministic."""

    def test_idempotency_key_format(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Idempotency key follows format: {booking_id}:revenue:1"""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            book_excursion,
            create_revenue_settlement,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_key", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Key Test Dive",
            slug="key-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
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

        settlement = create_revenue_settlement(
            booking=booking,
            processed_by=user,
        )

        expected_key = f"{booking.pk}:revenue:1"
        assert settlement.idempotency_key == expected_key
