"""Tests for diveops pricing snapshots.

Tests cover:
- Snapshot dataclass serialization
- Hash computation for input/output
- Snapshot building
- Snapshot immutability
"""

import pytest
import json
from decimal import Decimal
from unittest.mock import MagicMock

from django.utils import timezone

from ..snapshots import (
    MoneySnapshot,
    PricingLineSnapshot,
    EquipmentRentalSnapshot,
    PricingTotalsSnapshot,
    PricingInputsSnapshot,
    PricingMetadataSnapshot,
    PricingSnapshot,
    compute_hash,
    build_pricing_snapshot,
    extract_pricing_from_snapshot,
    SCHEMA_VERSION,
    TOOL_NAME,
)


class TestMoneySnapshot:
    """Tests for MoneySnapshot dataclass."""

    def test_from_decimal(self):
        """Test creating from Decimal and currency."""
        snapshot = MoneySnapshot.from_decimal(Decimal("100.50"), "MXN")
        assert snapshot.amount == "100.50"
        assert snapshot.currency == "MXN"

    def test_from_money(self):
        """Test creating from Money object."""
        mock_money = MagicMock()
        mock_money.amount = Decimal("250.00")
        mock_money.currency = "USD"

        snapshot = MoneySnapshot.from_money(mock_money)
        assert snapshot.amount == "250.00"
        assert snapshot.currency == "USD"

    def test_to_dict(self):
        """Test serialization to dict."""
        snapshot = MoneySnapshot(amount="100.50", currency="MXN")
        result = snapshot.to_dict()

        assert result == {"amount": "100.50", "currency": "MXN"}


class TestPricingLineSnapshot:
    """Tests for PricingLineSnapshot dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        shop_cost = MoneySnapshot(amount="50.00", currency="MXN")
        customer_charge = MoneySnapshot(amount="100.00", currency="MXN")

        line = PricingLineSnapshot(
            key="air_fill",
            label="Air Tank Fill",
            allocation="per_diver",
            shop_cost=shop_cost,
            customer_charge=customer_charge,
            refs={"agreement_id": "test-uuid"},
        )

        result = line.to_dict()

        assert result["key"] == "air_fill"
        assert result["label"] == "Air Tank Fill"
        assert result["allocation"] == "per_diver"
        assert result["shop_cost"]["amount"] == "50.00"
        assert result["customer_charge"]["amount"] == "100.00"
        assert result["refs"]["agreement_id"] == "test-uuid"


class TestEquipmentRentalSnapshot:
    """Tests for EquipmentRentalSnapshot dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        unit_cost = MoneySnapshot(amount="100.00", currency="MXN")
        unit_charge = MoneySnapshot(amount="200.00", currency="MXN")

        rental = EquipmentRentalSnapshot(
            diver_id="diver-uuid",
            catalog_item_id="item-uuid",
            description="BCD Rental",
            quantity=1,
            unit_cost=unit_cost,
            unit_charge=unit_charge,
            rental_id="rental-uuid",
        )

        result = rental.to_dict()

        assert result["diver_id"] == "diver-uuid"
        assert result["catalog_item_id"] == "item-uuid"
        assert result["description"] == "BCD Rental"
        assert result["quantity"] == 1
        assert result["rental_id"] == "rental-uuid"


class TestPricingTotalsSnapshot:
    """Tests for PricingTotalsSnapshot dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        totals = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="1800.00", currency="MXN"),
            shared_charge=MoneySnapshot(amount="2000.00", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="450.00", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="500.00", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="700.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=4,
        )

        result = totals.to_dict()

        assert result["diver_count"] == 4
        assert result["shared_cost"]["amount"] == "1800.00"
        assert result["total_charge_per_diver"]["amount"] == "700.00"
        assert result["margin_per_diver"]["amount"] == "150.00"


class TestComputeHash:
    """Tests for compute_hash function."""

    def test_dict_hash(self):
        """Test hashing a dict produces consistent results."""
        data = {"key": "value", "number": 123}
        hash1 = compute_hash(data)
        hash2 = compute_hash(data)

        assert hash1 == hash2
        assert hash1.startswith("sha256:")

    def test_different_dicts_different_hash(self):
        """Test different dicts produce different hashes."""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}

        hash1 = compute_hash(data1)
        hash2 = compute_hash(data2)

        assert hash1 != hash2

    def test_dict_order_independent(self):
        """Test dict hashing is order-independent (due to sort_keys)."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}

        hash1 = compute_hash(data1)
        hash2 = compute_hash(data2)

        assert hash1 == hash2

    def test_string_hash(self):
        """Test hashing a string."""
        hash1 = compute_hash("test string")
        hash2 = compute_hash("test string")

        assert hash1 == hash2
        assert hash1.startswith("sha256:")


