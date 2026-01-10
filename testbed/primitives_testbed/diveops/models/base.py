"""Base constants and imports for diveops models.

This module provides shared constants used across diveops models.
"""

from django.conf import settings

# Configurable waiver validity period (default 365 days, None = never expires)
DIVEOPS_WAIVER_VALIDITY_DAYS = getattr(settings, "DIVEOPS_WAIVER_VALIDITY_DAYS", 365)
