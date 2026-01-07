# DiveOps Pricing Architecture

## Overview

This document describes how django-primitives compose to support diveops pricing with dual cost/charge tracking, tiered boat pricing, gas-specific pricing, and equipment rentals.

## Design Principles

1. **Use primitives, don't reinvent**: Pricing logic builds on django-catalog, django-agreements, django-ledger, and django-money.
2. **Dual tracking**: Every priced component tracks both `shop_cost` (expense) and `customer_charge` (revenue).
3. **Immutable snapshots**: Booking prices are frozen at booking time; subsequent price changes don't affect historical bookings.
4. **Audit everything**: All pricing operations emit audit events with input parameters and output hashes.
5. **Deterministic and reproducible**: Given the same inputs, pricing calculations always produce the same outputs.

## Primitive Composition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRICING DATA SOURCES                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐     ┌─────────────────────┐     ┌───────────────┐ │
│  │    Price (charge)   │     │ Agreement (vendor)  │     │  CatalogItem  │ │
│  │                     │     │                     │     │               │ │
│  │ customer_charge     │     │ terms: {            │     │ Components:   │ │
│  │ (what customer pays)│     │   boat_tier: {...}, │     │ - Dive        │ │
│  │                     │     │   gas_fills: {...}, │     │ - Tank fill   │ │
│  │ Scopes:             │     │   equipment: {...}  │     │ - Guide fee   │ │
│  │ - agreement         │     │ }                   │     │ - Park fee    │ │
│  │ - party             │     │ (shop costs)        │     │ - Boat share  │ │
│  │ - organization      │     │                     │     │ - Equipment   │ │
│  │ - global            │     │                     │     │               │ │
│  └──────────┬──────────┘     └──────────┬──────────┘     └───────┬───────┘ │
│             │                           │                        │          │
│             └───────────────────────────┼────────────────────────┘          │
│                                         │                                   │
│                                         ▼                                   │
│                          ┌──────────────────────────────┐                   │
│                          │      Pricing Service         │                   │
│                          │                              │                   │
│                          │  quote_excursion()           │                   │
│                          │  snapshot_booking_pricing()  │                   │
│                          │  add_equipment_rental()      │                   │
│                          └──────────────┬───────────────┘                   │
│                                         │                                   │
└─────────────────────────────────────────┼───────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRICING OUTPUT                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Quote / Snapshot                              │    │
│  │                                                                      │    │
│  │  lines: [                                                            │    │
│  │    { key: "boat_share", label: "Boat Charter",                       │    │
│  │      allocation: "shared", shop_cost: 2500, customer_charge: 2500,   │    │
│  │      currency: "MXN", refs: [...] },                                 │    │
│  │    { key: "guide_fee", label: "Guide Fee",                           │    │
│  │      allocation: "shared", shop_cost: 500, customer_charge: 600,     │    │
│  │      currency: "MXN", refs: [...] },                                 │    │
│  │    { key: "air_fill", label: "Air Fill x2",                          │    │
│  │      allocation: "per_diver", shop_cost: 80, customer_charge: 0,     │    │
│  │      currency: "MXN", refs: [...] },                                 │    │
│  │    ...                                                               │    │
│  │  ],                                                                  │    │
│  │  totals: {                                                           │    │
│  │    shared_cost: 3000, shared_charge: 3100,                           │    │
│  │    per_diver_cost: 130, per_diver_charge: 50,                        │    │
│  │    total_cost_per_diver: 630, total_charge_per_diver: 567,           │    │
│  │    margin_per_diver: -63, diver_count: 6                             │    │
│  │  },                                                                  │    │
│  │  metadata: { version: "1.0", timestamp: "...", hash: "sha256:..." }  │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Models

### 1. CatalogItem (from django-catalog)

Dive components are represented as CatalogItems:

```python
# Component items (created via data migration or admin)
CatalogItem(kind="service", display_name="Tank Fill - Air", service_category="other")
CatalogItem(kind="service", display_name="Tank Fill - EAN32", service_category="other")
CatalogItem(kind="service", display_name="Guide Fee", service_category="other")
CatalogItem(kind="service", display_name="Park Bracelet", service_category="other")
CatalogItem(kind="service", display_name="Boat Share", service_category="other")
CatalogItem(kind="stock_item", display_name="BCD Rental", service_category="other")
```

### 2. Price (extended from pricing module)

Extended to support optional cost tracking:

```python
class Price(models.Model):
    catalog_item = ForeignKey(CatalogItem)

    # Customer charge (what customer pays)
    amount = DecimalField()  # existing
    currency = CharField()   # existing

    # Shop cost (what shop pays) - NEW
    cost_amount = DecimalField(null=True, blank=True)
    cost_currency = CharField(null=True, blank=True)

    # Scopes (existing)
    organization = ForeignKey(Organization, null=True)
    party = ForeignKey(Person, null=True)
    agreement = ForeignKey(Agreement, null=True)

    # Effective dating (existing)
    valid_from = DateTimeField()
    valid_to = DateTimeField(null=True)
```

