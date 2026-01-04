# Architecture: diveops

**Status:** Alpha / v0.3.0
**Updated:** 2026-01-03

## Design Intent

This module demonstrates how to build a domain-specific application as a thin layer on top of django-primitives. The diving operations domain exercises most primitives in a realistic business scenario.

- **Thin**: Domain models add only diving-specific data; infrastructure is delegated to primitives
- **Composable**: Uses multiple primitives together (parties, encounters, catalog, agreements)
- **Constrained**: Postgres CHECK constraints enforce invariants at the database level
- **Temporal**: Eligibility decisions can be evaluated at any point in time
- **Adapter Pattern**: Uses `integrations.py` to centralize primitive imports

---

## Wiring Map: Real Imports + Real Boundaries

### Primitive → Diveops FK Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRIMITIVE LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  django_parties          django_geo        django_encounters                │
│  ┌──────────────┐       ┌─────────┐       ┌────────────────────┐           │
│  │ Person       │       │ Place   │       │ Encounter          │           │
│  │ Organization │       └────┬────┘       │ EncounterDefinition│           │
│  └──────┬───────┘            │            └──────────┬─────────┘           │
│         │                    │                       │                      │
├─────────┼────────────────────┼───────────────────────┼──────────────────────┤
│         │                    │                       │                      │
│         ▼                    ▼                       ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        DIVEOPS LAYER                                │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  DiverProfile.person ─────────────────────► Person                  │   │
│  │  DiverCertification.agency ───────────────► Organization            │   │
│  │  DiveTrip.dive_shop ──────────────────────► Organization            │   │
│  │  DiveSite.place ──────────────────────────► Place                   │   │
│  │  DiveTrip.encounter ──────────────────────► Encounter               │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  django_catalog           django_agreements      primitives_testbed        │
│  ┌─────────────┐         ┌──────────────┐       ┌─────────────────┐        │
│  │ Basket      │         │ Agreement    │       │ Invoice         │        │
│  │ BasketItem  │         └──────┬───────┘       │ InvoiceLineItem │        │
│  │ CatalogItem │                │               │ Price           │        │
│  └──────┬──────┘                │               └────────┬────────┘        │
│         │                       │                        │                  │
│         ▼                       ▼                        ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        BOOKING LAYER                                │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  Booking.basket ──────────────────────────► Basket                  │   │
│  │  Booking.waiver_agreement ────────────────► Agreement               │   │
│  │  Booking.invoice ─────────────────────────► Invoice                 │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Actual Import Paths (from integrations.py)

```python
# Identity primitives
from django_parties.models import Organization, Person

# Location primitives
from django_geo.models import Place

# Workflow primitives
from django_encounters.models import Encounter, EncounterDefinition

# Commerce primitives
from django_catalog.models import Basket, BasketItem, CatalogItem

# Legal primitives
from django_agreements.models import Agreement

# Sequence generation
from django_sequence.services import next_sequence

# Invoicing (testbed module built on primitives)
from primitives_testbed.invoicing.models import Invoice, InvoiceLineItem
```

### Primitive Mapping (Detailed)

| Primitive Package | Model | Diveops FK | Usage |
|-------------------|-------|------------|-------|
| `django_parties` | `Person` | `DiverProfile.person` | Diver identity (name, email) |
| `django_parties` | `Organization` | `DiveTrip.dive_shop` | Dive shop running the trip |
| `django_parties` | `Organization` | `DiverCertification.agency` | Certifying agency (PADI, SSI) |
| `django_geo` | `Place` | `DiveSite.place` | Physical location (optional) |
| `django_encounters` | `Encounter` | `DiveTrip.encounter` | Trip workflow state machine |
| `django_catalog` | `Basket` | `Booking.basket` | Commerce cart for booking |
| `django_agreements` | `Agreement` | `Booking.waiver_agreement` | Liability waiver |
| `primitives_testbed.invoicing` | `Invoice` | `Booking.invoice` | Payment tracking |

---

## Postgres-Only Features (Confirmed)

Diveops uses these Postgres-specific features:

| Feature | Location | Purpose |
|---------|----------|---------|
| `UniqueConstraint` with `condition` | `Booking`, `TripRoster`, `DiverCertification` | Partial unique indexes (soft delete aware) |
| `CheckConstraint` with `Q()` | `DiverProfile`, `DiveSite`, `DiveTrip`, `DiverCertification` | Data integrity rules |
| `CheckConstraint` with `F()` | `DiveTrip`, `DiverCertification` | Cross-field validation |
| Deferrable constraints | Not used yet | Could use for complex transactions |

