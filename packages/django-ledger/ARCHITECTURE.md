# Architecture: django-ledger

**Status:** Stable / v0.1.0

Double-entry bookkeeping for Django applications.

---

## What This Package Is For

Answering the question: **"Where did the money go?"**

Use cases:
- Tracking account balances (receivables, payables, revenue, expenses)
- Recording financial transactions with balanced entries
- Historical balance queries (as-of date)
- Reversal transactions for corrections
- Currency-isolated accounts

---

## What This Package Is NOT For

- **Not payment processing** - Use Stripe/PayPal for actual payments
- **Not invoicing** - This tracks the accounting, not document generation
- **Not multi-currency conversion** - Accounts are currency-isolated
- **Not tax calculation** - Calculate taxes elsewhere, record results here

---

## Design Principles

1. **Double-entry** - Every transaction has balanced debits and credits
2. **Immutable entries** - Posted entries cannot be modified, only reversed
3. **Balance = debits - credits** - Standard accounting equation
4. **Currency isolation** - Accounts track single currency
5. **GenericFK owners** - Accounts can belong to any model (Customer, Vendor, etc.)
6. **Time semantics** - effective_at (business) vs recorded_at (system)

---

## Data Model

```
Account                                Transaction
├── id (UUID, BaseModel)               ├── id (auto)
├── owner (GenericFK)                  ├── description
│   ├── owner_content_type (FK)        ├── posted_at (null = draft)
│   └── owner_id (CharField for UUID)  ├── effective_at (time semantics)
├── account_type (receivable|payable|...) ├── recorded_at (time semantics)
├── currency (USD|EUR|...)             └── metadata (JSON)
├── name (optional)
└── BaseModel fields

Entry (IMMUTABLE after posted)
├── id (auto)
├── transaction (FK)
├── account (FK)
├── amount (Decimal, must be > 0)
├── entry_type (debit|credit)
├── description
├── effective_at (time semantics)
├── recorded_at (time semantics)
├── reverses (FK → Entry, for reversals)
└── metadata (JSON)

Balance Calculation:
  balance = SUM(debits) - SUM(credits)
  For receivable: positive = customer owes us
  For payable: positive = we owe vendor
```

---

## Account Types

| Type | Debit Effect | Credit Effect | Normal Balance |
|------|--------------|---------------|----------------|
| receivable | Increase | Decrease | Debit (positive) |
| payable | Decrease | Increase | Credit (negative) |
| revenue | Decrease | Increase | Credit (negative) |
| expense | Increase | Decrease | Debit (positive) |
| asset | Increase | Decrease | Debit (positive) |
| liability | Decrease | Increase | Credit (negative) |

---

## Public API

### Service Functions

```python
from django_ledger.services import record_transaction, get_balance, reverse_entry

# Record a balanced transaction
tx = record_transaction(
    description="Invoice #123",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ],
    effective_at=timezone.now(),
    metadata={'invoice_id': '123'},
)

# Get account balance
balance = get_balance(receivable)  # Current balance
past_balance = get_balance(receivable, as_of=some_date)  # Historical

# Reverse an entry
reversal_tx = reverse_entry(
    entry=original_entry,
    reason="Customer refund",
    effective_at=timezone.now(),
)
```

### Direct Model Usage

```python
from django_ledger.models import Account, Transaction, Entry

# Create account for a customer
from django.contrib.contenttypes.models import ContentType

account = Account.objects.create(
    owner_content_type=ContentType.objects.get_for_model(customer),
    owner_id=str(customer.pk),
    account_type='receivable',
    currency='USD',
    name='Customer A/R',
)

# Query accounts
customer_accounts = Account.objects.for_owner(customer)
receivables = Account.objects.by_type('receivable')
usd_accounts = Account.objects.by_currency('USD')
```

---

## Transaction Lifecycle

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│   Draft      │────→│   Validate    │────→│   Posted     │
│ (posted_at   │     │ debits ==     │     │ (posted_at   │
│  = NULL)     │     │ credits       │     │  = NOW)      │
└──────────────┘     └───────────────┘     └──────────────┘
                                                  │
                                                  │ Immutable!
                                                  ▼
                                           ┌──────────────┐
                                           │  Reversal    │
                                           │ (new tx with │
                                           │  opposite    │
                                           │  entry_type) │
                                           └──────────────┘
