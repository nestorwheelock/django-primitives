"""Tests for Money value object."""
import pytest
from decimal import Decimal

from django_money import Money


class TestMoneyCreation:
    """Test suite for Money creation and Decimal normalization."""

    def test_create_money_with_decimal(self):
        """Money should be created with Decimal amount."""
        money = Money(Decimal("19.99"), "USD")
        assert money.amount == Decimal("19.99")
        assert money.currency == "USD"

    def test_create_money_from_int(self):
        """Money should accept int and convert to Decimal."""
        money = Money(100, "USD")
        assert money.amount == Decimal("100")
        assert isinstance(money.amount, Decimal)

    def test_create_money_from_float(self):
        """Money should accept float and convert to Decimal via string."""
        money = Money(19.99, "USD")
        # Should convert via string to avoid float precision issues
        assert money.amount == Decimal("19.99")
        assert isinstance(money.amount, Decimal)

    def test_create_money_from_string(self):
        """Money should accept string and convert to Decimal."""
        money = Money("19.99", "USD")
        assert money.amount == Decimal("19.99")
        assert isinstance(money.amount, Decimal)

    def test_money_is_frozen(self):
        """Money should be immutable (frozen dataclass)."""
        money = Money(Decimal("100"), "USD")
        with pytest.raises(AttributeError):
            money.amount = Decimal("200")

    def test_money_amount_is_always_decimal(self):
        """Money.amount should always be Decimal regardless of input type."""
        # Test various input types
        from_decimal = Money(Decimal("10"), "USD")
        from_int = Money(10, "USD")
        from_float = Money(10.0, "USD")
        from_str = Money("10", "USD")

        assert isinstance(from_decimal.amount, Decimal)
        assert isinstance(from_int.amount, Decimal)
        assert isinstance(from_float.amount, Decimal)
        assert isinstance(from_str.amount, Decimal)

    def test_money_is_hashable(self):
        """Money should be hashable for use in sets and dict keys."""
        money1 = Money(Decimal("100"), "USD")
        money2 = Money(Decimal("100"), "USD")

        # Should be usable in set
        money_set = {money1, money2}
        assert len(money_set) == 1  # Same value, should be deduplicated

        # Should be usable as dict key
        money_dict = {money1: "value"}
        assert money_dict[money2] == "value"

    def test_money_equality(self):
        """Two Money objects with same amount and currency should be equal."""
        money1 = Money(Decimal("100"), "USD")
        money2 = Money(Decimal("100"), "USD")
        money3 = Money(Decimal("100"), "EUR")
        money4 = Money(Decimal("200"), "USD")

        assert money1 == money2
        assert money1 != money3  # Different currency
        assert money1 != money4  # Different amount

    def test_money_repr(self):
        """Money should have useful string representation."""
        money = Money(Decimal("19.99"), "USD")
        repr_str = repr(money)
        assert "19.99" in repr_str
        assert "USD" in repr_str


class TestCurrencyDecimals:
    """Test suite for CURRENCY_DECIMALS configuration."""

    def test_usd_has_2_decimals(self):
        """USD should have 2 decimal places."""
        from django_money import CURRENCY_DECIMALS
        assert CURRENCY_DECIMALS['USD'] == 2

    def test_jpy_has_0_decimals(self):
        """JPY (Japanese Yen) should have 0 decimal places."""
        from django_money import CURRENCY_DECIMALS
        assert CURRENCY_DECIMALS['JPY'] == 0

    def test_btc_has_8_decimals(self):
        """BTC (Bitcoin) should have 8 decimal places."""
        from django_money import CURRENCY_DECIMALS
        assert CURRENCY_DECIMALS['BTC'] == 8

    def test_common_currencies_defined(self):
        """Common currencies should be defined."""
        from django_money import CURRENCY_DECIMALS
        common = ['USD', 'EUR', 'GBP', 'JPY', 'MXN']
        for currency in common:
            assert currency in CURRENCY_DECIMALS


