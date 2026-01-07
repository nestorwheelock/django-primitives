# DiveOps Module Architecture Audit

**Date:** 2026-01-05
**Module:** `primitives_testbed.diveops`
**Scope:** Architecture, Data Flow, Relationships, Modular Design

---

## Executive Summary

The diveops module is a comprehensive dive operations management system built on top of the django-primitives ecosystem. It handles the complete lifecycle from diver registration through booking, excursion execution, dive logging, and financial settlement.

**Key Findings:**
- Well-structured service-oriented architecture with clear separation of concerns
- Strong audit logging with 40+ stable action constants
- PostgreSQL constraints enforce data integrity at the database level
- Complex pricing model with 4-level hierarchy and site adjustments
- Some role inconsistencies between ExcursionRoster and DiveAssignment
- Cost allocation model may need enhancement for shared vs per-dive costs

---

## 1. Module Structure

### File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `models.py` | 2,281 | 18 domain models |
| `services.py` | 3,183 | 42+ service functions |
| `staff_views.py` | 1,580 | 45+ admin views |
| `forms.py` | 1,321 | 15+ form classes |
| `audit.py` | 1,139 | Audit logging adapter |
| `eligibility_service.py` | 588 | Certification eligibility |
| `selectors.py` | 438 | Query optimizations |
| `validators.py` | 382 | Dive plan safety rules |
| `cancellation_policy.py` | 313 | Refund calculations |
| `integrations.py` | 280 | Primitive adapters |
| `decisioning.py` | 191 | Booking decisions |
| `settlement_service.py` | 172 | Financial posting |
| `pricing_service.py` | 137 | Price adjustments |
| `commission_service.py` | 133 | Revenue sharing |
| `staff_urls.py` | 69 | 68 URL patterns |
| `exceptions.py` | 37 | 7 exception types |

**Migrations:** 15 (0001-0015) tracking schema evolution

---

## 2. Entity Relationship Model

### Core Domain Hierarchy

```
Organization (dive_shop)
    │
    ├── ExcursionType (product template)
    │       │
    │       ├── ExcursionTypeDive (dive plan template) ─────┐
    │       │       └── dive_site (optional, site-specific) │
    │       │                                               │
    │       └── suitable_sites (M2M) ◄──────────────────────┘
    │               └── DiveSite
    │
    └── Excursion (operational outing)
            │
            ├── Dive (atomic dive event)
            │       │
            │       ├── plan_snapshot (frozen from template)
            │       ├── dive_site (where it happens)
            │       │
            │       ├── DiveAssignment (diver ↔ dive)
            │       │       └── role: diver/guide/instructor/student
            │       │
            │       └── DiveLog (per-diver record)
            │               └── overlay pattern (null = inherit from Dive)
            │
            └── Booking (reservation)
                    │
                    ├── DiverProfile (who)
                    ├── price_snapshot (immutable)
                    └── EligibilityOverride (optional exemption)
```

### Complete Entity Map (19 Models)

#### Reference Data Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `CertificationLevel` | Agency-scoped certification standards | FK: Organization (agency) |
| `DiverCertification` | Diver's certification records | FK: DiverProfile, CertificationLevel, Document |

#### Identity Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `DiverProfile` | Diver's dive-specific profile | O2O: Person (django-parties) |

#### Location Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `DiveSite` | Dive location with metadata | FK: Place (django-geo), CertificationLevel |
| `SitePriceAdjustment` | Site-specific cost factors | FK: DiveSite |

#### Product Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `ExcursionType` | Bookable dive product template | FK: CertificationLevel; M2M: DiveSite |
| `ExcursionTypeDive` | Individual dive template within product | FK: ExcursionType, DiveSite (optional) |

#### Operations Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `Trip` | Multi-day commercial package | FK: Organization, CatalogItem |
| `Excursion` | Single-day operational outing | FK: Organization, ExcursionType, Trip, DiveSite |
| `ExcursionRoster` | Check-in record | FK: Excursion, DiverProfile, Booking |
| `ExcursionRequirement` | Additional requirements per excursion | FK: Excursion, CertificationLevel |

#### Dive Execution Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `Dive` | Atomic dive within excursion | FK: Excursion, DiveSite |
| `DiveAssignment` | Diver assignment to specific dive | FK: Dive, DiverProfile |
| `DiveLog` | Per-diver personal dive record | FK: Dive, DiverProfile, DiveAssignment |

