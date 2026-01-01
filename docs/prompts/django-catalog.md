# Prompt: Rebuild django-catalog

## Instruction

Create a Django package called `django-catalog` that provides order catalog primitives with basket workflow and work item tracking.

## Package Purpose

Provide order/basket management primitives:
- `CatalogItem` - Items available for ordering with GenericFK owner
- `Basket` - Collection of items with commit workflow
- `BasketItem` - Line items in a basket
- `WorkItem` - Work spawned from basket items
- `DispenseLog` - Record of dispensed items
- Idempotent basket commit with collision detection

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-catalog/
├── pyproject.toml
├── README.md
├── src/django_catalog/
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
class CatalogError(Exception):
    """Base exception for catalog errors."""
    pass


class BasketError(CatalogError):
    """Base exception for basket errors."""
    pass


class BasketAlreadyCommittedError(BasketError):
    """Raised when trying to modify a committed basket."""
    def __init__(self, basket_id):
        self.basket_id = basket_id
        super().__init__(f"Basket {basket_id} is already committed")


class BasketEmptyError(BasketError):
    """Raised when trying to commit an empty basket."""
    def __init__(self, basket_id):
        self.basket_id = basket_id
        super().__init__(f"Cannot commit empty basket {basket_id}")


class ItemNotAvailableError(CatalogError):
    """Raised when an item is not available for ordering."""
    def __init__(self, item_id, reason=''):
        self.item_id = item_id
        self.reason = reason
        message = f"Item {item_id} is not available"
        if reason:
            message += f": {reason}"
        super().__init__(message)
```

## Models Specification

### CatalogItem Model

```python
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django_basemodels.models import UUIDModel, BaseModel


class CatalogItemQuerySet(models.QuerySet):
    """QuerySet for catalog items."""

    def for_owner(self, owner):
        """Get items for a specific owner."""
        content_type = ContentType.objects.get_for_model(owner)
        return self.filter(
            owner_content_type=content_type,
            owner_id=str(owner.pk)
        )

    def available(self):
        """Get available items only."""
        return self.filter(is_available=True)

    def by_category(self, category):
        """Filter by category."""
        return self.filter(category=category)


class CatalogItem(UUIDModel, BaseModel):
    """An item available in the catalog for ordering."""

    # Owner via GenericFK (who offers this item)
    owner_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    # Item details
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=100, blank=True, default='')

    # Pricing (optional, depends on use case)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default='USD')

    # Availability
    is_available = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_to = models.DateTimeField(null=True, blank=True)

    # Ordering
    sort_order = models.IntegerField(default=0)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    objects = CatalogItemQuerySet.as_manager()

    class Meta:
        app_label = 'django_catalog'
        verbose_name = 'catalog item'
        verbose_name_plural = 'catalog items'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['owner_content_type', 'owner_id']),
            models.Index(fields=['category']),
            models.Index(fields=['is_available']),
        ]

    def save(self, *args, **kwargs):
        self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
```

### Basket Model

```python
from django.conf import settings
from django.utils import timezone


class BasketStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    COMMITTED = 'committed', 'Committed'
    CANCELLED = 'cancelled', 'Cancelled'


class Basket(UUIDModel, BaseModel):
    """A collection of items being ordered."""

    # Context via GenericFK (what this basket is for)
    context_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        null=True, blank=True, related_name='+'
    )
    context_id = models.CharField(max_length=255, blank=True, default='')
    context = GenericForeignKey('context_content_type', 'context_id')

    # Status
    status = models.CharField(
        max_length=20,
        choices=BasketStatus.choices,
        default=BasketStatus.DRAFT
    )

    # Timing
    committed_at = models.DateTimeField(null=True, blank=True)
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='baskets_committed'
    )

    # Idempotency
    idempotency_key = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )

    # Metadata
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_catalog'
        verbose_name = 'basket'
        verbose_name_plural = 'baskets'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.context_id:
            self.context_id = str(self.context_id)
        super().save(*args, **kwargs)

    @property
    def is_committed(self) -> bool:
        return self.status == BasketStatus.COMMITTED

    @property
    def is_draft(self) -> bool:
        return self.status == BasketStatus.DRAFT

    @property
    def total_items(self) -> int:
        return self.items.count()

    @property
    def total_quantity(self):
        from django.db.models import Sum
        return self.items.aggregate(total=Sum('quantity'))['total'] or 0

    def __str__(self):
        return f"Basket {self.pk} ({self.status})"
