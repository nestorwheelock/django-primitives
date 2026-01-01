# django-ledger

Double-entry ledger primitives for Django applications.

## Features

- **Account Model**: Track balances with GenericFK owner
- **Transaction Model**: Group balanced entries
- **Entry Model**: Immutable ledger entries with reversal support
- **Double-Entry Enforcement**: Transactions must balance
- **Time Semantics**: effective_at vs recorded_at support

## Installation

```bash
pip install django-ledger
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django.contrib.contenttypes',
    'django_ledger',
]
```

Run migrations:

```bash
python manage.py migrate django_ledger
```

## Usage

### Creating Accounts

```python
from django_ledger.models import Account

# Create accounts for a customer
receivable = Account.objects.create(
    owner=customer,
    account_type='receivable',
    currency='USD',
)

revenue = Account.objects.create(
    owner=organization,
    account_type='revenue',
    currency='USD',
)
```

### Recording Transactions

```python
from django_ledger.services import record_transaction
from decimal import Decimal

# Record a sale
tx = record_transaction(
    description="Invoice #123",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ],
)
```

### Querying Balances

```python
from django_ledger.services import get_balance

balance = get_balance(receivable)  # Returns Decimal
```

### Reversing Entries

```python
from django_ledger.services import reverse_entry

# Create reversal
reversal = reverse_entry(
    entry=original_entry,
    reason="Customer refund",
)
```

## License

MIT