#### Booking Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `Booking` | Diver's reservation | FK: Excursion, DiverProfile, Basket, Invoice, Agreement |
| `EligibilityOverride` | Booking-scoped exemption | O2O: Booking |

#### Financial Layer
| Model | Purpose | Key Relationships |
|-------|---------|-------------------|
| `SettlementRecord` | Idempotent financial posting | FK: Booking, SettlementRun, Transaction |
| `SettlementRun` | Batch settlement processing | FK: Organization |
| `CommissionRule` | Effective-dated revenue sharing | FK: Organization, ExcursionType (optional) |

---

## 3. Data Flow Analysis

### 3.1 Booking Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BOOKING FLOW                                  │
└─────────────────────────────────────────────────────────────────────┘

1. PRODUCT SETUP
   ExcursionType ──► ExcursionTypeDive (templates)
        │                    │
        └── suitable_sites ◄─┴── dive_site (site-specific plans)

2. SCHEDULING
   ExcursionType ──► Excursion (operational instance)
        │                │
        └── base_price   └── price_per_diver (may differ)

3. BOOKING
   DiverProfile + Excursion ──► Booking
        │                            │
        ├── check_layered_eligibility()
        │        ├── certification level check
        │        ├── medical clearance check
        │        └── waiver validity check
        │
        └── price_snapshot (frozen at booking)

4. CHECK-IN
   Booking ──► ExcursionRoster
        │           │
        └── role: DIVER | DM | INSTRUCTOR

5. DIVE EXECUTION
   Excursion ──► Dive(s)
        │            │
        │            ├── plan_snapshot (from ExcursionTypeDive)
        │            └── dive_site
        │
        └── Roster entries ──► DiveAssignment(s)
                                    │
                                    └── role: diver | guide | instructor | student

6. LOGGING
   DiveAssignment ──► DiveLog (per-diver record)
        │                  │
        │                  ├── Override metrics (null = inherit from Dive)
        │                  ├── Air consumption
        │                  └── Equipment used

7. SETTLEMENT
   Booking ──► SettlementRecord(s)
        │           │
        │           ├── REVENUE (initial)
        │           └── REFUND (if cancelled)
        │
        └── idempotency_key prevents duplicates
```

### 3.2 Dive Plan Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DIVE PLAN FLOW                                  │
└─────────────────────────────────────────────────────────────────────┘

TEMPLATE CREATION:
┌──────────────────┐     ┌─────────────────────┐
│  ExcursionType   │────►│  ExcursionTypeDive  │
│  (product)       │     │  (dive template)    │
└──────────────────┘     └─────────────────────┘
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                    dive_site           route_segments
                    (optional)          (JSON profile)
                         │                   │
                         └───────┬───────────┘
                                 │
                            LIFECYCLE:
                         draft → published → retired

SNAPSHOT AT BRIEFING:
┌─────────────────────┐     ┌────────────────┐
│  ExcursionTypeDive  │────►│     Dive       │
│  (PUBLISHED)        │     │                │
└─────────────────────┘     └────────────────┘
         │                          │
         │    lock_dive_plan()      │
         └─────────────────────────►│
                                    │
                              plan_snapshot (JSON)
                              plan_locked_at
                              plan_template_id
                              plan_template_published_at

VALIDATION (Planned):
┌────────────────┐     ┌───────────────────┐     ┌─────────────────┐
│  plan_snapshot │────►│ segment_converter │────►│ deco_runner.py  │
│  (route_segments)    │ (Python)          │     │ (Rust binary)   │
└────────────────┘     └───────────────────┘     └─────────────────┘
                                                         │
                                                 Bühlmann ZHL-16C
                                                 ceiling, TTS, stops
```

### 3.3 Price Resolution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PRICE RESOLUTION                                │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │   ExcursionType     │
                    │   base_price        │
                    └─────────┬───────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌─────────────────┐
    │ SitePriceAdjust │ │ Pricing   │ │ CommissionRule  │
    │ - DISTANCE      │ │ Hierarchy │ │ (revenue share) │
    │ - PARK_FEE      │ │           │ │                 │
    │ - NIGHT         │ │ Agreement │ │ Type-specific   │
    │ - BOAT          │ │ Party     │ │ Shop default    │
    └─────────┬───────┘ │ Org       │ └────────┬────────┘
              │         │ Global    │          │
              │         └─────┬─────┘          │
              │               │                │
              └───────────────┼────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Booking           │
                    │   price_snapshot    │ ◄── IMMUTABLE
                    │   price_amount      │
                    └─────────────────────┘
