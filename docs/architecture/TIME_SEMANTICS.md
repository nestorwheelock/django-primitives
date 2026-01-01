# Time Semantics Contract

**Status:** Active
**Last Updated:** 2026-01-01

---

## Overview

This document defines the "constitutional" rules for handling time across all django-primitives packages. Every package that records facts must follow these rules to ensure consistent behavior across all verticals (vet clinic, pizza shop, dive operations, rentals, etc.).

---

## The Two Times

Every fact in the system has **two** timestamps:

| Field | Meaning | Who Controls |
|-------|---------|--------------|
| `effective_at` | When the fact is **true in the business world** | Business logic (may be backdated) |
| `recorded_at` | When the **system learned** the fact | System only (always `auto_now_add=True`) |

### Why Two Times?

**Real-world example:** A pharmacy dispenses medication at 2:00 PM, but the pharmacist doesn't enter it into the system until 2:30 PM.

- `effective_at = 2024-12-15 14:00:00` (when the patient received the medication)
- `recorded_at = 2024-12-15 14:30:00` (when it was recorded)

Without this distinction:
- Audit trails are misleading ("why does the log say 2:30 when the receipt says 2:00?")
- Point-in-time queries are wrong ("what was dispensed by 2:15?" would miss this entry)
- Legal/compliance issues ("the timestamp doesn't match the physical evidence")

---

## Rules

### Rule 1: Every Fact Gets Both Times

```python
class MyFact(TimeSemanticsMixin, models.Model):
    """Every model that records a business fact needs both times."""
    # Inherited from TimeSemanticsMixin:
    # - effective_at: DateTimeField (required)
    # - recorded_at: DateTimeField (auto_now_add=True)

    class Meta:
        abstract = True
```

**Even if effective_at defaults to recorded_at**, the field must exist. This allows:
- Backdating when business rules permit
- Consistent query patterns
- Clear audit trails

### Rule 2: `recorded_at` is Sacred

`recorded_at` must **always** be `auto_now_add=True`. It represents when the system learned the fact.

```python
# CORRECT
recorded_at = models.DateTimeField(auto_now_add=True)

# WRONG - never allow this
recorded_at = models.DateTimeField(default=timezone.now)  # Allows override
```

**No exceptions.** If you need a different "system time," create a new field.

### Rule 3: `effective_at` Policies are Explicit

Each model must declare its backdating policy:

```python
class MyModel(TimeSemanticsMixin):
    class TimePolicy:
        allow_backdate = True  # Can effective_at be before recorded_at?
        allow_future = False   # Can effective_at be in the future?
        max_backdate_days = 30 # How far back? (None = unlimited)
```

**Current package policies:**

| Package | Model | allow_backdate | allow_future | max_backdate_days |
|---------|-------|----------------|--------------|-------------------|
| django-catalog | DispenseLog | Yes | No | 7 |
| django-worklog | WorkSession | No | No | 0 |
| django-encounters | EncounterTransition | Yes | No | None |
| django-audit-log | AuditLog | No | No | 0 |

### Rule 4: Store UTC, Display Local

All timestamps are stored in UTC. Display conversion happens at the presentation layer.

```python
# Storage
effective_at = models.DateTimeField()  # Stored as UTC

# Query (always UTC)
MyModel.objects.filter(effective_at__gte=some_utc_datetime)

# Display (convert at presentation)
local_time = effective_at.astimezone(user_timezone)
```

**Date-only fields** (like `birth_date`) are an exception - store as `DateField` without timezone.

### Rule 5: Point-in-Time Queries

Every model with time semantics must support "as of" queries:

```python
# What was true at this moment?
MyModel.objects.as_of(timestamp)

# Implementation
class AsOfQuerySet(models.QuerySet):
    def as_of(self, timestamp):
        return self.filter(effective_at__lte=timestamp)
```

For **effective-dated records** (valid_from/valid_to):

```python
class EffectiveDatedQuerySet(models.QuerySet):
    def as_of(self, timestamp):
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=timestamp)
        )
```

---

## Effective Dating (valid_from / valid_to)

Some records have **temporal validity** - they're true for a period, not a point.

```python
class PriceListEntry(EffectiveDatedMixin):
    product = models.ForeignKey(Product)
    price = models.DecimalField(...)
    # Inherited: valid_from, valid_to, effective_at, recorded_at
```

### Rules for Effective Dating

1. **valid_from is required** - When does this record become effective?
2. **valid_to is nullable** - Null means "until further notice"
3. **No overlaps** - Enforce via database constraint or application logic
4. **Close old before opening new** - When updating, set old record's valid_to before creating new