### 3. Agreement.terms for Vendor Pricing

Vendor agreements store complex pricing rules in `terms` JSON:

```python
# Agreement between dive_shop and boat_vendor
Agreement(
    party_a=dive_shop,           # Organization
    party_b=boat_vendor,         # Organization (supplier)
    scope_type="vendor_pricing",
    scope_ref=dive_site,         # DiveSite (optional)
    terms={
        "boat_charter": {
            "base_cost": "2200.00",
            "included_divers": 4,
            "overage_per_diver": "150.00",
            "currency": "MXN"
        }
    }
)

# Agreement for gas fills
Agreement(
    party_a=dive_shop,
    party_b=gas_supplier,
    scope_type="vendor_pricing",
    terms={
        "gas_fills": {
            "air": {"cost": "40.00", "currency": "MXN"},
            "ean32": {"cost": "60.00", "currency": "MXN"},
            "ean36": {"cost": "70.00", "currency": "MXN"}
        }
    }
)
```

### 4. DiverEquipmentRental (diveops glue)

Links equipment to booking with snapshot pricing:

```python
class DiverEquipmentRental(BaseModel):
    booking = ForeignKey(Booking, on_delete=CASCADE)
    catalog_item = ForeignKey(CatalogItem, on_delete=PROTECT)  # Equipment item
    quantity = PositiveSmallIntegerField(default=1)

    # Snapshot at rental time (immutable)
    unit_cost_amount = DecimalField()
    unit_cost_currency = CharField()
    unit_charge_amount = DecimalField()
    unit_charge_currency = CharField()

    # Audit
    price_rule_id = UUIDField(null=True)  # Reference to Price used
    vendor_agreement_id = UUIDField(null=True)  # Reference to vendor Agreement
    rented_at = DateTimeField(auto_now_add=True)
    rented_by = ForeignKey(User)
```

### 5. BookingPricingSnapshot (stored in Booking.price_snapshot)

```json
{
  "schema_version": "1.0.0",
  "tool": "diveops-pricing",
  "generated_at": "2024-01-05T10:00:00Z",
  "input_hash": "sha256:abc123...",
  "output_hash": "sha256:def456...",

  "inputs": {
    "excursion_id": "uuid",
    "diver_count": 6,
    "dives_count": 2,
    "gas_type": "air",
    "site_id": "uuid"
  },

  "lines": [
    {
      "key": "boat_share",
      "label": "Boat Charter - Shipwreck",
      "allocation": "shared",
      "shop_cost": {"amount": "2500.00", "currency": "MXN"},
      "customer_charge": {"amount": "2500.00", "currency": "MXN"},
      "refs": {
        "vendor_agreement_id": "uuid",
        "dive_site_id": "uuid"
      }
    },
    {
      "key": "guide_fee",
      "label": "Guide Fee",
      "allocation": "shared",
      "shop_cost": {"amount": "500.00", "currency": "MXN"},
      "customer_charge": {"amount": "600.00", "currency": "MXN"},
      "refs": {
        "price_rule_id": "uuid"
      }
    },
    {
      "key": "air_fill",
      "label": "Air Fill x2",
      "allocation": "per_diver",
      "shop_cost": {"amount": "80.00", "currency": "MXN"},
      "customer_charge": {"amount": "0.00", "currency": "MXN"},
      "refs": {
        "vendor_agreement_id": "uuid",
        "catalog_item_id": "uuid"
      }
    },
    {
      "key": "park_bracelet",
      "label": "Park Entry Fee",
      "allocation": "per_diver",
      "shop_cost": {"amount": "50.00", "currency": "MXN"},
      "customer_charge": {"amount": "50.00", "currency": "MXN"},
      "refs": {
        "price_rule_id": "uuid"
      }
    }
  ],

  "equipment_rentals": [
    {
      "diver_id": "uuid",
      "catalog_item_id": "uuid",
      "description": "BCD Rental",
      "quantity": 1,
      "unit_cost": {"amount": "0.00", "currency": "MXN"},
      "unit_charge": {"amount": "200.00", "currency": "MXN"}
    }
  ],

  "totals": {
    "shared_cost": {"amount": "3000.00", "currency": "MXN"},
    "shared_charge": {"amount": "3100.00", "currency": "MXN"},
    "per_diver_cost": {"amount": "130.00", "currency": "MXN"},
    "per_diver_charge": {"amount": "50.00", "currency": "MXN"},
    "shared_cost_per_diver": {"amount": "500.00", "currency": "MXN"},
    "shared_charge_per_diver": {"amount": "516.67", "currency": "MXN"},
    "total_cost_per_diver": {"amount": "630.00", "currency": "MXN"},
    "total_charge_per_diver": {"amount": "566.67", "currency": "MXN"},
    "margin_per_diver": {"amount": "-63.33", "currency": "MXN"},
    "diver_count": 6
  }
}
```

