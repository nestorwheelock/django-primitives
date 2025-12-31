# django-catalog

Order catalog with basket workflow and work item spawning for Django.

## Features

- **CatalogItem**: Definition layer for orderable items (services, stock items)
- **Basket**: Encounter-scoped container for items before commit
- **BasketItem**: Items in basket with snapshot on commit
- **WorkItem**: Spawned executable tasks with board routing
- **DispenseLog**: Clinical record of pharmacy dispensing

## Installation

```bash
pip install django-catalog
```

## Quick Start

1. Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_catalog',
]
```

2. Configure your encounter model:

```python
# settings.py
CATALOG_ENCOUNTER_MODEL = 'emr.Encounter'

# Optional: inventory item linking
CATALOG_INVENTORY_ITEM_MODEL = 'inventory.InventoryItem'

# Optional: prescription linking for dispense logs
CATALOG_PRESCRIPTION_MODEL = 'pharmacy.Prescription'
```

3. Run migrations:

```bash
python manage.py migrate django_catalog
```

## Configuration

All settings are prefixed with `CATALOG_`:

```python
# Required: Encounter model for baskets and work items
CATALOG_ENCOUNTER_MODEL = 'emr.Encounter'

# Optional: Inventory item model for stock items
CATALOG_INVENTORY_ITEM_MODEL = 'inventory.InventoryItem'

# Optional: Prescription model for dispense logs
CATALOG_PRESCRIPTION_MODEL = 'pharmacy.Prescription'
```

## Workflow

### 1. Create Catalog Items

```python
from django_catalog.models import CatalogItem

# Service
blood_test = CatalogItem.objects.create(
    kind='service',
    service_category='lab',
    display_name='Complete Blood Count',
)

# Stock item (if inventory enabled)
medication = CatalogItem.objects.create(
    kind='stock_item',
    default_stock_action='dispense',
    display_name='Amoxicillin 500mg',
    inventory_item=some_inventory_item,
)
```

### 2. Basket Workflow

```python
from django_catalog.services import (
    get_or_create_draft_basket,
    add_item_to_basket,
    commit_basket,
)

# Create/get basket for encounter
basket = get_or_create_draft_basket(encounter, user)

# Add items
add_item_to_basket(basket, blood_test, user, quantity=1)
add_item_to_basket(basket, medication, user, quantity=2)

# Commit basket -> spawns WorkItems
work_items = commit_basket(basket, user)
```

### 3. Work Item Processing

```python
from django_catalog.services import update_work_item_status

# Start work
update_work_item_status(work_item, 'in_progress', user)

# Complete work
update_work_item_status(work_item, 'completed', user)
```

## Board Routing

Work items are routed to boards based on catalog item configuration:

| Kind | Category/Action | Target Board |
|------|-----------------|--------------|
| stock_item | dispense | Pharmacy |
| stock_item | administer | Treatment |
| service | lab | Lab |
| service | imaging | Imaging |
| service | procedure/consult/vaccine/other | Treatment |

## Services

```python
from django_catalog.services import (
    determine_target_board,
    spawn_work_item,
    snapshot_basket_item,
    commit_basket,
    cancel_basket,
    get_or_create_draft_basket,
    add_item_to_basket,
    update_work_item_status,
)
```

## License

Proprietary - See LICENSE file.

## Version

0.1.0