```python
# Update a price (correct way)
with transaction.atomic():
    old_price = PriceListEntry.objects.get(product=product, valid_to__isnull=True)
    old_price.valid_to = timezone.now()
    old_price.save()

    new_price = PriceListEntry.objects.create(
        product=product,
        price=new_amount,
        valid_from=timezone.now(),
        valid_to=None
    )
```

---

## Implementation Guide

### Adding Time Semantics to a New Model

```python
from django_decisioning.mixins import TimeSemanticsMixin

class MyBusinessFact(TimeSemanticsMixin, BaseModel):
    """A fact about the business."""

    # Your fields here
    amount = models.DecimalField(...)

    class TimePolicy:
        allow_backdate = True
        allow_future = False
        max_backdate_days = 7
```

### Adding Time Semantics to an Existing Model

1. Add the fields:
```python
effective_at = models.DateTimeField(default=timezone.now)
recorded_at = models.DateTimeField(auto_now_add=True)
```

2. Create migration:
```bash
python manage.py makemigrations
```

3. For existing rows, set `effective_at = recorded_at`:
```python
def forwards(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')
    MyModel.objects.filter(effective_at__isnull=True).update(
        effective_at=F('created_at')  # or recorded_at if it exists
    )
```

---

## Query Patterns

### "What was true at time T?"

```python
# Simple fact lookup
fact = MyModel.objects.filter(effective_at__lte=timestamp).latest('effective_at')

# Using as_of() helper
facts = MyModel.objects.as_of(timestamp)
```

### "What changed between T1 and T2?"

```python
# Facts that became effective in the window
changed = MyModel.objects.filter(
    effective_at__gt=start_time,
    effective_at__lte=end_time
)
```

### "When did we learn about this?"

```python
# For audit purposes - what did we record on a given day?
learned_today = MyModel.objects.filter(
    recorded_at__date=date.today()
)
```

### "Show me backdated entries"

```python
# Entries where effective_at < recorded_at
backdated = MyModel.objects.filter(
    effective_at__lt=F('recorded_at')
)
```

---

## Validation

### TimeSemantics Validator

```python
from django_decisioning.validators import validate_time_semantics

class MyModel(TimeSemanticsMixin):
    def clean(self):
        super().clean()
        validate_time_semantics(self)  # Checks against TimePolicy
```

The validator checks:
- `effective_at` is not in the future (if `allow_future=False`)
- `effective_at` is not too far in the past (if `max_backdate_days` is set)
- `effective_at` is present

---

## Migration Checklist

When adding time semantics to an existing package:

- [ ] Add `effective_at` field with sensible default
- [ ] Add `recorded_at` field with `auto_now_add=True`
- [ ] Create data migration to populate existing rows
- [ ] Add `TimePolicy` inner class with explicit policy
- [ ] Add `as_of()` to the model's QuerySet
- [ ] Update any time-based queries to use `effective_at`
- [ ] Add tests for backdating behavior
- [ ] Document the backdating policy in model docstring

---

## Anti-Patterns

### Don't: Use client timestamps for `recorded_at`

```python
# WRONG - client can lie about when they submitted
recorded_at = request.data.get('timestamp')

# CORRECT - server decides when it learned the fact
recorded_at = auto_now_add=True
```

### Don't: Use `auto_now` for `effective_at`

```python
# WRONG - can't backdate
effective_at = models.DateTimeField(auto_now=True)

# CORRECT - explicit, can be backdated if policy allows
effective_at = models.DateTimeField(default=timezone.now)
```

### Don't: Mix time semantics within a model

```python
# WRONG - some fields use effective_at, others use created_at
class Confusing(models.Model):
    happened_at = models.DateTimeField()  # Is this effective_at?
    created_at = models.DateTimeField(auto_now_add=True)  # Is this recorded_at?
    logged_at = models.DateTimeField()  # What is this?

# CORRECT - use standard field names
class Clear(TimeSemanticsMixin):
    # Uses effective_at and recorded_at from mixin
    pass
```

### Don't: Forget to index time fields

```python
# WRONG - slow queries on large tables
effective_at = models.DateTimeField()

# CORRECT - index for query performance
effective_at = models.DateTimeField(db_index=True)
```

---

## Appendix: Current Package Audit

| Package | Has effective_at | Has recorded_at | Notes |
|---------|-----------------|-----------------|-------|
| django-audit-log | No | Yes (created_at) | Needs retrofit |
| django-catalog | Partial (DispenseLog) | Yes | Needs consistency |
| django-encounters | No | Yes (created_at) | Needs retrofit |
| django-worklog | No (started_at/ended_at) | Yes | Needs review |
| django-rbac | No | Yes (created_at) | Needs retrofit |
| django-parties | No | Yes (created_at) | Low priority |

**Phase 8 (Retrofit)** will address these gaps by adding TimeSemanticsMixin to all relevant models.
