# Architecture: diveops

**Status:** Alpha / v0.2.0

## Design Intent

This module demonstrates how to build a domain-specific application as a thin layer on top of django-primitives. The diving operations domain exercises most primitives in a realistic business scenario.

- **Thin**: Domain models add only diving-specific data; infrastructure is delegated to primitives
- **Composable**: Uses multiple primitives together (parties, encounters, catalog, agreements)
- **Constrained**: Postgres CHECK constraints enforce invariants at the database level
- **Temporal**: Eligibility decisions can be evaluated at any point in time
- **Adapter Pattern**: Uses `integrations.py` to centralize primitive imports

## Primitive Mapping

| Primitive | Diveops Usage |
|-----------|---------------|
| `django-parties` | `DiverProfile.person` → Person, `DiveTrip.dive_shop` → Organization |
| `django-geo` | `DiveSite.place` → Place (optional) |
| `django-encounters` | `DiveTrip.encounter` → Encounter for trip workflow tracking |
| `django-catalog` | `Booking.basket` → Basket for booking commerce |
| `django-agreements` | `Booking.waiver_agreement` → Agreement for liability waivers |
| `django-invoicing` | `Booking.invoice` → Invoice for payment tracking |
| `django-ledger` | Invoice → Transaction for double-entry accounting |
| `django-sequence` | Invoice number generation |

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

All services are atomic (`@transaction.atomic`).

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
├── integrations.py      # Primitive imports adapter (centralized)
├── models.py            # Domain models (5 models)
├── services.py          # Write operations (atomic)
├── selectors.py         # Read operations (optimized)
├── decisioning.py       # Eligibility rules
├── exceptions.py        # Custom exceptions
├── ARCHITECTURE.md      # This document
└── migrations/
    ├── __init__.py
    ├── 0001_initial.py
    └── 0002_refactor_constraints_add_features.py
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
