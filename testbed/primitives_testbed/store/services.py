"""Store services for cart and order operations."""

from decimal import Decimal
from typing import Optional

from django.db import models, transaction
from django.utils import timezone

from django_catalog.models import CatalogItem
from django_sequence.services import next_sequence

from .models import StoreCart, StoreCartItem, StoreOrder, StoreOrderItem


def get_or_create_cart(user) -> StoreCart:
    """Get or create a cart for a logged-in user."""
    cart, _ = StoreCart.objects.get_or_create(user=user)
    return cart


def add_to_cart(user, catalog_item: CatalogItem, quantity: int = 1) -> StoreCartItem:
    """Add an item to the user's cart.

    If the item already exists, increments quantity.
    """
    cart = get_or_create_cart(user)

    cart_item, created = StoreCartItem.objects.get_or_create(
        cart=cart,
        catalog_item=catalog_item,
        defaults={"quantity": quantity},
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    return cart_item


def update_cart_item(user, catalog_item_id, quantity: int) -> Optional[StoreCartItem]:
    """Update the quantity of a cart item.

    If quantity is 0, removes the item.
    """
    try:
        cart = StoreCart.objects.get(user=user)
        cart_item = StoreCartItem.objects.get(
            cart=cart,
            catalog_item_id=catalog_item_id,
        )

        if quantity <= 0:
            cart_item.delete()
            return None
        else:
            cart_item.quantity = quantity
            cart_item.save()
            return cart_item
    except (StoreCart.DoesNotExist, StoreCartItem.DoesNotExist):
        return None


def remove_from_cart(user, catalog_item_id) -> bool:
    """Remove an item from the cart."""
    try:
        cart = StoreCart.objects.get(user=user)
        StoreCartItem.objects.filter(
            cart=cart,
            catalog_item_id=catalog_item_id,
        ).delete()
        return True
    except StoreCart.DoesNotExist:
        return False


def get_cart_items(user) -> list:
    """Get all items in a user's cart with calculated totals."""
    try:
        cart = StoreCart.objects.get(user=user)
        items = cart.items.select_related("catalog_item").all()

        result = []
        for item in items:
            price = get_item_price(item.catalog_item)
            result.append({
                "cart_item": item,
                "catalog_item": item.catalog_item,
                "quantity": item.quantity,
                "unit_price": price,
                "line_total": price * item.quantity,
            })
        return result
    except StoreCart.DoesNotExist:
        return []


def get_cart_total(user) -> Decimal:
    """Calculate the total of all items in the cart."""
    items = get_cart_items(user)
    return sum((item["line_total"] for item in items), Decimal("0"))


def get_item_price(catalog_item: CatalogItem) -> Decimal:
    """Get the price for a catalog item.

    For MVP, looks up global price from pricing module.
    Global scope = all scope FKs are NULL.
    Falls back to 0 if no price is set.
    """
    from django.utils import timezone
    from primitives_testbed.pricing.models import Price

    try:
        # Look for global price for this item (all scope FKs NULL)
        now = timezone.now()
        price = Price.objects.filter(
            catalog_item=catalog_item,
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
            valid_from__lte=now,
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=now)
        ).order_by("-valid_from").first()

        if price:
            return price.amount
    except Exception:
        pass

    return Decimal("0")


def get_item_entitlements(catalog_item: CatalogItem) -> list[str]:
    """Get the entitlement codes granted by a catalog item.

    Looks up the CatalogItemEntitlement mapping table.
    """
    from .models import CatalogItemEntitlement

    try:
        mapping = CatalogItemEntitlement.objects.get(catalog_item=catalog_item)
        return mapping.entitlement_codes or []
    except CatalogItemEntitlement.DoesNotExist:
        return []


def generate_order_number() -> str:
    """Generate a unique order number."""
    return next_sequence(
        scope="store_order",
        prefix="ORD-",
        pad_width=6,
        include_year=True,
    )


@transaction.atomic
def create_order_from_cart(
    user,
    tax_rate: Decimal = Decimal("0"),
    notes: str = "",
) -> StoreOrder:
    """Create an order from the user's cart.

    Args:
        user: The user placing the order
        tax_rate: Tax rate as decimal (0.08 = 8%)
        notes: Optional order notes

    Returns:
        Created StoreOrder
    """
    cart_items = get_cart_items(user)

    if not cart_items:
        raise ValueError("Cart is empty")

    # Calculate totals
    subtotal = sum((item["line_total"] for item in cart_items), Decimal("0"))
    tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
    total = subtotal + tax

    # Create order
    order = StoreOrder.objects.create(
        order_number=generate_order_number(),
        user=user,
        subtotal_amount=subtotal,
        tax_amount=tax,
        total_amount=total,
        notes=notes,
    )

    # Create line items
    for item in cart_items:
        entitlements = get_item_entitlements(item["catalog_item"])

        StoreOrderItem.objects.create(
            order=order,
            catalog_item=item["catalog_item"],
            description=item["catalog_item"].display_name,
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=item["line_total"],
            entitlement_codes=entitlements,
        )

    # Clear the cart
    cart = StoreCart.objects.get(user=user)
    cart.clear()

    return order


@transaction.atomic
def mark_order_paid(order: StoreOrder, actor=None) -> StoreOrder:
    """Mark an order as paid.

    This triggers fulfillment (entitlement grants).
    """
    if order.status != "pending":
        raise ValueError(f"Cannot mark {order.status} order as paid")

    order.status = "paid"
    order.paid_at = timezone.now()
    order.save()

    # Trigger fulfillment
    from primitives_testbed.diveops.fulfillment.services import fulfill_order

    fulfill_order(order, actor=actor)

    return order
