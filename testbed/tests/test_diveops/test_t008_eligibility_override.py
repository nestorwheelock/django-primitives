"""Tests for T-008: Activate EligibilityOverride (Booking-Only Exceptions).

This module tests INV-1: Booking-scoped eligibility override.

INV-1: Eligibility Override Rules
    - Overrides are booking-specific ONLY (OneToOne to Booking)
    - No FK to Excursion, Trip, or TripDay
    - Overrides do NOT modify requirements
    - Overrides only bypass a failed eligibility check for one booking
    - Requires approver + reason
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-008: EligibilityOverride Model Tests
# =============================================================================


@pytest.mark.django_db
class TestEligibilityOverrideModel:
    """Test: EligibilityOverride model exists with correct structure."""

    def test_eligibility_override_model_exists(self, db):
        """EligibilityOverride model can be imported."""
        from primitives_testbed.diveops.models import EligibilityOverride

        # Model exists
        assert EligibilityOverride is not None

    def test_eligibility_override_has_booking_fk(self, db):
        """EligibilityOverride has OneToOne relationship to Booking."""
        from primitives_testbed.diveops.models import EligibilityOverride

        field = EligibilityOverride._meta.get_field("booking")
        assert field.one_to_one is True
        assert field.related_model.__name__ == "Booking"

    def test_eligibility_override_has_required_fields(self, db):
        """EligibilityOverride has all required fields."""
        from primitives_testbed.diveops.models import EligibilityOverride

        # Required fields
        assert EligibilityOverride._meta.get_field("booking") is not None
        assert EligibilityOverride._meta.get_field("diver") is not None
        assert EligibilityOverride._meta.get_field("requirement_type") is not None
        assert EligibilityOverride._meta.get_field("original_requirement") is not None
        assert EligibilityOverride._meta.get_field("reason") is not None
        assert EligibilityOverride._meta.get_field("approved_by") is not None
        assert EligibilityOverride._meta.get_field("approved_at") is not None

    def test_eligibility_override_no_excursion_fk(self, db):
        """EligibilityOverride has NO FK to Excursion (booking-scoped only)."""
        from primitives_testbed.diveops.models import EligibilityOverride

        field_names = [f.name for f in EligibilityOverride._meta.get_fields()]
        assert "excursion" not in field_names

    def test_eligibility_override_no_trip_fk(self, db):
        """EligibilityOverride has NO FK to Trip (booking-scoped only)."""
        from primitives_testbed.diveops.models import EligibilityOverride

        field_names = [f.name for f in EligibilityOverride._meta.get_fields()]
        assert "trip" not in field_names


# =============================================================================
# T-008: Record Override Service Tests
# =============================================================================


@pytest.mark.django_db
class TestRecordBookingEligibilityOverride:
    """Test: record_booking_eligibility_override() service function."""

    def test_record_override_creates_record(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """record_booking_eligibility_override() creates EligibilityOverride record."""
        from primitives_testbed.diveops.eligibility_service import (
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import (
            Booking,
            EligibilityOverride,
            Excursion,
        )

        # Create excursion and booking
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        # Record override
        override = record_booking_eligibility_override(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW", "rank": 3},
            approver=user,
            reason="Experienced diver with logged dives",
        )

        # Verify record created
        assert override is not None
        assert override.booking == booking
        assert override.diver == diver_profile
        assert override.requirement_type == "certification"
        assert override.reason == "Experienced diver with logged dives"

        # Verify in database
        assert EligibilityOverride.objects.filter(booking=booking).exists()

    def test_record_override_requires_approver(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """record_booking_eligibility_override() requires approver."""
        from primitives_testbed.diveops.eligibility_service import (
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import Booking, Excursion

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        with pytest.raises(ValueError, match="approver"):
            record_booking_eligibility_override(
                booking=booking,
                diver=diver_profile,
                requirement_type="certification",
                original_requirement={"level": "AOW"},
                approver=None,
                reason="Test reason",
            )

    def test_record_override_requires_reason(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """record_booking_eligibility_override() requires reason."""
        from primitives_testbed.diveops.eligibility_service import (
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import Booking, Excursion

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        with pytest.raises(ValueError, match="reason"):
            record_booking_eligibility_override(
                booking=booking,
                diver=diver_profile,
                requirement_type="certification",
                original_requirement={"level": "AOW"},
                approver=user,
                reason="",
            )

    def test_record_override_emits_audit_event(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """record_booking_eligibility_override() emits audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.eligibility_service import (
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import Booking, Excursion

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        initial_count = AuditLog.objects.count()

        record_booking_eligibility_override(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW"},
            approver=user,
            reason="Experienced diver",
        )

        # Verify audit event emitted
        assert AuditLog.objects.count() > initial_count

        # Check audit event details
        audit_event = AuditLog.objects.order_by("-created_at").first()
        assert "overridden" in audit_event.action.lower()


# =============================================================================
# T-008: Override Integration with Eligibility Check
# =============================================================================


@pytest.mark.django_db
class TestOverridePermitsBooking:
    """Test: Override permits otherwise-failing booking."""

    def test_override_permits_ineligible_booking(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Booking with override passes eligibility despite missing cert."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            Excursion,
            ExcursionType,
        )

        # Create cert level requiring AOW
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_override", name="Advanced Open Water", rank=3
        )

        # Create excursion type requiring AOW
        excursion_type = ExcursionType.objects.create(
            name="Deep Dive Override Test",
            slug="deep-dive-override-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=40,
            base_price=Decimal("200.00"),
            currency="USD",
            min_certification_level=aow_level,
            requires_cert=True,
        )

        # Create excursion
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

        # Create booking (diver has no cert)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        # Without override, should be ineligible
        result_without_override = check_layered_eligibility(diver_profile, booking)
        assert result_without_override.eligible is False

        # Record override
        record_booking_eligibility_override(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW", "rank": 3},
            approver=user,
            reason="Experienced technical diver with 500+ dives",
        )

        # With override, should be eligible
        result_with_override = check_layered_eligibility(diver_profile, booking)
        assert result_with_override.eligible is True

    def test_override_metadata_indicates_override_used(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Eligibility result indicates override was used."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            Excursion,
            ExcursionType,
        )

        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_meta", name="AOW", rank=3
        )

        excursion_type = ExcursionType.objects.create(
            name="Meta Test Dive",
            slug="meta-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=30,
            base_price=Decimal("150.00"),
            currency="USD",
            min_certification_level=aow_level,
            requires_cert=True,
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

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        record_booking_eligibility_override(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW"},
            approver=user,
            reason="Override test",
        )

        result = check_layered_eligibility(diver_profile, booking)

        # Result should indicate override was used
        assert result.eligible is True
        assert hasattr(result, "override_used") and result.override_used is True


# =============================================================================
# T-008: Override Scope Tests
# =============================================================================


@pytest.mark.django_db
class TestOverrideBookingScopedOnly:
    """Test: Override applies ONLY to that booking."""

    def test_override_does_not_affect_other_bookings(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Override for booking A does not affect booking B."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            Excursion,
            ExcursionType,
        )

        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_scope", name="AOW", rank=3
        )

        excursion_type = ExcursionType.objects.create(
            name="Scope Test Dive",
            slug="scope-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=30,
            base_price=Decimal("150.00"),
            currency="USD",
            min_certification_level=aow_level,
            requires_cert=True,
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

        # Create two bookings for same diver
        booking_a = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        # Create second excursion for booking B
        day_after = timezone.now() + timedelta(days=2)
        excursion_b = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=day_after,
            return_time=day_after + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )

        booking_b = Booking.objects.create(
            excursion=excursion_b,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        # Override only booking A
        record_booking_eligibility_override(
            booking=booking_a,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW"},
            approver=user,
            reason="Override for booking A only",
        )

        # Booking A should be eligible (has override)
        result_a = check_layered_eligibility(diver_profile, booking_a)
        assert result_a.eligible is True

        # Booking B should NOT be eligible (no override)
        result_b = check_layered_eligibility(diver_profile, booking_b)
        assert result_b.eligible is False

    def test_override_does_not_modify_excursion_requirements(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Override does not change the excursion's requirements."""
        from primitives_testbed.diveops.eligibility_service import (
            record_booking_eligibility_override,
        )
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            Excursion,
            ExcursionType,
        )

        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_nomod", name="AOW", rank=3
        )

        excursion_type = ExcursionType.objects.create(
            name="No Modify Test",
            slug="no-modify-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=30,
            base_price=Decimal("150.00"),
            currency="USD",
            min_certification_level=aow_level,
            requires_cert=True,
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

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        # Record original requirement
        original_min_cert = excursion_type.min_certification_level
        original_requires_cert = excursion_type.requires_cert

        # Create override
        record_booking_eligibility_override(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW"},
            approver=user,
            reason="Override test",
        )

        # Reload excursion_type
        excursion_type.refresh_from_db()

        # Requirements should be unchanged
        assert excursion_type.min_certification_level == original_min_cert
        assert excursion_type.requires_cert == original_requires_cert


# =============================================================================
# T-008: One Override Per Booking Tests
# =============================================================================


@pytest.mark.django_db
class TestOneOverridePerBooking:
    """Test: Only one override per booking (OneToOne relationship)."""

    def test_cannot_create_duplicate_override(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """Cannot create second override for same booking."""
        from django.db import IntegrityError

        from primitives_testbed.diveops.models import (
            Booking,
            EligibilityOverride,
            Excursion,
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
        )

        # Create first override
        EligibilityOverride.objects.create(
            booking=booking,
            diver=diver_profile,
            requirement_type="certification",
            original_requirement={"level": "AOW"},
            reason="First override",
            approved_by=user,
        )

        # Try to create second - should fail
        with pytest.raises(IntegrityError):
            EligibilityOverride.objects.create(
                booking=booking,
                diver=diver_profile,
                requirement_type="experience",
                original_requirement={"min_dives": 50},
                reason="Second override",
                approved_by=user,
            )
