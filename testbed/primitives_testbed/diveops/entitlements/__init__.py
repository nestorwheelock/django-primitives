"""Entitlements module for diveops.

Provides entitlement grants that bridge commerce (purchases) with
CMS access control (paywalled content).
"""

from .models import EntitlementGrant
from .services import (
    grant_entitlements,
    revoke_entitlements,
    user_has_entitlement,
    user_has_all_entitlements,
    get_user_entitlements,
)
from .cms_checker import cms_entitlement_checker

__all__ = [
    "EntitlementGrant",
    "grant_entitlements",
    "revoke_entitlements",
    "user_has_entitlement",
    "user_has_all_entitlements",
    "get_user_entitlements",
    "cms_entitlement_checker",
]
