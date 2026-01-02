# Chapter 7: Catalog

> "Before you can sell it, you have to know what it is."
>
> — Retail wisdom

---

The 1888 Sears, Roebuck and Company catalog was 322 pages. By 1908, it had grown to over 1,000 pages and weighed four pounds. It was called "the wish book" because rural Americans would page through it dreaming of what they might order.

Every item in that catalog had a number, a description, a price, and an availability status. You could order item #31C457 and know exactly what you'd receive: a men's worsted wool suit, black, sizes 34-46, $12.50, ships in 6-8 weeks.

This was not accidental. Sears understood that commerce requires a shared vocabulary between buyer and seller. The catalog defines what can be bought. Without it, every transaction becomes a negotiation.

## The Primitive

**Catalog** answers: What things exist in this system that can be ordered, scheduled, or tracked?

This is distinct from inventory (how many do we have?), pricing (what does it cost?), and workflow (what happens after ordering?). The catalog is pure definition: a list of things that exist as abstract concepts, independent of any particular transaction.

A veterinary clinic's catalog includes wellness exams, blood panels, vaccinations, and nail trims. A pizzeria's catalog includes large pepperoni, medium cheese, and garlic bread. A subscription service's catalog includes monthly plans, annual plans, and add-on features.

The catalog doesn't know who's ordering. It doesn't know when. It doesn't know how many are in stock. It just knows what things are available to be ordered.

## Separation of Definition from Instance

The first principle of catalog design: definitions are not instances.

A "Large Pepperoni Pizza" in the catalog is not the same as the Large Pepperoni Pizza that customer #4523 ordered on March 15th at 7:42 PM. The catalog item is a template. The order line is an instance.

This separation matters for several reasons:

**Prices change.** A pizza that cost $18.99 when the catalog was printed might cost $19.99 now. But the order from March 15th should still show $18.99—that's what the customer agreed to pay. If your catalog item and order line are the same record, you can't preserve this history.

**Items are retired.** A clinic discontinues a particular vaccine. The catalog item is marked inactive. But historical records that reference that vaccine must remain valid. The patient's chart should still show they received it.

**Availability varies.** A consulting firm offers a "Strategic Planning Workshop." It's in the catalog permanently, but it might only be available in Q3 and Q4. The catalog defines the service; availability is a separate concern.

**Configurations differ.** A "Large Pizza" is a catalog item. "Large Pizza with half pepperoni, half mushroom, extra cheese, light sauce" is an instance with specific configuration. The catalog defines what's configurable; the instance captures the choices.

```python
class CatalogItem(UUIDModel, BaseModel):
    # Who offers this item
    owner_content_type = models.ForeignKey(ContentType, on_delete=CASCADE)
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    # What is it
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True)  # SKU, item code
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)

    # Pricing (reference, not the frozen price)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')

    # Availability
    is_available = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_to = models.DateTimeField(null=True, blank=True)

    # Flexible metadata
    metadata = models.JSONField(default=dict)
```

Notice the GenericForeignKey for owner. A catalog item might be offered by a restaurant, a clinic, a vendor, or a department. The catalog primitive doesn't assume any particular party type.

## The Basket: Transactions in Progress

Between browsing the catalog and completing a purchase lies a transitional state: items collected but not yet committed. This is the basket (also called cart, order, or draft).

The basket is not a mere UI convenience. It's a critical state in the transaction lifecycle:

**Draft state.** Items can be added, removed, or modified. Quantities can change. The basket is mutable.

**Committed state.** The customer confirms their intent. The basket becomes immutable. Prices are frozen. Work is spawned. This is the point of no return.

**Cancelled state.** The customer abandons the basket. No work is spawned. The basket might be retained for analytics but has no operational significance.

```python
class BasketStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    COMMITTED = 'committed', 'Committed'
    CANCELLED = 'cancelled', 'Cancelled'


class Basket(UUIDModel, BaseModel):
    # What this basket is for
    context_content_type = models.ForeignKey(ContentType, null=True, blank=True)
    context_id = models.CharField(max_length=255, blank=True)
    context = GenericForeignKey('context_content_type', 'context_id')

    # Status
    status = models.CharField(max_length=20, choices=BasketStatus.choices, default=BasketStatus.DRAFT)

    # Decision surface
    committed_at = models.DateTimeField(null=True, blank=True)
    committed_by = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)

    # Idempotency
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
```