```

---

## 4. Dependency Map

### External Primitive Dependencies

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRIMITIVE DEPENDENCIES                           │
└─────────────────────────────────────────────────────────────────────┘

                         diveops
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
    ▼                       ▼                       ▼
┌─────────────┐     ┌─────────────┐         ┌─────────────┐
│ FOUNDATION  │     │  IDENTITY   │         │   DOMAIN    │
├─────────────┤     ├─────────────┤         ├─────────────┤
│ basemodels  │     │   parties   │         │  encounters │
│ (BaseModel) │     │ (Person,    │         │ (Encounter, │
│             │     │  Org)       │         │  workflow)  │
└─────────────┘     └─────────────┘         └─────────────┘
                            │                       │
                            │               ┌───────┴───────┐
                            ▼               ▼               ▼
                    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
                    │    geo      │ │   catalog   │ │  agreements │
                    │ (Place)     │ │ (CatalogItem│ │ (Agreement) │
                    │             │ │  Basket)    │ │             │
                    └─────────────┘ └─────────────┘ └─────────────┘
                                           │
                                    ┌──────┴──────┐
                                    ▼             ▼
                            ┌─────────────┐ ┌─────────────┐
                            │  documents  │ │   ledger    │
                            │ (Document)  │ │(Transaction)│
                            └─────────────┘ └─────────────┘
                                    │
                                    ▼
                            ┌─────────────┐
                            │  sequence   │
                            │(next_seq()) │
                            └─────────────┘
```

### Adapter Pattern

All primitive imports are consolidated in `integrations.py`:

```python
# integrations.py - Single source of truth for dependencies
from django_parties.models import Person, Organization
from django_geo.models import Place
from django_catalog.models import CatalogItem, Basket
from django_agreements.models import Agreement
from django_documents.models import Document
from django_audit_log import log as audit_log
from django_sequence import next_sequence
from django_ledger.models import Transaction
```

**Benefits:**
- Clear dependency inventory
- Easy to update when primitives change
- Single point of integration testing

---

## 5. Role Model Analysis

### Current State

**ExcursionRoster (Check-in Level):**
```python
ROLE_CHOICES = [
    ("DIVER", "Diver"),
    ("DM", "Divemaster"),
    ("INSTRUCTOR", "Instructor"),
]
```

**DiveAssignment (Dive Level):**
```python
class Role(models.TextChoices):
    DIVER = "diver", "Diver"
    GUIDE = "guide", "Guide"
    INSTRUCTOR = "instructor", "Instructor"
    STUDENT = "student", "Student"
```

### Gap Analysis

| Role | ExcursionRoster | DiveAssignment | Notes |
|------|-----------------|----------------|-------|
| Diver (paying customer) | DIVER | diver | Consistent |
| Divemaster | DM | - | Missing at dive level |
| Guide | - | guide | Missing at roster level |
| Instructor | INSTRUCTOR | instructor | Consistent |
| Student | - | student | Missing at roster level |
| Photographer | - | - | **Missing entirely** |
| Videographer | - | - | **Missing entirely** |
| Safety Diver | - | - | **Missing entirely** |

### Recommendation: Unified Role Enumeration

```python
class DiveRole(models.TextChoices):
    # Customers
    DIVER = "diver", "Diver"
    STUDENT = "student", "Student"

    # Staff
    GUIDE = "guide", "Guide"
    DIVEMASTER = "divemaster", "Divemaster"
    INSTRUCTOR = "instructor", "Instructor"

    # Support
    PHOTOGRAPHER = "photographer", "Photographer"
    VIDEOGRAPHER = "videographer", "Videographer"
    SAFETY = "safety", "Safety Diver"
```

---

## 6. Cost Model Analysis

### Current State

**Excursion-Level Pricing:**
```python
class Excursion:
    price_per_diver = DecimalField()  # Single price for entire excursion
```

**Site Adjustments:**
```python
class SitePriceAdjustment:
    KIND_CHOICES = [
        ("distance", "Distance/Fuel Surcharge"),
        ("park_fee", "Park Entry Fee"),
        ("night", "Night Dive Surcharge"),
        ("boat", "Boat Charter Fee"),
    ]
    is_per_diver = BooleanField()  # Divided or shared
```

### Gap Analysis

The current model handles:
- Per-diver pricing at excursion level
- Site-specific adjustments (distance, park fees, etc.)
- Per-diver vs shared cost flag

