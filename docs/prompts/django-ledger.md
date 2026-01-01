# Prompt: Rebuild django-ledger

## Instruction

Create a Django package called `django-ledger` that provides double-entry accounting primitives with immutable posted entries.

## Package Purpose

Provide lightweight, immutable double-entry accounting:
- Account model with polymorphic owners via GenericFK
- Transaction model grouping balanced entries
- Entry model that is immutable once posted
- Balance calculation and entry reversal services

## Dependencies

- Django >= 4.2
- django.contrib.contenttypes

## File Structure

```
packages/django-ledger/
├── pyproject.toml
├── README.md
├── src/django_ledger/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_models.py
    └── test_services.py
```

## Exceptions Specification

### exceptions.py

```python
class LedgerError(Exception):
    """Base exception for ledger errors."""
    pass

class UnbalancedTransactionError(LedgerError):
    """Raised when transaction entries don't balance."""
    pass

class ImmutableEntryError(LedgerError):
    """Raised when attempting to modify a posted entry."""
    pass

class CurrencyMismatchError(LedgerError):
    """Reserved for future currency validation."""
    pass

class TransactionNotPostedError(LedgerError):
    """Reserved for future state checks."""
    pass
```

## Models Specification

### Account Model

```python
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class AccountQuerySet(models.QuerySet):
    def for_owner(self, owner):
        content_type = ContentType.objects.get_for_model(owner)
        return self.filter(
            owner_content_type=content_type,
            owner_id=str(owner.pk)
        )

    def by_type(self, account_type):
        return self.filter(account_type=account_type)

    def by_currency(self, currency):
        return self.filter(currency=currency)


class Account(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    owner_id = models.CharField(max_length=255)  # CharField for UUID support
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    account_type = models.CharField(max_length=50)  # receivable, payable, revenue, expense, etc.
    currency = models.CharField(max_length=3)  # ISO 4217
    name = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountQuerySet.as_manager()

    class Meta:
        app_label = 'django_ledger'
        indexes = [
            models.Index(fields=['owner_content_type', 'owner_id']),
            models.Index(fields=['account_type']),
            models.Index(fields=['currency']),
        ]

    def save(self, *args, **kwargs):
        self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_type} ({self.currency})"
```

### Transaction Model

```python
class Transaction(models.Model):
    description = models.TextField(blank=True, default='')
    posted_at = models.DateTimeField(null=True, blank=True)  # null = draft
    effective_at = models.DateTimeField(default=timezone.now)
    recorded_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_ledger'
        ordering = ['-effective_at', '-recorded_at']

    @property
    def is_posted(self) -> bool:
        return self.posted_at is not None

    def __str__(self):
        status = 'posted' if self.is_posted else 'draft'
        desc = self.description[:50] if self.description else 'No description'
        return f"Transaction ({status}): {desc}"
```

### Entry Model

```python
class EntryType(models.TextChoices):
    DEBIT = 'debit', 'Debit'
    CREDIT = 'credit', 'Credit'


class Entry(models.Model):
    transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name='entries'
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='entries'
    )
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    description = models.CharField(max_length=500, blank=True, default='')

    effective_at = models.DateTimeField(default=timezone.now)
    recorded_at = models.DateTimeField(auto_now_add=True)

    reverses = models.ForeignKey(
        'self', on_delete=models.PROTECT,
        null=True, blank=True, related_name='reversal_entries'
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_ledger'
        ordering = ['-effective_at', '-recorded_at']

    def save(self, *args, **kwargs):
        # Enforce immutability for posted entries
        if self.pk and self.transaction.is_posted:
            raise ImmutableEntryError(
                f"Cannot modify entry {self.pk} - transaction is posted. "
                "Create a reversal instead."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry_type} {self.amount} to {self.account}"
```

## Service Functions

### services.py