class TestQuantized:
    """Test suite for Money.quantized() method."""

    def test_quantized_usd_rounds_to_2_decimals(self):
        """USD should be quantized to 2 decimal places."""
        money = Money(Decimal("19.999"), "USD")
        quantized = money.quantized()
        assert quantized.amount == Decimal("20.00")
        assert quantized.currency == "USD"

    def test_quantized_jpy_rounds_to_0_decimals(self):
        """JPY should be quantized to 0 decimal places."""
        money = Money(Decimal("1999.5"), "JPY")
        quantized = money.quantized()
        assert quantized.amount == Decimal("2000")
        assert quantized.currency == "JPY"

    def test_quantized_btc_rounds_to_8_decimals(self):
        """BTC should be quantized to 8 decimal places."""
        money = Money(Decimal("0.000000016"), "BTC")
        quantized = money.quantized()
        # Should round to 8 decimals (0.000000016 rounds to 0.00000002)
        assert quantized.amount == Decimal("0.00000002")

    def test_quantized_uses_bankers_rounding(self):
        """Quantization should use banker's rounding (ROUND_HALF_EVEN)."""
        # 0.5 rounds to even (0), 1.5 rounds to even (2)
        money1 = Money(Decimal("10.005"), "USD")  # .005 -> .00 (round down to even)
        money2 = Money(Decimal("10.015"), "USD")  # .015 -> .02 (round up to even)
        money3 = Money(Decimal("10.025"), "USD")  # .025 -> .02 (round down to even)
        money4 = Money(Decimal("10.035"), "USD")  # .035 -> .04 (round up to even)

        assert money1.quantized().amount == Decimal("10.00")
        assert money2.quantized().amount == Decimal("10.02")
        assert money3.quantized().amount == Decimal("10.02")
        assert money4.quantized().amount == Decimal("10.04")

    def test_quantized_unknown_currency_defaults_to_2(self):
        """Unknown currencies should default to 2 decimal places."""
        money = Money(Decimal("19.999"), "XYZ")
        quantized = money.quantized()
        assert quantized.amount == Decimal("20.00")

    def test_quantized_returns_new_money_object(self):
        """quantized() should return a new Money object, not modify original."""
        original = Money(Decimal("19.999"), "USD")
        quantized = original.quantized()

        assert original.amount == Decimal("19.999")  # Unchanged
        assert quantized.amount == Decimal("20.00")  # New quantized value
        assert original is not quantized

    def test_quantized_preserves_exact_values(self):
        """Already-exact values should not change."""
        money = Money(Decimal("19.99"), "USD")
        quantized = money.quantized()
        assert quantized.amount == Decimal("19.99")