## Tiered Boat Pricing Calculation

The tiered boat pricing is stored in a vendor Agreement and calculated by the pricing service:

```python
def calculate_boat_cost(dive_site, diver_count, as_of=None):
    """Calculate boat cost using tiered pricing from vendor agreement.

    Args:
        dive_site: DiveSite instance
        diver_count: Number of divers
        as_of: Point in time for pricing (default: now)

    Returns:
        Money: Total boat cost
    """
    # Find active vendor agreement for this site
    agreement = Agreement.objects.filter(
        scope_type="vendor_pricing",
        scope_ref_content_type=ContentType.objects.get_for_model(DiveSite),
        scope_ref_id=str(dive_site.pk),
    ).current().first()

    if not agreement:
        raise PricingError(f"No vendor agreement found for site {dive_site}")

    boat_tier = agreement.terms.get("boat_charter", {})
    base_cost = Decimal(boat_tier.get("base_cost", "0"))
    included = boat_tier.get("included_divers", 4)
    overage = Decimal(boat_tier.get("overage_per_diver", "0"))
    currency = boat_tier.get("currency", "MXN")

    # Calculate total
    if diver_count <= included:
        total = base_cost
    else:
        total = base_cost + ((diver_count - included) * overage)

    return Money(total, currency)
```

**Example Calculation:**

| Divers | Base (4 included) | Overage | Total | Per Diver |
|--------|-------------------|---------|-------|-----------|
| 4 | 2,200 | 0 | 2,200 | 550.00 |
| 5 | 2,200 | 150 | 2,350 | 470.00 |
| 6 | 2,200 | 300 | 2,500 | 416.67 |
| 8 | 2,200 | 600 | 2,800 | 350.00 |

## Rounding Rules

All monetary calculations use banker's rounding (ROUND_HALF_EVEN):

```python
from decimal import Decimal, ROUND_HALF_EVEN

def round_money(amount: Decimal, currency: str = "MXN") -> Decimal:
    """Round to 2 decimal places using banker's rounding."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

# Per-diver allocation of shared costs
per_diver = round_money(shared_total / diver_count)

# Handle remainder: first N divers get +0.01 if needed
remainder = shared_total - (per_diver * diver_count)
```

## Service Functions

### quote_excursion()

Generates a non-binding price breakdown:

```python
def quote_excursion(
    *,
    excursion_id: UUID,
    actor_id: UUID,
    options: dict = None,
) -> dict:
    """Generate a pricing quote for an excursion.

    Args:
        excursion_id: Excursion to quote
        actor_id: User requesting quote
        options: Override options (gas_type, equipment, etc.)

    Returns:
        dict: Quote breakdown with lines, totals, metadata

    Emits:
        audit: excursion.quote.generated
    """
```

### snapshot_booking_pricing()

Creates an immutable pricing snapshot and ledger entries:

```python
@transaction.atomic
def snapshot_booking_pricing(
    *,
    booking_id: UUID,
    actor_id: UUID,
) -> Booking:
    """Create immutable pricing snapshot and ledger entries.

    Args:
        booking_id: Booking to snapshot
        actor_id: User creating snapshot

    Returns:
        Booking: Updated with price_snapshot

    Emits:
        audit: excursion.pricing.snapshotted

    Creates ledger entries:
        - Revenue entries (customer charges)
        - Expense entries (shop costs)
    """
```

### add_equipment_rental()

Records equipment rental for a diver:

```python
@transaction.atomic
def add_equipment_rental(
    *,
    booking_id: UUID,
    diver_id: UUID,
    catalog_item_id: UUID,
    quantity: int,
    actor_id: UUID,
) -> DiverEquipmentRental:
    """Add equipment rental to a booking.

    Args:
        booking_id: Booking to add rental to
        diver_id: Diver renting equipment
        catalog_item_id: Equipment catalog item
        quantity: Number of items
        actor_id: User adding rental

    Returns:
        DiverEquipmentRental: Created rental record

    Emits:
        audit: diver.equipment.rented
    """
```

## Ledger Integration

When a booking is confirmed, ledger entries are created:

```python
# Revenue entry (what customer pays)
Entry(
    transaction=tx,
    account=revenue_account,
    entry_type="credit",
    amount=total_charge,
    description="Excursion booking revenue"
)

# Expense/COGS entry (what shop pays)
Entry(
    transaction=tx,
    account=expense_account,
    entry_type="debit",
    amount=total_cost,
    description="Excursion booking costs"
)
```

