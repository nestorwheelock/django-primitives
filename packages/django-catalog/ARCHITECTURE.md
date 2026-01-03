# Architecture: django-catalog

**Status:** Stable / v0.1.0

Order catalog with basket-to-workitem workflow for encounter-based systems.

---

## What This Package Is For

Answering the question: **"What was ordered, and where does it go?"**

Use cases:
- Defining orderable items (stock items, services)
- Collecting orders in encounter-scoped baskets
- Transforming basket items into routed work items on commit
- Deterministic board routing (Pharmacy, Lab, Treatment, etc.)
- Pharmacy dispensing record keeping

---

## What This Package Is NOT For

- **Not inventory management** - Use separate inventory package for stock levels
- **Not pricing/billing** - Use django-ledger for financial transactions
- **Not scheduling** - Work items track work, not appointment slots
- **Not prescription management** - Links to prescriptions but doesn't manage them

---

## Design Principles

1. **Definition layer only** - CatalogItem defines what's orderable, not execution
2. **Basket is editable until committed** - One active draft basket per encounter
3. **WorkItems spawn only on commit** - No implicit spawns from other actions
4. **Idempotent commit** - Protected by @idempotent decorator, safe to retry
5. **Snapshot on commit** - CatalogItem identity captured at commit time
6. **Deterministic routing** - Target board derived from item kind and action

---

## Data Model

```
CatalogItem                            Basket
├── id (UUID)                          ├── id (UUID)
├── kind (stock_item|service)          ├── encounter (FK)
├── service_category (lab|imaging|...) ├── status (draft|committed|cancelled)
├── default_stock_action (dispense|administer) ├── created_by (FK → User)
├── display_name                       ├── committed_by (FK → User)
├── display_name_es                    ├── committed_at
├── is_billable                        ├── effective_at (time semantics)
├── active                             └── recorded_at (time semantics)
└── inventory_item (optional FK)
                                       One active draft basket per encounter (constraint)

BasketItem                             WorkItem
├── id (UUID)                          ├── id (UUID)
├── basket (FK)                        ├── basket_item (FK)
├── catalog_item (FK)                  ├── encounter (FK)
├── quantity                           ├── spawn_role (idempotency key)
├── stock_action_override              ├── target_board (pharmacy|lab|treatment|...)
├── display_name_snapshot              ├── target_lane (optional)
├── kind_snapshot                      ├── display_name (snapshot)
├── notes                              ├── kind (snapshot)
└── added_by (FK → User)               ├── quantity
                                       ├── notes
                                       ├── status (pending|in_progress|blocked|completed|cancelled)
                                       ├── status_detail
                                       ├── assigned_to (FK → User)
                                       ├── priority (0-100, lower = higher)
                                       ├── started_at
                                       ├── completed_at
                                       ├── completed_by
                                       ├── effective_at (time semantics)
                                       └── recorded_at (time semantics)

DispenseLog                            CatalogSettings (Singleton)
├── id (UUID)                          ├── default_currency
├── workitem (OneToOne)                ├── allow_inactive_items
├── display_name                       └── metadata (JSON)
├── quantity
├── dispensed_by (FK → User)
├── dispensed_at
├── notes
└── prescription (optional FK)
```

---

## Routing Rules

```
CatalogItem Kind    | Action/Category   | Target Board
--------------------|-------------------|-------------
stock_item          | dispense          | pharmacy
stock_item          | administer        | treatment
service             | lab               | lab
service             | imaging           | imaging
service             | procedure         | treatment
service             | consult           | treatment
service             | vaccine           | treatment
service             | other             | treatment
```

---

## Public API

### Service Functions

```python
from django_catalog.services import (
    get_or_create_draft_basket,
    add_item_to_basket,
    commit_basket,
    cancel_basket,
    update_work_item_status,
)

# Get or create draft basket for encounter
basket = get_or_create_draft_basket(encounter, user)

# Add items to basket
basket_item = add_item_to_basket(
    basket=basket,
    catalog_item=aspirin,
    user=doctor,
    quantity=2,
    notes="Take with food",
    stock_action_override='dispense',  # Optional override
)

# Commit basket (idempotent - safe to retry)
work_items = commit_basket(basket, user)

# Update work item status
update_work_item_status(
    work_item=work_item,
    new_status='completed',
    user=pharmacist,
    status_detail='dispensed',
)
```

### Direct Model Usage

```python
from django_catalog.models import CatalogItem, Basket, WorkItem

# Query active catalog items
items = CatalogItem.objects.filter(active=True, kind='stock_item')

# Query work items by board
pharmacy_items = WorkItem.objects.filter(
    target_board='pharmacy',
    status='pending',
)

# Query with time semantics
items_as_of = WorkItem.objects.as_of(some_date)
```

---

## Workflow

