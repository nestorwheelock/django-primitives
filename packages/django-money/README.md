# django-money

Immutable Money value object with currency-aware arithmetic for Django projects.

## Features

- **Immutable Money dataclass** - Thread-safe, hashable value object
- **Currency-aware arithmetic** - Addition, subtraction, multiplication with currency mismatch detection
- **Precision preservation** - Internal calculations maintain full precision
- **Quantization at boundaries** - `quantized()` method for display/settlement with banker's rounding
- **No Django dependency** - Pure Python, works anywhere

## Installation

```bash
pip install -e packages/django-money
```

## Usage

### Basic Operations

```python
from django_money import Money
from decimal import Decimal

# Create money values
price = Money(Decimal("19.99"), "USD")
tax = Money(Decimal("1.60"), "USD")

# Arithmetic
total = price + tax  # Money(Decimal("21.59"), "USD")
discount = price * Decimal("0.1")  # Money(Decimal("1.999"), "USD")

# Quantize for display/settlement
display_price = discount.quantized()  # Money(Decimal("2.00"), "USD") - banker's rounding
```

### Currency Safety

```python
from django_money import Money, CurrencyMismatchError

usd = Money(Decimal("100"), "USD")
eur = Money(Decimal("90"), "EUR")

try:
    total = usd + eur  # Raises CurrencyMismatchError
except CurrencyMismatchError as e:
    print(e)  # "Cannot add USD to EUR"
```

### With Django Models

```python
from django.db import models
from django_money import Money

class Invoice(models.Model):
    # Store as separate fields (recommended pattern)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')

    @property
    def total(self) -> Money:
        """Return Money object for calculations."""
        return Money(self.amount, self.currency)

    def set_total(self, money: Money):
        """Set from Money object."""
        self.amount = money.amount
        self.currency = money.currency
```

## Currency Decimals

Each currency has a defined number of decimal places for settlement:

| Currency | Decimals | Example |
|----------|----------|---------|
| USD, EUR, GBP, MXN | 2 | $19.99 |
| JPY, KRW | 0 | ¥1999 |
| BTC | 8 | 0.00019999 |

The `quantized()` method uses these rules with banker's rounding (ROUND_HALF_EVEN).

## Design Principles

1. **Immutability** - Money objects are frozen dataclasses
2. **Precision preservation** - Never quantize during intermediate calculations
3. **Quantize at boundaries** - Only quantize at display/settlement decision surfaces
4. **Explicit currency** - No implicit currency conversions
5. **No custom fields** - Use standard Django DecimalField + CharField
