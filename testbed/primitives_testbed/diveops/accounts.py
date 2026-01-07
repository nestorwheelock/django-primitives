"""Chart of Accounts management for diveops.

This module provides:
1. Deterministic account lookup (no scattered get_or_create)
2. Account seeding for required accounts
3. Configuration error when accounts are missing

Required accounts for a dive shop:
- Revenue: Dive Revenue, Equipment Rental Revenue
- Expense/COGS: Excursion Costs, Gas Costs
- Asset: Cash/Bank
- Liability: Accounts Payable (shop-wide or per-vendor)

Usage:
    # Get required accounts (raises if not seeded)
    accounts = get_required_accounts(shop, currency="MXN")

    # Seed accounts for a shop
    seed_accounts(shop, currency="MXN")
"""

import threading
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction

if TYPE_CHECKING:
    from django_ledger.models import Account
    from django_parties.models import Organization


class AccountConfigurationError(Exception):
    """Raised when required accounts are not configured.

    This error indicates that the chart of accounts needs to be seeded
    before performing the requested operation.
    """

    def __init__(self, shop, currency: str, missing_types: list[str]):
        self.shop = shop
        self.currency = currency
        self.missing_types = missing_types
        types_str = ", ".join(missing_types)
        super().__init__(
            f"Missing required accounts for {shop.name} ({currency}): {types_str}. "
            f"Run 'python manage.py seed_chart_of_accounts --org {shop.pk} --currency {currency}' "
            f"or use the staff portal to seed accounts."
        )


# Standard account types for dive operations
# Account numbers follow standard accounting conventions:
#   1000-1999: Assets
#   2000-2999: Liabilities
#   3000-3999: Equity
#   4000-4999: Revenue
#   5000-5999: Cost of Goods Sold (COGS)
#   6000-6999: Operating Expenses
ACCOUNT_TYPES = {
    # Asset accounts (1000-1999)
    "cash_bank": {
        "account_number": "1010",
        "account_type": "asset",
        "name_template": "Cash/Bank - {shop}",
        "description": "Primary cash and bank account",
    },
    "accounts_receivable": {
        "account_number": "1200",
        "account_type": "receivable",
        "name_template": "Accounts Receivable - {shop}",
        "description": "Customer receivables",
    },
    # Liability accounts (2000-2999)
    "accounts_payable": {
        "account_number": "2000",
        "account_type": "payable",
        "name_template": "Accounts Payable - {shop}",
        "description": "Shop-wide accounts payable (unattributed vendor costs)",
    },
    # Revenue accounts (4000-4999)
    "dive_revenue": {
        "account_number": "4000",
        "account_type": "revenue",
        "name_template": "Dive Revenue - {shop}",
        "description": "Revenue from dive excursions and courses",
    },
    "equipment_rental_revenue": {
        "account_number": "4100",
        "account_type": "revenue",
        "name_template": "Equipment Rental Revenue - {shop}",
        "description": "Revenue from equipment rentals",
    },
    # Cost of Goods Sold / Expense accounts (5000-5999)
    "excursion_costs": {
        "account_number": "5000",
        "account_type": "expense",
        "name_template": "Excursion Costs - {shop}",
        "description": "Cost of goods sold for excursions (boat, guides, etc.)",
    },
    "gas_costs": {
        "account_number": "5100",
        "account_type": "expense",
        "name_template": "Gas Costs - {shop}",
        "description": "Cost of tank fills (air, nitrox, etc.)",
    },
    "equipment_costs": {
        "account_number": "5200",
        "account_type": "expense",
        "name_template": "Equipment Costs - {shop}",
        "description": "Cost of equipment rentals and maintenance",
    },
}

# Required accounts that must exist for payables/pricing operations
REQUIRED_ACCOUNT_KEYS = [
    "excursion_costs",
    "cash_bank",
    "accounts_payable",
    "dive_revenue",
    "accounts_receivable",
]


@dataclass
class AccountSet:
    """Collection of accounts for a shop/currency combination.

    Provides named access to standard accounts.
    """

    shop: "Organization"
    currency: str

    # Revenue
    dive_revenue: "Account | None" = None
    equipment_rental_revenue: "Account | None" = None

    # Expense/COGS
    excursion_costs: "Account | None" = None
    gas_costs: "Account | None" = None
    equipment_costs: "Account | None" = None

    # Asset
    cash_bank: "Account | None" = None
    accounts_receivable: "Account | None" = None

    # Liability
    accounts_payable: "Account | None" = None

    def get_missing_required(self) -> list[str]:
        """Return list of missing required account keys."""
        missing = []
        for key in REQUIRED_ACCOUNT_KEYS:
            if getattr(self, key) is None:
                missing.append(key)
        return missing

    def is_complete(self) -> bool:
        """Check if all required accounts are present."""
        return len(self.get_missing_required()) == 0


