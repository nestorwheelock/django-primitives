# django-primitives

Reusable Django packages for building ERP and business applications. **18 packages, 887 tests.**

---

## What This Is

A complete set of standalone, pip-installable Django primitives that implement the core patterns needed for any business application: identity, catalog, accounting, workflow, time tracking, permissions, and more.

These primitives compose together to build:
- E-Commerce platforms
- Healthcare/EMR systems
- Inventory & warehouse management
- Project management tools
- CRM systems
- Accounting software
- Delivery & logistics
- Multi-tenant SaaS

---

## Packages

### Foundation Layer

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| **django-basemodels** | UUID PKs, timestamps, soft delete | `UUIDModel`, `TimeStampedModel`, `SoftDeleteModel`, `BaseModel` |
| **django-singleton** | One-row configuration tables | `SingletonModel` |
| **django-modules** | Feature flags per organization | `Module`, `OrgModuleState` |
| **django-layers** | Import boundary enforcement | `Layer`, `LayersConfig` |

### Identity & Access

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| **django-parties** | People, organizations, groups, contacts | `Party`, `Person`, `Organization`, `Group`, `Address`, `Phone`, `Email` |
| **django-rbac** | Role-based access control | `Role`, `UserRole`, `RBACUserMixin` |

### Time & Decision Infrastructure

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| **django-decisioning** | Temporal modeling, idempotency, backdating | `Decision`, `IdempotencyKey`, `TimeSemanticsMixin`, `EffectiveDatedMixin` |
| **django-audit-log** | Immutable audit trail | `AuditLog` |

### Domain Primitives

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| **django-catalog** | Products, orders, fulfillment | `CatalogItem`, `Basket`, `BasketItem`, `WorkItem`, `DispenseLog` |
| **django-encounters** | Stateful visits/sessions | `Encounter`, `EncounterDefinition`, `EncounterTransition` |
| **django-worklog** | Time tracking with switch policy | `WorkSession` |
| **django-geo** | Locations, coordinates, service areas | `GeoPoint`, `Place`, `ServiceArea` |

### Value Objects & Utilities

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| **django-money** | Immutable currency amounts | `Money` |
| **django-sequence** | Human-readable IDs (INV-2024-0001) | `Sequence` |

### Attachments & Content

| Package | Purpose | Key Classes |
|---------|---------|-------------|
| **django-documents** | File attachments with checksums | `Document` |
| **django-notes** | Comments and tagging | `Note`, `Tag`, `ObjectTag` |
| **django-agreements** | Terms, consent, version tracking | `Agreement`, `AgreementVersion` |
| **django-ledger** | Double-entry accounting | `Account`, `Transaction`, `Entry` |

---

## Installation

Each package is independently installable:

```bash
pip install django-basemodels
pip install django-parties
pip install django-catalog
# etc.
```

Or install from the monorepo:

```bash
cd packages/django-parties
pip install -e .
```

---

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    'django_basemodels',
    'django_parties',
    'django_rbac',
    'django_catalog',
    # Add the packages you need
]
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Use the Primitives

```python
from django_parties.models import Person, Organization
from django_catalog.models import CatalogItem, Basket
from django_money import Money
from django_geo.geo import GeoPoint

# Create a customer
customer = Person.objects.create(
    first_name='Maria',
    last_name='Garcia',
)

# Create a product
product = CatalogItem.objects.create(
    name='Widget Pro',
    sku='WGT-001',
    unit_price=Money('29.99', 'USD'),
)

# Create an order
basket = Basket.objects.create(owner=customer)
basket.add_item(product, quantity=2)

# Geographic queries
nearby = Place.objects.within_radius(lat=19.43, lng=-99.13, km=10)
```

---

## ERP Primitive Coverage

Based on ChatGPT's "10 ERP Primitives" analysis, this project provides complete coverage:

| Primitive | Package | Status |
|-----------|---------|--------|
| 1. Party (who) | django-parties | ✅ |
| 2. Catalog (what) | django-catalog | ✅ |
| 3. Account (ledger) | django-ledger | ✅ |
| 4. Encounter (session) | django-encounters | ✅ |
| 5. Decision (event) | django-decisioning | ✅ |
| 6. Worklog (time) | django-worklog | ✅ |
| 7. RBAC (access) | django-rbac | ✅ |
| 8. Audit (trail) | django-audit-log | ✅ |
| 9. Singleton (config) | django-singleton | ✅ |
| 10. Modules (features) | django-modules | ✅ |

**Plus 8 additional primitives:** Money, Sequence, Documents, Notes, Agreements, Geo, Layers, BaseModels.

---

## Project Structure

```
django-primitives/
├── packages/
│   ├── django-agreements/
│   ├── django-audit-log/
│   ├── django-basemodels/
│   ├── django-catalog/
│   ├── django-decisioning/
│   ├── django-documents/
│   ├── django-encounters/
│   ├── django-geo/
│   ├── django-layers/
│   ├── django-ledger/
│   ├── django-modules/
│   ├── django-money/
│   ├── django-notes/
│   ├── django-parties/
│   ├── django-rbac/
│   ├── django-sequence/
│   ├── django-singleton/
│   └── django-worklog/
├── docs/
│   ├── architecture/
│   └── extraction/
└── scripts/
```

---

## Testing

Run tests for a specific package:

```bash
cd packages/django-catalog
pip install -e .
pytest tests/ -v
```

Run all tests:

```bash
./scripts/test_all.sh
```

---

## Key Architectural Principles

1. **Party Pattern**: Person/Organization/Group are foundational identity
2. **User vs Person**: Authentication (User) is separate from identity (Person)
3. **Time Semantics**: `effective_at` (when it happened) vs `recorded_at` (when logged)
4. **Idempotency**: Critical operations use `IdempotencyKey` to prevent duplicates
5. **Soft Delete**: Domain models use `is_deleted` flag, not hard delete
6. **UUID Primary Keys**: All models use UUIDs for distributed-friendly IDs
7. **Double-Entry**: Financial transactions always balance

---

## Documentation

| Document | Purpose |
|----------|---------|
| [CONTRACT.md](docs/architecture/CONTRACT.md) | Architectural rules |
| [DEPENDENCIES.md](docs/architecture/DEPENDENCIES.md) | Layer boundaries |
| [CONVENTIONS.md](docs/architecture/CONVENTIONS.md) | Coding patterns |
| [ROADMAP.md](docs/extraction/ROADMAP.md) | Package extraction history |

---

## Origin

These patterns were extracted from production systems including [VetFriendly](https://github.com/nwheeler/vetfriendly), a veterinary practice management system.

---

## License

MIT