```

### BasketItem Model

```python
class BasketItem(UUIDModel, BaseModel):
    """A line item in a basket."""

    basket = models.ForeignKey(
        Basket, on_delete=models.CASCADE, related_name='items'
    )
    catalog_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT, related_name='basket_items'
    )

    # Quantity
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    # Price at time of adding (snapshot)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default='USD')

    # Instructions
    instructions = models.TextField(blank=True, default='')

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_catalog'
        verbose_name = 'basket item'
        verbose_name_plural = 'basket items'

    @property
    def line_total(self):
        if self.unit_price is None:
            return None
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity}x {self.catalog_item.name}"
```

### WorkItem Model

```python
class WorkItemStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    BLOCKED = 'blocked', 'Blocked'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class WorkItem(UUIDModel, BaseModel):
    """Work spawned from a basket item."""

    basket_item = models.ForeignKey(
        BasketItem, on_delete=models.CASCADE, related_name='work_items'
    )

    # What work to do
    work_type = models.CharField(max_length=100)
    spawn_role = models.CharField(max_length=100, blank=True, default='')

    # Status
    status = models.CharField(
        max_length=20,
        choices=WorkItemStatus.choices,
        default=WorkItemStatus.PENDING
    )

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='work_items_assigned'
    )

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Priority
    priority = models.IntegerField(default=0)

    # Notes
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_catalog'
        verbose_name = 'work item'
        verbose_name_plural = 'work items'
        ordering = ['-priority', 'created_at']
        constraints = [
            # Only one work item per basket_item + spawn_role
            models.UniqueConstraint(
                fields=['basket_item', 'spawn_role'],
                name='unique_basket_item_spawn_role'
            )
        ]

    @property
    def is_complete(self) -> bool:
        return self.status == WorkItemStatus.COMPLETED

    def start(self, user=None):
        """Mark work item as in progress."""
        self.status = WorkItemStatus.IN_PROGRESS
        self.started_at = timezone.now()
        if user:
            self.assigned_to = user
        self.save()

    def complete(self):
        """Mark work item as completed."""
        self.status = WorkItemStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.work_type} for {self.basket_item}"
```

### DispenseLog Model

```python
class DispenseLog(UUIDModel, BaseModel):
    """Record of an item being dispensed."""

    basket_item = models.ForeignKey(
        BasketItem, on_delete=models.CASCADE, related_name='dispense_logs'
    )

    # What was dispensed
    quantity_dispensed = models.DecimalField(max_digits=10, decimal_places=2)

    # Who dispensed it
    dispensed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='items_dispensed'
    )
    dispensed_at = models.DateTimeField(default=timezone.now)

    # Lot tracking (optional)
    lot_number = models.CharField(max_length=100, blank=True, default='')
    expiry_date = models.DateField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'django_catalog'
        verbose_name = 'dispense log'
        verbose_name_plural = 'dispense logs'
        ordering = ['-dispensed_at']

    def __str__(self):
        return f"Dispensed {self.quantity_dispensed} of {self.basket_item.catalog_item.name}"
```

## Services Specification

### services.py

```python
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from .models import (
    Basket, BasketItem, BasketStatus, WorkItem, CatalogItem
)
from .exceptions import (
    BasketAlreadyCommittedError, BasketEmptyError, ItemNotAvailableError
)