**Missing:**
- Per-dive cost allocation (some dives may cost more than others)
- Equipment rental costs (per-diver, per-dive)
- Guide/photographer fees (may be per-excursion or per-dive)
- Tank/air fills (typically per-dive)

### Cost Allocation Matrix

| Cost Type | Allocation | Current Model | Gap |
|-----------|------------|---------------|-----|
| Boat charter | Per-excursion (shared) | SitePriceAdjustment.BOAT | Partial |
| Park fees | Per-diver | SitePriceAdjustment.PARK_FEE | OK |
| Fuel surcharge | Per-excursion (shared) | SitePriceAdjustment.DISTANCE | Partial |
| Night surcharge | Per-diver | SitePriceAdjustment.NIGHT | OK |
| Tank/air fill | Per-dive | - | **Missing** |
| Equipment rental | Per-diver, per-dive | - | **Missing** |
| Guide fee | Per-dive (shared) | - | **Missing** |
| Photographer fee | Per-excursion (shared) | - | **Missing** |

### Recommendation: Tiered Boat Cost Model

**Real-World Example (from operator):**
| Dive Type | Boat Cost | Threshold | Overage |
|-----------|-----------|-----------|---------|
| Close site (boat) | 1,800 MXN | 4 divers | +150 MXN/person |
| Shipwreck (boat) | 2,200 MXN | 4 divers | +150 MXN/person |
| Shore dive | 0 (no boat) | - | Tanks + overhead only |

**Calculation Examples:**
- 4 divers to close site: 1,800 ÷ 4 = 450 MXN/diver
- 6 divers to close site: (1,800 + 2×150) ÷ 6 = 350 MXN/diver
- 8 divers to shipwreck: (2,200 + 4×150) ÷ 8 = 350 MXN/diver

```python
class BoatCostTier(BaseModel):
    """Site-specific boat charter pricing with capacity tiers.

    Captures real-world boat pricing: base cost for up to N divers,
    then additional per-person charge above threshold.
    """
    dive_site = models.ForeignKey(
        DiveSite,
        on_delete=models.CASCADE,
        related_name="boat_cost_tiers",
    )

    # Base pricing
    base_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Base boat charter cost (e.g., 1800 MXN)",
    )
    currency = models.CharField(max_length=3, default="MXN")

    # Capacity threshold
    included_divers = models.PositiveSmallIntegerField(
        default=4,
        help_text="Number of divers included in base cost",
    )

    # Overage pricing
    overage_per_person = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Additional cost per person above threshold (e.g., 150 MXN)",
    )

    # Applicability
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dive_site"],
                condition=Q(is_active=True),
                name="one_active_boat_tier_per_site",
            ),
        ]

    def calculate_total(self, diver_count: int) -> Decimal:
        """Calculate total boat cost for given diver count."""
        if diver_count <= self.included_divers:
            return self.base_cost
        overage_count = diver_count - self.included_divers
        return self.base_cost + (overage_count * self.overage_per_person)

    def calculate_per_diver(self, diver_count: int) -> Decimal:
        """Calculate per-diver share of boat cost."""
        if diver_count == 0:
            return Decimal("0")
        return self.calculate_total(diver_count) / diver_count


class GasFillPrice(BaseModel):
    """Tank fill pricing by gas mix.

    Air is cheaper than Nitrox, which is cheaper than Trimix.
    Prices are per-tank, per-fill.
    """

    class GasType(models.TextChoices):
        AIR = "air", "Air"
        EAN32 = "ean32", "Nitrox 32%"
        EAN36 = "ean36", "Nitrox 36%"
        TRIMIX = "trimix", "Trimix"

    gas_type = models.CharField(max_length=10, choices=GasType.choices, unique=True)
    cost_per_fill = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Shop's cost per tank fill",
    )
    charge_per_fill = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price charged to customer per fill",
    )
    currency = models.CharField(max_length=3, default="MXN")
    is_active = models.BooleanField(default=True)

    @property
    def margin(self) -> Decimal:
        return self.charge_per_fill - self.cost_per_fill


class EquipmentItem(BaseModel):
    """Equipment that can be rented to/from customers.

    Tracks both:
    - What shop pays to rent equipment (cost)
    - What shop charges customer for rental (charge)
    """

    class Category(models.TextChoices):
        BCD = "bcd", "BCD"
        REGULATOR = "regulator", "Regulator"
        WETSUIT = "wetsuit", "Wetsuit"
        MASK = "mask", "Mask"
        FINS = "fins", "Fins"
        COMPUTER = "computer", "Dive Computer"
        CAMERA = "camera", "Camera/Housing"
        LIGHT = "light", "Dive Light"
        SMB = "smb", "SMB/DSMB"
        OTHER = "other", "Other"

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=Category.choices)

    # What shop pays (if renting from supplier)
    shop_rental_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Shop's cost to rent this item (0 if shop-owned)",
    )

    # What customer pays
    customer_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price charged to customer for rental",
    )

    currency = models.CharField(max_length=3, default="MXN")
    is_per_dive = models.BooleanField(
        default=False,
        help_text="True = charged per dive, False = per day/excursion",
    )
    is_active = models.BooleanField(default=True)

    @property
    def margin(self) -> Decimal:
        return self.customer_charge - self.shop_rental_cost


class DiverEquipmentRental(BaseModel):
    """Equipment rented to a specific diver on an excursion.

    Links EquipmentItem to a Booking for invoicing.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="equipment_rentals",
    )
    equipment = models.ForeignKey(
        EquipmentItem,
        on_delete=models.PROTECT,
        related_name="rentals",
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    # Snapshot pricing at rental time
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    unit_charge = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="MXN")

    @property
    def total_cost(self) -> Decimal:
        return self.unit_cost * self.quantity

    @property
    def total_charge(self) -> Decimal:
        return self.unit_charge * self.quantity


class DiveCost(BaseModel):
    """General cost/charge items for a dive or excursion.

    For items that don't fit into Boat, Gas, or Equipment categories.
    Supports both shop costs and customer charges.
    """

    class CostType(models.TextChoices):
        GUIDE = "guide", "Guide Fee"
        PARK_FEE = "park_fee", "Park Entry Fee"
        TRANSPORT = "transport", "Transport/Transfer"
        FOOD = "food", "Food/Refreshments"
        OVERHEAD = "overhead", "Overhead/Admin"
        OTHER = "other", "Other"

    # Scope: site-level default or excursion-specific
    dive_site = models.ForeignKey(
        DiveSite,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="default_costs",
    )
    excursion = models.ForeignKey(
        Excursion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="additional_costs",
    )

    cost_type = models.CharField(max_length=20, choices=CostType.choices)
    description = models.CharField(max_length=100, blank=True)

    # Dual tracking: cost to shop AND charge to customer
    shop_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="What shop pays for this item",
    )
    customer_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="What customer is charged",
    )
    currency = models.CharField(max_length=3, default="MXN")

    # Allocation
    is_per_diver = models.BooleanField(
        default=True,
        help_text="True = per diver, False = shared among divers",
    )
    is_active = models.BooleanField(default=True)

    @property
    def margin(self) -> Decimal:
        return self.customer_charge - self.shop_cost
```