def _get_shop_content_type():
    """Get ContentType for Organization model."""
    from django_parties.models import Organization
    return ContentType.objects.get_for_model(Organization)


def _build_account_lookup_key(shop_id: str, currency: str, account_key: str) -> str:
    """Build cache key for account lookup."""
    return f"{shop_id}:{currency}:{account_key}"


# Account cache to avoid repeated database lookups
# Thread-safe with lock for concurrent request handling
_account_cache: dict[str, "Account"] = {}
_cache_lock = threading.Lock()


def clear_account_cache():
    """Clear the account cache. Use after seeding or testing."""
    global _account_cache
    with _cache_lock:
        _account_cache = {}


def get_account(
    shop: "Organization",
    currency: str,
    account_key: str,
    *,
    auto_create: bool = False,
) -> "Account | None":
    """Get a specific account by key.

    Args:
        shop: Organization (dive shop)
        currency: Currency code (USD, MXN, etc.)
        account_key: Key from ACCOUNT_TYPES
        auto_create: If True, create missing account (only for seeding)

    Returns:
        Account instance or None if not found

    Raises:
        ValueError: If account_key is not valid
    """
    from django_ledger.models import Account

    if account_key not in ACCOUNT_TYPES:
        raise ValueError(f"Unknown account key: {account_key}")

    cache_key = _build_account_lookup_key(str(shop.pk), currency, account_key)

    # Check cache first (thread-safe read)
    with _cache_lock:
        if cache_key in _account_cache:
            return _account_cache[cache_key]

    config = ACCOUNT_TYPES[account_key]
    shop_ct = _get_shop_content_type()

    # Try to find existing account
    account = Account.objects.filter(
        owner_content_type=shop_ct,
        owner_id=str(shop.pk),
        account_type=config["account_type"],
        currency=currency,
        name=config["name_template"].format(shop=shop.name),
    ).first()

    if account is None and auto_create:
        # Create the account with account number
        try:
            with transaction.atomic():
                account = Account.objects.create(
                    owner_content_type=shop_ct,
                    owner_id=str(shop.pk),
                    account_number=config.get("account_number", ""),
                    account_type=config["account_type"],
                    currency=currency,
                    name=config["name_template"].format(shop=shop.name),
                )
        except IntegrityError:
            # Race condition - another process created it
            account = Account.objects.filter(
                owner_content_type=shop_ct,
                owner_id=str(shop.pk),
                account_type=config["account_type"],
                currency=currency,
                name=config["name_template"].format(shop=shop.name),
            ).first()

    if account:
        with _cache_lock:
            _account_cache[cache_key] = account

    return account


def get_required_accounts(
    shop: "Organization",
    currency: str,
    *,
    auto_create: bool = False,
) -> AccountSet:
    """Get all required accounts for a shop/currency.

    This is the primary entry point for services that need accounts.

    Args:
        shop: Organization (dive shop)
        currency: Currency code
        auto_create: If True, create missing accounts (only for seeding/setup)

    Returns:
        AccountSet with all accounts

    Raises:
        AccountConfigurationError: If required accounts are missing and auto_create=False
    """
    account_set = AccountSet(shop=shop, currency=currency)

    for key in ACCOUNT_TYPES:
        account = get_account(shop, currency, key, auto_create=auto_create)
        setattr(account_set, key, account)

    if not auto_create and not account_set.is_complete():
        missing = account_set.get_missing_required()
        raise AccountConfigurationError(shop, currency, missing)

    return account_set


def _get_next_vendor_account_number(shop: "Organization") -> str:
    """Generate the next vendor payable account number.

    Vendor accounts start at 2100 and increment (2100, 2101, 2102...).
    Main accounts payable is 2000.

    Args:
        shop: Organization (dive shop)

    Returns:
        Next available account number string
    """
    from django_ledger.models import Account

    shop_ct = _get_shop_content_type()

    # Find existing vendor payable accounts (those starting with 21xx)
    existing = Account.objects.filter(
        owner_content_type=shop_ct,
        owner_id=str(shop.pk),
        account_type="payable",
        account_number__startswith="21",
    ).order_by("-account_number").first()

    if existing and existing.account_number:
        try:
            next_num = int(existing.account_number) + 1
            return str(next_num)
        except ValueError:
            pass

    # Start at 2100
    return "2100"


