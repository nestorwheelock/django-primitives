"""Tests for diveops pricing exceptions.

Tests cover:
- Exception hierarchy
- Error message formatting
- Attribute preservation
"""

import pytest

from ..exceptions import (
    PricingError,
    ConfigurationError,
    CurrencyMismatchError,
    MissingVendorAgreementError,
    MissingPriceError,
    SnapshotImmutableError,
)


class TestPricingError:
    """Tests for base PricingError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = PricingError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_is_exception(self):
        """Test PricingError is an Exception."""
        error = PricingError("test")
        assert isinstance(error, Exception)


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_message_only(self):
        """Test error with just a message."""
        error = ConfigurationError("Invalid configuration")
        assert str(error) == "Invalid configuration"
        assert error.errors == []

    def test_with_error_list(self):
        """Test error with detailed error list."""
        errors = ["field1 is required", "field2 must be positive"]
        error = ConfigurationError("Invalid configuration", errors=errors)

        assert str(error) == "Invalid configuration"
        assert error.errors == errors

    def test_is_pricing_error(self):
        """Test ConfigurationError inherits from PricingError."""
        error = ConfigurationError("test")
        assert isinstance(error, PricingError)


class TestCurrencyMismatchError:
    """Tests for CurrencyMismatchError."""

    def test_message_format(self):
        """Test error message includes currencies."""
        error = CurrencyMismatchError(expected="USD", actual="MXN")
        assert "USD" in str(error)
        assert "MXN" in str(error)

    def test_attributes(self):
        """Test currency attributes are preserved."""
        error = CurrencyMismatchError(expected="USD", actual="MXN")
        assert error.expected == "USD"
        assert error.actual == "MXN"

    def test_is_pricing_error(self):
        """Test CurrencyMismatchError inherits from PricingError."""
        error = CurrencyMismatchError(expected="USD", actual="MXN")
        assert isinstance(error, PricingError)


class TestMissingVendorAgreementError:
    """Tests for MissingVendorAgreementError."""

    def test_scope_type_only(self):
        """Test error with just scope type."""
        error = MissingVendorAgreementError(scope_type="vendor_pricing")
        assert "vendor_pricing" in str(error)
        assert error.scope_type == "vendor_pricing"
        assert error.scope_ref is None

    def test_with_scope_ref(self):
        """Test error with scope reference."""
        error = MissingVendorAgreementError(
            scope_type="vendor_pricing",
            scope_ref="DiveSite:abc-123",
        )
        assert "vendor_pricing" in str(error)
        assert "DiveSite:abc-123" in str(error)
        assert error.scope_ref == "DiveSite:abc-123"

    def test_is_configuration_error(self):
        """Test MissingVendorAgreementError inherits from ConfigurationError."""
        error = MissingVendorAgreementError(scope_type="test")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, PricingError)


class TestMissingPriceError:
    """Tests for MissingPriceError."""

    def test_catalog_item_only(self):
        """Test error with just catalog item ID."""
        error = MissingPriceError(catalog_item_id="item-uuid")
        assert "item-uuid" in str(error)
        assert error.catalog_item_id == "item-uuid"
        assert error.context is None

    def test_with_context(self):
        """Test error with context."""
        error = MissingPriceError(
            catalog_item_id="item-uuid",
            context="BCD Rental",
        )
        assert "item-uuid" in str(error)
        assert "BCD Rental" in str(error)
        assert error.context == "BCD Rental"

    def test_is_configuration_error(self):
        """Test MissingPriceError inherits from ConfigurationError."""
        error = MissingPriceError(catalog_item_id="test")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, PricingError)


class TestSnapshotImmutableError:
    """Tests for SnapshotImmutableError."""

    def test_message_includes_booking_id(self):
        """Test error message includes booking ID."""
        error = SnapshotImmutableError(booking_id="booking-uuid")
        assert "booking-uuid" in str(error)
        assert "immutable" in str(error).lower()

    def test_booking_id_attribute(self):
        """Test booking ID attribute is preserved."""
        error = SnapshotImmutableError(booking_id="booking-uuid")
        assert error.booking_id == "booking-uuid"

    def test_is_pricing_error(self):
        """Test SnapshotImmutableError inherits from PricingError."""
        error = SnapshotImmutableError(booking_id="test")
        assert isinstance(error, PricingError)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_can_catch_all_with_pricing_error(self):
        """Test all exceptions can be caught with PricingError."""
        exceptions = [
            PricingError("base"),
            ConfigurationError("config"),
            CurrencyMismatchError("USD", "MXN"),
            MissingVendorAgreementError("scope"),
            MissingPriceError("item"),
            SnapshotImmutableError("booking"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except PricingError:
                pass  # Should catch all
            except Exception:
                pytest.fail(f"{type(exc).__name__} not caught by PricingError")

    def test_can_catch_configuration_errors(self):
        """Test ConfigurationError catches its subclasses."""
        exceptions = [
            ConfigurationError("config"),
            MissingVendorAgreementError("scope"),
            MissingPriceError("item"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except ConfigurationError:
                pass
            except Exception:
                pytest.fail(f"{type(exc).__name__} not caught by ConfigurationError")