### Constraint Examples

```python
# Partial unique - only active bookings count
UniqueConstraint(
    fields=["trip", "diver"],
    condition=Q(status__in=["pending", "confirmed", "checked_in"]),
    name="diveops_booking_one_active_per_trip"
)

# Check with F() - expiration must be after certification
CheckConstraint(
    check=Q(expires_on__isnull=True) | Q(expires_on__gt=F("certified_on")),
    name="expires_after_certified"
)
```

---

## Adapter Points (Integration Status)

### Implemented ✅

| Integration | Status | Location |
|-------------|--------|----------|
| Person/Organization FKs | ✅ Complete | `models.py` |
| Place FK (optional) | ✅ Complete | `DiveSite.place` |
| Encounter FK (optional) | ✅ Complete | `DiveTrip.encounter` |
| Certification normalization | ✅ Complete | `CertificationLevel`, `DiverCertification`, `TripRequirement` |
| Decisioning with requirements | ✅ Complete | `can_diver_join_trip_v2()` |
| Basket creation | ✅ Complete | `integrations.create_trip_basket()` |
| Price resolution | ✅ Complete | `integrations.resolve_trip_price()` |
| Invoice creation | ✅ Complete | `integrations.create_booking_invoice()` |

### TODO: Future Phases 🔧

| Integration | Status | Required Work |
|-------------|--------|---------------|
| Waiver workflow | 🔧 FK only | Full Agreement lifecycle |
| Tax calculation | 🔧 Not started | Add tax support to invoice |
| Agreement pricing | 🔧 Not started | Pass diver's agreements to price resolution |

### Recently Implemented ✅

| Integration | Status | Location |
|-------------|--------|----------|
| Audit logging | ✅ Complete | `audit.py` → `django_audit_log` |
| Document attachment | ✅ Complete | `DiverCertification.proof_document` → `django_documents` |

### Future Considerations

| Integration | Primitive | Use Case |
|-------------|-----------|----------|
| Work sessions | `django_worklog` | Staff time tracking on trips |

## Domain Models

```
┌─────────────────┐       ┌──────────────────┐
│  DiverProfile   │       │    DiveSite      │
│─────────────────│       │──────────────────│
│ person (FK)     │       │ name             │
│ certification   │       │ max_depth_meters │
│ total_dives     │       │ min_cert_level   │
│ medical_clear   │       │ lat/lng          │
└────────┬────────┘       └────────┬─────────┘
         │                         │
         │  ┌──────────────────────┘
         │  │
         ▼  ▼
    ┌────────────────┐
    │    DiveTrip    │
    │────────────────│
    │ dive_shop (FK) │──→ Organization
    │ dive_site (FK) │
    │ departure_time │
    │ max_divers     │
    │ price_per_diver│
    │ encounter (FK) │──→ Encounter (optional)
    └───────┬────────┘
            │
            ▼
    ┌────────────────┐
    │    Booking     │
    │────────────────│
    │ trip (FK)      │
    │ diver (FK)     │
    │ basket (FK)    │──→ Basket
    │ invoice (FK)   │──→ Invoice
    │ waiver (FK)    │──→ Agreement
    └───────┬────────┘
            │
            ▼
    ┌────────────────┐
    │  TripRoster    │
    │────────────────│
    │ trip (FK)      │
    │ diver (FK)     │
    │ booking (FK)   │
    │ checked_in_at  │
    └────────────────┘
```

## Hard Rules (Invariants)

These rules are enforced at the database level via CHECK constraints:

| Constraint | Rule | Name |
|------------|------|------|
| DiverProfile | total_dives >= 0 | `diveops_diver_total_dives_gte_zero` |
| DiveSite | max_depth_meters > 0 | `diveops_site_depth_gt_zero` |
| DiveSite | latitude BETWEEN -90 AND 90 | `diveops_site_valid_latitude` |
| DiveSite | longitude BETWEEN -180 AND 180 | `diveops_site_valid_longitude` |
| DiveTrip | return_time > departure_time | `diveops_trip_return_after_departure` |
| DiveTrip | max_divers > 0 | `diveops_trip_max_divers_gt_zero` |
| DiveTrip | price_per_diver >= 0 | `diveops_trip_price_gte_zero` |
| Booking | One active booking per diver per trip | `diveops_booking_one_active_per_trip` |
| TripRoster | One roster entry per diver per trip | `diveops_roster_one_per_trip` |

