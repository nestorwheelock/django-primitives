# Prompt: Rebuild django-money

## Instruction

Create a Django package called `django-money` that provides an immutable Money value object with currency-aware arithmetic operations.

## Package Purpose

Provide a type-safe, precision-preserving way to handle monetary values:
- Immutability: All Money objects are frozen dataclass instances
- Type Safety: All numeric values stored internally as Decimal
- Currency Awareness: Operations between different currencies raise explicit errors
- Precision: Full decimal precision maintained until explicit quantization
- Banker's Rounding: Uses ROUND_HALF_EVEN for display/settlement rounding

## Dependencies

- Django >= 4.2
- No database models (value object only)

## File Structure

```
packages/django-money/
├── pyproject.toml
├── README.md
├── src/django_money/
│   ├── __init__.py
│   ├── money.py
│   └── exceptions.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_money.py
    └── test_integration.py
```

## Configuration

### CURRENCY_DECIMALS Dictionary

Maps ISO 4217 currency codes to decimal places:

```python
CURRENCY_DECIMALS = {
    'USD': 2, 'EUR': 2, 'GBP': 2, 'MXN': 2, 'CAD': 2,
    'AUD': 2, 'CHF': 2, 'CNY': 2,
    'JPY': 0, 'KRW': 0,  # No decimals
    'BTC': 8,  # Crypto
}
```

## Exceptions Specification

### exceptions.py

```python
class CurrencyMismatchError(ValueError):
    """Raised when attempting arithmetic between different currencies."""
    pass

class MoneyOverflowError(ValueError):
    """Reserved for future precision overflow detection."""
    pass
```

## Money Class Specification

### money.py

```python
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN

EARTH_RADIUS_KM = Decimal('6371.0')

CURRENCY_DECIMALS = {
    'USD': 2, 'EUR': 2, 'GBP': 2, 'MXN': 2, 'CAD': 2,
    'AUD': 2, 'CHF': 2, 'CNY': 2, 'JPY': 0, 'KRW': 0, 'BTC': 8,
}

@dataclass(frozen=True)
class Money:
    """Immutable monetary value with currency."""
    amount: Decimal
    currency: str

    def __post_init__(self):
        # Normalize amount to Decimal
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))

    def quantized(self) -> 'Money':
        """Return new Money with amount quantized to currency precision."""
        decimals = CURRENCY_DECIMALS.get(self.currency, 2)
        quantized_amount = self.amount.quantize(
            Decimal(10) ** -decimals,
            rounding=ROUND_HALF_EVEN
        )
        return Money(quantized_amount, self.currency)

    def is_positive(self) -> bool:
        return self.amount > 0

    def is_negative(self) -> bool:
        return self.amount < 0

    def is_zero(self) -> bool:
        return self.amount == 0

    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot add {self.currency} to {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot subtract {other.currency} from {self.currency}")
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor) -> 'Money':
        factor = Decimal(str(factor))
        return Money(self.amount * factor, self.currency)

    def __rmul__(self, factor) -> 'Money':
        return self.__mul__(factor)

    def __neg__(self) -> 'Money':
        return Money(-self.amount, self.currency)

    def __abs__(self) -> 'Money':
        return Money(abs(self.amount), self.currency)
```

## Test Cases (63 tests)

### TestMoneyCreation (9 tests)
1. `test_create_money_with_decimal` - Decimal amount stored correctly
2. `test_create_money_from_int` - Int converted to Decimal
3. `test_create_money_from_float` - Float converted via string
4. `test_create_money_from_string` - String converted to Decimal
5. `test_money_is_frozen` - Cannot modify attributes
6. `test_money_amount_is_always_decimal` - All inputs normalize to Decimal
7. `test_money_is_hashable` - Can use in sets/dicts
8. `test_money_equality` - == and != work correctly
9. `test_money_repr` - String representation is useful

### TestCurrencyDecimals (4 tests)
1. `test_usd_has_2_decimals` - USD = 2
2. `test_jpy_has_0_decimals` - JPY = 0
3. `test_btc_has_8_decimals` - BTC = 8
4. `test_common_currencies_defined` - USD, EUR, GBP, JPY, MXN exist