```

---

## Hard Rules

1. **Debits must equal credits** - Enforced by `record_transaction()` service
2. **Amount must be positive** - DB constraint `entry_amount_positive`
3. **Posted entries are immutable** - Raises `ImmutableEntryError` on modify
4. **Reversals reference original** - Entry.reverses FK tracks reversal chain
5. **owner_id is always string** - CharField for UUID support

---

## Invariants

- `Entry.amount > 0` always (direction via entry_type)
- For any posted Transaction: `SUM(debit amounts) == SUM(credit amounts)`
- Posted Transaction: `posted_at IS NOT NULL`
- Draft Transaction: `posted_at IS NULL`
- Entry with Transaction.is_posted=True cannot be modified
- Account.owner_id is always stored as string
- Reversal entry has opposite entry_type from original

---

## Known Gotchas

### 1. Amount Must Be Positive

**Problem:** Using negative amounts for credits.

```python
# WRONG - amount must be positive
Entry.objects.create(
    account=payable,
    amount=Decimal('-100.00'),  # Will fail constraint
    entry_type='credit',
)

# CORRECT - use entry_type for direction
Entry.objects.create(
    account=payable,
    amount=Decimal('100.00'),  # Positive
    entry_type='credit',  # Direction here
)
```

### 2. Posted Entries Are Immutable

**Problem:** Trying to modify a posted entry.

```python
entry = Entry.objects.first()
if entry.transaction.is_posted:
    entry.amount = Decimal('200.00')
    entry.save()  # Raises ImmutableEntryError!
```

**Solution:** Create a reversal transaction instead:

```python
reversal_tx = reverse_entry(entry, reason="Correction")
```

### 3. Unbalanced Transactions Rejected

**Problem:** Debits don't equal credits.

```python
record_transaction(
    description="Bad transaction",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('50.00'), 'entry_type': 'credit'},
    ],
)
# Raises: UnbalancedTransactionError: debits=100.00, credits=50.00
```

### 4. Balance Direction Confusion

**Problem:** Misinterpreting balance sign.

```python
balance = get_balance(receivable)  # Returns Decimal('100.00')
# This means: customer owes us $100 (debit balance)

balance = get_balance(payable)  # Returns Decimal('-100.00')
# This means: we owe vendor $100 (credit balance)
```

**Solution:** Remember: balance = debits - credits

### 5. Currency Mixing

**Problem:** Adding entries for accounts with different currencies.

```python
usd_account = Account.objects.create(currency='USD', ...)
eur_account = Account.objects.create(currency='EUR', ...)

# This will create invalid financial records!
record_transaction(
    description="Mixed currency",
    entries=[
        {'account': usd_account, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': eur_account, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ],
)
# Technically "balanced" but semantically wrong
```

**Solution:** Keep transactions within same currency. Use separate conversion transactions.

---

## Recommended Usage

### 1. Use Service Functions

```python
from django_ledger.services import record_transaction

# RECOMMENDED - validates balance
tx = record_transaction(
    description="Sale",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ],
)

# AVOID - bypasses validation
tx = Transaction.objects.create(description="Sale")
Entry.objects.create(transaction=tx, account=receivable, ...)
Entry.objects.create(transaction=tx, account=revenue, ...)
tx.posted_at = timezone.now()
tx.save()  # Could be unbalanced!
```

### 2. Handle Corrections with Reversals

```python
def correct_entry(original_entry, correct_amount, reason):
    """Correct an entry by reversing and re-recording."""
    from django_ledger.services import reverse_entry, record_transaction

    # Step 1: Reverse the original
    reverse_entry(original_entry, reason=reason)

    # Step 2: Record correct amount
    return record_transaction(
        description=f"Correction: {reason}",
        entries=[
            {'account': original_entry.account, 'amount': correct_amount, ...},
            # ... balancing entries
        ],
    )
```

### 3. Query Historical Balances

```python
from datetime import date
from django_ledger.services import get_balance

# End of month balance
eom = date(2024, 12, 31)
december_balance = get_balance(account, as_of=eom)

# Balance at any point in time
past_balance = get_balance(account, as_of=some_datetime)
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete on Account)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Account model with GenericFK owner
- Transaction model with posting workflow
- Entry model with immutability enforcement
- record_transaction() with balance validation
- get_balance() with as_of support
- reverse_entry() for corrections
- Time semantics (effective_at, recorded_at)