The idempotency_key is critical. When a customer double-clicks the "Place Order" button, you need to ensure only one order is created. The idempotency key—typically derived from the session or form submission—ensures that duplicate requests return the existing basket rather than creating new ones.

## The Snapshot Principle

When an item is added to a basket, the price at that moment is captured:

```python
class BasketItem(UUIDModel, BaseModel):
    basket = models.ForeignKey(Basket, on_delete=CASCADE, related_name='items')
    catalog_item = models.ForeignKey(CatalogItem, on_delete=PROTECT)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    # Price snapshot - frozen at add time
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')

    # Configuration and notes
    instructions = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
```

The `unit_price` here is a snapshot, not a reference. When the catalog price changes, existing basket items retain their original price. When the basket is committed, the price is locked forever.

This solves several problems:

- **Price disputes:** "I added it when it was $15!" Yes, and we have the snapshot to prove it.
- **Promotional pricing:** Flash sales affect items added during the sale, not before or after.
- **Multi-day transactions:** Enterprise orders that take weeks to finalize maintain consistent pricing throughout.

The `metadata` field captures configuration that the catalog doesn't know about. A pizza basket item might include `{"half_toppings": ["pepperoni", "mushroom"], "extra_cheese": true}`. This configuration is instance-specific.

## Work Spawning

When a basket is committed, work begins. This is where the catalog connects to the workflow primitive.

A pizza order spawns work for the kitchen. A lab test order spawns work for the phlebotomist. A subscription order spawns work for the provisioning system.

```python
class WorkItem(UUIDModel, BaseModel):
    basket_item = models.ForeignKey(BasketItem, on_delete=CASCADE, related_name='work_items')

    work_type = models.CharField(max_length=100)
    spawn_role = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=WorkItemStatus.choices, default='pending')

    assigned_to = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    priority = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['basket_item', 'spawn_role'],
                name='unique_basket_item_spawn_role'
            )
        ]
```

The unique constraint on `(basket_item, spawn_role)` is crucial. If the commit operation is retried (due to network failure, user double-click, or system restart), it must not create duplicate work items. The constraint enforces idempotency at the database level.

The commit operation itself is wrapped in a transaction:

```python
@transaction.atomic
def commit_basket(basket, committed_by, work_types=None):
    basket.refresh_from_db()  # Get latest state

    if basket.is_committed:
        return basket  # Already committed, return as-is (idempotent)

    if basket.total_items == 0:
        raise BasketEmptyError(basket.pk)

    basket.status = BasketStatus.COMMITTED
    basket.committed_at = timezone.now()
    basket.committed_by = committed_by
    basket.save()

    # Spawn work items
    if work_types:
        for item in basket.items.all():
            for work_type in work_types:
                WorkItem.objects.get_or_create(
                    basket_item=item,
                    spawn_role=work_type,
                    defaults={'work_type': work_type, 'status': 'pending'}
                )

    return basket
```

The `get_or_create` call, combined with the unique constraint, ensures that calling `commit_basket` twice produces identical results. This is the idempotency pattern at work.

## Dispensing and Fulfillment

Some basket items represent physical goods that must be dispensed. Medications, supplies, products—things that are counted and tracked.

```python
class DispenseLog(UUIDModel, BaseModel):
    basket_item = models.ForeignKey(BasketItem, on_delete=CASCADE, related_name='dispense_logs')

    quantity_dispensed = models.DecimalField(max_digits=10, decimal_places=2)

    dispensed_by = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)
    dispensed_at = models.DateTimeField(default=timezone.now)

    # Lot tracking
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
```

The DispenseLog is append-only. Each dispensing event creates a new record. You can query total dispensed by summing the logs:

```python
total_dispensed = basket_item.dispense_logs.aggregate(
    total=Sum('quantity_dispensed')
)['total'] or 0
```