**Complete Cost Model Summary:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DIVE SHOP COST MODEL                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SHARED COSTS (divided among divers):                               │
│  ├── BoatCostTier: Tiered by site + diver count                     │
│  │       Close site: 1,800 MXN base (4 divers) + 150/extra          │
│  │       Shipwreck:  2,200 MXN base (4 divers) + 150/extra          │
│  │       Shore:      0 (no boat)                                    │
│  │                                                                   │
│  └── DiveCost (is_per_diver=False): Guide fees, transport, food     │
│                                                                      │
│  PER-DIVER COSTS (each diver pays):                                 │
│  ├── GasFillPrice: Air vs Nitrox pricing                            │
│  │       Air:    cost=X, charge=Y (per tank)                        │
│  │       EAN32:  cost=X, charge=Y (per tank)                        │
│  │                                                                   │
│  ├── DiverEquipmentRental: What diver rents                         │
│  │       BCD:       shop_cost=0 (owned), charge=200/day             │
│  │       Regulator: shop_cost=0 (owned), charge=150/day             │
│  │       Computer:  shop_cost=100 (rental), charge=250/day          │
│  │                                                                   │
│  └── DiveCost (is_per_diver=True): Park fees, overhead              │
│                                                                      │
│  DUAL TRACKING (cost vs charge):                                    │
│  ├── shop_cost:      What shop pays (expense)                       │
│  ├── customer_charge: What customer pays (revenue)                  │
│  └── margin:         Profit = charge - cost                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Example: 2-Tank Boat Dive to Shipwreck, 6 Divers**

