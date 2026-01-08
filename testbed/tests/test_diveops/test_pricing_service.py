"""Tests for ExcursionTypePricingService.

Tests the pricing computation that combines:
- ExcursionType base_price
- SitePriceAdjustment for distance, park fees, night surcharges
- Mode filtering (boat vs shore adjustments)
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


@pytest.fixture
def place(db):
    """Create a Place for dive site."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Test Reef Location",
        latitude=Decimal("25.123456"),
        longitude=Decimal("-80.123456"),
    )


@pytest.fixture
def another_place(db):
    """Create another Place."""
    from django_geo.models import Place

    return Place.objects.create(
        name="Distant Reef Location",
        latitude=Decimal("26.000000"),
        longitude=Decimal("-81.000000"),
    )


@pytest.fixture
def dive_site(db, place):
    """Create a nearby dive site."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="Nearby Reef",
        place=place,
        max_depth_meters=20,
        difficulty="intermediate",
    )


@pytest.fixture
def distant_site(db, another_place):
    """Create a distant dive site with higher costs."""
    from primitives_testbed.diveops.models import DiveSite

    return DiveSite.objects.create(
        name="Distant Wall",
        place=another_place,
        max_depth_meters=40,
        difficulty="advanced",
    )


@pytest.fixture
def beginner_boat_type(db):
    """Create a beginner boat dive excursion type."""
    from primitives_testbed.diveops.models import ExcursionType

    return ExcursionType.objects.create(
        name="Beginner Reef Dive",
        slug="beginner-reef",
        dive_mode="boat",
        time_of_day="day",
        max_depth_meters=18,
        base_price=Decimal("75.00"),
        currency="USD",
    )


@pytest.fixture
def shore_dive_type(db):
    """Create a shore dive excursion type."""
    from primitives_testbed.diveops.models import ExcursionType

    return ExcursionType.objects.create(
        name="Shore Dive",
        slug="shore-dive",
        dive_mode="shore",
        time_of_day="day",
        max_depth_meters=15,
        base_price=Decimal("50.00"),
        currency="USD",
    )


@pytest.fixture
def night_shore_type(db):
    """Create a night shore dive excursion type."""
    from primitives_testbed.diveops.models import ExcursionType

    return ExcursionType.objects.create(
        name="Night Shore Dive",
        slug="night-shore",
        dive_mode="shore",
        time_of_day="night",
        max_depth_meters=15,
        base_price=Decimal("60.00"),
        currency="USD",
    )


@pytest.fixture
def distance_adjustment(db, distant_site):
    """Create a distance surcharge for distant site."""
    from primitives_testbed.diveops.models import SitePriceAdjustment

    return SitePriceAdjustment.objects.create(
        dive_site=distant_site,
        kind="distance",
        amount=Decimal("25.00"),
        currency="USD",
    )


@pytest.fixture
def park_fee_adjustment(db, dive_site):
    """Create a park fee for nearby site."""
    from primitives_testbed.diveops.models import SitePriceAdjustment

    return SitePriceAdjustment.objects.create(
        dive_site=dive_site,
        kind="park_fee",
        amount=Decimal("10.00"),
        currency="USD",
    )


@pytest.fixture
def night_surcharge(db, dive_site):
    """Create a night dive surcharge."""
    from primitives_testbed.diveops.models import SitePriceAdjustment

    return SitePriceAdjustment.objects.create(
        dive_site=dive_site,
        kind="night",
        amount=Decimal("15.00"),
        currency="USD",
    )


@pytest.fixture
def boat_fee(db, dive_site):
    """Create a boat-only fee."""
    from primitives_testbed.diveops.models import SitePriceAdjustment

    return SitePriceAdjustment.objects.create(
        dive_site=dive_site,
        kind="boat",
        amount=Decimal("20.00"),
        currency="USD",
        applies_to_mode="boat",
    )


# =============================================================================
# Basic Price Computation Tests
# =============================================================================


@pytest.mark.django_db
class TestBasicPriceComputation:
    """Tests for basic price computation."""

    def test_compute_price_base_only(self, beginner_boat_type, dive_site):
        """Compute price with no site adjustments returns base price."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.base_price == Decimal("75.00")
        assert result.total_price == Decimal("75.00")
        assert result.currency == "USD"
        assert len(result.adjustments) == 0

    def test_compute_price_with_park_fee(self, beginner_boat_type, dive_site, park_fee_adjustment):
        """Compute price includes park fee adjustment."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.base_price == Decimal("75.00")
        assert result.total_price == Decimal("85.00")  # 75 + 10 park fee
        assert len(result.adjustments) == 1
        assert ("park_fee", Decimal("10.00")) in result.adjustments

    def test_compute_price_with_distance_surcharge(self, beginner_boat_type, distant_site, distance_adjustment):
        """Compute price includes distance surcharge."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=distant_site,
        )

        assert result.base_price == Decimal("75.00")
        assert result.total_price == Decimal("100.00")  # 75 + 25 distance
        assert len(result.adjustments) == 1
        assert ("distance", Decimal("25.00")) in result.adjustments


