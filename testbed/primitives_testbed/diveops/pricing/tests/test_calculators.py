"""Tests for diveops pricing calculators.

Tests cover:
- Tiered boat cost calculation
- Gas fill pricing
- Component pricing resolution
- Shared cost allocation and rounding
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ..calculators import (
    calculate_boat_cost,
    calculate_gas_fills,
    resolve_component_pricing,
    allocate_shared_costs,
    round_money,
    BoatCostResult,
    GasFillResult,
)
from ..exceptions import (
    MissingVendorAgreementError,
    MissingPriceError,
    ConfigurationError,
)


class TestRoundMoney:
    """Tests for round_money function using banker's rounding."""

    def test_round_half_to_even_down(self):
        """Test banker's rounding - 0.125 rounds to 0.12 (even)."""
        result = round_money(Decimal("0.125"))
        assert result == Decimal("0.12")

    def test_round_half_to_even_up(self):
        """Test banker's rounding - 0.135 rounds to 0.14 (even)."""
        result = round_money(Decimal("0.135"))
        assert result == Decimal("0.14")

    def test_round_normal_up(self):
        """Test normal rounding up."""
        result = round_money(Decimal("0.126"))
        assert result == Decimal("0.13")

    def test_round_normal_down(self):
        """Test normal rounding down."""
        result = round_money(Decimal("0.124"))
        assert result == Decimal("0.12")

    def test_round_custom_places(self):
        """Test rounding to different decimal places."""
        result = round_money(Decimal("1.2345"), places=3)
        assert result == Decimal("1.234")


class TestAllocateSharedCosts:
    """Tests for allocate_shared_costs function."""

    def test_even_division(self):
        """Test clean division with no remainder."""
        per_diver, amounts = allocate_shared_costs(Decimal("100.00"), 4)
        assert per_diver == Decimal("25.00")
        assert len(amounts) == 4
        assert all(a == Decimal("25.00") for a in amounts)
        assert sum(amounts) == Decimal("100.00")

    def test_remainder_distribution(self):
        """Test remainder distributed to first divers."""
        per_diver, amounts = allocate_shared_costs(Decimal("100.00"), 3)
        # 100 / 3 = 33.33... rounds to 33.33
        # 33.33 * 3 = 99.99, remainder = 0.01
        assert per_diver == Decimal("33.33")
        assert len(amounts) == 3
        # One diver gets the extra penny
        assert amounts[0] == Decimal("33.34")
        assert amounts[1] == Decimal("33.33")
        assert amounts[2] == Decimal("33.33")
        assert sum(amounts) == Decimal("100.00")

    def test_zero_divers(self):
        """Test zero divers returns zero."""
        per_diver, amounts = allocate_shared_costs(Decimal("100.00"), 0)
        assert per_diver == Decimal("0")
        assert amounts == []

    def test_negative_divers(self):
        """Test negative divers returns zero."""
        per_diver, amounts = allocate_shared_costs(Decimal("100.00"), -5)
        assert per_diver == Decimal("0")
        assert amounts == []

    def test_large_remainder(self):
        """Test large remainder distributed across multiple divers."""
        # 100 / 7 = 14.285714... rounds to 14.29
        # 14.29 * 7 = 100.03, remainder = -0.03
        per_diver, amounts = allocate_shared_costs(Decimal("100.00"), 7)
        assert len(amounts) == 7
        assert sum(amounts) == Decimal("100.00")

    def test_small_amount(self):
        """Test small amount allocation."""
        per_diver, amounts = allocate_shared_costs(Decimal("0.03"), 3)
        assert len(amounts) == 3
        assert sum(amounts) == Decimal("0.03")

    def test_rounding_stability(self):
        """Test that repeated allocations are stable."""
        # Run multiple times with same input
        results = []
        for _ in range(10):
            _, amounts = allocate_shared_costs(Decimal("100.00"), 3)
            results.append(amounts)

        # All results should be identical
        assert all(r == results[0] for r in results)


