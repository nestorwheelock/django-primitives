# django-sequence

Human-readable sequence IDs for Django. Generate "INV-2026-000123" style identifiers for invoices, orders, tickets, and other business documents.

## Features

- **Human-readable sequences** - "INV-2026-000123" instead of UUIDs
- **Per-organization isolation** - Each tenant gets their own sequence
- **Atomic increments** - Uses `select_for_update()` for concurrency safety
- **Configurable formatting** - Custom prefixes, year inclusion, padding width
- **Gap policy** - Choose whether gaps are allowed

## Installation

```bash
pip install -e packages/django-sequence
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_sequence',
]
```

Run migrations:

```bash
python manage.py migrate django_sequence
```

## Usage

### Basic Usage

```python
from django_sequence.services import next_sequence

# Get next invoice number
invoice_number = next_sequence('invoice', org=my_org)
# Returns: "INV-2026-000001"

# Get next order number
order_number = next_sequence('order', org=my_org)
# Returns: "ORD-2026-000001"
```

### Custom Sequence Configuration

```python
from django_sequence.models import Sequence

# Create a custom sequence
Sequence.objects.create(
    scope='ticket',
    org=my_org,
    prefix='TKT-',
    include_year=False,
    pad_width=6,
    current_value=0,
)

# Use it
ticket_number = next_sequence('ticket', org=my_org)
# Returns: "TKT-000001"
```

### In Models

```python
from django.db import models
from django_sequence.services import next_sequence

class Invoice(models.Model):
    number = models.CharField(max_length=50, unique=True, blank=True)
    org = models.ForeignKey('myapp.Organization', on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_sequence('invoice', org=self.org)
        super().save(*args, **kwargs)
```

## Design Principles

1. **UUIDs for machines, sequences for humans** - Use UUIDs as primary keys, sequences for display
2. **Atomic operations** - `select_for_update()` prevents race conditions
3. **Per-org isolation** - Multi-tenant safe by design
4. **Gaps are OK** - Failed transactions may create gaps; this is normal and expected

## Default Sequences

| Scope | Prefix | Format |
|-------|--------|--------|
| invoice | INV- | INV-2026-000001 |
| order | ORD- | ORD-2026-000001 |
| ticket | TKT- | TKT-000001 |
| receipt | RCP- | RCP-2026-000001 |