@pytest.mark.django_db
class TestMultipleAdjustments:
    """Tests for multiple adjustments combined."""

    def test_compute_price_multiple_adjustments(self, beginner_boat_type, dive_site, park_fee_adjustment, boat_fee):
        """Compute price includes multiple adjustments."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.base_price == Decimal("75.00")
        # 75 + 10 (park) + 20 (boat) = 105
        assert result.total_price == Decimal("105.00")
        assert len(result.adjustments) == 2

    def test_adjustments_list_contains_all(self, beginner_boat_type, dive_site, park_fee_adjustment, boat_fee):
        """Adjustments list includes all applied adjustments."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        adjustment_kinds = [adj[0] for adj in result.adjustments]
        assert "park_fee" in adjustment_kinds
        assert "boat" in adjustment_kinds


# =============================================================================
# Mode Filtering Tests
# =============================================================================


@pytest.mark.django_db
class TestModeFiltering:
    """Tests for dive mode filtering of adjustments."""

    def test_boat_fee_applies_to_boat_dive(self, beginner_boat_type, dive_site, boat_fee):
        """Boat fee applies to boat dive types."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.total_price == Decimal("95.00")  # 75 + 20 boat
        assert ("boat", Decimal("20.00")) in result.adjustments

    def test_boat_fee_does_not_apply_to_shore_dive(self, shore_dive_type, dive_site, boat_fee):
        """Boat fee does not apply to shore dive types."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=shore_dive_type,
            dive_site=dive_site,
        )

        assert result.total_price == Decimal("50.00")  # Just base, no boat fee
        assert ("boat", Decimal("20.00")) not in result.adjustments

    def test_universal_fee_applies_to_both_modes(self, beginner_boat_type, shore_dive_type, dive_site, park_fee_adjustment):
        """Park fee (no mode filter) applies to both boat and shore dives."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        boat_result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )
        shore_result = compute_excursion_price(
            excursion_type=shore_dive_type,
            dive_site=dive_site,
        )

        assert boat_result.total_price == Decimal("85.00")  # 75 + 10
        assert shore_result.total_price == Decimal("60.00")  # 50 + 10


# =============================================================================
# Night Dive Surcharge Tests
# =============================================================================


@pytest.mark.django_db
class TestNightSurcharge:
    """Tests for night dive surcharge handling."""

    def test_night_surcharge_applies_to_night_dive(self, night_shore_type, dive_site, night_surcharge):
        """Night surcharge applies when excursion type is night dive."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=night_shore_type,
            dive_site=dive_site,
        )

        assert result.base_price == Decimal("60.00")
        assert result.total_price == Decimal("75.00")  # 60 + 15 night
        assert ("night", Decimal("15.00")) in result.adjustments

    def test_night_surcharge_does_not_apply_to_day_dive(self, shore_dive_type, dive_site, night_surcharge):
        """Night surcharge does not apply to day dives."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=shore_dive_type,
            dive_site=dive_site,
        )

        assert result.total_price == Decimal("50.00")  # Just base, no night
        assert ("night", Decimal("15.00")) not in result.adjustments


# =============================================================================
# Inactive Adjustment Tests
# =============================================================================


@pytest.mark.django_db
class TestInactiveAdjustments:
    """Tests for inactive adjustments."""

    def test_inactive_adjustment_not_applied(self, beginner_boat_type, dive_site):
        """Inactive adjustments are not included in price."""
        from primitives_testbed.diveops.models import SitePriceAdjustment
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        # Create inactive adjustment
        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="park_fee",
            amount=Decimal("50.00"),
            is_active=False,
        )

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.total_price == Decimal("75.00")  # Just base
        assert len(result.adjustments) == 0

    def test_soft_deleted_adjustment_not_applied(self, beginner_boat_type, dive_site, park_fee_adjustment):
        """Soft deleted adjustments are not included in price."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        # Soft delete the adjustment
        park_fee_adjustment.deleted_at = timezone.now()
        park_fee_adjustment.save()

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.total_price == Decimal("75.00")  # Just base
        assert len(result.adjustments) == 0


# =============================================================================
# ComputedPrice Value Object Tests
# =============================================================================