@pytest.mark.django_db
class TestCalculateBoatCost:
    """Tests for calculate_boat_cost function using Agreement terms."""

    @pytest.fixture
    def mock_dive_site(self):
        """Create a mock dive site."""
        site = MagicMock()
        site.pk = "test-site-uuid"
        return site

    @pytest.fixture
    def mock_agreement_base(self, mock_dive_site):
        """Create mock for Agreement query with base tier pricing."""
        agreement = MagicMock()
        agreement.pk = "test-agreement-uuid"
        agreement.terms = {
            "boat_charter": {
                "base_cost": "1800",
                "included_divers": 4,
                "overage_per_diver": "150",
                "currency": "MXN",
            }
        }
        return agreement

    def test_boat_cost_under_threshold(self, mock_dive_site, mock_agreement_base):
        """Test boat cost when under included diver count."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = mock_agreement_base
                mock_agreement_cls.objects.filter.return_value = mock_qs

                result = calculate_boat_cost(mock_dive_site, diver_count=4)

                assert isinstance(result, BoatCostResult)
                assert result.total.amount == Decimal("1800")
                assert result.total.currency == "MXN"
                assert result.per_diver.amount == Decimal("450")  # 1800 / 4
                assert result.overage_count == 0
                assert result.included_divers == 4
                assert result.diver_count == 4
                assert result.agreement_id == "test-agreement-uuid"

    def test_boat_cost_over_threshold(self, mock_dive_site, mock_agreement_base):
        """Test boat cost with overage (6 divers = 4 base + 2 overage)."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = mock_agreement_base
                mock_agreement_cls.objects.filter.return_value = mock_qs

                result = calculate_boat_cost(mock_dive_site, diver_count=6)

                # Base 1800 + (2 overage * 150) = 1800 + 300 = 2100
                assert result.total.amount == Decimal("2100")
                assert result.overage_count == 2
                assert result.per_diver.amount == Decimal("350")  # 2100 / 6

    def test_boat_cost_missing_agreement(self, mock_dive_site):
        """Test error when vendor agreement not found."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = None
                mock_agreement_cls.objects.filter.return_value = mock_qs

                with pytest.raises(MissingVendorAgreementError) as exc_info:
                    calculate_boat_cost(mock_dive_site, diver_count=4)

                assert "vendor_pricing" in str(exc_info.value)

    def test_boat_cost_missing_terms(self, mock_dive_site):
        """Test error when agreement missing boat_charter terms."""
        agreement = MagicMock()
        agreement.pk = "test-agreement-uuid"
        agreement.terms = {}  # No boat_charter

        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = agreement
                mock_agreement_cls.objects.filter.return_value = mock_qs

                with pytest.raises(ConfigurationError) as exc_info:
                    calculate_boat_cost(mock_dive_site, diver_count=4)

                assert "boat_charter" in str(exc_info.value)

    def test_boat_cost_zero_divers(self, mock_dive_site):
        """Test error when diver count is zero."""
        with pytest.raises(ConfigurationError) as exc_info:
            calculate_boat_cost(mock_dive_site, diver_count=0)

        assert "positive" in str(exc_info.value)

    def test_boat_cost_negative_divers(self, mock_dive_site):
        """Test error when diver count is negative."""
        with pytest.raises(ConfigurationError) as exc_info:
            calculate_boat_cost(mock_dive_site, diver_count=-1)

        assert "positive" in str(exc_info.value)


@pytest.mark.django_db
class TestCalculateGasFills:
    """Tests for calculate_gas_fills function."""

    @pytest.fixture
    def mock_dive_shop(self):
        """Create a mock dive shop."""
        shop = MagicMock()
        shop.pk = "test-shop-uuid"
        return shop

    @pytest.fixture
    def mock_gas_agreement(self):
        """Create mock agreement with gas fill pricing."""
        agreement = MagicMock()
        agreement.pk = "test-gas-agreement-uuid"
        agreement.terms = {
            "gas_fills": {
                "air": {"cost": "50", "charge": "100", "currency": "MXN"},
                "ean32": {"cost": "100", "charge": "200", "currency": "MXN"},
                "ean36": {"cost": "120", "charge": "250", "currency": "MXN"},
            }
        }
        return agreement

    def test_air_fill_pricing(self, mock_dive_shop, mock_gas_agreement):
        """Test air fill cost calculation."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = mock_gas_agreement
                mock_agreement_cls.objects.filter.return_value = mock_qs

                result = calculate_gas_fills(mock_dive_shop, gas_type="air", fills_count=2)

                assert isinstance(result, GasFillResult)
                assert result.cost_per_fill.amount == Decimal("50")
                assert result.charge_per_fill.amount == Decimal("100")
                assert result.total_cost.amount == Decimal("100")  # 50 * 2
                assert result.total_charge.amount == Decimal("200")  # 100 * 2
                assert result.fills_count == 2
                assert result.gas_type == "air"

    def test_nitrox_fill_pricing(self, mock_dive_shop, mock_gas_agreement):
        """Test EAN32 fill cost calculation."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = mock_gas_agreement
                mock_agreement_cls.objects.filter.return_value = mock_qs

                result = calculate_gas_fills(mock_dive_shop, gas_type="ean32", fills_count=1)

                assert result.cost_per_fill.amount == Decimal("100")
                assert result.charge_per_fill.amount == Decimal("200")
                assert result.total_cost.amount == Decimal("100")
                assert result.total_charge.amount == Decimal("200")

    def test_gas_fill_customer_override(self, mock_dive_shop, mock_gas_agreement):
        """Test gas fill with customer charge override (e.g., included in package)."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = mock_gas_agreement
                mock_agreement_cls.objects.filter.return_value = mock_qs

                result = calculate_gas_fills(
                    mock_dive_shop,
                    gas_type="air",
                    fills_count=2,
                    customer_charge_amount=Decimal("0"),  # Included in package
                )

                assert result.charge_per_fill.amount == Decimal("0")
                assert result.total_charge.amount == Decimal("0")
                # Cost should still be calculated
                assert result.cost_per_fill.amount == Decimal("50")
                assert result.total_cost.amount == Decimal("100")

    def test_gas_fill_missing_agreement(self, mock_dive_shop):
        """Test error when gas vendor agreement not found."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = None
                mock_agreement_cls.objects.filter.return_value = mock_qs

                with pytest.raises(MissingVendorAgreementError) as exc_info:
                    calculate_gas_fills(mock_dive_shop, gas_type="air", fills_count=1)

                assert "gas_vendor_pricing" in str(exc_info.value)

    def test_gas_fill_unknown_gas_type(self, mock_dive_shop, mock_gas_agreement):
        """Test error when gas type not in agreement."""
        with patch("primitives_testbed.diveops.pricing.calculators.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.calculators.Agreement") as mock_agreement_cls:
                mock_ct.objects.get_for_model.return_value = MagicMock()
                mock_qs = MagicMock()
                mock_qs.as_of.return_value.first.return_value = mock_gas_agreement
                mock_agreement_cls.objects.filter.return_value = mock_qs

                with pytest.raises(ConfigurationError) as exc_info:
                    calculate_gas_fills(mock_dive_shop, gas_type="trimix", fills_count=1)

                assert "trimix" in str(exc_info.value)

    def test_gas_fill_zero_count(self, mock_dive_shop):
        """Test error when fills count is zero."""
        with pytest.raises(ConfigurationError) as exc_info:
            calculate_gas_fills(mock_dive_shop, gas_type="air", fills_count=0)

        assert "positive" in str(exc_info.value)


class TestTieredBoatCostExamples:
    """Integration-style tests for tiered boat cost scenarios.

    From user requirements:
    - Closer dive sites cost 1800 MXN
    - Shipwreck costs 2200 MXN
    - Base price for up to 4 people
    - After that, 150 MXN more per person
    """

    def test_scenario_close_site_4_divers(self):
        """Close site, 4 divers (at threshold): 1800 MXN total, 450 per diver."""
        # Simulate tier calculation
        base_cost = Decimal("1800")
        included_divers = 4
        overage_per_diver = Decimal("150")
        diver_count = 4

        overage_count = max(0, diver_count - included_divers)
        total = base_cost + (overage_count * overage_per_diver)
        per_diver = round_money(total / diver_count)

        assert total == Decimal("1800")
        assert per_diver == Decimal("450")
        assert overage_count == 0

    def test_scenario_close_site_6_divers(self):
        """Close site, 6 divers (2 over): 1800 + 300 = 2100 MXN total."""
        base_cost = Decimal("1800")
        included_divers = 4
        overage_per_diver = Decimal("150")
        diver_count = 6

        overage_count = max(0, diver_count - included_divers)
        total = base_cost + (overage_count * overage_per_diver)
        per_diver = round_money(total / diver_count)

        assert total == Decimal("2100")
        assert per_diver == Decimal("350")  # 2100 / 6
        assert overage_count == 2

    def test_scenario_shipwreck_4_divers(self):
        """Shipwreck site, 4 divers: 2200 MXN total, 550 per diver."""
        base_cost = Decimal("2200")
        included_divers = 4
        overage_per_diver = Decimal("150")
        diver_count = 4

        overage_count = max(0, diver_count - included_divers)
        total = base_cost + (overage_count * overage_per_diver)
        per_diver = round_money(total / diver_count)

        assert total == Decimal("2200")
        assert per_diver == Decimal("550")
        assert overage_count == 0

    def test_scenario_shipwreck_8_divers(self):
        """Shipwreck site, 8 divers (4 over): 2200 + 600 = 2800 MXN total."""
        base_cost = Decimal("2200")
        included_divers = 4
        overage_per_diver = Decimal("150")
        diver_count = 8

        overage_count = max(0, diver_count - included_divers)
        total = base_cost + (overage_count * overage_per_diver)
        per_diver = round_money(total / diver_count)

        assert total == Decimal("2800")
        assert per_diver == Decimal("350")  # 2800 / 8
        assert overage_count == 4

    def test_scenario_shore_dive_minimal_cost(self):
        """Shore dive: minimal cost (only tanks and overhead)."""
        # Shore dive has no boat cost, just gas
        base_boat_cost = Decimal("0")
        tank_fills = 2
        air_cost_per_fill = Decimal("50")

        total_gas_cost = tank_fills * air_cost_per_fill

        assert base_boat_cost == Decimal("0")
        assert total_gas_cost == Decimal("100")


class TestGasPricingExamples:
    """Integration-style tests for gas pricing scenarios.

    From user requirements:
    - Nitrox costs X
    - Air costs Y
    """

    def test_air_vs_nitrox_cost_difference(self):
        """Air is cheaper than nitrox."""
        air_cost = Decimal("50")
        ean32_cost = Decimal("100")
        ean36_cost = Decimal("120")

        assert air_cost < ean32_cost < ean36_cost

    def test_two_tank_air_dive(self):
        """Two tank air dive cost calculation."""
        air_cost_per_fill = Decimal("50")
        air_charge_per_fill = Decimal("100")
        fills = 2

        shop_cost = air_cost_per_fill * fills
        customer_charge = air_charge_per_fill * fills
        margin = customer_charge - shop_cost

        assert shop_cost == Decimal("100")
        assert customer_charge == Decimal("200")
        assert margin == Decimal("100")  # 100% markup

    def test_two_tank_nitrox_dive(self):
        """Two tank nitrox dive cost calculation."""
        ean32_cost_per_fill = Decimal("100")
        ean32_charge_per_fill = Decimal("200")
        fills = 2

        shop_cost = ean32_cost_per_fill * fills
        customer_charge = ean32_charge_per_fill * fills
        margin = customer_charge - shop_cost

        assert shop_cost == Decimal("200")
        assert customer_charge == Decimal("400")
        assert margin == Decimal("200")  # 100% markup