class TestBuildPricingSnapshot:
    """Tests for build_pricing_snapshot function."""

    @pytest.fixture
    def mock_excursion(self):
        """Create a mock excursion."""
        excursion = MagicMock()
        excursion.pk = "excursion-uuid"
        excursion.dive_site.pk = "site-uuid"
        excursion.dive_site.name = "Test Site"
        excursion.dive_shop.pk = "shop-uuid"
        excursion.excursion_type.dives_per_excursion = 2
        return excursion

    @pytest.fixture
    def sample_lines(self):
        """Create sample pricing lines."""
        return [
            PricingLineSnapshot(
                key="boat_share",
                label="Boat Charter Share",
                allocation="shared",
                shop_cost=MoneySnapshot(amount="450.00", currency="MXN"),
                customer_charge=MoneySnapshot(amount="500.00", currency="MXN"),
            ),
            PricingLineSnapshot(
                key="air_fill",
                label="Air Fill",
                allocation="per_diver",
                shop_cost=MoneySnapshot(amount="100.00", currency="MXN"),
                customer_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            ),
        ]

    @pytest.fixture
    def sample_totals(self):
        """Create sample totals."""
        return PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="1800.00", currency="MXN"),
            shared_charge=MoneySnapshot(amount="2000.00", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="450.00", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="500.00", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="700.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=4,
        )

    def test_build_snapshot_structure(self, mock_excursion, sample_lines, sample_totals):
        """Test building a complete pricing snapshot."""
        snapshot = build_pricing_snapshot(
            excursion=mock_excursion,
            lines=sample_lines,
            equipment_rentals=[],
            totals=sample_totals,
            gas_type="air",
        )

        assert isinstance(snapshot, PricingSnapshot)
        assert snapshot.inputs.excursion_id == "excursion-uuid"
        assert snapshot.inputs.site_id == "site-uuid"
        assert snapshot.inputs.gas_type == "air"
        assert snapshot.inputs.diver_count == 4
        assert len(snapshot.lines) == 2
        assert snapshot.metadata.schema_version == SCHEMA_VERSION
        assert snapshot.metadata.tool == TOOL_NAME

    def test_snapshot_has_hashes(self, mock_excursion, sample_lines, sample_totals):
        """Test snapshot includes input and output hashes."""
        snapshot = build_pricing_snapshot(
            excursion=mock_excursion,
            lines=sample_lines,
            equipment_rentals=[],
            totals=sample_totals,
        )

        assert snapshot.metadata.input_hash.startswith("sha256:")
        assert snapshot.metadata.output_hash.startswith("sha256:")
        assert snapshot.metadata.input_hash != snapshot.metadata.output_hash

    def test_snapshot_to_json(self, mock_excursion, sample_lines, sample_totals):
        """Test snapshot serializes to deterministic JSON."""
        snapshot = build_pricing_snapshot(
            excursion=mock_excursion,
            lines=sample_lines,
            equipment_rentals=[],
            totals=sample_totals,
        )

        json_str = snapshot.to_json()
        parsed = json.loads(json_str)

        assert "inputs" in parsed
        assert "lines" in parsed
        assert "equipment_rentals" in parsed
        assert "totals" in parsed
        assert "metadata" in parsed


class TestExtractPricingFromSnapshot:
    """Tests for extract_pricing_from_snapshot function."""

    def test_extract_key_values(self):
        """Test extracting key pricing values from snapshot dict."""
        snapshot_dict = {
            "totals": {
                "total_charge_per_diver": {"amount": "700.00", "currency": "MXN"},
                "total_cost_per_diver": {"amount": "550.00", "currency": "MXN"},
                "margin_per_diver": {"amount": "150.00", "currency": "MXN"},
                "shared_cost": {"amount": "1800.00", "currency": "MXN"},
                "diver_count": 4,
            },
            "metadata": {
                "schema_version": "1.0.0",
            },
        }

        result = extract_pricing_from_snapshot(snapshot_dict)

        assert result["total_charge_per_diver"] == Decimal("700.00")
        assert result["total_cost_per_diver"] == Decimal("550.00")
        assert result["margin_per_diver"] == Decimal("150.00")
        assert result["diver_count"] == 4
        assert result["currency"] == "MXN"
        assert result["schema_version"] == "1.0.0"

    def test_extract_empty_snapshot(self):
        """Test extracting from empty snapshot dict."""
        result = extract_pricing_from_snapshot({})

        assert result["total_charge_per_diver"] == Decimal("0")
        assert result["diver_count"] == 0


class TestSnapshotImmutability:
    """Tests for snapshot immutability semantics."""

    def test_snapshot_hashes_change_with_prices(self):
        """Test that changing prices produces different hashes."""
        totals1 = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="1800.00", currency="MXN"),
            shared_charge=MoneySnapshot(amount="2000.00", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="450.00", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="500.00", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="700.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=4,
        )

        totals2 = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="2000.00", currency="MXN"),  # Changed
            shared_charge=MoneySnapshot(amount="2200.00", currency="MXN"),  # Changed
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="500.00", currency="MXN"),  # Changed
            shared_charge_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),  # Changed
            total_cost_per_diver=MoneySnapshot(amount="600.00", currency="MXN"),  # Changed
            total_charge_per_diver=MoneySnapshot(amount="750.00", currency="MXN"),  # Changed
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=4,
        )

        hash1 = compute_hash(totals1.to_dict())
        hash2 = compute_hash(totals2.to_dict())

        assert hash1 != hash2

    def test_snapshot_same_data_same_hash(self):
        """Test that same data produces same hash."""
        totals1 = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="1800.00", currency="MXN"),
            shared_charge=MoneySnapshot(amount="2000.00", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="450.00", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="500.00", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="700.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=4,
        )

        totals2 = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="1800.00", currency="MXN"),
            shared_charge=MoneySnapshot(amount="2000.00", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="450.00", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="500.00", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="700.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=4,
        )

        hash1 = compute_hash(totals1.to_dict())
        hash2 = compute_hash(totals2.to_dict())

        assert hash1 == hash2
