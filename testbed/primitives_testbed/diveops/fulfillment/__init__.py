"""Fulfillment module for processing paid orders.

Handles the pipeline from payment -> entitlement grants.
"""

from .services import fulfill_order, get_order_entitlements

__all__ = ["fulfill_order", "get_order_entitlements"]
