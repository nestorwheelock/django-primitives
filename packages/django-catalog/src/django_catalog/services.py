"""Catalog services for basket commit and workitem spawning.

- WorkItems spawn only on basket commit
- Spawning must be idempotent (enforced via DB unique constraint)
- Commit operation uses @idempotent decorator for double-click protection
- Routing is deterministic and stored on creation
- No implicit spawns from SOAP/Vitals/documentation
"""
from django.db import transaction
from django.utils import timezone

from django_catalog.models import Basket, BasketItem, CatalogItem, CatalogSettings, WorkItem
from django_decisioning.decorators import idempotent


def get_catalog_settings() -> CatalogSettings:
    """Get the catalog settings singleton.

    Returns:
        CatalogSettings: The singleton instance
    """
    return CatalogSettings.get_instance()


def determine_target_board(catalog_item: CatalogItem, stock_action_override: str = '') -> str:
    """Determine target board based on CatalogItem kind and routing rules.

    Routing rules:
    - stock_item dispense -> Pharmacy board
    - stock_item administer -> Treatment board
    - service lab -> Lab board
    - service imaging -> Imaging board
    - service procedure/consult/vaccine/other -> Treatment board
    """
    if catalog_item.kind == 'stock_item':
        action = stock_action_override or catalog_item.default_stock_action
        if action == 'dispense':
            return 'pharmacy'
        elif action == 'administer':
            return 'treatment'
        return 'pharmacy'

    elif catalog_item.kind == 'service':
        category = catalog_item.service_category
        if category == 'lab':
            return 'lab'
        elif category == 'imaging':
            return 'imaging'
        else:
            return 'treatment'

    return 'treatment'


def spawn_work_item(
    basket_item: BasketItem,
    spawn_role: str = 'primary',
) -> WorkItem:
    """Spawn a WorkItem from a BasketItem.

    Idempotency: Uses get_or_create to avoid IntegrityError issues in transactions.
    The DB unique constraint (basket_item, spawn_role) ensures no duplicates.

    Returns:
        WorkItem: The spawned (or existing) work item
    """
    catalog_item = basket_item.catalog_item
    encounter = basket_item.basket.encounter

    target_board = determine_target_board(
        catalog_item,
        basket_item.stock_action_override
    )

    work_item, created = WorkItem.objects.get_or_create(
        basket_item=basket_item,
        spawn_role=spawn_role,
        defaults={
            'encounter': encounter,
            'target_board': target_board,
            'target_lane': '',
            'display_name': basket_item.display_name_snapshot or catalog_item.display_name,
            'kind': basket_item.kind_snapshot or catalog_item.kind,
            'quantity': basket_item.quantity,
            'notes': basket_item.notes,
            'status': 'pending',
            'priority': 50,
        }
    )
    return work_item


def snapshot_basket_item(basket_item: BasketItem) -> None:
    """Snapshot CatalogItem identity into BasketItem on commit.

    - CatalogItem identity is snapshotted into BasketItem on commit
    - display_name and kind are captured at commit time
    """
    catalog_item = basket_item.catalog_item
    basket_item.display_name_snapshot = catalog_item.display_name
    basket_item.kind_snapshot = catalog_item.kind
    basket_item.save(update_fields=['display_name_snapshot', 'kind_snapshot', 'updated_at'])


@idempotent(
    scope='basket_commit',
    key_from=lambda basket, user: str(basket.pk)
)
def commit_basket(basket: Basket, user) -> list[WorkItem]:
    """Transform BasketItems into WorkItems on basket commit.

    - Basket is editable until committed
    - On commit, BasketItems are transformed into WorkItems
    - CatalogItem identity is snapshotted
    - Idempotent: double-calling returns cached result via IdempotencyKey

    Note: On first call, returns list of WorkItem objects.
    On retry (idempotent cache hit), returns list of serialized PKs.
    For consistency, callers should check the return type or use
    WorkItem.objects.filter(basket_item__basket=basket) to get the actual objects.

    Returns:
        List of spawned WorkItems (first call) or cached PKs (retry).
    """
    work_items = []

    for basket_item in basket.items.select_related('catalog_item').all():
        snapshot_basket_item(basket_item)
        work_item = spawn_work_item(basket_item, spawn_role='primary')
        work_items.append(work_item)

    basket.status = 'committed'
    basket.committed_by = user
    basket.committed_at = timezone.now()
    basket.save(update_fields=['status', 'committed_by', 'committed_at', 'updated_at'])

    return work_items


def cancel_basket(basket: Basket) -> None:
    """Cancel a draft basket.

    Only draft baskets can be cancelled.
    """
    if basket.status != 'draft':
        raise ValueError("Only draft baskets can be cancelled")

    basket.status = 'cancelled'
    basket.save(update_fields=['status', 'updated_at'])


def get_or_create_draft_basket(encounter, user) -> Basket:
    """Get existing draft basket or create new one for encounter.

    Returns:
        Basket: Draft basket for the encounter
    """
    basket, created = Basket.objects.get_or_create(
        encounter=encounter,
        status='draft',
        defaults={'created_by': user}
    )
    return basket


def add_item_to_basket(
    basket: Basket,
    catalog_item: CatalogItem,
    user,
    quantity: int = 1,
    notes: str = '',
    stock_action_override: str = '',
) -> BasketItem:
    """Add a catalog item to a basket.

    Args:
        basket: The basket to add to
        catalog_item: The catalog item to add
        user: User adding the item
        quantity: Quantity to add (default 1)
        notes: Optional notes
        stock_action_override: Optional override for stock action

    Returns:
        BasketItem: The created basket item
    """
    if not basket.is_editable:
        raise ValueError("Cannot add items to a committed or cancelled basket")

    settings = get_catalog_settings()
    if not catalog_item.active and not settings.allow_inactive_items:
        raise ValueError("Cannot add inactive catalog items to basket")

    return BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_item,
        quantity=quantity,
        notes=notes,
        stock_action_override=stock_action_override,
        added_by=user,
    )


def update_work_item_status(
    work_item: WorkItem,
    new_status: str,
    user=None,
    status_detail: str = '',
) -> WorkItem:
    """Update work item status with proper timestamps.

    Args:
        work_item: The work item to update
        new_status: New status value
        user: User making the change (for completed_by)
        status_detail: Optional board-specific phase

    Returns:
        WorkItem: Updated work item
    """
    old_status = work_item.status
    work_item.status = new_status

    if status_detail:
        work_item.status_detail = status_detail

    # Set timestamps based on status transitions
    if new_status == 'in_progress' and old_status == 'pending':
        work_item.started_at = timezone.now()

    if new_status == 'completed':
        work_item.completed_at = timezone.now()
        if user:
            work_item.completed_by = user

    work_item.save()
    return work_item
