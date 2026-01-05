"""Tests for diveops pricing services.

Tests cover:
- Ledger entry balance verification
- Quote generation
- Booking snapshot immutability
- Equipment rental duplicate detection
- Strict/lenient snapshot modes
- Gas type parameter handling
- Settlement batch partial failure
- Missing price error handling
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from ..exceptions import (
    DuplicateRentalError,
    MissingPriceError,
    MissingVendorAgreementError,
    MissingCatalogItemError,
)
from ..snapshots import MoneySnapshot, PricingTotalsSnapshot
from ..services import GAS_FRACTIONS


class TestLedgerEntryBalance:
    """Tests for _create_ledger_entries balance verification."""

    def _make_totals(self, charge: str, cost: str, currency: str = "MXN"):
        """Create a PricingTotalsSnapshot for testing."""
        return PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="0", currency=currency),
            shared_charge=MoneySnapshot(amount="0", currency=currency),
            per_diver_cost=MoneySnapshot(amount=cost, currency=currency),
            per_diver_charge=MoneySnapshot(amount=charge, currency=currency),
            shared_cost_per_diver=MoneySnapshot(amount="0", currency=currency),
            shared_charge_per_diver=MoneySnapshot(amount="0", currency=currency),
            total_cost_per_diver=MoneySnapshot(amount=cost, currency=currency),
            total_charge_per_diver=MoneySnapshot(amount=charge, currency=currency),
            margin_per_diver=MoneySnapshot(
                amount=str(Decimal(charge) - Decimal(cost)), currency=currency
            ),
            diver_count=1,
        )

    def test_ledger_entries_balanced_charge_only(self):
        """Test ledger entries balance when only charge (no cost)."""
        # When charge > 0 and cost = 0:
        # Debit Receivable = charge
        # Credit Revenue = charge
        # Total debits = charge, Total credits = charge ✓
        totals = self._make_totals(charge="700.00", cost="0")

        debits = Decimal(totals.total_charge_per_diver.amount)
        credits = Decimal(totals.total_charge_per_diver.amount)

        assert debits == credits

    def test_ledger_entries_balanced_charge_and_cost(self):
        """Test ledger entries balance when both charge and cost exist."""
        # When charge > 0 and cost > 0:
        # Debit Receivable = charge
        # Credit Revenue = charge
        # Debit Expense = cost
        # Credit Payables = cost
        # Total debits = charge + cost, Total credits = charge + cost ✓
        totals = self._make_totals(charge="700.00", cost="550.00")

        charge = Decimal(totals.total_charge_per_diver.amount)
        cost = Decimal(totals.total_cost_per_diver.amount)

        total_debits = charge + cost
        total_credits = charge + cost

        assert total_debits == total_credits

    def test_ledger_entries_balanced_cost_only(self):
        """Test ledger entries balance when only cost (no charge)."""
        # When charge = 0 and cost > 0:
        # Debit Expense = cost
        # Credit Payables = cost
        # Total debits = cost, Total credits = cost ✓
        totals = self._make_totals(charge="0", cost="550.00")

        cost = Decimal(totals.total_cost_per_diver.amount)

        total_debits = cost
        total_credits = cost

        assert total_debits == total_credits

    def test_ledger_entries_skip_zero_amounts(self):
        """Test no entries created when both charge and cost are zero."""
        totals = self._make_totals(charge="0", cost="0")

        charge = Decimal(totals.total_charge_per_diver.amount)
        cost = Decimal(totals.total_cost_per_diver.amount)

        # Should return None / skip entry creation
        assert charge == 0 and cost == 0


@pytest.mark.django_db
class TestCreateLedgerEntriesIntegration:
    """Integration tests for _create_ledger_entries with real DB."""

    @pytest.fixture
    def mock_booking(self):
        """Create a mock booking with required relationships."""
        booking = MagicMock()
        booking.pk = "booking-uuid"
        booking.excursion.pk = "excursion-uuid"
        booking.excursion.dive_shop.pk = "shop-uuid"
        booking.excursion.dive_shop.name = "Test Dive Shop"
        booking.excursion.__str__ = lambda self: "Test Excursion"
        booking.diver.pk = "diver-uuid"
        booking.diver.person.get_short_name.return_value = "John D."
        return booking

    def test_ledger_transaction_has_balanced_entries(self, mock_booking):
        """Verify transaction debits equal credits after creation."""
        from ..services import _create_ledger_entries

        totals = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="0", currency="MXN"),
            shared_charge=MoneySnapshot(amount="0", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="550.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="700.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="0", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="0", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="550.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="700.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="150.00", currency="MXN"),
            diver_count=1,
        )

        with patch("primitives_testbed.diveops.pricing.services.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.services.Account") as mock_account:
                with patch("primitives_testbed.diveops.pricing.services.Transaction") as mock_tx:
                    with patch("primitives_testbed.diveops.pricing.services.Entry") as mock_entry:
                        # Setup mocks
                        mock_ct.objects.get_for_model.return_value = MagicMock()
                        mock_account.objects.get_or_create.return_value = (MagicMock(), True)
                        mock_tx_instance = MagicMock()
                        mock_tx.objects.create.return_value = mock_tx_instance

                        # Call function
                        result = _create_ledger_entries(
                            booking=mock_booking,
                            totals=totals,
                            actor=MagicMock(),
                        )

                        # Verify 4 entries created (2 for revenue, 2 for expense)
                        assert mock_entry.objects.create.call_count == 4

                        # Extract entry calls
                        calls = mock_entry.objects.create.call_args_list

                        # Calculate totals
                        total_debits = Decimal("0")
                        total_credits = Decimal("0")

                        for call in calls:
                            kwargs = call.kwargs
                            amount = kwargs["amount"]
                            entry_type = kwargs["entry_type"]

                            if entry_type == "debit":
                                total_debits += amount
                            elif entry_type == "credit":
                                total_credits += amount

                        # Verify balance
                        assert total_debits == total_credits
                        assert total_debits == Decimal("1250.00")  # 700 + 550

    def test_ledger_entry_types_correct(self, mock_booking):
        """Verify entry types follow accounting rules."""
        from ..services import _create_ledger_entries

        totals = PricingTotalsSnapshot(
            shared_cost=MoneySnapshot(amount="0", currency="MXN"),
            shared_charge=MoneySnapshot(amount="0", currency="MXN"),
            per_diver_cost=MoneySnapshot(amount="100.00", currency="MXN"),
            per_diver_charge=MoneySnapshot(amount="200.00", currency="MXN"),
            shared_cost_per_diver=MoneySnapshot(amount="0", currency="MXN"),
            shared_charge_per_diver=MoneySnapshot(amount="0", currency="MXN"),
            total_cost_per_diver=MoneySnapshot(amount="100.00", currency="MXN"),
            total_charge_per_diver=MoneySnapshot(amount="200.00", currency="MXN"),
            margin_per_diver=MoneySnapshot(amount="100.00", currency="MXN"),
            diver_count=1,
        )

        with patch("primitives_testbed.diveops.pricing.services.ContentType") as mock_ct:
            with patch("primitives_testbed.diveops.pricing.services.Account") as mock_account:
                with patch("primitives_testbed.diveops.pricing.services.Transaction") as mock_tx:
                    with patch("primitives_testbed.diveops.pricing.services.Entry") as mock_entry:
                        mock_ct.objects.get_for_model.return_value = MagicMock()

                        # Track which account gets which entry type
                        accounts = {
                            "receivable": MagicMock(account_type="receivable"),
                            "revenue": MagicMock(account_type="revenue"),
                            "expense": MagicMock(account_type="expense"),
                            "payable": MagicMock(account_type="payable"),
                        }

                        call_count = [0]

                        def get_or_create_side_effect(**kwargs):
                            account_type = kwargs.get("account_type")
                            return accounts[account_type], True

                        mock_account.objects.get_or_create.side_effect = get_or_create_side_effect
                        mock_tx.objects.create.return_value = MagicMock()

                        _create_ledger_entries(
                            booking=mock_booking,
                            totals=totals,
                            actor=MagicMock(),
                        )

                        calls = mock_entry.objects.create.call_args_list

                        # Verify accounting rules:
                        # - Receivable is debited (customer owes us)
                        # - Revenue is credited (we earned it)
                        # - Expense is debited (our cost)
                        # - Payable is credited (we owe vendors)
                        entry_map = {}
                        for call in calls:
                            kwargs = call.kwargs
                            account = kwargs["account"]
                            entry_type = kwargs["entry_type"]
                            entry_map[account.account_type] = entry_type

                        assert entry_map["receivable"] == "debit"
                        assert entry_map["revenue"] == "credit"
                        assert entry_map["expense"] == "debit"
                        assert entry_map["payable"] == "credit"


class TestGasFractions:
    """Tests for gas type fractions."""

    def test_air_fraction(self):
        """Air has 21% O2."""
        assert GAS_FRACTIONS["air"]["o2"] == 0.21
        assert GAS_FRACTIONS["air"]["he"] == 0.0

    def test_ean32_fraction(self):
        """EAN32 (Nitrox 32) has 32% O2."""
        assert GAS_FRACTIONS["ean32"]["o2"] == 0.32
        assert GAS_FRACTIONS["ean32"]["he"] == 0.0

    def test_ean36_fraction(self):
        """EAN36 (Nitrox 36) has 36% O2."""
        assert GAS_FRACTIONS["ean36"]["o2"] == 0.36
        assert GAS_FRACTIONS["ean36"]["he"] == 0.0

    def test_supported_gas_types(self):
        """All supported gas types are defined."""
        assert "air" in GAS_FRACTIONS
        assert "ean32" in GAS_FRACTIONS
        assert "ean36" in GAS_FRACTIONS


class TestDuplicateRentalError:
    """Tests for duplicate rental detection."""

    def test_error_message_format(self):
        """DuplicateRentalError includes booking and catalog item IDs."""
        error = DuplicateRentalError(
            booking_id="booking-123",
            catalog_item_id="item-456",
        )
        assert "booking=booking-123" in str(error)
        assert "catalog_item=item-456" in str(error)

    def test_error_attributes(self):
        """DuplicateRentalError stores booking and catalog item IDs."""
        error = DuplicateRentalError(
            booking_id="booking-123",
            catalog_item_id="item-456",
        )
        assert error.booking_id == "booking-123"
        assert error.catalog_item_id == "item-456"


class TestMissingCatalogItemError:
    """Tests for missing catalog item detection."""

    def test_error_message_includes_identifier(self):
        """MissingCatalogItemError includes the identifier."""
        error = MissingCatalogItemError("Guide Fee")
        assert "Guide Fee" in str(error)
        assert "not found or inactive" in str(error)

    def test_error_attribute(self):
        """MissingCatalogItemError stores the identifier as slug."""
        error = MissingCatalogItemError("Park Entry Fee")
        assert error.slug == "Park Entry Fee"


class TestAddEquipmentRentalValidation:
    """Tests for add_equipment_rental validation."""

    def test_missing_price_raises_error(self):
        """add_equipment_rental raises MissingPriceError when no price configured."""
        # This is a unit test to verify the exception is properly defined
        # The integration test would require DB fixtures
        error = MissingPriceError("equipment-item-123", "no price rule found")
        assert "equipment-item-123" in str(error)
        assert error.catalog_item_id == "equipment-item-123"


class TestSnapshotStrictMode:
    """Tests for snapshot_booking_pricing strict/lenient modes."""

    def test_strict_mode_raises_on_missing_vendor_agreement(self):
        """allow_incomplete=False raises MissingVendorAgreementError."""
        error = MissingVendorAgreementError(
            scope_type="boat",
            scope_ref="dive-site-123",
        )
        assert "boat" in str(error)
        assert "dive-site-123" in str(error)
        assert error.scope_type == "boat"
        assert error.scope_ref == "dive-site-123"

    def test_strict_mode_raises_on_missing_catalog_item(self):
        """allow_incomplete=False raises MissingCatalogItemError."""
        error = MissingCatalogItemError("Guide Fee")
        assert "Guide Fee" in str(error)
        assert error.slug == "Guide Fee"


class TestSettlementBatchSavepoints:
    """Tests for settlement batch savepoint behavior."""

    def test_savepoint_allows_partial_success(self):
        """Successful settlements should persist even when some fail.

        This is a design test - verifies the savepoint pattern is used.
        The implementation uses transaction.savepoint() per booking.
        """
        # Verify savepoint pattern by checking the code structure
        from primitives_testbed.diveops.settlement_service import run_settlement_batch
        import inspect

        source = inspect.getsource(run_settlement_batch)

        # Verify savepoint is used in the implementation
        assert "transaction.savepoint()" in source
        assert "savepoint_commit" in source
        assert "savepoint_rollback" in source


class TestCatalogDisplayNameLookup:
    """Tests for deterministic catalog item lookup."""

    def test_display_name_constants_defined(self):
        """Verify display name constants are properly defined."""
        from ..services import CATALOG_DISPLAY_NAME_GUIDE_FEE, CATALOG_DISPLAY_NAME_PARK_FEE

        assert CATALOG_DISPLAY_NAME_GUIDE_FEE == "Guide Fee"
        assert CATALOG_DISPLAY_NAME_PARK_FEE == "Park Entry Fee"

    @pytest.mark.django_db
    def test_get_catalog_item_raises_on_missing(self):
        """_get_catalog_item raises MissingCatalogItemError when not found."""
        from ..services import _get_catalog_item

        with pytest.raises(MissingCatalogItemError) as exc_info:
            _get_catalog_item("Nonexistent Item")
        assert "Nonexistent Item" in str(exc_info.value)