| Cost Item | Shop Cost | Customer Charge | Allocation |
|-----------|-----------|-----------------|------------|
| Boat (2200 + 2×150) | 2,500 MXN | 2,500 MXN | ÷6 = 417/diver |
| Guide fee | 500 MXN | 600 MXN | ÷6 = 100/diver |
| Air fill ×2 | 80 MXN | 0 (included) | per diver |
| Park fee | 50 MXN | 50 MXN | per diver |
| **Subtotal** | | | **567 MXN/diver** |
| Equipment (1 diver rents BCD) | 0 | 200 MXN | that diver only |

**Shore Dive Example: 2-Tank, 4 Divers**

| Cost Item | Shop Cost | Customer Charge | Allocation |
|-----------|-----------|-----------------|------------|
| Boat | 0 | 0 | N/A |
| Air fill ×2 | 80 MXN | 0 (included) | per diver |
| Overhead | 50 MXN | 100 MXN | per diver |
| **Subtotal** | | | **100 MXN/diver** |

**Usage in Price Calculation:**
```python
def calculate_excursion_price(excursion, diver_count, gas_type="air"):
    """Calculate total and per-diver price for excursion.

    Returns both shop costs and customer charges for margin analysis.
    """
    site = excursion.primary_site

    # 1. Boat cost (tiered, shared)
    boat_tier = site.boat_cost_tiers.filter(is_active=True).first() if site else None
    boat_total = boat_tier.calculate_total(diver_count) if boat_tier else Decimal("0")
    boat_per_diver = boat_total / diver_count if diver_count > 0 else Decimal("0")

    # 2. Gas fills (per-diver, varies by mix)
    gas_price = GasFillPrice.objects.filter(gas_type=gas_type, is_active=True).first()
    dives_per_excursion = excursion.excursion_type.dives_per_excursion or 2
    gas_cost = (gas_price.cost_per_fill * dives_per_excursion) if gas_price else Decimal("0")
    gas_charge = (gas_price.charge_per_fill * dives_per_excursion) if gas_price else Decimal("0")

    # 3. Other costs (guide fees, park fees, etc.)
    other_costs = DiveCost.objects.filter(
        Q(dive_site=site) | Q(excursion=excursion),
        is_active=True,
    )
    per_diver_cost = other_costs.filter(is_per_diver=True).aggregate(
        cost=Sum("shop_cost"), charge=Sum("customer_charge")
    )
    shared_cost = other_costs.filter(is_per_diver=False).aggregate(
        cost=Sum("shop_cost"), charge=Sum("customer_charge")
    )

    return {
        "boat_per_diver": boat_per_diver,
        "gas_cost_per_diver": gas_cost,
        "gas_charge_per_diver": gas_charge,
        "other_per_diver_cost": per_diver_cost["cost"] or Decimal("0"),
        "other_per_diver_charge": per_diver_cost["charge"] or Decimal("0"),
        "shared_cost_per_diver": (shared_cost["cost"] or Decimal("0")) / diver_count,
        "shared_charge_per_diver": (shared_cost["charge"] or Decimal("0")) / diver_count,
        "total_cost_per_diver": ...,  # sum of costs
        "total_charge_per_diver": ...,  # sum of charges
        "margin_per_diver": ...,  # charge - cost
    }
```

---

## 7. Audit Trail Completeness

### Current Coverage

The audit system in `audit.py` provides comprehensive logging:

**Entity Coverage:**
| Entity | Create | Update | Delete | State Changes |
|--------|--------|--------|--------|---------------|
| DiverProfile | DIVER_CREATED | DIVER_UPDATED | DIVER_DELETED | - |
| DiverCertification | CERT_ADDED | CERT_UPDATED | CERT_REMOVED | CERT_VERIFIED |
| Booking | BOOKING_CREATED | - | - | CONFIRMED, CANCELLED, CHECKED_IN |
| Excursion | EXCURSION_CREATED | EXCURSION_UPDATED | - | STARTED, COMPLETED, CANCELLED |
| Dive | DIVE_CREATED | DIVE_UPDATED | - | DIVE_LOGGED, PLAN_LOCKED |
| DiveAssignment | ASSIGNMENT_CREATED | - | - | Status FSM |
| DiveLog | LOG_CREATED | LOG_UPDATED | - | LOG_VERIFIED |
| Settlement | - | - | - | SETTLEMENT_POSTED |
| EligibilityOverride | - | - | - | OVERRIDE_APPROVED |

### Audit Data Captured

```python
log_*_event(
    action=Actions.XXX,
    entity=model_instance,
    actor=User,
    data={
        "changes": {"field": {"old": x, "new": y}},
        "reason": "...",
        "context": {...}
    },
    request=HttpRequest  # optional, for IP/UA
)
```