def get_vendor_payable_account(
    shop: "Organization",
    vendor: "Organization",
    currency: str,
    *,
    auto_create: bool = False,
) -> "Account | None":
    """Get or create a vendor-specific payable account.

    Vendor payable accounts are owned by the shop (not the vendor) but
    have the vendor name in the account name for identification.
    Account numbers are auto-assigned starting at 2100.

    Args:
        shop: Organization (dive shop) - the account owner
        vendor: Organization (vendor) - for account naming
        currency: Currency code
        auto_create: If True, create if missing

    Returns:
        Account instance or None if not found and auto_create=False
    """
    from django_ledger.models import Account

    shop_ct = _get_shop_content_type()
    account_name = f"Accounts Payable - {vendor.name}"

    # Try to find existing account
    account = Account.objects.filter(
        owner_content_type=shop_ct,
        owner_id=str(shop.pk),
        account_type="payable",
        currency=currency,
        name=account_name,
    ).first()

    if account is None and auto_create:
        try:
            with transaction.atomic():
                account_number = _get_next_vendor_account_number(shop)
                account = Account.objects.create(
                    owner_content_type=shop_ct,
                    owner_id=str(shop.pk),
                    account_number=account_number,
                    account_type="payable",
                    currency=currency,
                    name=account_name,
                )
        except IntegrityError:
            account = Account.objects.filter(
                owner_content_type=shop_ct,
                owner_id=str(shop.pk),
                account_type="payable",
                currency=currency,
                name=account_name,
            ).first()

    return account


@transaction.atomic
def seed_accounts(
    shop: "Organization",
    currency: str = "MXN",
    *,
    vendors: list["Organization"] = None,
) -> AccountSet:
    """Seed the chart of accounts for a shop.

    Creates all standard accounts for the shop/currency combination.
    This is idempotent - existing accounts are not modified.

    Args:
        shop: Organization (dive shop)
        currency: Currency code (default: MXN)
        vendors: Optional list of vendors to create AP accounts for

    Returns:
        AccountSet with all created/existing accounts
    """
    # Clear cache to ensure fresh lookup after seeding
    clear_account_cache()

    # Create standard accounts
    account_set = get_required_accounts(shop, currency, auto_create=True)

    # Create vendor-specific payable accounts if vendors provided
    if vendors:
        for vendor in vendors:
            get_vendor_payable_account(shop, vendor, currency, auto_create=True)

    return account_set


def list_accounts(
    shop: "Organization" = None,
    currency: str = None,
    account_type: str = None,
):
    """List accounts with optional filters.

    Args:
        shop: Filter by shop organization
        currency: Filter by currency
        account_type: Filter by account type

    Returns:
        QuerySet of Account instances (lazy evaluation)
    """
    from django_ledger.models import Account

    queryset = Account.objects.all()

    if shop:
        shop_ct = _get_shop_content_type()
        queryset = queryset.filter(
            owner_content_type=shop_ct,
            owner_id=str(shop.pk),
        )

    if currency:
        queryset = queryset.filter(currency=currency)

    if account_type:
        queryset = queryset.filter(account_type=account_type)

    return queryset.order_by("account_type", "account_number", "name")


def deactivate_account(account: "Account", actor=None) -> "Account":
    """Deactivate an account.

    Deactivated accounts cannot receive new entries but retain all history.
    This is the proper way to "close" an account - accounts are never deleted.

    Args:
        account: Account to deactivate
        actor: User performing the action (for audit log)

    Returns:
        Updated Account instance
    """
    from .audit import Actions, log_event

    if not account.is_active:
        return account  # Already inactive

    account.is_active = False
    account.save(update_fields=["is_active", "updated_at"])

    log_event(
        action=Actions.ACCOUNT_DEACTIVATED,
        actor=actor,
        target=account,
        data={
            "account_number": account.account_number,
            "name": account.name,
            "account_type": account.account_type,
        },
    )

    return account


def reactivate_account(account: "Account", actor=None) -> "Account":
    """Reactivate a previously deactivated account.

    Args:
        account: Account to reactivate
        actor: User performing the action (for audit log)

    Returns:
        Updated Account instance
    """
    from .audit import Actions, log_event

    if account.is_active:
        return account  # Already active

    account.is_active = True
    account.save(update_fields=["is_active", "updated_at"])

    log_event(
        action=Actions.ACCOUNT_REACTIVATED,
        actor=actor,
        target=account,
        data={
            "account_number": account.account_number,
            "name": account.name,
            "account_type": account.account_type,
        },
    )

    return account


def can_deactivate_account(account: "Account") -> tuple[bool, str]:
    """Check if an account can be safely deactivated.

    Accounts can always be deactivated, but this provides warnings
    if there are pending transactions.

    Args:
        account: Account to check

    Returns:
        Tuple of (can_deactivate, warning_message)
    """
    # Check for unposted transactions involving this account
    unposted_entries = account.entries.filter(transaction__posted_at__isnull=True).count()
    if unposted_entries > 0:
        return True, f"Warning: Account has {unposted_entries} entries in unposted transactions"
    return True, ""
