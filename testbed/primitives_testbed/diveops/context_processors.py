"""Context processors for diveops module."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache


# Cache TTL for unread counts - short enough to feel "live", long enough to help
UNREAD_COUNT_CACHE_TTL = 30  # seconds


def diveops_context(request):
    """Add diveops-specific context variables to all templates."""
    tz_name = getattr(settings, "DIVE_SHOP_TIMEZONE", "UTC")
    shop_name = getattr(settings, "DIVE_SHOP_NAME", "Dive Shop")
    latitude = getattr(settings, "DIVE_SHOP_LATITUDE", 0)
    longitude = getattr(settings, "DIVE_SHOP_LONGITUDE", 0)

    # Get timezone abbreviation (e.g., EST, PST)
    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        tz_abbrev = now.strftime("%Z")
    except Exception:
        tz_abbrev = "UTC"

    context = {
        "business_timezone": tz_name,
        "business_timezone_abbrev": tz_abbrev,
        "dive_shop_name": shop_name,
        "dive_shop_latitude": latitude,
        "dive_shop_longitude": longitude,
        "unread_messages_count": 0,  # Default to 0 (for customers)
        "staff_unread_count": 0,  # Default to 0 (for staff inbox)
    }

    # Add unread message count for authenticated users (with caching)
    if request.user.is_authenticated:
        context["unread_messages_count"] = _get_unread_messages_count_cached(request.user)
        context["staff_unread_count"] = _get_staff_unread_count_cached(request.user)

    return context


def _get_unread_messages_count_cached(user):
    """Get unread message count with 30-second cache."""
    cache_key = f"unread_count:customer:{user.pk}"
    count = cache.get(cache_key)
    if count is None:
        count = _get_unread_messages_count(user)
        cache.set(cache_key, count, UNREAD_COUNT_CACHE_TTL)
    return count


def _get_staff_unread_count_cached(user):
    """Get staff unread count with 30-second cache."""
    if not user.is_staff:
        return 0
    cache_key = f"unread_count:staff:{user.pk}"
    count = cache.get(cache_key)
    if count is None:
        count = _get_staff_unread_count(user)
        cache.set(cache_key, count, UNREAD_COUNT_CACHE_TTL)
    return count


def _get_unread_messages_count(user):
    """Get total unread message count for a user across all conversations.

    Uses get_customer_inbox with aggregate instead of iteration.
    """
    try:
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        from django_parties.models import Person
        from django_communication.services import get_customer_inbox

        # Find person by email (single query, get full object for the service)
        person = Person.objects.filter(
            email__iexact=user.email,
            deleted_at__isnull=True
        ).first()

        if not person:
            return 0

        # Use get_customer_inbox which annotates unread_count properly
        # Then aggregate to sum in the database
        inbox = get_customer_inbox(person)
        result = inbox.aggregate(
            total=Coalesce(Sum("unread_count"), 0)
        )

        return result["total"]
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Error getting unread messages count")
        return 0


def _get_staff_unread_count(user):
    """Get total unread message count for staff inbox.

    Uses aggregate query on get_staff_inbox instead of Python iteration.
    """
    try:
        if not user.is_staff:
            return 0

        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        from django_communication.services import get_staff_inbox

        # Get inbox queryset with unread_count already annotated
        # Use .aggregate() to sum in the database instead of Python
        inbox = get_staff_inbox(user, scope="all")

        result = inbox.aggregate(
            total=Coalesce(Sum("unread_count"), 0)
        )

        return result["total"]
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Error getting staff unread count")
        return 0
