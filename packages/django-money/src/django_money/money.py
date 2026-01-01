"""Money value object with currency-aware arithmetic."""

from decimal import Decimal, ROUND_HALF_EVEN
from dataclasses import dataclass
from typing import Union

from django_money.exceptions import CurrencyMismatchError


# Currency precision rules for settlement/display
CURRENCY_DECIMALS = {
    'USD': 2, 'EUR': 2, 'GBP': 2, 'MXN': 2,
    'CAD': 2, 'AUD': 2, 'CHF': 2, 'CNY': 2,
    'JPY': 0, 'KRW': 0,  # No decimal currencies
    'BTC': 8,  # Crypto
}


@dataclass(frozen=True)
class Money:
    """
    Immutable money value object.

    Always normalizes amount to Decimal for precision.
    Supports currency-aware arithmetic operations.

    Usage:
        price = Money(Decimal("19.99"), "USD")
        tax = Money(Decimal("1.60"), "USD")
        total = price + tax  # Money(Decimal("21.59"), "USD")

        # Quantize for display/settlement
        display = total.quantized()  # Uses banker's rounding
    """
    amount: Decimal
    currency: str

    def __post_init__(self):
        """Normalize amount to Decimal."""
        if not isinstance(self.amount, Decimal):
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))

    def quantized(self) -> 'Money':
        """
        Return quantized to currency decimals for display/settlement.

        Uses banker's rounding (ROUND_HALF_EVEN) which rounds .5 to the
        nearest even number, reducing bias over many transactions.

        Returns:
            New Money object with quantized amount
        """
        decimals = CURRENCY_DECIMALS.get(self.currency, 2)
        quantized_amount = self.amount.quantize(
            Decimal(10) ** -decimals,
            rounding=ROUND_HALF_EVEN
        )
        return Money(quantized_amount, self.currency)

    def __add__(self, other: 'Money') -> 'Money':
        """Add two Money objects with the same currency."""
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot add {self.currency} to {other.currency}"
            )
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        """Subtract two Money objects with the same currency."""
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot subtract {other.currency} from {self.currency}"
            )
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Union[Decimal, int, float]) -> 'Money':
        """Multiply Money by a numeric factor."""
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def __rmul__(self, factor: Union[Decimal, int, float]) -> 'Money':
        """Right multiplication (factor * money)."""
        return self.__mul__(factor)

    def __neg__(self) -> 'Money':
        """Negate the money amount."""
        return Money(-self.amount, self.currency)

    def __abs__(self) -> 'Money':
        """Return absolute value of Money."""
        return Money(abs(self.amount), self.currency)

    def is_positive(self) -> bool:
        """Check if amount is greater than zero."""
        return self.amount > 0

    def is_negative(self) -> bool:
        """Check if amount is less than zero."""
        return self.amount < 0

    def is_zero(self) -> bool:
        """Check if amount is exactly zero."""
        return self.amount == 0