def create_basket(
    context=None,
    idempotency_key: Optional[str] = None,
    notes: str = '',
    metadata: Optional[Dict] = None,
) -> Basket:
    """
    Create a new basket.

    Args:
        context: Optional context object (what this basket is for)
        idempotency_key: Optional key for idempotent creation
        notes: Optional notes
        metadata: Optional metadata

    Returns:
        Basket instance
    """
    # Check for existing basket with same idempotency key
    if idempotency_key:
        existing = Basket.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    basket = Basket.objects.create(
        context=context,
        idempotency_key=idempotency_key,
        notes=notes,
        metadata=metadata or {},
    )
    return basket


def add_item(
    basket: Basket,
    catalog_item: CatalogItem,
    quantity=1,
    unit_price=None,
    instructions: str = '',
    metadata: Optional[Dict] = None,
) -> BasketItem:
    """
    Add an item to a basket.

    Args:
        basket: Basket to add to
        catalog_item: Item to add
        quantity: Quantity to add
        unit_price: Override price (defaults to catalog item price)
        instructions: Special instructions
        metadata: Additional metadata

    Returns:
        BasketItem instance

    Raises:
        BasketAlreadyCommittedError: If basket is already committed
        ItemNotAvailableError: If item is not available
    """
    if basket.is_committed:
        raise BasketAlreadyCommittedError(basket.pk)

    if not catalog_item.is_available:
        raise ItemNotAvailableError(catalog_item.pk, 'Item is not available')

    # Use catalog price if not specified
    if unit_price is None:
        unit_price = catalog_item.unit_price

    item = BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_item,
        quantity=quantity,
        unit_price=unit_price,
        currency=catalog_item.currency,
        instructions=instructions,
        metadata=metadata or {},
    )
    return item


@transaction.atomic
def commit_basket(
    basket: Basket,
    committed_by=None,
    spawn_work: bool = True,
    work_types: Optional[list] = None,
) -> Basket:
    """
    Commit a basket, making it immutable and optionally spawning work items.

    Args:
        basket: Basket to commit
        committed_by: User committing the basket
        spawn_work: Whether to create work items
        work_types: List of work types to spawn (if spawn_work is True)

    Returns:
        Committed Basket instance

    Raises:
        BasketAlreadyCommittedError: If already committed
        BasketEmptyError: If basket has no items
    """
    # Refresh to get latest state
    basket.refresh_from_db()

    if basket.is_committed:
        # Idempotent - return as-is if already committed
        return basket

    if basket.total_items == 0:
        raise BasketEmptyError(basket.pk)

    # Update status
    basket.status = BasketStatus.COMMITTED
    basket.committed_at = timezone.now()
    basket.committed_by = committed_by
    basket.save()

    # Spawn work items if requested
    if spawn_work and work_types:
        for item in basket.items.all():
            for work_type in work_types:
                WorkItem.objects.get_or_create(
                    basket_item=item,
                    spawn_role=work_type,
                    defaults={
                        'work_type': work_type,
                        'status': 'pending',
                    }
                )

    return basket


def cancel_basket(basket: Basket) -> Basket:
    """
    Cancel a draft basket.

    Args:
        basket: Basket to cancel

    Returns:
        Cancelled Basket instance

    Raises:
        BasketAlreadyCommittedError: If basket is already committed
    """
    if basket.is_committed:
        raise BasketAlreadyCommittedError(basket.pk)

    basket.status = BasketStatus.CANCELLED
    basket.save()
    return basket