**Strengths:**
- Stable action constants (40+)
- Field-level change tracking
- Actor attribution
- Request context capture
- Sensitivity levels

**Gaps:**
- No audit for SitePriceAdjustment changes
- No audit for CommissionRule changes
- No audit for ExcursionRequirement changes

---

## 8. Business Logic Patterns

### 8.1 Eligibility Checking

```
check_layered_eligibility(diver, excursion, effective_at)
    │
    ├── Layer 1: ExcursionType requirements
    │       └── certification level >= required
    │
    ├── Layer 2: Excursion requirements
    │       └── additional gear, medical, experience
    │
    ├── Layer 3: Diver status
    │       ├── medical current?
    │       └── waiver valid?
    │
    └── Layer 4: Booking overrides
            └── EligibilityOverride (if approved)
```

**Short-circuit behavior:** Fails fast on first unmet requirement.

### 8.2 Price Immutability (INV-3)

```
At Booking Creation:
┌────────────────────┐
│ resolve_price()    │
│ + adjustments      │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ price_snapshot     │◄── IMMUTABLE JSON
│ {                  │
│   base_price,      │
│   adjustments: [], │
│   final_amount,    │
│   currency,        │
│   resolved_at      │
│ }                  │
└────────────────────┘
         │
         ├── price_amount (denormalized)
         └── price_currency (denormalized)
```

### 8.3 Dive Plan Snapshot

```
Template Changes After Lock:
┌────────────────────┐     ┌────────────────────┐
│ ExcursionTypeDive  │     │       Dive         │
│ (updated after     │     │                    │
│  briefing sent)    │     │ plan_snapshot ─────│──► OLD VERSION
└────────────────────┘     │ plan_template_id   │
                           │ plan_snapshot_     │
                           │   outdated = True  │◄── FLAG SET
                           └────────────────────┘

Resnapshot Option:
resnapshot_dive_plan(dive) → captures new template version
```

### 8.4 Safety Validation

```
validators.py:
├── validate_mod() - Maximum Operating Depth for gas mix
├── validate_ndl() - No-Decompression Limits (PADI RDP)
├── validate_cert_depth() - Certification depth limits
├── validate_safety_stop() - Required for dives > 10m
└── validate_ascent_rate() - Max 9 m/min (PADI standard)
```

---

## 9. Constraint Inventory

### Database Constraints (PostgreSQL)

| Model | Constraint | Type | Rule |
|-------|------------|------|------|
| CertificationLevel | code per agency | UNIQUE | (agency, code) |
| CertificationLevel | rank > 0 | CHECK | rank >= 1 |
| CertificationLevel | depth > 0 | CHECK | max_depth_meters >= 1 |
| DiverCertification | one active per level | UNIQUE | (diver, level) WHERE deleted_at IS NULL |
| Excursion | return after departure | CHECK | return_time > departure_time |
| Excursion | price >= 0 | CHECK | price_per_diver >= 0 |
| Excursion | same calendar day | CHECK | date(departure) = date(return) |
| Booking | one per excursion | UNIQUE | (excursion, diver) WHERE deleted_at IS NULL |
| ExcursionRoster | one per excursion | UNIQUE | (excursion, diver) |
| Dive | sequence per excursion | UNIQUE | (excursion, sequence) |
| DiveAssignment | one per dive | UNIQUE | (dive, diver) |
| DiveLog | one per dive | UNIQUE | (dive, diver) |
| ExcursionType | base_price >= 0 | CHECK | base_price >= 0 |
| CommissionRule | rate >= 0 | CHECK | rate >= 0 |
| CommissionRule | percentage <= 100 | CHECK | rate <= 100 (if percentage type) |
| SettlementRecord | idempotency | UNIQUE | idempotency_key |

### Application-Level Invariants

| Invariant | Enforcement | Location |
|-----------|-------------|----------|
| INV-1: Booking-scoped overrides | OneToOne constraint | EligibilityOverride |
| INV-2: Layered eligibility | Service function | eligibility_service.py |
| INV-3: Price immutability | JSON snapshot + denorm | Booking.price_snapshot |
| INV-4: Idempotent settlement | Unique key | SettlementRecord.idempotency_key |

---

## 10. Findings Summary

### Strengths

1. **Clean Architecture**
   - Service-oriented design with clear separation
   - Models are data, services are logic, views are UI
   - Adapter pattern for primitive dependencies

