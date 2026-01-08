"""Tests for T-004: Cancellation Refund Decision (NO MONEY MOVEMENT).

This module tests the refund decision logic for booking cancellations.

Requirements:
- RefundDecision dataclass captures refund outcome
- cancel_booking() computes refund using agreement terms
- Uses Booking.price_snapshot exclusively (immutable)
- Terminates agreement on cancellation
- NO settlement records, NO ledger entries

The refund is a DECISION, not a MOVEMENT of money.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-004: Cancellation Refund Decision Tests
# =============================================================================


@pytest.mark.django_db
class TestRefundDecisionDataclass:
    """Test: RefundDecision captures refund outcome."""

    def test_refund_decision_has_required_fields(self):
        """RefundDecision has amount, percent, reason, policy_version."""
        from primitives_testbed.diveops.cancellation_policy import RefundDecision

        decision = RefundDecision(
            refund_amount=Decimal("50.00"),
            refund_percent=50,
            original_amount=Decimal("100.00"),
            currency="USD",
            hours_before_departure=36,
            policy_tier_applied={"hours_before": 24, "refund_percent": 50},
            reason="Cancelled 36 hours before departure",
        )

        assert decision.refund_amount == Decimal("50.00")
        assert decision.refund_percent == 50
        assert decision.original_amount == Decimal("100.00")
        assert decision.currency == "USD"
        assert decision.hours_before_departure == 36

    def test_refund_decision_is_immutable(self):
        """RefundDecision is frozen dataclass."""
        from primitives_testbed.diveops.cancellation_policy import RefundDecision

        decision = RefundDecision(
            refund_amount=Decimal("50.00"),
            refund_percent=50,
            original_amount=Decimal("100.00"),
            currency="USD",
            hours_before_departure=36,
            policy_tier_applied={"hours_before": 24, "refund_percent": 50},
            reason="Test",
        )

        with pytest.raises(AttributeError):
            decision.refund_amount = Decimal("100.00")


@pytest.mark.django_db
class TestComputeRefundDecision:
    """Test: compute_refund_decision() applies policy correctly."""

    def test_full_refund_when_cancelled_early(self):
        """Cancellation 48+ hours before gets 100% refund."""
        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
            compute_refund_decision,
        )

        departure = timezone.now() + timedelta(hours=72)
        cancellation_time = timezone.now()

        decision = compute_refund_decision(
            original_amount=Decimal("100.00"),
            currency="USD",
            departure_time=departure,
            cancellation_time=cancellation_time,
            policy=DEFAULT_CANCELLATION_POLICY,
        )

        assert decision.refund_percent == 100
        assert decision.refund_amount == Decimal("100.00")
        # Allow for slight timing differences in test execution
        assert decision.hours_before_departure >= 48  # Policy tier threshold

    def test_partial_refund_when_cancelled_medium(self):
        """Cancellation 24-48 hours before gets 50% refund."""
        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
            compute_refund_decision,
        )

        departure = timezone.now() + timedelta(hours=36)
        cancellation_time = timezone.now()

        decision = compute_refund_decision(
            original_amount=Decimal("100.00"),
            currency="USD",
            departure_time=departure,
            cancellation_time=cancellation_time,
            policy=DEFAULT_CANCELLATION_POLICY,
        )

        assert decision.refund_percent == 50
        assert decision.refund_amount == Decimal("50.00")

    def test_no_refund_when_cancelled_late(self):
        """Cancellation <24 hours before gets 0% refund."""
        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
            compute_refund_decision,
        )

        departure = timezone.now() + timedelta(hours=12)
        cancellation_time = timezone.now()

        decision = compute_refund_decision(
            original_amount=Decimal("100.00"),
            currency="USD",
            departure_time=departure,
            cancellation_time=cancellation_time,
            policy=DEFAULT_CANCELLATION_POLICY,
        )

        assert decision.refund_percent == 0
        assert decision.refund_amount == Decimal("0.00")

    def test_custom_policy_applied(self):
        """Custom policy tiers are applied correctly."""
        from primitives_testbed.diveops.cancellation_policy import compute_refund_decision

        custom_policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 72, "refund_percent": 100},
                {"hours_before": 24, "refund_percent": 25},
                {"hours_before": 0, "refund_percent": 0},
            ],
        }

        departure = timezone.now() + timedelta(hours=36)
        cancellation_time = timezone.now()

        decision = compute_refund_decision(
            original_amount=Decimal("200.00"),
            currency="USD",
            departure_time=departure,
            cancellation_time=cancellation_time,
            policy=custom_policy,
        )

        # 36 hours before, should match the 24-hour tier (25%)
        assert decision.refund_percent == 25
        assert decision.refund_amount == Decimal("50.00")

    def test_refund_rounds_to_two_decimals(self):
        """Refund amount is rounded to 2 decimal places."""
        from primitives_testbed.diveops.cancellation_policy import compute_refund_decision

        policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 24, "refund_percent": 33},
                {"hours_before": 0, "refund_percent": 0},
            ],
        }

        departure = timezone.now() + timedelta(hours=48)
        cancellation_time = timezone.now()

        decision = compute_refund_decision(
            original_amount=Decimal("100.00"),
            currency="USD",
            departure_time=departure,
            cancellation_time=cancellation_time,
            policy=policy,
        )

        # 33% of 100 = 33.00
        assert decision.refund_amount == Decimal("33.00")


@pytest.mark.django_db
class TestCancelBookingWithRefund:
    """Test: cancel_booking() computes refund decision."""

    def test_cancel_booking_returns_refund_decision(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """cancel_booking() returns RefundDecision when agreement exists."""
        from primitives_testbed.diveops.cancellation_policy import RefundDecision
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_cancel", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Cancel",
            slug="test-cancel",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        # Excursion 3 days from now (enough time for full refund)
        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
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

        result = cancel_booking(booking, cancelled_by=user)

        # Result should include refund decision
        assert hasattr(result, "refund_decision")
        assert isinstance(result.refund_decision, RefundDecision)
        assert result.refund_decision.refund_percent == 100

    def test_cancel_booking_uses_price_snapshot(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Refund is computed from price_snapshot, not current price."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_snap", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Snapshot",
            slug="test-snapshot",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("150.00"),
            currency="USD",
        )

        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
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

        original_price = booking.price_amount

        # Change the excursion price AFTER booking
        excursion.price_per_diver = Decimal("999.99")
        excursion.save()
        excursion_type.base_price = Decimal("999.99")
        excursion_type.save()

        result = cancel_booking(booking, cancelled_by=user)

        # Refund should be based on ORIGINAL snapshotted price
        assert result.refund_decision.original_amount == original_price

    def test_cancel_booking_no_agreement_no_refund_decision(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Booking without agreement returns null refund decision."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_noagr", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test No Agreement",
            slug="test-no-agreement",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        # Book WITHOUT agreement
        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=False,
        )

        result = cancel_booking(booking, cancelled_by=user)

        # No refund decision when no agreement
        assert result.refund_decision is None


@pytest.mark.django_db
class TestCancelBookingTerminatesAgreement:
    """Test: cancel_booking() terminates the waiver agreement."""

    def test_agreement_terminated_on_cancellation(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Agreement is terminated when booking is cancelled."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_term", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Terminate",
            slug="test-terminate",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
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

        agreement = booking.waiver_agreement
        assert agreement.valid_to is None  # Not terminated yet

        cancel_booking(booking, cancelled_by=user)

        agreement.refresh_from_db()
        assert agreement.valid_to is not None  # Now terminated
        assert agreement.is_active is False

    def test_agreement_version_created_on_termination(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Termination creates new AgreementVersion record."""
        from django_agreements.models import AgreementVersion

        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_vers2", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Version",
            slug="test-version",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
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

        agreement = booking.waiver_agreement
        initial_version_count = AgreementVersion.objects.filter(
            agreement=agreement
        ).count()

        cancel_booking(booking, cancelled_by=user)

        # Should have one more version (termination record)
        final_version_count = AgreementVersion.objects.filter(
            agreement=agreement
        ).count()
        assert final_version_count == initial_version_count + 1


