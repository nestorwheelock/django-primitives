"""Entitlement service functions.

Provides operations for granting, revoking, and checking entitlements.
"""

from datetime import datetime
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import EntitlementGrant


@transaction.atomic
def grant_entitlements(
    user,
    codes: list[str],
    source_type: str = "manual",
    source_id: str = "",
    starts_at: Optional[datetime] = None,
    ends_at: Optional[datetime] = None,
) -> list[EntitlementGrant]:
    """Grant one or more entitlements to a user.

    Creates EntitlementGrant records for each code. Idempotent - if
    an entitlement already exists with the same (user, code, source_type, source_id),
    it will be skipped.

    Args:
        user: User to grant entitlements to
        codes: List of entitlement codes to grant
        source_type: How the entitlement was granted ('invoice', 'manual')
        source_id: Reference to the source (invoice ID, etc.)
        starts_at: When the entitlement becomes active (null = immediate)
        ends_at: When the entitlement expires (null = permanent)

    Returns:
        List of created EntitlementGrant objects
    """
    grants = []
    for code in codes:
        grant, created = EntitlementGrant.objects.get_or_create(
            user=user,
            code=code,
            source_type=source_type,
            source_id=source_id,
            defaults={
                "starts_at": starts_at,
                "ends_at": ends_at,
            },
        )
        if created:
            grants.append(grant)
    return grants


@transaction.atomic
def revoke_entitlements(
    user,
    codes: list[str],
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
) -> int:
    """Revoke entitlements from a user.

    Args:
        user: User to revoke entitlements from
        codes: List of entitlement codes to revoke
        source_type: If provided, only revoke grants from this source
        source_id: If provided, only revoke grants from this specific source

    Returns:
        Number of grants deleted
    """
    qs = EntitlementGrant.objects.filter(user=user, code__in=codes)
    if source_type:
        qs = qs.filter(source_type=source_type)
    if source_id:
        qs = qs.filter(source_id=source_id)
    count, _ = qs.delete()
    return count


def user_has_entitlement(
    user,
    code: str,
    at: Optional[datetime] = None,
) -> bool:
    """Check if a user has a specific entitlement.

    Args:
        user: User to check
        code: Entitlement code to check for
        at: Point in time to check (default: now)

    Returns:
        True if user has the entitlement and it's active
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    at = at or timezone.now()

    # Build query for active entitlements
    query = Q(user=user, code=code)

    # Check start time (null or in the past)
    query &= Q(starts_at__isnull=True) | Q(starts_at__lte=at)

    # Check end time (null or in the future)
    query &= Q(ends_at__isnull=True) | Q(ends_at__gt=at)

    return EntitlementGrant.objects.filter(query).exists()


def user_has_all_entitlements(
    user,
    codes: list[str],
    at: Optional[datetime] = None,
) -> bool:
    """Check if a user has ALL specified entitlements.

    Args:
        user: User to check
        codes: List of entitlement codes to check for
        at: Point in time to check (default: now)

    Returns:
        True if user has all entitlements and they're all active
    """
    if not codes:
        return True

    for code in codes:
        if not user_has_entitlement(user, code, at):
            return False
    return True


def get_user_entitlements(
    user,
    at: Optional[datetime] = None,
) -> list[str]:
    """Get all active entitlement codes for a user.

    Args:
        user: User to get entitlements for
        at: Point in time to check (default: now)

    Returns:
        List of active entitlement codes
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []

    at = at or timezone.now()

    # Build query for active entitlements
    query = Q(user=user)
    query &= Q(starts_at__isnull=True) | Q(starts_at__lte=at)
    query &= Q(ends_at__isnull=True) | Q(ends_at__gt=at)

    return list(
        EntitlementGrant.objects.filter(query)
        .values_list("code", flat=True)
        .distinct()
    )
