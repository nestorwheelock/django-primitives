"""T-009: Commission Rule Definition (Minimal Viable)

Tests for commission rule model and calculation service.

Commission rules define how revenue is split for bookings:
- Shop default commission rate (applies to all bookings)
- ExcursionType-specific overrides (higher priority)
- Effective dating for rate changes
- Percentage or fixed amount rates

INV-3: Commission rules are effective-dated.
       Latest effective_at <= as_of date wins.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def create_test_excursion(dive_shop, dive_site, user, excursion_type=None):
    """Helper to create a valid Excursion for tests."""
    from primitives_testbed.diveops.models import Excursion

    now = timezone.now()
    departure = now + timedelta(days=7)
    return_time = departure + timedelta(hours=4)

    return Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        excursion_type=excursion_type,
        departure_time=departure,
        return_time=return_time,
        max_divers=10,
        price_per_diver=Decimal("100.00"),
        status="scheduled",
        created_by=user,
    )


def create_test_excursion_type(cert_level):
    """Helper to create a valid ExcursionType for tests."""
    from primitives_testbed.diveops.models import ExcursionType
    import uuid

    return ExcursionType.objects.create(
        name="Test Excursion Type",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        dive_mode=ExcursionType.DiveMode.BOAT,
        max_depth_meters=18,
        requires_cert=True,
        min_certification_level=cert_level,
        base_price=Decimal("100.00"),
    )


# =============================================================================
# T-009: Commission Rule Model Tests
# =============================================================================


@pytest.mark.django_db
class TestCommissionRuleModel:
    """Test: CommissionRule model exists with required structure."""

    def test_commission_rule_model_exists(self):
        """CommissionRule model can be imported."""
        from primitives_testbed.diveops.models import CommissionRule

        assert CommissionRule is not None

    def test_commission_rule_has_dive_shop_fk(self):
        """CommissionRule has FK to dive_shop (Organization)."""
        from primitives_testbed.diveops.models import CommissionRule

        field = CommissionRule._meta.get_field("dive_shop")
        assert field.related_model.__name__ == "Organization"
        assert not field.null  # Required

    def test_commission_rule_has_rate_type_choices(self):
        """CommissionRule has rate_type with percentage/fixed choices."""
        from primitives_testbed.diveops.models import CommissionRule

        assert hasattr(CommissionRule, "RateType")
        assert CommissionRule.RateType.PERCENTAGE == "percentage"
        assert CommissionRule.RateType.FIXED == "fixed"

    def test_commission_rule_has_rate_value(self):
        """CommissionRule has rate_value DecimalField."""
        from primitives_testbed.diveops.models import CommissionRule

        field = CommissionRule._meta.get_field("rate_value")
        assert field.get_internal_type() == "DecimalField"

    def test_commission_rule_has_effective_at(self):
        """CommissionRule has effective_at DateTimeField."""
        from primitives_testbed.diveops.models import CommissionRule

        field = CommissionRule._meta.get_field("effective_at")
        assert "DateTime" in field.get_internal_type()

    def test_commission_rule_has_optional_excursion_type_fk(self):
        """CommissionRule has optional FK to ExcursionType for overrides."""
        from primitives_testbed.diveops.models import CommissionRule

        field = CommissionRule._meta.get_field("excursion_type")
        assert field.null  # Optional
        assert field.related_model.__name__ == "ExcursionType"


# =============================================================================
# T-009: Commission Rule Creation Tests
# =============================================================================


@pytest.mark.django_db
class TestCommissionRuleCreation:
    """Test: CommissionRule records can be created."""

    def test_create_percentage_commission_rule(self, dive_shop):
        """Create a percentage-based commission rule."""
        from primitives_testbed.diveops.models import CommissionRule

        rule = CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("15.00"),  # 15%
            effective_at=timezone.now(),
        )
        assert rule.pk is not None
        assert rule.rate_type == "percentage"
        assert rule.rate_value == Decimal("15.00")

    def test_create_fixed_commission_rule(self, dive_shop):
        """Create a fixed-amount commission rule."""
        from primitives_testbed.diveops.models import CommissionRule

        rule = CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.FIXED,
            rate_value=Decimal("25.00"),  # $25 flat
            effective_at=timezone.now(),
        )
        assert rule.pk is not None
        assert rule.rate_type == "fixed"
        assert rule.rate_value == Decimal("25.00")

    def test_create_excursion_type_specific_rule(self, dive_shop, padi_agency):
        """Create a commission rule for a specific ExcursionType."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            CommissionRule,
        )

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="aow",
            name="Advanced Open Water",
            rank=3,
        )
        excursion_type = create_test_excursion_type(cert_level)

        rule = CommissionRule.objects.create(
            dive_shop=dive_shop,
            excursion_type=excursion_type,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("20.00"),  # 20% for night dives
            effective_at=timezone.now(),
        )
        assert rule.excursion_type == excursion_type


# =============================================================================
# T-009: Commission Calculation Service Tests
# =============================================================================


