# Architecture: django-decisioning

**Status:** Stable / v0.1.0

Time semantics and idempotency patterns for Django business operations.

---

## What This Package Is For

Answering the questions: **"When did this happen (business time vs system time)?"** and **"Has this operation already been executed?"**

Use cases:
- Dual timestamps for business facts (effective_at vs recorded_at)
- Backdating corrections while preserving audit trail
- Preventing duplicate operations from retries
- Double-click protection on commits
- Recording decisions with immutable evidence

---

## What This Package Is NOT For

- **Not an audit log** - Use django-audit-log for who-did-what tracking
- **Not a job queue** - Don't use for async task scheduling
- **Not event sourcing** - This tracks facts, not domain events
- **Not distributed locking** - Only protects within single database

---

## Design Principles

1. **Dual time semantics** - Every fact has effective_at (business) and recorded_at (system)
2. **Immutable recorded_at** - System timestamp is auto_now_add, never override
3. **Backdating allowed** - effective_at can be set to past for corrections
4. **At-most-once execution** - Idempotent decorator ensures single execution
5. **Fail-safe retry** - Failed operations can be retried, succeeded operations replay cache

---

## Data Model

```
IdempotencyKey                         Decision
├── scope (string)                     ├── effective_at (datetime)
├── key (string)                       ├── recorded_at (auto)
├── request_hash (string)              ├── actor_user (FK)
├── state (pending→processing→done)    ├── on_behalf_of_user (FK)
├── locked_at (datetime)               ├── authority_context (JSON)
├── expires_at (datetime)              ├── target (GenericFK)
├── error_code/message                 ├── action (string)
├── response_snapshot (JSON)           ├── snapshot (JSON)
└── result (GenericFK)                 ├── outcome (JSON)
                                       └── finalized_at (datetime)

TimeSemanticsMixin (Abstract)          EffectiveDatedMixin (Abstract)
├── effective_at (datetime)            ├── effective_at (inherited)
└── recorded_at (auto_now_add)         ├── recorded_at (inherited)
                                       ├── valid_from (datetime)
                                       └── valid_to (nullable datetime)
```

---

## Public API

### Time Semantics Mixins

```python
from django_decisioning import TimeSemanticsMixin, EffectiveDatedMixin

class ClinicalNote(TimeSemanticsMixin, models.Model):
    """Note with business time vs system time."""
    content = models.TextField()
    # effective_at: when note was written (can backdate)
    # recorded_at: when system saved it (immutable)

class RoleAssignment(EffectiveDatedMixin, models.Model):
    """Assignment with validity window."""
    user = models.ForeignKey(User, ...)
    role = models.ForeignKey(Role, ...)
    # valid_from: when assignment becomes effective
    # valid_to: when assignment expires (null = indefinite)
```

### Idempotent Decorator

```python
from django_decisioning import idempotent

@idempotent(
    scope='basket_commit',
    key_from=lambda basket, user: str(basket.pk)
)
def commit_basket(basket, user):
    """Only executes once per basket, retries return cached result."""
    work_items = create_work_items(basket)
    return work_items
```

### QuerySet Methods

```python
from django_decisioning import EventAsOfQuerySet, EffectiveDatedQuerySet

# Query facts as of a point in time
notes = Note.objects.as_of(some_date)

# Query currently valid records
assignments = Assignment.objects.current()
```

---

## API Parameters