2. **Data Integrity**
   - PostgreSQL constraints enforce invariants at DB level
   - Soft delete with constraint-aware unique indexes
   - Immutable snapshots prevent retroactive changes

3. **Audit Completeness**
   - 40+ stable action constants
   - Field-level change tracking
   - Actor and context attribution

4. **Domain Modeling**
   - Rich dive domain with proper state machines
   - Overlay pattern for personal dive logs
   - Effective dating for commission rules

### Issues

| ID | Severity | Issue | Impact | Recommendation |
|----|----------|-------|--------|----------------|
| A-1 | P1 | Role inconsistency between ExcursionRoster and DiveAssignment | Confusing data model, missing roles | Unify role enumeration |
| A-2 | P1 | Missing photographer/videographer roles | Can't track media staff | Add to Role choices |
| A-3 | P2 | No per-dive cost allocation | Shared boat costs can't be properly allocated | Add DiveCost model |
| A-4 | P2 | Large services.py (3,183 lines) | Maintainability | Split by domain concern |
| A-5 | P2 | Missing audit for price adjustments | No trail for pricing changes | Add to audit.py |
| A-6 | P3 | No async task infrastructure | Settlement batches are synchronous | Add Django-RQ |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DIVEOPS MODULE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   Views     │  │   Forms     │  │  Templates  │  │    URLs    │ │
│  │(staff_views)│  │  (forms)    │  │ (templates) │  │(staff_urls)│ │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └────────────┘ │
│         │                │                                          │
│         └────────────────┼──────────────────────────────────────┐   │
│                          │                                      │   │
│                          ▼                                      ▼   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      SERVICES LAYER                          │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │ services.py │ eligibility_service │ settlement_service │ ... │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                   │
│         ▼                   ▼                   ▼                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Models    │    │    Audit    │    │ Validators  │             │
│  │ (models.py) │    │ (audit.py)  │    │(validators) │             │
│  └──────┬──────┘    └─────────────┘    └─────────────┘             │
│         │                                                           │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DJANGO PRIMITIVES                                 │
├─────────────────────────────────────────────────────────────────────┤
│ basemodels │ parties │ geo │ catalog │ agreements │ documents │ ... │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Recommendations

### Immediate (P0/P1)

1. **Unify Role Enumeration**
   - Create shared `DiveRole` TextChoices
   - Apply to both ExcursionRoster and DiveAssignment
   - Add missing roles: photographer, videographer, safety

2. **Add Missing Audit Events**
   - SitePriceAdjustment create/update/delete
   - CommissionRule create/update
   - ExcursionRequirement changes

### Short-term (P2)

3. **Cost Allocation Model**
   - Design DiveCost model for per-dive costs
   - Support shared vs per-diver allocation
   - Integrate with price_snapshot

4. **Split services.py**
   - diver_services.py (diver, certification)
   - booking_services.py (booking, check-in)
   - excursion_services.py (excursion, dive)
   - financial_services.py (settlement, commission)

### Long-term (P3)

5. **Async Infrastructure**
   - Add Django-RQ for background tasks
   - Migrate settlement batch processing
   - Add email notification queue

6. **Validation Pipeline**
   - Complete Rust binary integration
   - Add gas planning calculator
   - Implement real-time dive computer sync

---

## Appendix A: File-Level Dependencies

```
models.py
├── imports from: django_basemodels, django_parties, django_geo, django_catalog,
│                 django_agreements, django_documents, django_encounters
└── imported by: services.py, forms.py, staff_views.py, selectors.py, audit.py

services.py
├── imports from: models.py, audit.py, integrations.py, validators.py,
│                 eligibility_service.py, cancellation_policy.py
└── imported by: staff_views.py, forms.py (save methods)

audit.py
├── imports from: django_audit_log
└── imported by: services.py

integrations.py
├── imports from: all django_* primitives
└── imported by: services.py, forms.py, staff_views.py
```

---

## Appendix B: Migration Timeline

| Migration | Date Added | Changes |
|-----------|------------|---------|
| 0001 | Initial | Core models: CertificationLevel, DiverProfile, DiveSite, Trip, Dive, Booking |
| 0002-0007 | Phase 2 | ExcursionType, dive_mode, price_snapshot |
| 0008-0011 | Phase 3 | Settlement, Commission, EligibilityOverride |
| 0012-0015 | Phase 4 | DiveAssignment, DiveLog, route_segments, dive_site FK |

---

*Report generated: 2026-01-05*
