# Django + Postgres Operational Rules

**Status:** Active
**Last Updated:** 2026-01-01

---

## Overview

This document defines the operational rules for using Django with PostgreSQL in the django-primitives framework. These rules prevent common pitfalls that cause data integrity issues, performance problems, or debugging nightmares.

---

## UUID Strategy

### Decision: Stay with UUIDv4

**We use `uuid.uuid4` for all primary keys. No migration to UUIDv7/ULID.**

**Rationale:**
- Codebase **never orders by UUID** - always by `created_at`, priority, or name
- Index fragmentation only matters if ordering by UUID (we don't)
- UUIDv4 is stdlib - no dependencies, no custom code
- True randomness = security benefit (can't guess IDs, no timing leaks)
- Real performance killers are elsewhere (N+1, missing indexes, bloat)

### Rules

```python
# CORRECT: Order by timestamp
class Meta:
    ordering = ['-created_at']

# WRONG: Never order by UUID
class Meta:
    ordering = ['id']  # Meaningless and expensive
```

### Human-Readable IDs

Use django-sequence for human-facing identifiers:
- Invoices: `INV-2026-000123`
- Orders: `ORD-2026-000456`
- Tickets: `TKT-2026-000789`

UUIDs are for machines. Humans get sequences.

### GenericFK Object IDs

**Rule:** Always use `CharField(max_length=255)` for GenericFK object IDs.

```python
# CORRECT: CharField supports UUIDs
target_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
target_id = models.CharField(max_length=255)  # String for UUID support
target = GenericForeignKey('target_type', 'target_id')

# WRONG: PositiveIntegerField breaks in UUID-first codebase
target_id = models.PositiveIntegerField()  # Can't store UUIDs!
```

This is a UUID-first framework. Integer assumptions will bite you.

---

## Timezone Handling

### The "Today" Problem

"Today" is ambiguous without timezone context. A transaction at 11:00 PM PST is "tomorrow" in UTC.

### Rules

1. **Store UTC always** - `DateTimeField` with `USE_TZ=True`

2. **Separate business date from instant** when needed:
```python
# Instant (when it happened in absolute time)
created_at = models.DateTimeField(auto_now_add=True)

# Business date (what day the business considers this)
service_date = models.DateField()  # Local date, no timezone
```

3. **Display conversion at presentation layer** - never store local time

4. **Reporting queries must be timezone-aware** - group by local date, not UTC date

### Anti-Patterns

```python
# WRONG: "today" without timezone context
MyModel.objects.filter(created_at__date=date.today())

# CORRECT: Explicit timezone
from django.utils import timezone
local_now = timezone.localtime()
MyModel.objects.filter(created_at__date=local_now.date())
```

```python
# WRONG: Storing local time
created_at = timezone.now().astimezone(local_tz)  # Don't do this

# CORRECT: Store UTC, convert on display
created_at = timezone.now()  # UTC
display_time = created_at.astimezone(user_timezone)  # Convert for display
```

---

## Transaction Boundaries

### Rule: Every Decision Surface Must Be Atomic

Any "commit / post / transition" action must be inside `transaction.atomic()`.

```python
from django.db import transaction

@transaction.atomic
def commit_basket(basket, user):
    """Transform BasketItems into WorkItems on basket commit."""
    work_items = []
    for basket_item in basket.items.all():
        snapshot_basket_item(basket_item)
        work_item = spawn_work_item(basket_item)
        work_items.append(work_item)

    basket.status = 'committed'
    basket.save()
    return work_items
```

### Why This Matters

Half-committed state is unacceptable:
- A basket commit that creates 3 of 5 work items is worse than a failure
- A transition that updates state but doesn't log is an audit gap
- A payment that debits but doesn't credit is a financial nightmare

### Current Compliance

| Service | Has @transaction.atomic | Status |
|---------|------------------------|--------|
| `commit_basket()` | Yes | Compliant |
| `transition()` | Yes | Compliant |
| `start_session()` | Yes | Compliant |
| `stop_session()` | Yes | Compliant |

---

## N+1 Query Prevention

### Rules

1. **Always use `select_related()` for FK traversal**
2. **Always use `prefetch_related()` for M2M/reverse FK**
3. **Add query-count assertions in tests for list views**

### Examples

```python
# WRONG: N+1 on FK
for basket_item in basket.items.all():
    print(basket_item.catalog_item.display_name)  # Query per item!

# CORRECT: Select related
for basket_item in basket.items.select_related('catalog_item').all():
    print(basket_item.catalog_item.display_name)  # Single query
```

```python
# WRONG: N+1 on reverse FK
for basket in Basket.objects.all():
    print(len(basket.items.all()))  # Query per basket!

# CORRECT: Prefetch related
for basket in Basket.objects.prefetch_related('items').all():
    print(len(basket.items.all()))  # Single query
```

### Test Pattern

```python
def test_list_view_query_count(self):
    """Ensure list view doesn't N+1."""
    # Setup: Create 10 items
    for _ in range(10):
        create_test_item()

    with self.assertNumQueries(3):  # Explicit count
        response = self.client.get('/api/items/')

    self.assertEqual(response.status_code, 200)
    self.assertEqual(len(response.json()), 10)
```

---

## Signal Avoidance

### Rule: Prefer Explicit Service Functions

Signals feel clean until you need to reason about side effects.

### Allowed Signal Uses

- Cache invalidation (non-critical)
- Denormalization updates (with idempotency)
- Audit logging (append-only, never fails)

### Forbidden Signal Uses

- Spawning work items
- Sending notifications
- Modifying related records
- Anything with business logic

### Why

```python
# With signals: "Why did X happen?"
# Answer: Archaeology through signal handlers, middleware, apps.py

# With explicit services: "Why did X happen?"
# Answer: Read the service function
```

### Example

```python
# WRONG: Business logic in signal
@receiver(post_save, sender=Basket)
def on_basket_save(sender, instance, **kwargs):
    if instance.status == 'committed':
        spawn_work_items(instance)  # Hidden side effect!

# CORRECT: Explicit service
def commit_basket(basket, user):
    """Commit basket and spawn work items."""
    basket.status = 'committed'
    basket.save()
    return spawn_work_items(basket)  # Explicit, visible
```

---

## GenericFK Usage Guidelines

### Rule: GenericFK Only for Cross-Cutting Concerns

`GenericForeignKey` has no database constraints, is harder to query, and creates orphan risks.

### Allowed Uses

| Use Case | Example | Rationale |
|----------|---------|-----------|
| Audit logs | `AuditLog.target` | Attaches to any model |
| Notes/comments | `Note.target` | Universal attachment |
| Documents | `Document.target` | Universal attachment |
| Work sessions | `WorkSession.context` | Context can be any model |
| Decisions | `Decision.target` | Records decision about any model |

### Forbidden Uses

- Core domain relationships (use explicit FK)
- Anything queried in hot paths
- Anything requiring FK constraints

### Current Compliance

| Package | Model | Use | Status |
|---------|-------|-----|--------|
| django-encounters | Encounter.subject | Cross-cutting | Compliant |
| django-worklog | WorkSession.context | Cross-cutting | Compliant |
| django-audit-log | AuditLog.target | Cross-cutting | Compliant |

---

## JSONField Discipline

### Rule: JSONField is for Metadata, Not Query Surfaces

### Allowed Uses

- Immutable snapshots (audit, decisions)
- Configuration blobs (CatalogSettings.metadata)
- Schema-stable structured data (EncounterDefinition.states)

### Hot-Path Query Requirement

If querying JSON in hot paths, add GIN index:

```python
class MyModel(models.Model):
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(
                name='mymodel_metadata_gin',
                fields=['metadata'],
                opclasses=['jsonb_path_ops']
            )
        ]
```

### Anti-Patterns

```python
# WRONG: Using JSON as primary query surface
Product.objects.filter(metadata__category='electronics')  # No index = slow

# CORRECT: Promote to real field if querying frequently
class Product(models.Model):
    category = models.CharField(max_length=100, db_index=True)  # Real field
    metadata = models.JSONField(default=dict)  # For truly optional data
```

---

## Postgres Migration Safety

### Adding Columns

```python
# SAFE: Nullable column (instant, no rewrite)
field = models.CharField(max_length=100, null=True)

# DANGEROUS: Non-null with default on big table (rewrites entire table)
field = models.CharField(max_length=100, default='x')
```

**For non-null columns on large tables:**
1. Add as nullable
2. Backfill data
3. Add NOT NULL constraint

### Adding Indexes

```python
# DANGEROUS: Standard AddIndex locks the table
migrations.AddIndex(
    model_name='mymodel',
    index=models.Index(fields=['created_at']),
)

# SAFE: Use CONCURRENTLY (doesn't lock)
migrations.RunSQL(
    "CREATE INDEX CONCURRENTLY mymodel_created_at_idx ON mymodel (created_at);",
    reverse_sql="DROP INDEX CONCURRENTLY mymodel_created_at_idx;"
)
```

### Renaming/Removing Columns

Three-step deployment:
1. Deploy code that handles both old and new column names
2. Run migration to rename/remove
3. Deploy code that only uses new column name

---

## Connection Pooling

### Rule: Use PgBouncer in Production

Django workers × connections = connection exhaustion at scale.

### Configuration

```python
# Django settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'pgbouncer-host',
        'PORT': 6432,
        'CONN_MAX_AGE': 0,  # Let PgBouncer handle pooling
    }
}
```

### PgBouncer Mode

Use **transaction pooling** for Django:
```ini
[pgbouncer]
pool_mode = transaction
```

---

## Locking for Allocations

### Rule: SELECT FOR UPDATE for Any "Allocate" Operation

Any operation that reserves/allocates a scarce resource needs locking.

### Examples

```python
# Sequence number generation
with transaction.atomic():
    seq = Sequence.objects.select_for_update().get(scope=scope, org=org)
    seq.current_value += 1
    seq.save()
    return seq.formatted_value

# Inventory reservation
with transaction.atomic():
    item = InventoryItem.objects.select_for_update().get(sku=sku)
    if item.available_quantity < requested:
        raise InsufficientInventory()
    item.available_quantity -= requested
    item.save()
    return create_reservation(item, requested)

# Slot assignment
with transaction.atomic():
    slot = TimeSlot.objects.select_for_update().get(id=slot_id)
    if slot.is_booked:
        raise SlotAlreadyBooked()
    slot.is_booked = True
    slot.booked_by = user
    slot.save()
```

### Without Locking

```python
# WRONG: Race condition
seq = Sequence.objects.get(scope=scope)
seq.current_value += 1  # Two requests read same value
seq.save()  # Both save current_value + 1, one number skipped
```

---

## Autovacuum Awareness

### Rule: Monitor Bloat on Write-Heavy Tables

PostgreSQL's MVCC means updates/deletes leave dead tuples. Autovacuum cleans them, but may need tuning.

### High-Write Tables in This Framework

| Table | Write Pattern | Risk |
|-------|---------------|------|
| AuditLog | Append-only, grows forever | Bloat from sheer size |
| WorkItem | Many status updates | Bloat from updates |
| IdempotencyKey | High churn with expiration | Bloat from deletes |

### Mitigation Strategies

**For AuditLog:**
- Consider table partitioning by month
- Archive old partitions to cold storage

**For WorkItem:**
- Tune autovacuum for more frequent runs
- Monitor bloat with `pgstattuple` extension

**For IdempotencyKey:**
- Regular cleanup job for expired keys
- Consider shorter expiration windows

### Monitoring Query

```sql
-- Check table bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size,
    n_dead_tup,
    n_live_tup,
    round(n_dead_tup * 100.0 / nullif(n_live_tup, 0), 2) as dead_pct
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY n_dead_tup DESC
LIMIT 10;
```

---

## Quick Reference Checklist

Before deploying any feature:

- [ ] UUID PKs (never order by UUID)
- [ ] Timestamps in UTC, convert on display
- [ ] Decision surfaces wrapped in `@transaction.atomic`
- [ ] `select_related()` for FK traversals
- [ ] `prefetch_related()` for reverse FK / M2M
- [ ] Query count assertions in tests
- [ ] No business logic in signals
- [ ] GenericFK only for cross-cutting concerns
- [ ] JSONField for metadata only
- [ ] Migrations use CONCURRENTLY for indexes
- [ ] `select_for_update()` for allocation operations