### @idempotent Decorator

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scope` | str | Yes | Operation scope (e.g., 'basket_commit', 'payment') |
| `key_from` | callable | No | Function to derive key from args |
| `timeout` | int | No | Lock timeout in seconds (not yet implemented) |

### IdempotencyKey States

| State | Description |
|-------|-------------|
| `pending` | Key created but not started |
| `processing` | Operation in progress |
| `succeeded` | Completed successfully, response cached |
| `failed` | Failed, can be retried |

---

## Hard Rules

1. **recorded_at is sacred** - Never allow override, always auto_now_add
2. **Idempotency scope+key is unique** - Enforced by database constraint
3. **Succeeded operations replay** - Return cached response, never re-execute
4. **Failed operations allow retry** - Reset state to processing on retry
5. **Processing state has timeout** - Stale locks can be detected (not enforced yet)

---

## Invariants

- `recorded_at <= now()` always (system can't record future facts)
- `effective_at` can be past, present, or future (backdating, current, scheduled)
- For EffectiveDatedMixin: `valid_to > valid_from` when both are set
- IdempotencyKey(scope, key) is globally unique
- Succeeded IdempotencyKey has non-null response_snapshot

---

## Known Gotchas

### 1. Effective vs Recorded Confusion

**Problem:** Using wrong timestamp for queries.

```python
# WRONG - uses recorded_at for business logic
notes.filter(recorded_at__date=today)

# CORRECT - uses effective_at for business logic
notes.filter(effective_at__date=today)
```

### 2. Backdating Doesn't Change recorded_at

**Problem:** Expecting recorded_at to match effective_at on backdate.

```python
note = Note.objects.create(
    effective_at=yesterday,  # Backdated
    content="Late entry"
)
# recorded_at is still NOW, not yesterday
```

**Why:** Audit trail must show when system learned the fact.

### 3. Idempotent Returns Serialized PKs on Retry

**Problem:** Expecting model instances on retry.

```python
@idempotent(scope='commit', key_from=lambda b, u: str(b.pk))
def commit(basket, user):
    return [WorkItem.objects.create(...), ...]

# First call: returns [WorkItem, WorkItem, ...]
# Second call: returns [{'__model__': True, 'pk': 'uuid'}, ...]
```

**Solution:** Query database if you need model instances after retry.

### 4. Idempotency Scope Collisions

**Problem:** Using same scope for different operations.

```python
# WRONG - both use 'process' scope
@idempotent(scope='process', key_from=lambda x: str(x.pk))
def process_order(order): ...

@idempotent(scope='process', key_from=lambda x: str(x.pk))
def process_refund(refund): ...  # May collide if PKs overlap!

# CORRECT - distinct scopes
@idempotent(scope='order_process', key_from=lambda x: str(x.pk))
def process_order(order): ...

@idempotent(scope='refund_process', key_from=lambda x: str(x.pk))
def process_refund(refund): ...
```

### 5. Cleanup Required for IdempotencyKey Table

**Problem:** Table grows unboundedly.

**Solution:** Run cleanup command periodically:

```bash
# Delete keys older than 7 days
python manage.py cleanup_idempotency_keys --days=7

# Dry run first
python manage.py cleanup_idempotency_keys --days=7 --dry-run

# Include stale processing keys (careful!)
python manage.py cleanup_idempotency_keys --days=7 --include-processing
```

---

## Recommended Usage

### 1. Add Time Semantics to Domain Models

```python
from django_decisioning import TimeSemanticsMixin

class ClinicalEvent(TimeSemanticsMixin, models.Model):
    patient = models.ForeignKey(Patient, ...)
    event_type = models.CharField(...)
```

### 2. Protect Commit Operations

```python
from django_decisioning import idempotent

@idempotent(
    scope='invoice_finalize',
    key_from=lambda invoice, user: str(invoice.pk)
)
def finalize_invoice(invoice, user):
    # This runs at most once per invoice
    ledger_entry = create_ledger_entry(invoice)
    invoice.status = 'finalized'
    invoice.save()
    return ledger_entry
```

### 3. Query Historical State

```python
# What assignments were valid on Jan 1?
jan1 = datetime(2024, 1, 1, tzinfo=UTC)
assignments = UserRole.objects.as_of(jan1)

# What's currently valid?
current = UserRole.objects.current()
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (optional, for BaseModel features)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- TimeSemanticsMixin, EffectiveDatedMixin
- IdempotencyKey model with state machine
- @idempotent decorator
- Decision model for audit trail
- cleanup_idempotency_keys management command