```
┌──────────────┐    ┌───────────────┐    ┌─────────────┐
│ CatalogItem  │───→│  BasketItem   │───→│  WorkItem   │
│ (definition) │    │ (pre-commit)  │    │ (execution) │
└──────────────┘    └───────────────┘    └─────────────┘
                           │
                           │ commit_basket()
                           ▼
                    ┌───────────────┐
                    │ @idempotent   │
                    │ - snapshot    │
                    │ - route       │
                    │ - spawn       │
                    └───────────────┘
```

---

## Hard Rules

1. **One active basket per encounter** - Enforced by unique constraint on (encounter, status='draft', deleted_at IS NULL)
2. **Basket immutable after commit** - is_editable returns False for committed/cancelled
3. **WorkItems only spawn on commit** - No creation from SOAP notes, vitals, or documentation
4. **Spawning is idempotent** - Unique constraint on (basket_item, spawn_role)
5. **Commit is idempotent** - @idempotent decorator prevents double execution
6. **Snapshots are immutable** - display_name_snapshot captured at commit, never updated

---

## Invariants

- Active CatalogItem has unique display_name (within active items)
- Basket in 'draft' status: is_editable = True
- Basket in 'committed' or 'cancelled' status: is_editable = False
- Only one Basket per encounter can be 'draft' at any time
- WorkItem.target_board is derived deterministically from CatalogItem at spawn time
- WorkItem(basket_item, spawn_role) is globally unique
- BasketItem.display_name_snapshot is non-empty after commit

---

## Known Gotchas

### 1. Commit Returns Different Types on Retry

**Problem:** First call returns WorkItem objects, retry returns serialized PKs.

```python
# First call
result = commit_basket(basket, user)
# result = [WorkItem, WorkItem, ...]

# Retry (cache hit)
result = commit_basket(basket, user)
# result = [{'__model__': True, 'pk': 'uuid'}, ...]
```

**Solution:** Query database if you need model instances:

```python
work_items = WorkItem.objects.filter(basket_item__basket=basket)
```

### 2. Adding Items to Committed Basket

**Problem:** Attempting to add items after commit.

```python
basket.status = 'committed'
basket.save()

add_item_to_basket(basket, item, user)
# Raises: ValueError("Cannot add items to a committed or cancelled basket")
```

**Solution:** Create a new basket for additional orders.

### 3. Inactive Items Block Addition

**Problem:** Trying to add inactive catalog items.

```python
item.active = False
item.save()

add_item_to_basket(basket, item, user)
# Raises: ValueError("Cannot add inactive catalog items to basket")
```

**Solution:** Either activate the item or enable `allow_inactive_items` in CatalogSettings.

### 4. Stock Action Override Not Persisting

**Problem:** Override not being used for routing.

```python
# Override must be passed at add time, not after
basket_item = add_item_to_basket(
    basket=basket,
    catalog_item=item,
    user=user,
    stock_action_override='administer',  # Must be here
)
```

### 5. Unique Constraint on Active Basket

**Problem:** Creating second draft basket for same encounter.

```python
basket1 = Basket.objects.create(encounter=enc, status='draft', created_by=user)
basket2 = Basket.objects.create(encounter=enc, status='draft', created_by=user)
# IntegrityError: unique_active_basket_per_encounter
```

**Solution:** Use `get_or_create_draft_basket()` which handles this.

---

## Recommended Usage

### 1. Use Service Functions

```python
# RECOMMENDED - uses proper validation and idempotency
from django_catalog.services import commit_basket

work_items = commit_basket(basket, user)

# AVOID - bypasses validation
basket.status = 'committed'
basket.save()  # No work items created!
```

### 2. Handle Commit Return Value

```python
def commit_and_get_items(basket, user):
    """Commit basket and always return fresh WorkItem queryset."""
    commit_basket(basket, user)  # Idempotent
    return WorkItem.objects.filter(basket_item__basket=basket)
```

### 3. Board-Specific Workflows

```python
# Pharmacy board workflow
def dispense_item(work_item, pharmacist):
    """Mark pharmacy work item as dispensed."""
    from django_catalog.models import DispenseLog

    DispenseLog.objects.create(
        workitem=work_item,
        display_name=work_item.display_name,
        quantity=work_item.quantity,
        dispensed_by=pharmacist,
        dispensed_at=timezone.now(),
    )

    update_work_item_status(
        work_item=work_item,
        new_status='completed',
        user=pharmacist,
        status_detail='dispensed',
    )
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)
- django-decisioning (for time semantics and @idempotent)
- django-singleton (for CatalogSettings)
- django-encounters (for ENCOUNTER_MODEL configuration)

---

## Configuration

```python
# settings.py
DJANGO_CATALOG_ENCOUNTER_MODEL = 'django_encounters.Encounter'
DJANGO_CATALOG_INVENTORY_ITEM_MODEL = 'inventory.InventoryItem'  # Optional
DJANGO_CATALOG_PRESCRIPTION_MODEL = 'prescriptions.Prescription'  # Optional
```

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- CatalogItem with kind-based routing
- Basket with one-active-per-encounter constraint
- BasketItem with snapshot on commit
- WorkItem with deterministic board routing
- DispenseLog for pharmacy records
- CatalogSettings singleton
- Full service layer with idempotent commit
