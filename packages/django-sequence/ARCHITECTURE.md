# Architecture: django-sequence

**Status:** Stable / v0.1.0

Human-readable sequence generator for invoices, orders, tickets, etc.

---

## What This Package Is For

Answering the question: **"What's the next invoice/order/ticket number?"**

Use cases:
- Invoice numbers (INV-2024-000123)
- Order IDs (ORD-000456)
- Ticket numbers (TKT-2024-000789)
- Case references
- Any sequential, human-readable identifier

---

## What This Package Is NOT For

- **Not a UUID replacement** - Use UUIDs for primary keys
- **Not globally unique** - Scoped per org, not globally
- **Not cryptographically secure** - Sequential, predictable
- **Not for high-frequency** - Use Redis for > 1000/second

---

## Design Principles

1. **Org-scoped isolation** - Each org has its own sequences
2. **Formatted output** - Includes prefix, year (optional), zero-padding
3. **Atomic increment** - select_for_update prevents race conditions
4. **GenericFK for org** - Works with any organization model
5. **Customizable format** - Prefix, padding width, year inclusion

---

## Data Model

```
Sequence
├── id (UUID, BaseModel)
├── scope (string: 'invoice', 'order', etc.)
├── org (GenericFK, optional)
│   ├── org_content_type
│   └── org_id (CharField for UUID)
├── prefix (e.g., 'INV-', 'ORD-')
├── current_value (bigint)
├── pad_width (default: 6)
├── include_year (default: True)
└── BaseModel fields

Format Examples:
  With year:    "INV-2024-000123"
  Without year: "TKT-000042"

Constraint:
  Unique on (scope, org_content_type, org_id)
```

---

## Public API

### Service Functions

```python
from django_sequence.services import next_sequence, get_current_sequence

# Get next invoice number for an org
invoice_number = next_sequence('invoice', org=my_org)
# Returns: "INV-2024-000001"

# Get next without incrementing
current = get_current_sequence('invoice', org=my_org)
# Returns: "INV-2024-000001" (same as before)

# Next call increments
next_num = next_sequence('invoice', org=my_org)
# Returns: "INV-2024-000002"

# Global sequence (no org)
ticket = next_sequence('ticket')
# Returns: "TKT-2024-000001"
```

### Creating Custom Sequences

```python
from django_sequence.models import Sequence
from django.contrib.contenttypes.models import ContentType

# Create sequence with custom format
Sequence.objects.create(
    scope='purchase_order',
    org_content_type=ContentType.objects.get_for_model(my_org),
    org_id=str(my_org.pk),
    prefix='PO-',
    pad_width=8,
    include_year=False,
)

# Results in: "PO-00000001", "PO-00000002", ...
```

### Querying Sequences

```python
from django_sequence.models import Sequence

# Get sequence for scope and org
seq = Sequence.objects.get(
    scope='invoice',
    org_content_type=ContentType.objects.get_for_model(org),
    org_id=str(org.pk),
)

# Check current value
print(f"Next invoice: {seq.formatted_value}")
```

---

## Hard Rules

1. **Unique per scope+org** - Constraint on (scope, org_content_type, org_id)
2. **Atomic increment** - Uses select_for_update for thread safety
3. **Never decrements** - Values only go up
4. **Year from current date** - formatted_value uses today's year

---

## Invariants

- Sequence(scope, org) is unique per combination
- current_value is always >= 0
- current_value never decreases
- formatted_value includes current year when include_year=True
- org_id is always stored as string

---

## Known Gotchas

### 1. Year Rollover

**Problem:** Year changes mid-operation.

```python
# December 31, 11:59 PM
seq = next_sequence('invoice', org)
# Returns: "INV-2024-000100"

# January 1, 12:01 AM
seq = next_sequence('invoice', org)
# Returns: "INV-2025-000101" (year changed, counter continued!)
```

**Note:** Counter doesn't reset on year change. This is intentional for uniqueness.

### 2. Concurrent Access

**Problem:** Race conditions without proper locking.

```python
# The service function handles this with select_for_update
# WRONG - direct increment can race
seq = Sequence.objects.get(scope='invoice', ...)
seq.current_value += 1
seq.save()  # Race condition!

# CORRECT - use service function
next_sequence('invoice', org)  # Uses select_for_update
```

### 3. Gaps in Sequence

**Problem:** Expecting contiguous numbers.

```python
# Rollback after increment leaves gap
with transaction.atomic():
    invoice_num = next_sequence('invoice', org)  # Gets 000100
    raise Exception("Something failed")
    # Rollback happens, but 000100 is "used"

# Next call gets 000101, gap at 000100
```

**Solution:** Gaps are normal and expected. Don't rely on contiguity.

### 4. Missing Sequence Definition

**Problem:** Calling next_sequence for undefined scope.

```python
next_sequence('undefined_scope', org)
# Creates sequence with defaults:
# prefix='undefined_scope-', pad_width=6, include_year=True
```

**Solution:** Pre-create sequences with proper settings in migrations.

---

## Recommended Usage

### 1. Define Sequences in Migrations

```python
def create_sequences(apps, schema_editor):
    Sequence = apps.get_model('django_sequence', 'Sequence')

    sequences = [
        ('invoice', 'INV-', 6, True),
        ('order', 'ORD-', 6, True),
        ('ticket', 'TKT-', 6, False),
    ]

    for scope, prefix, pad, year in sequences:
        Sequence.objects.get_or_create(
            scope=scope,
            org_content_type=None,  # Global
            org_id='',
            defaults={
                'prefix': prefix,
                'pad_width': pad,
                'include_year': year,
            }
        )
```

### 2. Use in Model Creation

```python
from django_sequence.services import next_sequence

class Invoice(models.Model):
    number = models.CharField(max_length=50, unique=True)
    # ... other fields

    @classmethod
    def create(cls, org, **kwargs):
        invoice = cls(
            number=next_sequence('invoice', org=org),
            **kwargs
        )
        invoice.save()
        return invoice
```

### 3. Display Formatted Value

```python
# In views/templates
invoice_number = invoice.number  # Already formatted: "INV-2024-000123"

# Parse if needed
parts = invoice_number.split('-')
prefix = parts[0]      # "INV"
year = parts[1]        # "2024"
number = parts[2]      # "000123"
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Sequence model with org scoping
- next_sequence() with atomic increment
- Configurable prefix, padding, year inclusion
- GenericFK for organization model
