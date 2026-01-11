"""Context processors for diveops module."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings


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
        "unread_messages_count": 0,  # Default to 0
    }

    # Add unread message count for authenticated users
    if request.user.is_authenticated:
        context["unread_messages_count"] = _get_unread_messages_count(request.user)

    return context


def _get_unread_messages_count(user):
    """Get total unread message count for a user across all conversations."""
    try:
        from .selectors import get_current_diver

        diver = get_current_diver(user)
        if not diver or not diver.person:
            return 0

        from django_communication.models import ConversationParticipant

        # Get all conversation participations for this person
        participations = ConversationParticipant.objects.filter(
            person=diver.person,
            conversation__status="active",
        ).select_related("conversation")

        total_unread = 0
        for participation in participations:
            total_unread += participation.unread_count

        return total_unread
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Error getting unread messages count")
        return 0
