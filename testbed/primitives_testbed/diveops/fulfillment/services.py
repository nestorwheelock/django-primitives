"""Fulfillment services for processing orders.

When an order is paid, this module:
1. Collects entitlement codes from all order items
2. Grants those entitlements to the purchasing user
3. Updates order status to fulfilled
4. Records audit events (if audit log available)
"""

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from primitives_testbed.store.models import StoreOrder

logger = logging.getLogger(__name__)


def get_order_entitlements(order: StoreOrder) -> list[str]:
    """Collect all entitlement codes from an order's items.

    Args:
        order: The order to collect entitlements from

    Returns:
        List of unique entitlement codes
    """
    codes = set()
    for item in order.items.all():
        for code in item.entitlement_codes:
            codes.add(code)
    return list(codes)


@transaction.atomic
def fulfill_order(order: StoreOrder, actor=None) -> list[str]:
    """Fulfill an order by granting entitlements to the purchaser.

    Args:
        order: The paid order to fulfill
        actor: The user performing the fulfillment (for audit)

    Returns:
        List of entitlement codes granted

    Raises:
        ValueError: If order is not in paid status
    """
    if order.status not in ("paid", "pending"):
        raise ValueError(f"Cannot fulfill order in status={order.status}")

    # Collect entitlements from all items
    entitlement_codes = get_order_entitlements(order)

    if entitlement_codes:
        # Grant entitlements to the user
        from primitives_testbed.diveops.entitlements.services import grant_entitlements

        grants = grant_entitlements(
            user=order.user,
            codes=entitlement_codes,
            source_type="invoice",
            source_id=str(order.pk),
        )

        logger.info(
            f"Fulfilled order {order.order_number}: granted {len(grants)} entitlements "
            f"({entitlement_codes}) to user {order.user.email}"
        )

    # Update order status
    order.status = "fulfilled"
    order.fulfilled_at = timezone.now()
    order.save()

    # Record audit event if available
    try:
        from django_audit_log.services import log_event

        log_event(
            event_type="order.fulfilled",
            actor=actor or order.user,
            target=order,
            metadata={
                "order_number": order.order_number,
                "entitlements_granted": entitlement_codes,
                "user_email": order.user.email,
            },
        )
    except Exception as e:
        # Audit logging is optional - don't fail fulfillment
        logger.warning(f"Failed to record audit event: {e}")

    return entitlement_codes


def get_entitlements_for_catalog_item(catalog_item) -> list[str]:
    """Get entitlement codes configured for a catalog item.

    Looks up the CatalogItemEntitlement mapping.

    Args:
        catalog_item: The CatalogItem to lookup

    Returns:
        List of entitlement codes, or empty list if none configured
    """
    from primitives_testbed.store.models import CatalogItemEntitlement

    try:
        mapping = CatalogItemEntitlement.objects.get(catalog_item=catalog_item)
        return mapping.entitlement_codes or []
    except CatalogItemEntitlement.DoesNotExist:
        return []