## Audit Events

| Action | When | Payload |
|--------|------|---------|
| `excursion.quote.generated` | quote_excursion() called | excursion_id, diver_count, output_hash |
| `excursion.pricing.snapshotted` | Booking pricing frozen | booking_id, snapshot_hash, ledger_tx_id |
| `diver.equipment.rented` | Equipment added to booking | booking_id, diver_id, item_id, cost, charge |
| `pricing.validation.failed` | Misconfiguration detected | excursion_id, errors |

## Example: Shipwreck Trip, 6 Divers, 2 Tanks

**Input:**
- Site: Shipwreck (boat_tier: base=2200, included=4, overage=150)
- Divers: 6
- Tanks: 2 per diver
- Gas: Air (cost=40/fill, charge=0 included)
- Guide: cost=500, charge=600
- Park: cost=50, charge=50 per diver
- 1 diver rents BCD (cost=0, charge=200)

**Calculation:**

| Item | Allocation | Shop Cost | Customer Charge |
|------|------------|-----------|-----------------|
| Boat (2200 + 2×150) | shared | 2,500 | 2,500 |
| Guide | shared | 500 | 600 |
| Air fill ×2 | per_diver | 80 | 0 |
| Park bracelet | per_diver | 50 | 50 |
| **Subtotal** | | | |
| BCD rental (1 diver) | per_selected | 0 | 200 |

**Totals (6 divers):**

| Metric | Amount |
|--------|--------|
| Shared cost | 3,000 MXN |
| Shared charge | 3,100 MXN |
| Per-diver cost | 130 MXN |
| Per-diver charge | 50 MXN |
| Shared cost/diver | 500.00 MXN |
| Shared charge/diver | 516.67 MXN |
| **Total cost/diver** | **630.00 MXN** |
| **Total charge/diver** | **566.67 MXN** |
| Margin/diver | -63.33 MXN |

**Output Schema:**
```json
{
  "schema_version": "1.0.0",
  "inputs": {
    "excursion_id": "...",
    "site_name": "Shipwreck",
    "diver_count": 6,
    "dives_count": 2,
    "gas_type": "air"
  },
  "lines": [
    {"key": "boat_share", "allocation": "shared", "shop_cost": "2500.00", "customer_charge": "2500.00", "currency": "MXN"},
    {"key": "guide_fee", "allocation": "shared", "shop_cost": "500.00", "customer_charge": "600.00", "currency": "MXN"},
    {"key": "air_fill", "allocation": "per_diver", "shop_cost": "80.00", "customer_charge": "0.00", "currency": "MXN"},
    {"key": "park_bracelet", "allocation": "per_diver", "shop_cost": "50.00", "customer_charge": "50.00", "currency": "MXN"}
  ],
  "equipment_rentals": [
    {"diver_id": "...", "description": "BCD Rental", "unit_cost": "0.00", "unit_charge": "200.00", "currency": "MXN"}
  ],
  "totals": {
    "shared_cost": "3000.00",
    "shared_charge": "3100.00",
    "per_diver_cost": "130.00",
    "per_diver_charge": "50.00",
    "total_cost_per_diver": "630.00",
    "total_charge_per_diver": "566.67",
    "margin_per_diver": "-63.33",
    "diver_count": 6,
    "currency": "MXN"
  },
  "metadata": {
    "version": "1.0.0",
    "timestamp": "2024-01-05T10:00:00Z",
    "input_hash": "sha256:...",
    "output_hash": "sha256:..."
  }
}
```

## File Structure

```
testbed/primitives_testbed/
├── pricing/
│   ├── models.py          # Price extended with cost_amount
│   ├── selectors.py       # resolve_price, resolve_cost
│   └── migrations/
│       └── 0004_price_cost_fields.py
│
└── diveops/
    ├── pricing/
    │   ├── __init__.py
    │   ├── models.py      # DiverEquipmentRental
    │   ├── services.py    # quote_excursion, snapshot_booking_pricing
    │   ├── calculators.py # boat_cost, gas_cost calculations
    │   ├── snapshots.py   # build_pricing_snapshot
    │   └── exceptions.py  # PricingError, ConfigurationError
    ├── audit.py           # Extended with pricing actions
    └── migrations/
        └── 0016_diver_equipment_rental.py
```

## Configuration Validation

```python
def validate_pricing_configuration(excursion_id: UUID) -> list[str]:
    """Validate that all required pricing is configured.

    Returns:
        list: Warning/error messages (empty = valid)

    Checks:
        - Vendor agreement exists for site (boat pricing)
        - Gas fill pricing configured
        - Guide fee price exists
        - Park fee price exists (if site requires)
    """
```