```python
from decimal import Decimal
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Account, Transaction, Entry, EntryType
from .exceptions import UnbalancedTransactionError

@transaction.atomic
def record_transaction(
    description: str,
    entries: List[Dict[str, Any]],
    effective_at: Optional[Any] = None,
    metadata: Optional[Dict] = None,
) -> Transaction:
    """
    Record a balanced double-entry transaction atomically.

    Args:
        description: Transaction description
        entries: List of entry dicts with keys: account, amount, entry_type, description
        effective_at: Business timestamp (defaults to now)
        metadata: Additional metadata dict

    Returns:
        Posted Transaction instance

    Raises:
        UnbalancedTransactionError: If debits != credits
    """
    # Validate balance
    debits = sum(e['amount'] for e in entries if e['entry_type'] == 'debit')
    credits = sum(e['amount'] for e in entries if e['entry_type'] == 'credit')

    if debits != credits:
        raise UnbalancedTransactionError(
            f"Transaction unbalanced: debits={debits}, credits={credits}"
        )

    # Create transaction
    tx = Transaction.objects.create(
        description=description,
        effective_at=effective_at or timezone.now(),
        metadata=metadata or {},
    )

    # Create entries
    for entry_data in entries:
        Entry.objects.create(
            transaction=tx,
            account=entry_data['account'],
            amount=entry_data['amount'],
            entry_type=entry_data['entry_type'],
            description=entry_data.get('description', ''),
            effective_at=tx.effective_at,
        )

    # Post transaction
    tx.posted_at = timezone.now()
    tx.save()

    return tx


def get_balance(
    account: Account,
    as_of: Optional[Any] = None,
) -> Decimal:
    """
    Calculate account balance: sum(debits) - sum(credits).

    Args:
        account: Account to calculate balance for
        as_of: Optional historical timestamp

    Returns:
        Decimal balance
    """
    entries = Entry.objects.filter(
        account=account,
        transaction__posted_at__isnull=False,
    )

    if as_of:
        entries = entries.filter(effective_at__lte=as_of)

    debit_sum = entries.filter(entry_type='debit').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

    credit_sum = entries.filter(entry_type='credit').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

    return debit_sum - credit_sum


@transaction.atomic
def reverse_entry(
    entry: Entry,
    reason: str,
    effective_at: Optional[Any] = None,
) -> Transaction:
    """
    Create a reversal transaction for an entry.

    Args:
        entry: Entry to reverse
        reason: Reason for reversal
        effective_at: When reversal is effective

    Returns:
        New reversal Transaction (posted)
    """
    # Determine opposite type
    opposite_type = EntryType.CREDIT if entry.entry_type == 'debit' else EntryType.DEBIT

    # Create reversal transaction
    tx = Transaction.objects.create(
        description=f"Reversal: {reason}",
        effective_at=effective_at or timezone.now(),
        metadata={'reverses_entry_id': entry.pk, 'reason': reason},
    )

    # Create reversal entry
    Entry.objects.create(
        transaction=tx,
        account=entry.account,
        amount=entry.amount,
        entry_type=opposite_type,
        description=f"Reversal of entry {entry.pk}: {reason}",
        effective_at=tx.effective_at,
        reverses=entry,
    )

    # Post reversal
    tx.posted_at = timezone.now()
    tx.save()

    return tx
```

## Test Models

### tests/models.py

```python
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

class Customer(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'
```

## Test Cases (48 tests)

### Account Model Tests (7 tests)
1. `test_account_has_owner_generic_fk` - GenericFK works
2. `test_account_owner_id_is_charfield` - UUID support
3. `test_account_has_account_type` - Type stored
4. `test_account_has_currency` - Currency stored
5. `test_account_has_name_optional` - Name optional
6. `test_account_name_defaults_to_empty` - Default ''
7. `test_account_has_timestamps` - created_at, updated_at

### Transaction Model Tests (8 tests)
1. `test_transaction_has_description` - Description field
2. `test_transaction_description_is_optional` - Optional
3. `test_transaction_has_posted_at_nullable` - Can be draft
4. `test_transaction_is_posted_property` - Property works
5. `test_transaction_has_effective_at` - Business timestamp
6. `test_transaction_effective_at_defaults_to_now` - Default
7. `test_transaction_has_recorded_at` - System timestamp
8. `test_transaction_has_metadata` - JSONField

