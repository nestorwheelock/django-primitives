# Architecture: django-money

**Status:** Stable / v0.1.0

Immutable Money value object with currency-aware arithmetic.

---

## What This Package Is For

Answering the question: **"How do I handle currency amounts without floating-point errors?"**

Use cases:
- Representing monetary values with exact precision
- Currency-safe arithmetic (add, subtract, multiply)
- Currency-safe comparisons (prevent USD vs EUR comparisons)
- Display/settlement rounding (banker's rounding)
- Internal precision for calculations

---

## What This Package Is NOT For

- **Not a Django model** - This is a value object, no database storage
- **Not currency conversion** - Use exchange rate service for conversions
- **Not formatting** - Use locale libraries for display formatting
- **Not validation** - Validate currency codes at application level

---

## Design Principles

1. **Immutable** - Money objects cannot be changed after creation
2. **Decimal-based** - Uses Python Decimal for exact arithmetic
3. **Currency enforcement** - Operations require matching currencies
4. **Explicit rounding** - quantized() for display/settlement
5. **Fail-fast** - Raises exceptions for currency mismatches

---

## Data Model

```python
@dataclass(frozen=True)
class Money:
    amount: Decimal    # Always Decimal, normalized on creation
    currency: str      # ISO 4217 currency code

# Currency Decimal Places (for quantized())
CURRENCY_DECIMALS = {
    'USD': 2, 'EUR': 2, 'GBP': 2, 'MXN': 2,
    'CAD': 2, 'AUD': 2, 'CHF': 2, 'CNY': 2,
    'JPY': 0, 'KRW': 0,  # No decimal currencies
    'BTC': 8,            # Crypto
}
```

---

## Public API

### Creating Money

```python
from decimal import Decimal
from django_money import Money

# From Decimal (recommended)
price = Money(Decimal("19.99"), "USD")

# From int or float (auto-converted)
tax = Money(1.60, "USD")  # Becomes Decimal("1.6")

# From string via Decimal
total = Money(Decimal("21.59"), "USD")
```

### Arithmetic Operations

```python
price = Money(Decimal("100.00"), "USD")
discount = Money(Decimal("10.00"), "USD")

# Addition and subtraction
net = price - discount          # Money(90.00, USD)
with_tax = net + tax            # Money(91.60, USD)

# Multiplication by scalar
doubled = price * 2             # Money(200.00, USD)
scaled = 0.9 * price            # Money(90.00, USD)

# Negation and absolute value
refund = -price                 # Money(-100.00, USD)
abs_value = abs(refund)         # Money(100.00, USD)
```

### Comparison Operations

```python
a = Money(Decimal("100.00"), "USD")
b = Money(Decimal("50.00"), "USD")

# All comparisons
a > b   # True
a >= b  # True
a < b   # False
a <= b  # False
a == b  # False (from dataclass)

# Sorting works
prices = [c, a, b]
sorted(prices)  # Sorted by amount
```

### Quantization

```python
# Internal precision
precise = Money(Decimal("19.995"), "USD")

# Quantize for display/settlement
display = precise.quantized()  # Money(20.00, USD)

# Uses banker's rounding (ROUND_HALF_EVEN)
# 19.995 → 20.00 (round to even)
# 19.985 → 19.98 (round to even)
```

### Helper Methods

```python
money = Money(Decimal("100.00"), "USD")

money.is_positive()  # True
money.is_negative()  # False
money.is_zero()      # False

zero = Money(Decimal("0"), "USD")
zero.is_zero()       # True
```

---

## Hard Rules

1. **Currency match required** - All operations require same currency
2. **Immutable objects** - Cannot modify amount or currency after creation
3. **Decimal precision** - Amounts stored as Decimal, not float
4. **No implicit conversion** - Never auto-convert between currencies

---

## Invariants

- `Money.amount` is always a `Decimal` (normalized in `__post_init__`)
- `Money` is frozen (immutable dataclass)
- All arithmetic returns new `Money` objects
- `CurrencyMismatchError` raised for cross-currency operations

---

## Known Gotchas

### 1. Currency Mismatch on Operations

**Problem:** Trying to add different currencies.

```python
usd = Money(Decimal("100"), "USD")
eur = Money(Decimal("100"), "EUR")

total = usd + eur
# Raises: CurrencyMismatchError: Cannot add USD to EUR
```

**Solution:** Convert to same currency first (external service).

### 2. Currency Mismatch on Comparisons

**Problem:** Comparing different currencies.

```python
usd = Money(Decimal("100"), "USD")
eur = Money(Decimal("100"), "EUR")

usd > eur
# Raises: CurrencyMismatchError: Cannot compare USD to EUR
```

**Solution:** Only compare same-currency Money objects.

### 3. Float Precision Loss

**Problem:** Using float directly.

```python
# CAUTION - float has precision issues
money = Money(0.1 + 0.2, "USD")
# money.amount = Decimal("0.30000000000000004")

# BETTER - use Decimal or string
money = Money(Decimal("0.1") + Decimal("0.2"), "USD")
# money.amount = Decimal("0.3")
```

### 4. Forgetting to Quantize

**Problem:** Using internal precision for display.

```python
# Internal calculation
subtotal = Money(Decimal("33.333333"), "USD")

# WRONG - shows too many decimals
print(f"Total: ${subtotal.amount}")  # $33.333333

# CORRECT - quantize for display
display = subtotal.quantized()
print(f"Total: ${display.amount}")   # $33.33
```

### 5. Division Not Supported

**Problem:** Trying to divide Money.

```python
total = Money(Decimal("100"), "USD")
per_person = total / 3  # TypeError: unsupported operand

# Use multiplication with Decimal instead
per_person = total * Decimal("0.333333")
```

---

## Recommended Usage

### 1. Store Amounts in Cents/Minor Units

```python
# In Django model, store as integer cents
class Invoice(models.Model):
    amount_cents = models.IntegerField()
    currency = models.CharField(max_length=3)

    @property
    def amount(self) -> Money:
        return Money(
            Decimal(self.amount_cents) / Decimal("100"),
            self.currency
        )

    @amount.setter
    def amount(self, money: Money):
        self.amount_cents = int(money.quantized().amount * 100)
        self.currency = money.currency
```

### 2. Keep Full Precision in Calculations

```python
# Calculate with full precision
items = [
    Money(Decimal("33.33"), "USD"),
    Money(Decimal("33.33"), "USD"),
    Money(Decimal("33.34"), "USD"),
]
subtotal = sum(items, Money(Decimal("0"), "USD"))
# subtotal = Money(100.00, USD) - exact!

# Only quantize at the end
display_total = subtotal.quantized()
```

### 3. Use for All Financial Calculations

```python
from django_money import Money

def calculate_order_total(items, tax_rate, discount):
    """Calculate order total with proper precision."""
    subtotal = Money(Decimal("0"), "USD")
    for item in items:
        subtotal = subtotal + item.price * item.quantity

    # Apply discount
    discount_amount = subtotal * discount
    after_discount = subtotal - discount_amount

    # Apply tax
    tax = after_discount * tax_rate
    total = after_discount + tax

    # Quantize only for final display/storage
    return total.quantized()
```

---

## Dependencies

None. This is a standalone Python module.

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Immutable Money dataclass
- Arithmetic: add, subtract, multiply, negate, abs
- Comparisons: lt, le, gt, ge
- quantized() with banker's rounding
- CurrencyMismatchError for cross-currency operations