**Note:** The Booking constraint is conditional - it only applies to active bookings (pending, confirmed, checked_in). Cancelled bookings are excluded, allowing a diver to rebook after cancellation.

## Soft Rules (Eligibility)

These rules are enforced at the application layer in `decisioning.py`:

1. **Certification Level**: Diver must meet or exceed site's minimum certification
2. **Medical Clearance**: Diver must have current medical clearance
3. **Trip Status**: Trip must not be cancelled
4. **Trip Timing**: Trip must not have departed
5. **Trip Capacity**: Trip must have available spots
6. **Waiver Validity**: Diver's waiver must be current (configurable expiration)

## Waiver Expiration

Waiver validity is configurable via Django settings:

```python
# settings.py
DIVEOPS_WAIVER_VALIDITY_DAYS = 365  # Default: 365 days
# Set to None for waivers that never expire
```

Check waiver validity:
```python
diver.is_waiver_valid()  # Check as of now
diver.is_waiver_valid(as_of=some_datetime)  # Check at specific time
```

## TripRoster Roles

Each roster entry has a role indicating the diver's function on the trip:

| Role | Description |
|------|-------------|
| `DIVER` | Paying customer diver (default) |
| `DM` | Divemaster leading/assisting the trip |
| `INSTRUCTOR` | Instructor conducting training |

```python
TripRoster.objects.create(
    trip=trip,
    diver=diver,
    booking=booking,
    role="DM",  # Divemaster on this trip
    checked_in_by=user,
)
```

## Certification Level Hierarchy

```
instructor (6) > dm (5) > rescue (4) > aow (3) > ow (2) > sd (1)
```

A diver with `aow` (Advanced Open Water) can dive sites requiring `ow` or `sd`, but not `rescue` or higher.

## Service Layer

All write operations go through services:

| Service | Description |
|---------|-------------|
| `book_trip()` | Create booking, optionally create basket/invoice |
| `check_in()` | Create roster entry, update booking status |
| `start_trip()` | Transition trip to in_progress |
| `complete_trip()` | Complete trip, increment dive counts |
| `cancel_booking()` | Cancel a booking |
| `add_certification()` | Add a certification to a diver |
| `update_certification()` | Update certification details |
| `remove_certification()` | Soft delete a certification |
| `verify_certification()` | Mark certification as verified |
| `unverify_certification()` | Remove verification status |

All services are atomic (`@transaction.atomic`).

## Audit Logging

DiveOps emits audit events for domain-significant actions but does NOT store audit data locally.
The `django_audit_log` primitive owns all audit persistence.

### Why This Architecture?

1. **Separation of Concerns**: Domain logic focuses on diving operations; audit infrastructure is a cross-cutting concern handled by a dedicated primitive
2. **Compliance Ready**: All certification-related actions create immutable audit records
3. **Extractable**: DiveOps remains thin and portable - audit dependency is explicit
4. **Consistent**: All domain apps use the same audit infrastructure

### Adapter Pattern

All audit calls go through `diveops/audit.py`, never directly to `django_audit_log`:

```python
from diveops.audit import log_certification_event, Actions

log_certification_event(
    action=Actions.CERTIFICATION_VERIFIED,
    certification=cert,
    actor=request.user,
)
```

### Stable Action Constants

These strings are part of the DiveOps audit contract and must remain stable:

| Action | Description | Trigger |
|--------|-------------|---------|
| `certification_added` | New certification created | `add_certification()` |
| `certification_updated` | Certification fields changed | `update_certification()` |
| `certification_removed` | Certification soft deleted | `remove_certification()` |
| `certification_verified` | Staff verified the certification | `verify_certification()` |
| `certification_unverified` | Verification removed | `unverify_certification()` |

### Audit Event Structure

Each certification audit event includes:

```python
{
    "action": "certification_verified",
    "obj": certification,  # Target model instance
    "actor": user,         # Django User who performed action
    "changes": {},         # Field changes (for updates)
    "metadata": {
        "agency_id": "uuid",
        "agency_name": "PADI",
        "level_id": "uuid",
        "level_name": "Advanced Open Water",
        "diver_id": "uuid",
    }
}
```