### Entry Model Tests (10 tests)
1. `test_entry_has_transaction_fk` - FK relationship
2. `test_entry_has_account_fk` - FK relationship
3. `test_entry_has_amount_decimal` - Decimal precision
4. `test_entry_has_entry_type` - debit/credit choices
5. `test_entry_has_description` - Optional description
6. `test_entry_has_effective_at` - Business timestamp
7. `test_entry_has_recorded_at` - System timestamp
8. `test_entry_has_reverses_fk` - Self-referential FK
9. `test_entry_reversal_entries_related_name` - Reverse relation
10. `test_entry_has_metadata` - JSONField

### Entry Immutability Tests (2 tests)
1. `test_entry_can_be_modified_before_posting` - Draft editable
2. `test_entry_immutable_after_posting` - Posted immutable

### Account QuerySet Tests (3 tests)
1. `test_for_owner_returns_accounts` - Filters by owner
2. `test_by_type_filters_accounts` - Filters by type
3. `test_by_currency_filters_accounts` - Filters by currency

### record_transaction Tests (7 tests)
1. `test_record_transaction_creates_transaction` - Creates tx
2. `test_record_transaction_creates_entries` - Creates entries
3. `test_record_transaction_posts_transaction` - is_posted=True
4. `test_record_transaction_enforces_balance` - UnbalancedTransactionError
5. `test_record_transaction_multiple_entries` - 3+ entries
6. `test_record_transaction_with_metadata` - Metadata stored
7. `test_record_transaction_with_effective_at` - Custom timestamp

### get_balance Tests (5 tests)
1. `test_get_balance_returns_zero_for_empty` - Zero balance
2. `test_get_balance_calculates_debit_minus_credit` - Formula
3. `test_get_balance_credit_account` - Negative for credit
4. `test_get_balance_multiple_transactions` - Accumulates
5. `test_get_balance_as_of_timestamp` - Historical

### reverse_entry Tests (5 tests)
1. `test_reverse_entry_creates_new_transaction` - New tx
2. `test_reverse_entry_creates_opposite_entry` - Opposite type
3. `test_reverse_entry_links_to_original` - reverses FK
4. `test_reverse_entry_nets_to_zero` - Balance cancels
5. `test_reverse_entry_includes_reason` - Reason in description

### Integration Test (1 test)
1. `test_complete_sales_cycle` - Sale, payment, refund workflow

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'Account',
    'Transaction',
    'Entry',
    'record_transaction',
    'get_balance',
    'reverse_entry',
    'LedgerError',
    'UnbalancedTransactionError',
    'ImmutableEntryError',
]

def __getattr__(name):
    if name in ('Account', 'Transaction', 'Entry'):
        from .models import Account, Transaction, Entry
        return locals()[name]
    if name in ('record_transaction', 'get_balance', 'reverse_entry'):
        from .services import record_transaction, get_balance, reverse_entry
        return locals()[name]
    if name in ('LedgerError', 'UnbalancedTransactionError', 'ImmutableEntryError'):
        from .exceptions import LedgerError, UnbalancedTransactionError, ImmutableEntryError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Double-Entry Balance**: debits must equal credits
2. **Immutable Posted Entries**: Cannot modify after posting
3. **Reversal Pattern**: Create opposite entry instead of delete
4. **GenericFK Owners**: Accounts owned by any model
5. **Balance = Debits - Credits**: Consistent formula

## Usage Examples

```python
from decimal import Decimal
from django_ledger import Account, record_transaction, get_balance, reverse_entry

# Create accounts
receivable = Account.objects.create(
    owner=customer, account_type='receivable', currency='USD'
)
revenue = Account.objects.create(
    owner=org, account_type='revenue', currency='USD'
)

# Record transaction
tx = record_transaction(
    description="Invoice #123",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ]
)

# Check balance
balance = get_balance(receivable)  # Decimal('100.00')

# Reverse if needed
reversal = reverse_entry(tx.entries.first(), reason="Refund")
balance = get_balance(receivable)  # Decimal('0')
```

## Acceptance Criteria

- [ ] Account model with GenericFK owner
- [ ] Transaction model with posted_at for immutability
- [ ] Entry model with immutability enforcement
- [ ] record_transaction enforces balance
- [ ] get_balance calculates debits - credits
- [ ] reverse_entry creates opposite entry
- [ ] All 48 tests passing
- [ ] README with usage examples