### TestQuantized (7 tests)
1. `test_quantized_usd_rounds_to_2_decimals` - 19.999 → 20.00
2. `test_quantized_jpy_rounds_to_0_decimals` - 1999.5 → 2000
3. `test_quantized_btc_rounds_to_8_decimals` - 0.123456789 → 0.12345679
4. `test_quantized_uses_bankers_rounding` - ROUND_HALF_EVEN verified
5. `test_quantized_unknown_currency_defaults_to_2` - XYZ uses 2 decimals
6. `test_quantized_returns_new_money_object` - Original unchanged
7. `test_quantized_preserves_exact_values` - No unnecessary changes

### TestArithmeticOperations (14 tests)
1. `test_add_same_currency` - Addition works
2. `test_add_different_currency_raises` - CurrencyMismatchError
3. `test_subtract_same_currency` - Subtraction works
4. `test_subtract_different_currency_raises` - CurrencyMismatchError
5. `test_subtract_can_go_negative` - Negative results allowed
6. `test_multiply_by_decimal` - Decimal multiplication
7. `test_multiply_by_int` - Int multiplication
8. `test_multiply_by_float` - Float multiplication
9. `test_multiply_preserves_precision` - No auto-quantization
10. `test_negation` - Negates positive amount
11. `test_negation_of_negative` - Double negation
12. `test_rmul_int` - 3 * money works
13. `test_arithmetic_returns_new_money` - Originals unchanged

### TestComparisonMethods (12 tests)
1. `test_is_positive_with_positive_amount` - True for > 0
2. `test_is_positive_with_zero` - False for == 0
3. `test_is_positive_with_negative` - False for < 0
4. `test_is_negative_with_negative_amount` - True for < 0
5. `test_is_negative_with_zero` - False for == 0
6. `test_is_negative_with_positive` - False for > 0
7. `test_is_zero_with_zero` - True for == 0
8. `test_is_zero_with_positive` - False for > 0
9. `test_is_zero_with_negative` - False for < 0
10. `test_is_zero_with_very_small_amount` - False for 0.0001
11. `test_abs_returns_absolute_value` - abs(-10) = 10
12. `test_abs_of_positive_unchanged` - abs(10) = 10

### TestRealWorldCalculations (5 tests)
1. `test_shopping_cart_total` - Sum multiple items
2. `test_discount_calculation` - 15% off $100
3. `test_tax_calculation_with_rounding` - 8.25% tax, quantize at end
4. `test_split_bill_equally` - $100 / 3 = $33.33...
5. `test_pro_rata_allocation` - 50% + 30% + 20% = 100%

### TestEdgeCases (6 tests)
1. `test_zero_amount_operations` - Zero + x = x
2. `test_very_large_amounts` - Billions work
3. `test_very_small_amounts` - 0.0001 works
4. `test_high_precision_intermediate_calculations` - Full precision preserved
5. `test_chained_operations` - ((100 * 2) + 50) - 25 = 225
6. `test_currency_mismatch_error_message` - Includes both currencies

### TestJPYNoDecimals (2 tests)
1. `test_jpy_quantization` - 1999.5 → 2000
2. `test_jpy_arithmetic` - Works with whole numbers

### TestBTCHighPrecision (2 tests)
1. `test_btc_quantization` - 8 decimal places
2. `test_btc_small_transaction` - 0.00000001 (1 satoshi) works

### TestImmutability (2 tests)
1. `test_operations_dont_modify_original` - All ops return new
2. `test_cannot_modify_attributes` - AttributeError on set

## __init__.py Exports

```python
from .money import Money, CURRENCY_DECIMALS
from .exceptions import CurrencyMismatchError, MoneyOverflowError

__all__ = [
    'Money',
    'CURRENCY_DECIMALS',
    'CurrencyMismatchError',
    'MoneyOverflowError',
]
```

## Key Behaviors

1. **Immutability**: Frozen dataclass, all operations return new objects
2. **Precision**: Full Decimal precision until quantized()
3. **Currency Safety**: Mismatched currencies raise explicit errors
4. **Banker's Rounding**: ROUND_HALF_EVEN reduces systematic bias
5. **Type Normalization**: Int/float/str all converted to Decimal

## Use Cases

1. **E-commerce** - Shopping cart totals, tax calculations
2. **Invoicing** - Line items, discounts, totals
3. **Accounting** - Journal entries, account balances
4. **Payroll** - Salary calculations, deductions

## Acceptance Criteria

- [ ] Money frozen dataclass implemented
- [ ] All arithmetic operators work
- [ ] CurrencyMismatchError raised for mismatched ops
- [ ] quantized() uses ROUND_HALF_EVEN
- [ ] CURRENCY_DECIMALS covers common currencies
- [ ] All 63 tests passing
- [ ] README with usage examples
