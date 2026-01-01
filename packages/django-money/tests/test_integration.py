"""Integration and edge case tests for django-money."""
import pytest
from decimal import Decimal

from django_money import Money, CurrencyMismatchError, CURRENCY_DECIMALS


class TestRealWorldCalculations:
    """Tests that simulate real-world financial calculations."""

    def test_shopping_cart_total(self):
        """Calculate a shopping cart total with multiple items."""
        items = [
            Money(Decimal("19.99"), "USD"),  # Item 1
            Money(Decimal("5.49"), "USD"),   # Item 2
            Money(Decimal("12.00"), "USD"),  # Item 3
        ]

        subtotal = Money(Decimal("0"), "USD")
        for item in items:
            subtotal = subtotal + item

        assert subtotal.amount == Decimal("37.48")

    def test_discount_calculation(self):
        """Apply a percentage discount to a price."""
        price = Money(Decimal("100.00"), "USD")
        discount_rate = Decimal("0.15")  # 15% discount

        discount = price * discount_rate
        final_price = price - discount

        assert discount.amount == Decimal("15.00")
        assert final_price.amount == Decimal("85.00")

    def test_tax_calculation_with_rounding(self):
        """Calculate tax and verify proper rounding at settlement."""
        price = Money(Decimal("19.99"), "USD")
        tax_rate = Decimal("0.0825")  # 8.25% tax

        tax = price * tax_rate
        # Tax amount before rounding: 1.649175
        assert tax.amount == Decimal("1.649175")

        # At settlement, quantize to 2 decimals
        tax_rounded = tax.quantized()
        assert tax_rounded.amount == Decimal("1.65")

        total = (price + tax).quantized()
        assert total.amount == Decimal("21.64")

    def test_split_bill_equally(self):
        """Split a bill among multiple people."""
        total = Money(Decimal("100.00"), "USD")
        num_people = 3

        per_person = total * (Decimal("1") / Decimal(num_people))
        # 100 / 3 = 33.333333...

        # Verify precision is preserved
        assert per_person.amount == Decimal("33.33333333333333333333333333")

        # At settlement, round properly
        per_person_rounded = per_person.quantized()
        assert per_person_rounded.amount == Decimal("33.33")

    def test_pro_rata_allocation(self):
        """Allocate a total proportionally."""
        total = Money(Decimal("1000.00"), "USD")
        proportions = [Decimal("0.5"), Decimal("0.3"), Decimal("0.2")]

        allocations = [total * p for p in proportions]

        assert allocations[0].amount == Decimal("500.00")
        assert allocations[1].amount == Decimal("300.00")
        assert allocations[2].amount == Decimal("200.00")

        # Verify sum equals original
        recombined = allocations[0] + allocations[1] + allocations[2]
        assert recombined.amount == total.amount


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_amount_operations(self):
        """Operations with zero amounts."""
        zero = Money(Decimal("0"), "USD")
        positive = Money(Decimal("100"), "USD")

        assert (zero + positive).amount == Decimal("100")
        assert (positive + zero).amount == Decimal("100")
        assert (positive - zero).amount == Decimal("100")
        assert (zero - positive).amount == Decimal("-100")
        assert (zero * 100).amount == Decimal("0")

    def test_very_large_amounts(self):
        """Handle very large amounts (billions)."""
        billion = Money(Decimal("1000000000.00"), "USD")
        doubled = billion + billion

        assert doubled.amount == Decimal("2000000000.00")
        assert doubled.quantized().amount == Decimal("2000000000.00")

    def test_very_small_amounts(self):
        """Handle very small amounts (fractions of cents)."""
        small = Money(Decimal("0.0001"), "USD")
        multiplied = small * 10000

        assert multiplied.amount == Decimal("1.0000")

    def test_high_precision_intermediate_calculations(self):
        """Precision is maintained during intermediate calculations."""
        # Tax calculation that would lose precision with early rounding
        price = Money(Decimal("1.00"), "USD")
        tax_rate = Decimal("0.07")  # 7%

        # Buy 1000 items
        subtotal = price * 1000  # $1000.00
        tax = subtotal * tax_rate  # $70.00

        total = subtotal + tax
        assert total.amount == Decimal("1070.00")

    def test_chained_operations(self):
        """Multiple chained operations."""
        base = Money(Decimal("100"), "USD")
        result = ((base * 2) + Money(Decimal("50"), "USD")) - Money(Decimal("25"), "USD")

        assert result.amount == Decimal("225")

    def test_negative_results(self):
        """Operations resulting in negative amounts."""
        credit = Money(Decimal("50"), "USD")
        debit = Money(Decimal("100"), "USD")

        balance = credit - debit
        assert balance.amount == Decimal("-50")
        assert balance.is_negative() is True

    def test_currency_mismatch_error_message(self):
        """Error message should include both currencies."""
        usd = Money(Decimal("100"), "USD")
        eur = Money(Decimal("100"), "EUR")

        with pytest.raises(CurrencyMismatchError) as exc_info:
            usd + eur

        error_msg = str(exc_info.value)
        assert "USD" in error_msg
        assert "EUR" in error_msg


class TestJPYNoDecimals:
    """Special tests for JPY (0 decimal places)."""

    def test_jpy_quantization(self):
        """JPY should round to whole numbers."""
        yen = Money(Decimal("1999.5"), "JPY")
        quantized = yen.quantized()
        assert quantized.amount == Decimal("2000")

    def test_jpy_arithmetic(self):
        """JPY arithmetic works normally, quantize at settlement."""
        price = Money(Decimal("1000"), "JPY")
        quantity = 3
        tax_rate = Decimal("0.10")

        subtotal = price * quantity
        tax = subtotal * tax_rate
        total = subtotal + tax

        assert total.amount == Decimal("3300.0")
        assert total.quantized().amount == Decimal("3300")


class TestBTCHighPrecision:
    """Special tests for BTC (8 decimal places)."""

    def test_btc_quantization(self):
        """BTC should round to 8 decimals (satoshi)."""
        btc = Money(Decimal("0.123456789"), "BTC")
        quantized = btc.quantized()
        # 0.123456789 rounds to 0.12345679 (banker's rounding)
        assert quantized.amount == Decimal("0.12345679")

    def test_btc_small_transaction(self):
        """Handle very small BTC transactions."""
        satoshi = Money(Decimal("0.00000001"), "BTC")  # 1 satoshi
        result = satoshi * 1000

        assert result.amount == Decimal("0.00001")


class TestImmutability:
    """Verify Money objects are truly immutable."""

    def test_operations_dont_modify_original(self):
        """All operations return new objects."""
        original = Money(Decimal("100"), "USD")
        original_id = id(original)
        original_amount = original.amount

        # Try various operations
        _ = original + Money(Decimal("50"), "USD")
        _ = original - Money(Decimal("50"), "USD")
        _ = original * 2
        _ = -original
        _ = abs(original)
        _ = original.quantized()

        # Original should be unchanged
        assert id(original) == original_id
        assert original.amount == original_amount

    def test_cannot_modify_attributes(self):
        """Attempting to modify attributes raises error."""
        money = Money(Decimal("100"), "USD")

        with pytest.raises(AttributeError):
            money.amount = Decimal("200")

        with pytest.raises(AttributeError):
            money.currency = "EUR"
