"""Django Catalog configuration.

All settings can be overridden in your Django settings.py.

Example:
    # settings.py
    CATALOG_ENCOUNTER_MODEL = 'emr.Encounter'
    CATALOG_INVENTORY_ITEM_MODEL = 'inventory.InventoryItem'
"""

from django.conf import settings


# =============================================================================
# SWAPPABLE MODELS
# =============================================================================

# Encounter model for Basket and WorkItem FKs
# Must be set by consuming application
ENCOUNTER_MODEL = getattr(
    settings,
    'CATALOG_ENCOUNTER_MODEL',
    'django_catalog.Encounter'  # Default placeholder
)

# Inventory item model for CatalogItem FK (optional)
# Set to None or empty string to disable inventory linking
INVENTORY_ITEM_MODEL = getattr(
    settings,
    'CATALOG_INVENTORY_ITEM_MODEL',
    None
)

# Prescription model for DispenseLog FK (optional)
PRESCRIPTION_MODEL = getattr(
    settings,
    'CATALOG_PRESCRIPTION_MODEL',
    None
)


def get_setting(name: str, default=None):
    """Get a setting with CATALOG_ prefix."""
    return getattr(settings, f"CATALOG_{name}", default)


def is_inventory_enabled() -> bool:
    """Check if inventory linking is enabled."""
    return bool(INVENTORY_ITEM_MODEL)


def is_prescription_enabled() -> bool:
    """Check if prescription linking is enabled."""
    return bool(PRESCRIPTION_MODEL)


# =============================================================================
# DEFAULT SETTINGS REFERENCE
# =============================================================================

# CATALOG_ENCOUNTER_MODEL = 'emr.Encounter'  # REQUIRED - encounter model for baskets
# CATALOG_INVENTORY_ITEM_MODEL = 'inventory.InventoryItem'  # Optional - for stock items
# CATALOG_PRESCRIPTION_MODEL = 'pharmacy.Prescription'  # Optional - for dispense logs
