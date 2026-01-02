"""Django Money - Immutable Money value object with currency-aware arithmetic."""

__version__ = "0.1.0"

from django_money.money import Money, CURRENCY_DECIMALS
from django_money.exceptions import CurrencyMismatchError, MoneyOverflowError

__all__ = [
    "Money",
    "CURRENCY_DECIMALS",
    "CurrencyMismatchError",
    "MoneyOverflowError",
]