### Not Audited (by design)

These actions are NOT audited because they don't represent compliance-relevant state changes:

- Reading certification data (selectors)
- Eligibility checks (decisioning)
- Booking/trip operations (separate audit scope)

## Selector Layer

Read-only queries with N+1 prevention:

| Selector | Description |
|----------|-------------|
| `list_upcoming_trips()` | Upcoming trips with filters |
| `get_trip_with_roster()` | Trip detail with full roster |
| `list_diver_bookings()` | Diver's bookings with trip data |
| `list_dive_sites()` | Sites filtered by certification |
| `list_shop_trips()` | Shop's trips with booking counts |

All selectors use `select_related()` and `prefetch_related()` appropriately.

## Dependencies

**Depends on:**
- django-parties (Person, Organization)
- django-geo (Place)
- django-encounters (Encounter, EncounterDefinition)
- django-catalog (Basket, BasketItem, CatalogItem)
- django-agreements (Agreement)
- django-documents (Document) - for certification proof uploads
- django-audit-log (log) - for certification audit events
- django-ledger (Account, Transaction)
- django-sequence (next_sequence)
- primitives_testbed.invoicing (Invoice, InvoiceLineItem)

**Depended on by:**
- None (this is a domain application, not a reusable primitive)

## File Structure

```
diveops/
├── __init__.py
├── apps.py              # Django app config
├── audit.py             # Audit logging adapter (wraps django_audit_log)
├── integrations.py      # Primitive imports adapter (centralized)
├── models.py            # Domain models (5 models)
├── services.py          # Write operations (atomic)
├── selectors.py         # Read operations (optimized)
├── decisioning.py       # Eligibility rules
├── exceptions.py        # Custom exceptions
├── forms.py             # Django forms for staff views
├── staff_urls.py        # Staff portal URL patterns
├── staff_views.py       # Staff portal views
├── ARCHITECTURE.md      # This document
├── templates/diveops/   # Staff portal templates
└── migrations/
    ├── __init__.py
    ├── 0001_initial.py
    └── ...
```

### integrations.py

Centralizes all primitive package imports following the adapter pattern:

```python
from primitives_testbed.diveops.integrations import (
    Person, Organization,  # django-parties
    Place,                 # django-geo
    Encounter,             # django-encounters
    Basket, BasketItem,    # django-catalog
    Agreement,             # django-agreements
    next_sequence,         # django-sequence
)
```

This makes primitive dependencies explicit and easier to maintain.

## Usage Examples

### Book a trip

```python
from primitives_testbed.diveops.services import book_trip
from primitives_testbed.diveops.decisioning import can_diver_join_trip

# Check eligibility first
result = can_diver_join_trip(diver, trip, as_of=timezone.now())
if not result.allowed:
    print(f"Not eligible: {result.reasons}")
    print(f"Required actions: {result.required_actions}")
else:
    booking = book_trip(trip, diver, user, create_invoice=True)
```

### Check in a diver

```python
from primitives_testbed.diveops.services import check_in

roster = check_in(booking, user, require_waiver=True)
```

### Complete a trip

```python
from primitives_testbed.diveops.services import complete_trip

trip = complete_trip(trip, user)
# All checked-in divers now have +1 total_dives
```

### Rebook after cancellation

```python
from primitives_testbed.diveops.services import book_trip, cancel_booking

# Original booking
booking = book_trip(trip, diver, user)

# Cancel
cancel_booking(booking, user)

# Rebook - allowed because cancelled bookings don't block
new_booking = book_trip(trip, diver, user)
```

## Testing Strategy

Tests are organized by concern:

| Test File | Coverage |
|-----------|----------|
| `test_models.py` | Model creation, DB constraints |
| `test_services.py` | Service functions, atomicity |
| `test_decisioning.py` | Eligibility rules, temporal evaluation |

All tests use pytest with `@pytest.mark.django_db` for database access.

## Future Considerations

1. **Waiver Management**: Full waiver workflow with django-agreements
2. **Equipment Tracking**: Link to django-catalog for rental equipment
3. **Dive Logs**: Post-trip dive logging with django-documents
4. **Instructor Assignment**: Link staff to trips via django-worklog
5. **Multi-dive Trips**: Support multiple dives per trip
