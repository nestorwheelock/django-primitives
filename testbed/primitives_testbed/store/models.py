"""Store models for e-commerce cart and orders.

Provides a simplified commerce flow separate from the clinical
encounter/basket/invoice workflow.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum, F
from django.utils import timezone

from django_catalog.models import CatalogItem


class StoreCart(models.Model):
    """Shopping cart for logged-in users.

    Persists cart between sessions. For anonymous users,
    cart data is stored in the session only.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "shopping cart"
        verbose_name_plural = "shopping carts"

    def __str__(self):
        return f"Cart for {self.user.email}"

    @property
    def item_count(self):
        """Total quantity of all items in cart."""
        return self.items.aggregate(total=Sum("quantity"))["total"] or 0

    def clear(self):
        """Remove all items from cart."""
        self.items.all().delete()


class StoreCartItem(models.Model):
    """Item in a shopping cart."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        StoreCart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    catalog_item = models.ForeignKey(
        CatalogItem,
        on_delete=models.CASCADE,
        related_name="store_cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "catalog_item"],
                name="unique_cart_item",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="storecartitem_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.catalog_item.display_name}"


class StoreOrder(models.Model):
    """Order placed through the store.

    Simplified invoice-like model for store purchases.
    Does not require clinical encounters or baskets.
    """

    STATUS_CHOICES = [
        ("pending", "Pending Payment"),
        ("paid", "Paid"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True)

    # Customer
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="store_orders",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    # Totals (USD only for MVP)
    subtotal_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
    )
    currency = models.CharField(max_length=3, default="USD")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "store order"
        verbose_name_plural = "store orders"

    def __str__(self):
        return f"Order {self.order_number} - ${self.total_amount} ({self.status})"


class StoreOrderItem(models.Model):
    """Line item on a store order.

    Snapshots catalog item data at time of order.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        StoreOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )

    # Source item (for reference)
    catalog_item = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        related_name="store_order_items",
    )

    # Snapshotted data (immutable after order)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    # Entitlements this item grants
    entitlement_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="Entitlement codes granted by this item",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="storeorderitem_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.description}"


class CatalogItemEntitlement(models.Model):
    """Maps catalog items to entitlement codes they grant.

    When a store order containing this item is fulfilled,
    the user receives these entitlements.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    catalog_item = models.OneToOneField(
        CatalogItem,
        on_delete=models.CASCADE,
        related_name="store_entitlement",
    )
    entitlement_codes = models.JSONField(
        default=list,
        help_text="List of entitlement codes this item grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "catalog item entitlement"
        verbose_name_plural = "catalog item entitlements"

    def __str__(self):
        return f"{self.catalog_item.display_name} -> {self.entitlement_codes}"