@pytest.mark.django_db
class TestComputedPriceValueObject:
    """Tests for ComputedPrice value object."""

    def test_computed_price_has_breakdown(self, beginner_boat_type, dive_site, park_fee_adjustment, boat_fee):
        """ComputedPrice includes breakdown dict for display."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert "base" in result.breakdown
        assert "adjustments" in result.breakdown
        assert "total" in result.breakdown
        assert result.breakdown["base"] == Decimal("75.00")
        assert result.breakdown["total"] == Decimal("105.00")

    def test_computed_price_is_frozen(self, beginner_boat_type, dive_site):
        """ComputedPrice is immutable (frozen dataclass)."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        with pytest.raises(AttributeError):
            result.total_price = Decimal("999.00")


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.django_db
class TestEdgeCases:
    """Tests for edge cases in pricing."""

    def test_zero_base_price(self, dive_site):
        """Excursion type with zero base price works correctly."""
        from primitives_testbed.diveops.models import ExcursionType
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        free_type = ExcursionType.objects.create(
            name="Free Intro",
            slug="free-intro",
            dive_mode="shore",
            max_depth_meters=5,
            base_price=Decimal("0.00"),
        )

        result = compute_excursion_price(
            excursion_type=free_type,
            dive_site=dive_site,
        )

        assert result.base_price == Decimal("0.00")
        assert result.total_price == Decimal("0.00")

    def test_zero_base_with_adjustments(self, dive_site, park_fee_adjustment):
        """Zero base price plus adjustments works correctly."""
        from primitives_testbed.diveops.models import ExcursionType
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        free_type = ExcursionType.objects.create(
            name="Free Intro",
            slug="free-intro-2",
            dive_mode="shore",
            max_depth_meters=5,
            base_price=Decimal("0.00"),
        )

        result = compute_excursion_price(
            excursion_type=free_type,
            dive_site=dive_site,
        )

        assert result.base_price == Decimal("0.00")
        assert result.total_price == Decimal("10.00")  # Just park fee

    def test_site_with_no_adjustments(self, beginner_boat_type, dive_site):
        """Site with no adjustments returns just base price."""
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        result = compute_excursion_price(
            excursion_type=beginner_boat_type,
            dive_site=dive_site,
        )

        assert result.total_price == result.base_price
        assert len(result.adjustments) == 0


# =============================================================================
# Complex Scenario Tests
# =============================================================================


@pytest.mark.django_db
class TestComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_night_boat_dive_at_distant_site_with_park_fee(self, distant_site):
        """Complex scenario: night boat dive at distant site with park fee."""
        from primitives_testbed.diveops.models import ExcursionType, SitePriceAdjustment
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        # Create night boat type
        night_boat_type = ExcursionType.objects.create(
            name="Night Boat Dive",
            slug="night-boat",
            dive_mode="boat",
            time_of_day="night",
            max_depth_meters=25,
            base_price=Decimal("100.00"),
        )

        # Add adjustments to distant site
        SitePriceAdjustment.objects.create(
            dive_site=distant_site,
            kind="distance",
            amount=Decimal("30.00"),
        )
        SitePriceAdjustment.objects.create(
            dive_site=distant_site,
            kind="park_fee",
            amount=Decimal("15.00"),
        )
        SitePriceAdjustment.objects.create(
            dive_site=distant_site,
            kind="night",
            amount=Decimal("20.00"),
        )
        SitePriceAdjustment.objects.create(
            dive_site=distant_site,
            kind="boat",
            amount=Decimal("25.00"),
            applies_to_mode="boat",
        )

        result = compute_excursion_price(
            excursion_type=night_boat_type,
            dive_site=distant_site,
        )

        # 100 base + 30 distance + 15 park + 20 night + 25 boat = 190
        assert result.base_price == Decimal("100.00")
        assert result.total_price == Decimal("190.00")
        assert len(result.adjustments) == 4

    def test_dsd_shore_intro_minimal_cost(self, dive_site):
        """DSD shore intro has minimal adjustments."""
        from primitives_testbed.diveops.models import ExcursionType, SitePriceAdjustment
        from primitives_testbed.diveops.pricing_service import compute_excursion_price

        dsd_type = ExcursionType.objects.create(
            name="DSD Intro",
            slug="dsd-intro",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=6,
            base_price=Decimal("125.00"),
            requires_cert=False,
            is_training=True,
        )

        # Add boat fee (shouldn't apply to shore)
        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="boat",
            amount=Decimal("50.00"),
            applies_to_mode="boat",
        )

        result = compute_excursion_price(
            excursion_type=dsd_type,
            dive_site=dive_site,
        )

        # Just base, no boat fee for shore dive
        assert result.total_price == Decimal("125.00")
        assert len(result.adjustments) == 0