class TestArithmeticOperations:
    """Test suite for Money arithmetic operations."""

    def test_add_same_currency(self):
        """Adding two Money objects with same currency should work."""
        m1 = Money(Decimal("10.00"), "USD")
        m2 = Money(Decimal("5.50"), "USD")
        result = m1 + m2
        assert result.amount == Decimal("15.50")
        assert result.currency == "USD"

    def test_add_different_currency_raises(self):
        """Adding Money with different currencies should raise CurrencyMismatchError."""
        from django_money import CurrencyMismatchError
        m1 = Money(Decimal("10.00"), "USD")
        m2 = Money(Decimal("10.00"), "EUR")
        with pytest.raises(CurrencyMismatchError):
            m1 + m2

    def test_subtract_same_currency(self):
        """Subtracting Money objects with same currency should work."""
        m1 = Money(Decimal("10.00"), "USD")
        m2 = Money(Decimal("3.50"), "USD")
        result = m1 - m2
        assert result.amount == Decimal("6.50")
        assert result.currency == "USD"

    def test_subtract_different_currency_raises(self):
        """Subtracting Money with different currencies should raise CurrencyMismatchError."""
        from django_money import CurrencyMismatchError
        m1 = Money(Decimal("10.00"), "USD")
        m2 = Money(Decimal("5.00"), "EUR")
        with pytest.raises(CurrencyMismatchError):
            m1 - m2

    def test_subtract_can_go_negative(self):
        """Subtraction can result in negative amounts."""
        m1 = Money(Decimal("5.00"), "USD")
        m2 = Money(Decimal("10.00"), "USD")
        result = m1 - m2
        assert result.amount == Decimal("-5.00")

    def test_multiply_by_decimal(self):
        """Multiplying Money by Decimal should work."""
        money = Money(Decimal("10.00"), "USD")
        result = money * Decimal("1.5")
        assert result.amount == Decimal("15.00")
        assert result.currency == "USD"

    def test_multiply_by_int(self):
        """Multiplying Money by int should work."""
        money = Money(Decimal("10.00"), "USD")
        result = money * 3
        assert result.amount == Decimal("30.00")
        assert result.currency == "USD"

    def test_multiply_by_float(self):
        """Multiplying Money by float should work (converts via string)."""
        money = Money(Decimal("10.00"), "USD")
        result = money * 0.1
        assert result.amount == Decimal("1.00")
        assert result.currency == "USD"

    def test_multiply_preserves_precision(self):
        """Multiplication should preserve full precision (no auto-quantization)."""
        money = Money(Decimal("10.00"), "USD")
        result = money * Decimal("0.333")
        # Should keep full precision, not quantize
        assert result.amount == Decimal("3.330")

    def test_negation(self):
        """Negating Money should invert the sign."""
        positive = Money(Decimal("10.00"), "USD")
        negative = -positive
        assert negative.amount == Decimal("-10.00")
        assert negative.currency == "USD"

    def test_negation_of_negative(self):
        """Negating negative Money should give positive."""
        negative = Money(Decimal("-10.00"), "USD")
        positive = -negative
        assert positive.amount == Decimal("10.00")

    def test_rmul_int(self):
        """Right multiplication (3 * money) should work."""
        money = Money(Decimal("10.00"), "USD")
        result = 3 * money
        assert result.amount == Decimal("30.00")

    def test_arithmetic_returns_new_money(self):
        """Arithmetic operations should return new Money objects."""
        m1 = Money(Decimal("10.00"), "USD")
        m2 = Money(Decimal("5.00"), "USD")

        result = m1 + m2
        assert result is not m1
        assert result is not m2
        assert m1.amount == Decimal("10.00")  # Original unchanged
        assert m2.amount == Decimal("5.00")   # Original unchanged


class TestComparisonMethods:
    """Test suite for Money comparison and helper methods."""

    def test_is_positive_with_positive_amount(self):
        """is_positive() should return True for positive amounts."""
        money = Money(Decimal("10.00"), "USD")
        assert money.is_positive() is True

    def test_is_positive_with_zero(self):
        """is_positive() should return False for zero."""
        money = Money(Decimal("0"), "USD")
        assert money.is_positive() is False

    def test_is_positive_with_negative(self):
        """is_positive() should return False for negative amounts."""
        money = Money(Decimal("-10.00"), "USD")
        assert money.is_positive() is False

    def test_is_negative_with_negative_amount(self):
        """is_negative() should return True for negative amounts."""
        money = Money(Decimal("-10.00"), "USD")
        assert money.is_negative() is True

    def test_is_negative_with_zero(self):
        """is_negative() should return False for zero."""
        money = Money(Decimal("0"), "USD")
        assert money.is_negative() is False

    def test_is_negative_with_positive(self):
        """is_negative() should return False for positive amounts."""
        money = Money(Decimal("10.00"), "USD")
        assert money.is_negative() is False

    def test_is_zero_with_zero(self):
        """is_zero() should return True for zero."""
        money = Money(Decimal("0"), "USD")
        assert money.is_zero() is True

    def test_is_zero_with_positive(self):
        """is_zero() should return False for positive amounts."""
        money = Money(Decimal("10.00"), "USD")
        assert money.is_zero() is False

    def test_is_zero_with_negative(self):
        """is_zero() should return False for negative amounts."""
        money = Money(Decimal("-10.00"), "USD")
        assert money.is_zero() is False

    def test_is_zero_with_very_small_amount(self):
        """is_zero() should return False for very small non-zero amounts."""
        money = Money(Decimal("0.0001"), "USD")
        assert money.is_zero() is False

    def test_abs_returns_absolute_value(self):
        """abs() should return Money with absolute value."""
        negative = Money(Decimal("-10.00"), "USD")
        result = abs(negative)
        assert result.amount == Decimal("10.00")
        assert result.currency == "USD"

    def test_abs_of_positive_unchanged(self):
        """abs() of positive Money should return same value."""
        positive = Money(Decimal("10.00"), "USD")
        result = abs(positive)
        assert result.amount == Decimal("10.00")


