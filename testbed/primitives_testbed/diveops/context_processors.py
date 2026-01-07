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

    return {
        "business_timezone": tz_name,
        "business_timezone_abbrev": tz_abbrev,
        "dive_shop_name": shop_name,
        "dive_shop_latitude": latitude,
        "dive_shop_longitude": longitude,
    }