This pattern handles partial dispensing (10 tablets ordered, 5 dispensed today, 5 tomorrow), overfilling (customer got 12 instead of 10, logged for accuracy), and lot tracking (FDA requires knowing which lot number was dispensed to which patient).

## Package Structure

The catalog primitive, like all django-primitives packages, follows a consistent structure. This is not just organization—it's a contract that enables reproducibility.

```
packages/django-catalog/
├── pyproject.toml           # Package metadata and dependencies
├── README.md                # Usage documentation
├── src/
│   └── django_catalog/
│       ├── __init__.py      # Exports public API
│       ├── apps.py          # Django app configuration
│       ├── models.py        # CatalogItem, Basket, BasketItem, WorkItem, DispenseLog
│       ├── services.py      # create_basket, add_item, commit_basket, cancel_basket
│       ├── exceptions.py    # BasketAlreadyCommittedError, BasketEmptyError, etc.
│       └── migrations/
│           └── 0001_initial.py
└── tests/
    ├── conftest.py          # Pytest fixtures
    ├── settings.py          # Test Django settings
    ├── models.py            # Test models (Organization, etc.)
    ├── test_models.py       # Model tests
    └── test_services.py     # Service function tests
```

This structure is replicated across all 18 packages. When you understand one, you understand them all.

## Hands-On: Building a Catalog with AI

### Exercise 1: Unconstrained Catalog

Ask an AI:

```
Build a Django e-commerce system with products and shopping cart.
Include add to cart and checkout functionality.
```

Examine the result. Typically:

- Products and cart items are tightly coupled
- No snapshot of price at add time
- Checkout modifies the cart instead of committing it
- No idempotency protection
- No work spawning concept
- All business logic in views

This works for a tutorial but fails in production.

### Exercise 2: Constrained Catalog

Now ask with explicit constraints:

```
Build a Django catalog and basket system using these constraints:

1. CatalogItem model with GenericFK owner
   - name, code, description, category
   - unit_price as DecimalField, currency as CharField(3)
   - is_available, available_from, available_to
   - metadata as JSONField

2. Basket model with status workflow
   - status: draft → committed OR cancelled
   - committed_at, committed_by for decision surface
   - idempotency_key (unique, nullable) for duplicate prevention
   - context via GenericFK (what this basket is for)

3. BasketItem model with price snapshot
   - FK to Basket and CatalogItem
   - unit_price captured AT ADD TIME (snapshot, not reference)
   - quantity as DecimalField
   - instructions and metadata for configuration

4. WorkItem model with unique constraint
   - FK to BasketItem
   - work_type, spawn_role
   - status: pending → in_progress → completed
   - UniqueConstraint on (basket_item, spawn_role) for idempotency

5. Service functions:
   - create_basket(context, idempotency_key) - idempotent creation
   - add_item(basket, catalog_item, quantity) - snapshots price
   - commit_basket(basket, committed_by, work_types) - atomic, idempotent
   - cancel_basket(basket) - only works on draft

6. Exceptions:
   - BasketAlreadyCommittedError - raised on modification after commit
   - BasketEmptyError - raised on commit with no items
   - ItemNotAvailableError - raised when adding unavailable item

Write tests first using TDD. Minimum 50 tests covering models and services.
```

The constraints force correct implementation of snapshots, idempotency, and work spawning.

### Exercise 3: Clinic Order Flow

Test the pattern with a real-world scenario:

```
Using the catalog primitives, implement a veterinary clinic order flow:

Scenario: A patient (pet) visits for a wellness exam. The vet orders:
- 1x Wellness Exam ($75)
- 1x Rabies Vaccine ($25)
- 1x Heartworm Test ($45)

Implement:
1. Create catalog items for the clinic (owner = clinic organization)
2. Create a basket for the patient visit (context = encounter)
3. Add items to basket with price snapshots
4. Commit basket, spawning work items for:
   - "perform" role (vet performs exam/procedures)
   - "dispense" role (tech dispenses vaccine)
   - "lab" role (lab processes heartworm test)

Write tests verifying:
- Catalog items are created with correct owner
- Basket items snapshot prices at add time
- Commit creates exactly 3 work items per basket item (9 total)
- Calling commit twice returns same basket (idempotent)
- Work items have correct roles and statuses
- Total basket value is calculated correctly
```

