"""Django Catalog - Order catalog with basket workflow and work item spawning.

Provides:
- CatalogItem: Definition layer for orderable items (services, stock items)
- Basket: Encounter-scoped container for items before commit
- BasketItem: Items in basket with snapshot on commit
- WorkItem: Spawned executable tasks with board routing
- DispenseLog: Clinical record of pharmacy dispensing

Usage:
    INSTALLED_APPS = [
        ...
        'django_catalog',
    ]

    # Configure swappable models
    CATALOG_ENCOUNTER_MODEL = 'emr.Encounter'
    CATALOG_INVENTORY_ITEM_MODEL = 'inventory.InventoryItem'

See conf.py for all configuration options.
"""

__version__ = "0.1.0"