```

## Test Cases (83 tests)

### CatalogItem Model Tests (12 tests)
1. `test_catalog_item_creation` - Create with required fields
2. `test_catalog_item_has_uuid_pk` - UUID primary key
3. `test_catalog_item_owner_generic_fk` - GenericFK works
4. `test_catalog_item_price_optional` - Price is nullable
5. `test_catalog_item_is_available_default` - Defaults to True
6. `test_catalog_item_soft_delete` - Soft delete works
7. `test_catalog_item_ordering` - Ordered by sort_order, name
8. `test_catalog_item_for_owner_query` - QuerySet filter works
9. `test_catalog_item_available_query` - Available filter works
10. `test_catalog_item_by_category_query` - Category filter works
11. `test_catalog_item_metadata_json` - JSONField works
12. `test_catalog_item_str_representation` - String returns name

### Basket Model Tests (14 tests)
1. `test_basket_creation` - Create with required fields
2. `test_basket_has_uuid_pk` - UUID primary key
3. `test_basket_status_default_draft` - Defaults to draft
4. `test_basket_context_generic_fk` - GenericFK works
5. `test_basket_context_optional` - Context is nullable
6. `test_basket_is_committed_property` - Property works
7. `test_basket_is_draft_property` - Property works
8. `test_basket_total_items_property` - Counts items
9. `test_basket_total_quantity_property` - Sums quantity
10. `test_basket_idempotency_key_unique` - Unique constraint
11. `test_basket_soft_delete` - Soft delete works
12. `test_basket_ordering` - Ordered by created_at desc
13. `test_basket_committed_at_nullable` - Nullable before commit
14. `test_basket_str_representation` - String format

### BasketItem Model Tests (10 tests)
1. `test_basket_item_creation` - Create with required fields
2. `test_basket_item_has_uuid_pk` - UUID primary key
3. `test_basket_item_basket_fk` - FK to basket
4. `test_basket_item_catalog_item_fk` - FK to catalog item
5. `test_basket_item_quantity_default` - Defaults to 1
6. `test_basket_item_price_snapshot` - Price at time of adding
7. `test_basket_item_line_total_property` - Calculates total
8. `test_basket_item_line_total_null_price` - None if no price
9. `test_basket_item_instructions_optional` - Optional field
10. `test_basket_item_str_representation` - String format

### WorkItem Model Tests (12 tests)
1. `test_work_item_creation` - Create with required fields
2. `test_work_item_has_uuid_pk` - UUID primary key
3. `test_work_item_basket_item_fk` - FK to basket item
4. `test_work_item_status_default_pending` - Defaults to pending
5. `test_work_item_assigned_to_optional` - Nullable
6. `test_work_item_is_complete_property` - Property works
7. `test_work_item_start_method` - Transitions to in_progress
8. `test_work_item_complete_method` - Transitions to completed
9. `test_work_item_unique_constraint` - basket_item + spawn_role unique
10. `test_work_item_ordering` - Ordered by priority, created_at
11. `test_work_item_soft_delete` - Soft delete works
12. `test_work_item_str_representation` - String format

### DispenseLog Model Tests (8 tests)
1. `test_dispense_log_creation` - Create with required fields
2. `test_dispense_log_has_uuid_pk` - UUID primary key
3. `test_dispense_log_basket_item_fk` - FK to basket item
4. `test_dispense_log_dispensed_by_optional` - Nullable
5. `test_dispense_log_dispensed_at_default` - Defaults to now
6. `test_dispense_log_lot_number_optional` - Optional field
7. `test_dispense_log_ordering` - Ordered by dispensed_at desc
8. `test_dispense_log_str_representation` - String format

### create_basket Service Tests (6 tests)
1. `test_create_basket_basic` - Creates basket
2. `test_create_basket_with_context` - Context attached
3. `test_create_basket_idempotent` - Same key returns same basket
4. `test_create_basket_different_keys` - Different keys create new
5. `test_create_basket_with_notes` - Notes stored
6. `test_create_basket_with_metadata` - Metadata stored

### add_item Service Tests (8 tests)
1. `test_add_item_basic` - Adds item to basket
2. `test_add_item_with_quantity` - Custom quantity
3. `test_add_item_price_snapshot` - Captures price
4. `test_add_item_price_override` - Override price
5. `test_add_item_with_instructions` - Instructions stored
6. `test_add_item_to_committed_raises` - Error on committed
7. `test_add_item_unavailable_raises` - Error on unavailable
8. `test_add_item_multiple_same_item` - Multiple of same item

### commit_basket Service Tests (9 tests)
1. `test_commit_basket_sets_status` - Status changes
2. `test_commit_basket_sets_committed_at` - Timestamp set
3. `test_commit_basket_sets_committed_by` - User recorded
4. `test_commit_basket_idempotent` - Second call returns same
5. `test_commit_basket_spawns_work` - Work items created
6. `test_commit_basket_work_unique` - Work items not duplicated
7. `test_commit_basket_empty_raises` - Error on empty
8. `test_commit_basket_already_committed_returns` - Idempotent
9. `test_commit_basket_atomic` - Transaction rollback on error

### cancel_basket Service Tests (4 tests)
1. `test_cancel_basket_sets_status` - Status changes
2. `test_cancel_basket_committed_raises` - Error on committed
3. `test_cancel_basket_returns_basket` - Returns updated basket
4. `test_cancel_basket_draft_only` - Only works on draft

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    # Models
    'CatalogItem',
    'Basket',
    'BasketStatus',
    'BasketItem',
    'WorkItem',
    'WorkItemStatus',
    'DispenseLog',
    # Services
    'create_basket',
    'add_item',
    'commit_basket',
    'cancel_basket',
    # Exceptions
    'CatalogError',
    'BasketError',
    'BasketAlreadyCommittedError',
    'BasketEmptyError',
    'ItemNotAvailableError',
]

def __getattr__(name):
    if name in ('CatalogItem', 'Basket', 'BasketStatus', 'BasketItem',
                'WorkItem', 'WorkItemStatus', 'DispenseLog'):
        from .models import (
            CatalogItem, Basket, BasketStatus, BasketItem,
            WorkItem, WorkItemStatus, DispenseLog
        )
        return locals()[name]
    if name in ('create_basket', 'add_item', 'commit_basket', 'cancel_basket'):
        from .services import create_basket, add_item, commit_basket, cancel_basket
        return locals()[name]
    if name in ('CatalogError', 'BasketError', 'BasketAlreadyCommittedError',
                'BasketEmptyError', 'ItemNotAvailableError'):
        from .exceptions import (
            CatalogError, BasketError, BasketAlreadyCommittedError,
            BasketEmptyError, ItemNotAvailableError
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Basket Workflow**: draft → committed (immutable) or cancelled
2. **Idempotent Commit**: Same basket returns same result
3. **Price Snapshot**: Capture price at time of adding to basket
4. **Work Spawning**: Create work items on commit
5. **Unique Work Items**: One per basket_item + spawn_role

## Usage Examples

```python
from django_catalog import (
    CatalogItem, create_basket, add_item, commit_basket
)

# Create catalog items
item1 = CatalogItem.objects.create(
    owner=organization,
    name='Blood Test',
    code='LAB-001',
    unit_price=Decimal('50.00'),
    category='laboratory'
)

# Create basket
basket = create_basket(
    context=patient_visit,
    idempotency_key=f"visit-{visit_id}-orders"
)

# Add items
add_item(basket, item1, quantity=1, instructions='Fasting required')
add_item(basket, item2, quantity=2)

# Commit with work spawning
basket = commit_basket(
    basket,
    committed_by=request.user,
    spawn_work=True,
    work_types=['collect', 'process', 'report']
)

# Query catalog items
available = CatalogItem.objects.for_owner(org).available()
lab_items = CatalogItem.objects.by_category('laboratory')
```

## Acceptance Criteria

- [ ] CatalogItem model with GenericFK owner
- [ ] Basket model with status workflow
- [ ] BasketItem with price snapshot
- [ ] WorkItem with unique constraint
- [ ] DispenseLog for tracking
- [ ] create_basket, add_item, commit_basket, cancel_basket services
- [ ] Idempotent basket creation and commit
- [ ] All 83 tests passing
- [ ] README with usage examples
