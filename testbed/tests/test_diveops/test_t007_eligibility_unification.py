"""Tests for T-007: Eligibility Engine Unification.

This module tests INV-2: Layered Hierarchy Authoritative.

INV-2: Layered Eligibility Hierarchy
    - Single entry point: check_layered_eligibility(diver, target, *, effective_at=None)
    - Target can be: ExcursionType, Excursion, Trip, or Booking
    - Evaluates layers: ExcursionType → Excursion → Trip
    - Short-circuits on first failure
    - Respects effective_at time parameter
"""

import warnings
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-007: Unified Eligibility Engine Tests
# =============================================================================


@pytest.mark.django_db
class TestLayeredEligibilityTrip:
    """Test: check_layered_eligibility(diver, trip) matches legacy wrapper.

    Legacy can_diver_join_trip() behavior must be preserved when
    called through new unified function with Trip target.
    """

    def test_layered_eligibility_trip_future_confirmed_is_eligible(
        self, dive_shop, diver_profile, user, padi_agency
    ):
        """check_layered_eligibility(diver, trip) returns eligible for future confirmed trip."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import Trip

        # Create a future confirmed trip
        trip = Trip.objects.create(
            name="Test Trip",
            dive_shop=dive_shop,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=8),
            status="confirmed",
            created_by=user,
        )

        # Call unified function
        result = check_layered_eligibility(diver_profile, trip)

        # Should be eligible - trip is confirmed and in the future
        assert result.eligible is True
        assert result.reason == ""
        assert "trip" in result.checked_layers

    def test_layered_eligibility_trip_cancelled_is_ineligible(
        self, dive_shop, diver_profile, user
    ):
        """Cancelled trip returns ineligible."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import Trip

        trip = Trip.objects.create(
            name="Cancelled Trip",
            dive_shop=dive_shop,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=8),
            status="cancelled",
            created_by=user,
        )

        result = check_layered_eligibility(diver_profile, trip)

        assert result.eligible is False
        assert "cancelled" in result.reason.lower()

    def test_layered_eligibility_trip_past_is_ineligible(
        self, dive_shop, diver_profile, user
    ):
        """Past trip returns ineligible."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import Trip

        trip = Trip.objects.create(
            name="Past Trip",
            dive_shop=dive_shop,
            start_date=date.today() - timedelta(days=7),
            end_date=date.today() - timedelta(days=6),
            status="completed",
            created_by=user,
        )

        result = check_layered_eligibility(diver_profile, trip)

        assert result.eligible is False


@pytest.mark.django_db
class TestLayeredEligibilityExcursion:
    """Test: check_layered_eligibility(diver, excursion) enforces type then excursion.

    Excursion eligibility checks both ExcursionType (certification) and
    Excursion-specific requirements (operational).
    """

    def test_layered_eligibility_excursion_enforces_type_then_excursion(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Excursion check evaluates ExcursionType first, then Excursion requirements."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            Excursion,
            ExcursionType,
        )

        # Create cert level requiring Advanced Open Water
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_test", name="Advanced Open Water", rank=3
        )

        # Create excursion type requiring AOW
        excursion_type = ExcursionType.objects.create(
            name="Deep Dive",
            slug="deep-dive-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=40,
            base_price=Decimal("200.00"),
            currency="USD",
            min_certification_level=aow_level,
            requires_cert=True,
        )

        # Create excursion with this type
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

        # Diver has no certification - should fail at ExcursionType layer
        result = check_layered_eligibility(diver_profile, excursion)

        assert result.eligible is False
        assert "certification" in result.reason.lower()
        assert "excursion_type" in result.checked_layers

    def test_layered_eligibility_excursion_with_sufficient_cert(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Diver with sufficient certification passes excursion eligibility."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            Excursion,
            ExcursionType,
        )

        # Create cert levels
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow_test_unified", name="Open Water", rank=2
        )

        # Create excursion type requiring OW
        excursion_type = ExcursionType.objects.create(
            name="Reef Dive",
            slug="reef-dive-test-unified",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
            min_certification_level=ow_level,
            requires_cert=True,
        )

        # Give diver OW certification
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW12345",
            issued_on=date.today() - timedelta(days=30),
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
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        result = check_layered_eligibility(diver_profile, excursion)

        assert result.eligible is True
        assert result.reason == ""


@pytest.mark.django_db
class TestLayeredEligibilityBooking:
    """Test: check_layered_eligibility(diver, booking) delegates to excursion."""

    def test_layered_eligibility_booking_delegates_to_excursion(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Booking eligibility delegates to its excursion."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            Excursion,
            ExcursionType,
        )

        # Create excursion type (no cert required)
        excursion_type = ExcursionType.objects.create(
            name="DSD",
            slug="dsd-test-unified",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=12,
            base_price=Decimal("150.00"),
            currency="USD",
            requires_cert=False,
            is_training=True,
        )

        # Create excursion
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=3),
            max_divers=4,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )

        # Create booking
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
        )

        result = check_layered_eligibility(diver_profile, booking)

        # Since this is DSD (no cert required), should be eligible
        assert result.eligible is True


@pytest.mark.django_db
class TestEffectiveAtTimeSemantics:
    """Test: effective_at parameter is respected for temporal eligibility."""

    def test_effective_at_is_respected(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """check_layered_eligibility respects effective_at parameter."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            Excursion,
            ExcursionType,
        )

        # Create cert level
        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow_time_test", name="Open Water", rank=2
        )

        excursion_type = ExcursionType.objects.create(
            name="Time Test Dive",
            slug="time-test-dive",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
            min_certification_level=ow_level,
            requires_cert=True,
        )

        # Give diver a certification that expired yesterday
        yesterday = date.today() - timedelta(days=1)
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW-EXPIRED",
            issued_on=date.today() - timedelta(days=365),
            expires_on=yesterday,
        )

        # Create excursion in the future
        next_week = timezone.now() + timedelta(days=7)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=next_week,
            return_time=next_week + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        # Check eligibility at current time - should fail (cert expired)
        result_now = check_layered_eligibility(diver_profile, excursion)
        assert result_now.eligible is False

        # Check eligibility at a time when cert was valid (last week)
        last_week = timezone.now() - timedelta(days=7)
        result_last_week = check_layered_eligibility(
            diver_profile, excursion, effective_at=last_week
        )
        assert result_last_week.eligible is True

    def test_effective_at_defaults_to_now(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """If effective_at is None, it defaults to current time."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            Excursion,
            ExcursionType,
        )

        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow_default_time", name="Open Water", rank=2
        )

        excursion_type = ExcursionType.objects.create(
            name="Default Time Dive",
            slug="default-time-dive",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
            min_certification_level=ow_level,
            requires_cert=True,
        )

        # Give diver a valid (non-expired) certification
        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW-VALID",
            issued_on=date.today() - timedelta(days=30),
            expires_on=None,  # Never expires
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

        # Call without effective_at - should use current time
        result = check_layered_eligibility(diver_profile, excursion)
        assert result.eligible is True


@pytest.mark.django_db
class TestDeprecationWarning:
    """Test: can_diver_join_trip emits deprecation warning."""

    def test_deprecation_warning_emitted(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """can_diver_join_trip() emits DeprecationWarning pointing to new function."""
        from primitives_testbed.diveops.decisioning import can_diver_join_trip
        from primitives_testbed.diveops.models import DiveTrip  # Alias for Excursion

        # DiveTrip is an alias for Excursion which has departure_time
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = DiveTrip.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=100,
            currency="USD",
            status="scheduled",
            created_by=user,
        )

        # Give diver medical clearance
        diver_profile.medical_clearance_valid_until = date.today() + timedelta(days=365)
        diver_profile.save()

        # Should emit deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            can_diver_join_trip(diver_profile, excursion)

            # Check that deprecation warning was issued
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "check_layered_eligibility" in str(w[0].message)


@pytest.mark.django_db
class TestEligibilityResultSchema:
    """Test: unified EligibilityResult has correct schema."""

    def test_eligibility_result_has_checked_layers(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """EligibilityResult includes checked_layers list."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            DiverCertification,
            Excursion,
            ExcursionType,
        )

        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow_schema_test", name="Open Water", rank=2
        )

        excursion_type = ExcursionType.objects.create(
            name="Schema Test Dive",
            slug="schema-test-dive",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
            min_certification_level=ow_level,
            requires_cert=True,
        )

        DiverCertification.objects.create(
            diver=diver_profile,
            level=ow_level,
            card_number="OW-SCHEMA",
            issued_on=date.today() - timedelta(days=30),
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

        result = check_layered_eligibility(diver_profile, excursion)

        # Result should have checked_layers attribute
        assert hasattr(result, "checked_layers")
        assert isinstance(result.checked_layers, list)
        # For Excursion, should check excursion_type layer
        assert "excursion_type" in result.checked_layers

    def test_eligibility_result_has_override_allowed(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """EligibilityResult includes override_allowed flag."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )

        # Create excursion type requiring cert
        aow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="aow_override_test", name="AOW", rank=3
        )

        excursion_type = ExcursionType.objects.create(
            name="Override Test Dive",
            slug="override-test-dive",
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

        # Diver has no cert - should fail with override_allowed=True
        result = check_layered_eligibility(diver_profile, excursion)

        assert result.eligible is False
        assert hasattr(result, "override_allowed")
        assert result.override_allowed is True


@pytest.mark.django_db
class TestExcursionTypeDirectEligibility:
    """Test: check_layered_eligibility(diver, excursion_type) works directly."""

    def test_excursion_type_direct_eligibility_check(
        self, diver_profile, padi_agency
    ):
        """ExcursionType can be passed directly as target."""
        from primitives_testbed.diveops.eligibility_service import (
            check_layered_eligibility,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            ExcursionType,
        )

        ow_level = CertificationLevel.objects.create(
            agency=padi_agency, code="ow_direct_test", name="Open Water", rank=2
        )

        excursion_type = ExcursionType.objects.create(
            name="Direct Type Test",
            slug="direct-type-test",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
            min_certification_level=ow_level,
            requires_cert=True,
        )

        # Diver has no cert - should fail
        result = check_layered_eligibility(diver_profile, excursion_type)

        assert result.eligible is False
        assert "certification" in result.reason.lower()
        assert "excursion_type" in result.checked_layers