This exercise integrates the catalog with identity (parties), time (timestamps), and workflow (work items).

## The Prompt Contract for Catalog

Include these constraints when working with catalog-related code:

```markdown
## Catalog Primitive Constraints

### Must Do
- CatalogItem has GenericFK owner (not hardcoded to User/Organization)
- BasketItem snapshots unit_price at add time (not reference to catalog)
- Basket has status workflow: draft → committed OR cancelled
- commit_basket is atomic and idempotent
- WorkItem has UniqueConstraint on (basket_item, spawn_role)
- All prices use DecimalField, never Float

### Must Not
- Never modify committed baskets (raise BasketAlreadyCommittedError)
- Never delete basket items (cancel basket instead)
- Never reference catalog price after adding to basket
- Never spawn duplicate work items (use get_or_create with unique constraint)
- Never put workflow logic in CatalogItem model

### Invariants
- CatalogItem defines what can be ordered (template)
- BasketItem is what was actually ordered (instance)
- Prices are frozen at BasketItem creation (snapshot)
- Basket commit is irreversible (append-only history)
- Work items exist only for committed baskets
```

## What AI Gets Wrong

Without explicit constraints, AI-generated catalog code typically:

1. **References live prices** — The cart links to products and reads current_price. Price changes affect old carts.

2. **Uses mutable checkout** — The "checkout" button updates a status field. The cart can be modified after checkout in some edge cases.

3. **Ignores idempotency** — Double-clicking "Place Order" creates duplicate orders.

4. **Hard-codes party types** — Products belong to "the store" implicitly. No support for multi-vendor scenarios.

5. **Mixes definition and instance** — Product variants are separate products instead of configuration on basket items.

6. **Lacks work spawning** — Order completion doesn't trigger any backend processes. Fulfillment is a separate, disconnected system.

The fix is explicit constraints. Define the pattern, and the AI follows it.

## Why This Matters Later

The catalog primitive is the transaction engine:

- **Ledger**: Every basket commit should create ledger entries—revenue recognition when services are rendered.

- **Agreements**: Special pricing agreements (discounts, contract rates) affect how prices are computed and snapshotted.

- **Workflows**: Work items spawned from baskets drive the encounter state machine.

- **Audit**: Every basket commit is a decision that should be logged with full context.

Get the catalog wrong, and transactions become chaotic. Get it right, and you have a solid foundation for any system where things are ordered, scheduled, or fulfilled.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-catalog | `docs/prompts/django-catalog.md` | ~60 tests |

### Using the Prompt

```bash
cat docs/prompts/django-catalog.md | claude

# Request: "Start with CatalogItem and Category models,
# then implement Basket with commit() for price locking."
```

### Key Constraints

- **Price snapshots on BasketItem**: `unit_price_snapshot` captures price at add-time
- **Basket.commit() locks everything**: Committed baskets are immutable
- **Work spawning**: Committed baskets can spawn work items
- **Idempotent operations**: Add-to-cart handles duplicates gracefully

If Claude stores prices only on CatalogItem without snapshotting to BasketItem, that's a constraint violation.

---

## Sources and References

1. **Sears Catalog History** — "Sears, Roebuck & Co. Catalogs," National Museum of American History, Smithsonian Institution. The 1908 "big book" exceeded 1,000 pages.

2. **Idempotency in Distributed Systems** — Helland, Pat. "Idempotence Is Not a Medical Condition," *ACM Queue*, April 2012. Foundational paper on idempotent operations.

3. **ACID Properties** — Haerder, T. and Reuter, A. "Principles of Transaction-Oriented Database Recovery," *ACM Computing Surveys*, December 1983. The atomicity guarantee underlying commit_basket.

4. **FDA Lot Tracking Requirements** — 21 CFR Part 820.65 requires traceability of components and products. DispenseLog implements this pattern for regulated products.

---

*Status: Complete*
