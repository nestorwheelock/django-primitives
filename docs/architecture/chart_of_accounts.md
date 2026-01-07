# Chart of Accounts Architecture

## Overview

The Chart of Accounts in diveops uses `django_ledger.Account` with extensions for:
- **Account numbering** following standard accounting conventions
- **Account deactivation** instead of deletion (accounting standard compliance)
- **Database-level constraints** via PostgreSQL triggers

## Account Numbering Convention

Account numbers follow standard accounting conventions:

| Range       | Type                  | Examples                              |
|-------------|----------------------|---------------------------------------|
| 1000-1999   | Assets               | 1010 Cash/Bank, 1200 Accounts Receivable |
| 2000-2999   | Liabilities          | 2000 Accounts Payable (shop-wide), 2100+ vendor-specific |
| 3000-3999   | Equity               | Reserved for future use               |
| 4000-4999   | Revenue              | 4000 Dive Revenue, 4100 Equipment Rental |
| 5000-5999   | COGS/Expenses        | 5000 Excursion Costs, 5100 Gas Costs, 5200 Equipment |
| 6000-6999   | Operating Expenses   | Reserved for future use               |

### Vendor Payable Accounts

Vendor-specific payable accounts are automatically assigned numbers starting at 2100:
- First vendor: 2100
- Second vendor: 2101
- etc.

The main shop-wide Accounts Payable is 2000.

### Account Number Assignment

Account numbers are assigned:
1. **Automatically** when seeding standard accounts via `seed_accounts()`
2. **Automatically** when creating vendor payable accounts via `get_vendor_payable_account()`
3. **Manually** when creating custom accounts via the staff portal

## Account Lifecycle: No Deletion, Only Deactivation

### Accounting Standard Requirement

**Accounts cannot be deleted.** This is a fundamental accounting principle:
- Historical transactions reference accounts
- Deleting accounts would orphan ledger entries
- Audit trails must be preserved

### Deactivation vs Deletion

| Action      | What Happens                                    |
|-------------|------------------------------------------------|
| Deactivate  | `is_active = False`, account preserved, no new entries allowed |
| Reactivate  | `is_active = True`, account can receive entries again |
| Delete      | **NOT ALLOWED** - use deactivation instead     |

### Database Constraint (PostgreSQL Trigger)

A PostgreSQL trigger enforces that no entries can be created on inactive accounts:

```sql
CREATE OR REPLACE FUNCTION check_account_is_active()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT (SELECT is_active FROM django_ledger_account WHERE id = NEW.account_id) THEN
        RAISE EXCEPTION 'Cannot create entry on inactive account (account_id: %)', NEW.account_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER entry_check_account_active
BEFORE INSERT ON django_ledger_entry
FOR EACH ROW
EXECUTE FUNCTION check_account_is_active();
```

This constraint is enforced at:
1. **Database level** (PostgreSQL trigger) - cannot be bypassed
2. **Application level** (Entry.save() method) - provides friendly error messages

### Invariants

1. **No new entries on inactive accounts** - Enforced by PostgreSQL trigger
2. **Existing entries preserved** - Deactivation doesn't affect historical data
3. **Account numbers immutable** - Once assigned, account numbers should not change
4. **All actions audit logged** - Creation, updates, deactivation, reactivation

## Account Model Fields

```python
class Account(BaseModel):
    # Identity
    id = UUIDField(primary_key=True)

    # Owner (GenericFK to Organization)
    owner_content_type = ForeignKey(ContentType)
    owner_id = CharField(max_length=255)

    # Account identification
    account_number = CharField(max_length=20, blank=True, db_index=True)
    name = CharField(max_length=255)
    account_type = CharField(max_length=50)  # asset, liability, revenue, expense, receivable, payable
    currency = CharField(max_length=3)  # USD, MXN, EUR

    # Lifecycle
    is_active = BooleanField(default=True, db_index=True)

    # BaseModel provides: created_at, updated_at, deleted_at (soft delete)
```

## Service Functions

### Account Management (`accounts.py`)

```python
# Get/create accounts
get_account(shop, currency, account_key, auto_create=False)
get_required_accounts(shop, currency, auto_create=False)
get_vendor_payable_account(shop, vendor, currency, auto_create=False)

# Seeding
seed_accounts(shop, currency="MXN", vendors=None)

# Lifecycle
deactivate_account(account, actor=None)  # Sets is_active=False, audit logged
reactivate_account(account, actor=None)  # Sets is_active=True, audit logged
can_deactivate_account(account)          # Returns (can_deactivate, warning)

# Listing
list_accounts(shop=None, currency=None, account_type=None)
```

## Audit Trail

All account operations are logged via `django_audit_log`:

| Action                   | When Logged                           |
|--------------------------|---------------------------------------|
| `account_created`        | New account created                   |
| `account_updated`        | Account name/number/type changed      |
| `account_deactivated`    | Account deactivated                   |
| `account_reactivated`    | Account reactivated                   |
| `accounts_seeded`        | Chart of accounts seeded              |

## Staff Portal UI

### Chart of Accounts List (`/staff/diveops/accounts/`)

Features:
- **Search** by account name or number
- **Filter** by shop, currency, type, status (active/inactive)
- **Sort** by account number, name, type
- **Pagination** (50 per page)
- **Status badges** (Active/Inactive)
- **Actions**: Edit, Deactivate/Reactivate

### Account Actions

| URL Pattern                              | View                    | Description                    |
|------------------------------------------|-------------------------|--------------------------------|
| `/accounts/`                             | AccountListView         | List with search/filter/sort   |
| `/accounts/add/`                         | AccountCreateView       | Create new account             |
| `/accounts/<uuid>/edit/`                 | AccountUpdateView       | Edit account details           |
| `/accounts/<uuid>/deactivate/`           | AccountDeactivateView   | Deactivate (with confirmation) |
| `/accounts/<uuid>/reactivate/`           | AccountReactivateView   | Reactivate (with confirmation) |
| `/accounts/seed/`                        | AccountSeedView         | Seed standard accounts         |

## Error Handling

### InactiveAccountError

Raised when attempting to create an entry on an inactive account:

```python
from django_ledger.exceptions import InactiveAccountError

try:
    entry = Entry.objects.create(
        transaction=tx,
        account=inactive_account,  # is_active=False
        amount=100,
        entry_type='debit',
    )
except InactiveAccountError as e:
    # "Cannot create entry on inactive account 'X'. Reactivate the account first."
```

### AccountConfigurationError

Raised when required accounts are missing:

```python
from diveops.accounts import AccountConfigurationError

try:
    accounts = get_required_accounts(shop, "MXN")
except AccountConfigurationError as e:
    # "Missing required accounts for Shop (MXN): cash_bank, dive_revenue..."
```

## Best Practices

1. **Seed accounts before operations** - Use `seed_accounts()` during shop setup
2. **Never bypass deactivation** - Always use service functions, not direct model updates
3. **Check account status before transactions** - Use `is_active` filter or handle `InactiveAccountError`
4. **Document account number assignments** - Keep records of what each number represents
5. **Use vendor-specific payables** - Create separate accounts per vendor for reconciliation