@pytest.mark.django_db
class TestCalculateCommission:
    """Test: calculate_commission service function."""

    def test_calculate_commission_with_percentage_rate(
        self, dive_shop, dive_site, diver_profile, user
    ):
        """Commission calculated as percentage of booking price."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import (
            Booking,
            CommissionRule,
        )

        # Create commission rule: 15%
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("15.00"),
            effective_at=timezone.now() - timedelta(days=1),
        )

        # Create excursion and booking
        excursion = create_test_excursion(dive_shop, dive_site, user)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        commission = calculate_commission(booking)
        assert commission == Decimal("15.00")  # 15% of $100

    def test_calculate_commission_with_fixed_rate(
        self, dive_shop, dive_site, diver_profile, user
    ):
        """Commission calculated as fixed amount."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import (
            Booking,
            CommissionRule,
        )

        # Create commission rule: $25 fixed
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.FIXED,
            rate_value=Decimal("25.00"),
            effective_at=timezone.now() - timedelta(days=1),
        )

        # Create excursion and booking
        excursion = create_test_excursion(dive_shop, dive_site, user)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        commission = calculate_commission(booking)
        assert commission == Decimal("25.00")  # Fixed $25

    def test_calculate_commission_no_rule_returns_zero(
        self, dive_shop, dive_site, diver_profile, user
    ):
        """No commission rule returns zero commission."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import Booking

        # No commission rule created

        excursion = create_test_excursion(dive_shop, dive_site, user)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        commission = calculate_commission(booking)
        assert commission == Decimal("0.00")


# =============================================================================
# T-009: Effective Dating Tests (INV-3)
# =============================================================================


@pytest.mark.django_db
class TestCommissionEffectiveDating:
    """Test: Commission rules respect effective dating (INV-3)."""

    def test_uses_latest_effective_rule(self, dive_shop, dive_site, diver_profile, user):
        """Latest effective_at <= as_of wins."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import (
            Booking,
            CommissionRule,
        )

        now = timezone.now()

        # Old rule: 10% (30 days ago)
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("10.00"),
            effective_at=now - timedelta(days=30),
        )

        # Current rule: 15% (7 days ago)
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("15.00"),
            effective_at=now - timedelta(days=7),
        )

        # Future rule: 20% (7 days from now) - should NOT apply
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("20.00"),
            effective_at=now + timedelta(days=7),
        )

        excursion = create_test_excursion(dive_shop, dive_site, user)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        # Should use 15% rule (latest effective)
        commission = calculate_commission(booking)
        assert commission == Decimal("15.00")

    def test_as_of_parameter_selects_historical_rule(
        self, dive_shop, dive_site, diver_profile, user
    ):
        """as_of parameter allows selecting historical rates."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import (
            Booking,
            CommissionRule,
        )

        now = timezone.now()

        # Old rule: 10% (30 days ago)
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("10.00"),
            effective_at=now - timedelta(days=30),
        )

        # Current rule: 15% (7 days ago)
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("15.00"),
            effective_at=now - timedelta(days=7),
        )

        excursion = create_test_excursion(dive_shop, dive_site, user)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        # Calculate with as_of 20 days ago (before current rule)
        historical_as_of = now - timedelta(days=20)
        commission = calculate_commission(booking, as_of=historical_as_of)
        assert commission == Decimal("10.00")  # Uses old 10% rule


# =============================================================================
# T-009: ExcursionType Override Tests
# =============================================================================


@pytest.mark.django_db
class TestExcursionTypeOverride:
    """Test: ExcursionType-specific rules override shop defaults."""

    def test_excursion_type_rule_overrides_shop_default(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """ExcursionType-specific rule takes precedence over shop default."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            CommissionRule,
        )

        now = timezone.now()

        # Shop default: 10%
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            excursion_type=None,  # Shop default
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("10.00"),
            effective_at=now - timedelta(days=30),
        )

        # Create ExcursionType
        cert_level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="ow-test",
            name="Open Water Test",
            rank=2,
        )
        excursion_type = create_test_excursion_type(cert_level)

        # ExcursionType-specific rule: 20%
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            excursion_type=excursion_type,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("20.00"),
            effective_at=now - timedelta(days=30),
        )

        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        # Should use 20% ExcursionType-specific rule
        commission = calculate_commission(booking)
        assert commission == Decimal("20.00")

    def test_falls_back_to_shop_default_if_no_type_rule(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Falls back to shop default if no ExcursionType-specific rule."""
        from primitives_testbed.diveops.commission_service import calculate_commission
        from primitives_testbed.diveops.models import (
            Booking,
            CertificationLevel,
            CommissionRule,
        )

        now = timezone.now()

        # Shop default: 10%
        CommissionRule.objects.create(
            dive_shop=dive_shop,
            excursion_type=None,
            rate_type=CommissionRule.RateType.PERCENTAGE,
            rate_value=Decimal("10.00"),
            effective_at=now - timedelta(days=30),
        )

        # Create ExcursionType WITHOUT a specific rule
        cert_level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="ow-test2",
            name="Open Water Test 2",
            rank=2,
        )
        excursion_type = create_test_excursion_type(cert_level)

        excursion = create_test_excursion(dive_shop, dive_site, user, excursion_type)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="confirmed",
            price_snapshot={"amount": "100.00", "currency": "USD"},
        )

        # Should fall back to 10% shop default
        commission = calculate_commission(booking)
        assert commission == Decimal("10.00")