@pytest.mark.django_db
class TestCancelBookingAuditEvents:
    """Test: cancel_booking() emits proper audit events."""

    def test_cancellation_emits_refund_decision_in_metadata(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Cancellation audit event includes refund decision details."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion, cancel_booking

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_meta", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Audit Meta",
            slug="test-audit-meta",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
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

        cancel_booking(booking, cancelled_by=user)

        # Find the cancellation audit event
        cancel_event = AuditLog.objects.filter(
            action=Actions.BOOKING_CANCELLED
        ).latest("created_at")

        # Should include refund decision in metadata
        assert "refund_percent" in cancel_event.metadata
        assert "refund_amount" in cancel_event.metadata


@pytest.mark.django_db
class TestCancellationResultDataclass:
    """Test: CancellationResult bundles booking and refund decision."""

    def test_cancellation_result_has_booking_and_decision(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """CancellationResult contains both booking and refund_decision."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import (
            CancellationResult,
            book_excursion,
            cancel_booking,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_res", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Result",
            slug="test-result",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        departure = timezone.now() + timedelta(days=3)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=departure,
            return_time=departure + timedelta(hours=4),
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

        result = cancel_booking(booking, cancelled_by=user)

        assert isinstance(result, CancellationResult)
        assert result.booking == booking
        assert result.booking.status == "cancelled"