class TestComparisonOperators:
    """Test suite for Money comparison operators (<, <=, >, >=)."""

    def test_lt_same_currency(self):
        """Less than comparison should work with same currency."""
        small = Money(Decimal("5.00"), "USD")
        large = Money(Decimal("10.00"), "USD")

        assert small < large
        assert not large < small
        assert not small < small  # Equal values

    def test_le_same_currency(self):
        """Less than or equal comparison should work with same currency."""
        small = Money(Decimal("5.00"), "USD")
        large = Money(Decimal("10.00"), "USD")
        equal = Money(Decimal("5.00"), "USD")

        assert small <= large
        assert small <= equal
        assert not large <= small

    def test_gt_same_currency(self):
        """Greater than comparison should work with same currency."""
        small = Money(Decimal("5.00"), "USD")
        large = Money(Decimal("10.00"), "USD")

        assert large > small
        assert not small > large
        assert not small > small  # Equal values

    def test_ge_same_currency(self):
        """Greater than or equal comparison should work with same currency."""
        small = Money(Decimal("5.00"), "USD")
        large = Money(Decimal("10.00"), "USD")
        equal = Money(Decimal("10.00"), "USD")

        assert large >= small
        assert large >= equal
        assert not small >= large

    def test_lt_different_currency_raises(self):
        """Less than with different currencies should raise CurrencyMismatchError."""
        import pytest
        from django_money.exceptions import CurrencyMismatchError

        usd = Money(Decimal("10.00"), "USD")
        eur = Money(Decimal("10.00"), "EUR")

        with pytest.raises(CurrencyMismatchError):
            usd < eur

    def test_le_different_currency_raises(self):
        """Less than or equal with different currencies should raise."""
        import pytest
        from django_money.exceptions import CurrencyMismatchError

        usd = Money(Decimal("10.00"), "USD")
        eur = Money(Decimal("10.00"), "EUR")

        with pytest.raises(CurrencyMismatchError):
            usd <= eur

    def test_gt_different_currency_raises(self):
        """Greater than with different currencies should raise."""
        import pytest
        from django_money.exceptions import CurrencyMismatchError

        usd = Money(Decimal("10.00"), "USD")
        eur = Money(Decimal("10.00"), "EUR")

        with pytest.raises(CurrencyMismatchError):
            usd > eur

    def test_ge_different_currency_raises(self):
        """Greater than or equal with different currencies should raise."""
        import pytest
        from django_money.exceptions import CurrencyMismatchError

        usd = Money(Decimal("10.00"), "USD")
        eur = Money(Decimal("10.00"), "EUR")

        with pytest.raises(CurrencyMismatchError):
            usd >= eur

    def test_sorting_list_of_money(self):
        """Money objects should be sortable when same currency."""
        prices = [
            Money(Decimal("25.00"), "USD"),
            Money(Decimal("10.00"), "USD"),
            Money(Decimal("50.00"), "USD"),
            Money(Decimal("5.00"), "USD"),
        ]

        sorted_prices = sorted(prices)

        assert sorted_prices[0].amount == Decimal("5.00")
        assert sorted_prices[1].amount == Decimal("10.00")
        assert sorted_prices[2].amount == Decimal("25.00")
        assert sorted_prices[3].amount == Decimal("50.00")

    def test_min_max_with_money(self):
        """min() and max() should work with Money objects."""
        prices = [
            Money(Decimal("25.00"), "USD"),
            Money(Decimal("10.00"), "USD"),
            Money(Decimal("50.00"), "USD"),
        ]

        assert min(prices).amount == Decimal("10.00")
        assert max(prices).amount == Decimal("50.00")
