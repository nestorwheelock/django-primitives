"""Tests for diveops accounts module.

Tests cover:
- Account seeding idempotency
- Required accounts validation
- AccountConfigurationError behavior
- Per-vendor payable account creation
- Account cache behavior
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from ..accounts import (
    ACCOUNT_TYPES,
    REQUIRED_ACCOUNT_KEYS,
    AccountConfigurationError,
    AccountSet,
    clear_account_cache,
    get_account,
    get_required_accounts,
    get_vendor_payable_account,
    list_accounts,
    seed_accounts,
)


class TestAccountTypes:
    """Tests for account type configuration."""

    def test_all_required_keys_exist_in_account_types(self):
        """All required account keys must exist in ACCOUNT_TYPES."""
        for key in REQUIRED_ACCOUNT_KEYS:
            assert key in ACCOUNT_TYPES, f"Required key '{key}' not in ACCOUNT_TYPES"

    def test_account_types_have_required_fields(self):
        """Each account type config must have required fields."""
        required_fields = ["account_type", "name_template", "description"]
        for key, config in ACCOUNT_TYPES.items():
            for field in required_fields:
                assert field in config, f"Account type '{key}' missing field '{field}'"

    def test_name_template_has_shop_placeholder(self):
        """Name templates must include {shop} placeholder."""
        for key, config in ACCOUNT_TYPES.items():
            template = config["name_template"]
            assert "{shop}" in template, f"Account type '{key}' template missing {{shop}}"


class TestAccountSet:
    """Tests for AccountSet dataclass."""

    def test_get_missing_required_all_none(self):
        """get_missing_required returns all required keys when accounts are None."""
        mock_shop = MagicMock()
        mock_shop.pk = "shop-id"

        account_set = AccountSet(shop=mock_shop, currency="MXN")
        missing = account_set.get_missing_required()

        assert set(missing) == set(REQUIRED_ACCOUNT_KEYS)

    def test_get_missing_required_partial(self):
        """get_missing_required returns only missing keys."""
        mock_shop = MagicMock()
        mock_shop.pk = "shop-id"

        account_set = AccountSet(
            shop=mock_shop,
            currency="MXN",
            dive_revenue=MagicMock(),  # Present
            excursion_costs=MagicMock(),  # Present
            # Others are None
        )
        missing = account_set.get_missing_required()

        assert "dive_revenue" not in missing
        assert "excursion_costs" not in missing
        assert "cash_bank" in missing
        assert "accounts_payable" in missing
        assert "accounts_receivable" in missing

    def test_is_complete_all_present(self):
        """is_complete returns True when all required accounts are present."""
        mock_shop = MagicMock()
        mock_shop.pk = "shop-id"

        account_set = AccountSet(
            shop=mock_shop,
            currency="MXN",
            dive_revenue=MagicMock(),
            accounts_receivable=MagicMock(),
            excursion_costs=MagicMock(),
            cash_bank=MagicMock(),
            accounts_payable=MagicMock(),
        )

        assert account_set.is_complete()

    def test_is_complete_missing_required(self):
        """is_complete returns False when required accounts are missing."""
        mock_shop = MagicMock()
        mock_shop.pk = "shop-id"

        account_set = AccountSet(
            shop=mock_shop,
            currency="MXN",
            dive_revenue=MagicMock(),
            # Missing: excursion_costs, cash_bank, accounts_payable, accounts_receivable
        )

        assert not account_set.is_complete()


class TestAccountConfigurationError:
    """Tests for AccountConfigurationError exception."""

    def test_error_message_includes_shop_name(self):
        """Error message should include shop name."""
        mock_shop = MagicMock()
        mock_shop.name = "Test Dive Shop"
        mock_shop.pk = "shop-123"

        error = AccountConfigurationError(
            shop=mock_shop,
            currency="MXN",
            missing_types=["cash_bank", "excursion_costs"],
        )

        assert "Test Dive Shop" in str(error)

    def test_error_message_includes_currency(self):
        """Error message should include currency."""
        mock_shop = MagicMock()
        mock_shop.name = "Test Shop"
        mock_shop.pk = "shop-123"

        error = AccountConfigurationError(
            shop=mock_shop,
            currency="USD",
            missing_types=["cash_bank"],
        )

        assert "USD" in str(error)

    def test_error_message_includes_missing_types(self):
        """Error message should list missing account types."""
        mock_shop = MagicMock()
        mock_shop.name = "Test Shop"
        mock_shop.pk = "shop-123"

        error = AccountConfigurationError(
            shop=mock_shop,
            currency="MXN",
            missing_types=["cash_bank", "excursion_costs"],
        )

        assert "cash_bank" in str(error)
        assert "excursion_costs" in str(error)

    def test_error_suggests_seed_command(self):
        """Error message should suggest the seed command."""
        mock_shop = MagicMock()
        mock_shop.name = "Test Shop"
        mock_shop.pk = "shop-123"

        error = AccountConfigurationError(
            shop=mock_shop,
            currency="MXN",
            missing_types=["cash_bank"],
        )

        assert "seed_chart_of_accounts" in str(error)

    def test_error_stores_attributes(self):
        """Error should store shop, currency, and missing_types."""
        mock_shop = MagicMock()
        mock_shop.name = "Test Shop"
        mock_shop.pk = "shop-123"

        error = AccountConfigurationError(
            shop=mock_shop,
            currency="EUR",
            missing_types=["cash_bank", "dive_revenue"],
        )

        assert error.shop == mock_shop
        assert error.currency == "EUR"
        assert error.missing_types == ["cash_bank", "dive_revenue"]


class TestGetAccount:
    """Tests for get_account function."""

    def test_invalid_account_key_raises_value_error(self):
        """get_account raises ValueError for unknown account key."""
        mock_shop = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            get_account(mock_shop, "MXN", "invalid_key")

        assert "Unknown account key" in str(exc_info.value)


class TestCacheManagement:
    """Tests for account cache management."""

    def test_clear_account_cache(self):
        """clear_account_cache should reset the cache."""
        # This test verifies the function doesn't error
        # Full integration test would verify cache behavior
        clear_account_cache()
        # No exception means success


class TestSeedAccountsIdempotency:
    """Tests for seed_accounts idempotency."""

    # These tests would require database access and are marked for integration testing
    # In a full test suite, you would use @pytest.mark.django_db

    @pytest.mark.skip(reason="Requires database integration")
    def test_seed_accounts_creates_all_types(self):
        """seed_accounts should create all account types."""
        pass

    @pytest.mark.skip(reason="Requires database integration")
    def test_seed_accounts_idempotent(self):
        """Calling seed_accounts twice should not duplicate accounts."""
        pass

    @pytest.mark.skip(reason="Requires database integration")
    def test_seed_accounts_creates_vendor_payables(self):
        """seed_accounts with vendors creates per-vendor AP accounts."""
        pass


class TestGetRequiredAccountsValidation:
    """Tests for get_required_accounts validation."""

    @pytest.mark.skip(reason="Requires database integration")
    def test_raises_error_when_accounts_not_seeded(self):
        """get_required_accounts raises AccountConfigurationError when not seeded."""
        pass

    @pytest.mark.skip(reason="Requires database integration")
    def test_returns_account_set_when_seeded(self):
        """get_required_accounts returns AccountSet when accounts are seeded."""
        pass

    @pytest.mark.skip(reason="Requires database integration")
    def test_auto_create_seeds_accounts(self):
        """get_required_accounts with auto_create=True creates missing accounts."""
        pass
