# DiveOps Trip/Excursion Semantic Refactor

**Date**: 2026-01-04
**Status**: Planning

---

## 1. Architecture Documents Read

| Document | Key Insights |
|----------|--------------|
| `CLAUDE.md` | TDD workflow, service layer pattern, audit logging style |
| `docs/book/*.md` | All 18 primitives architecture chapters |
| `diveops/ARCHITECTURE.md` | Current diveops design |
| `diveops/models.py` | Current DiveTrip = operational outing |
| `diveops/services.py` | book_trip, check_in, start_trip, complete_trip |

---

## 2. Primitives Inventory (18 Packages)

### Foundation Layer
| Package | Purpose | Relevance to Refactor |
|---------|---------|----------------------|
| django-basemodels | UUID, timestamps, soft delete | All new models inherit BaseModel |
| django-singleton | Single-instance config | Shop settings |
| django-modules | Model grouping | Module organization |
| django-layers | Import boundaries | Layer enforcement |

### Identity Layer
| Package | Purpose | Relevance to Refactor |
|---------|---------|----------------------|
| django-parties | Party pattern (Person, Org) | Divers, shops, affiliates |
| django-rbac | Role-based access | Staff permissions |

### Infrastructure Layer
| Package | Purpose | Relevance to Refactor |
|---------|---------|----------------------|
| django-decisioning | Time semantics, idempotency | effective_at for excursion scheduling |
| django-audit-log | Immutable audit trail | All Trip/Excursion mutations |

### Domain Layer
| Package | Purpose | Relevance to Refactor |
|---------|---------|----------------------|
| django-encounters | State machine | Excursion workflow states |
| django-catalog | CatalogItem, Basket, WorkItem | Trip packages as catalog items |
| django-worklog | Work session timing | Dive logging |
| django-geo | Place, ServiceArea | Dive sites (already used) |
| django-ledger | Double-entry accounting | Commission posting |

### Content Layer
| Package | Purpose | Relevance to Refactor |
|---------|---------|----------------------|
| django-documents | File attachments | Dive logs, photos |
| django-notes | Notes/tagging | Trip notes |
| django-agreements | Contracts, waivers | Waiver tracking (already used) |

### Value Objects
| Package | Purpose | Relevance to Refactor |
|---------|---------|----------------------|
| django-money | Immutable Money | Pricing (already used) |
| django-sequence | Human-readable IDs | Trip/Excursion numbers |

---

## 3. Semantic Mapping: Current → Target

### Authoritative Definitions

| Concept | Definition | Cardinality |
|---------|------------|-------------|
| **Dive** | Atomic, loggable unit of underwater activity | Belongs to 1 Excursion |
| **Excursion** | Operational fulfillment (single calendar day) | Contains 1..N Dives |
| **Trip** | Commercial package/itinerary (may span days) | Contains 1..N Excursions |

### Current Code Mapping

| Current Entity | Target Entity | Notes |
|----------------|---------------|-------|
| `DiveTrip` | `Excursion` | Rename + add Dive child |
| (new) | `Trip` | Commercial wrapper |
| (new) | `Dive` | Atomic dive log |
| `Booking` | `Booking` | Links to Excursion or Trip |
| `TripRoster` | `ExcursionRoster` | Rename |
| `TripRequirement` | `ExcursionRequirement` | Rename |

---

## 4. Primitive → Domain Mapping

### Which Primitive Handles What

| Domain Concept | Primitive | How |
|----------------|-----------|-----|
| Excursion scheduling | django_decisioning | TimeSemanticsMixin for effective_at |
| Excursion state machine | django_encounters | Encounter FK (scheduled→boarding→in_progress→completed) |
| Trip as sellable product | django_catalog | CatalogItem represents trip packages |
| Trip sales workflow | django_catalog | Basket → commit → WorkItem spawning |
| Trip→Excursion fulfillment | (domain logic) | Trip line items derive Excursion schedule |
| Commission calculation | django_ledger | Account per affiliate, transaction per sale |
| Commission posting | django_ledger | Entry with GenericFK to Trip line item |
| Waiver agreements | django_agreements | Agreement per booking |
| Audit trail | django_audit_log | All mutations emit events |
| Dive site location | django_geo | Place FK (already implemented) |
| Diver identity | django_parties | Person → DiverProfile |
| Shop identity | django_parties | Organization |

---

## 5. Current DiveTrip Usage Inventory

### Model (models.py:477-579)
```python
class DiveTrip(BaseModel):
    dive_shop = FK(Organization)
    dive_site = FK(DiveSite)
    encounter = OneToOne(Encounter, null=True)  # state machine
    departure_time = DateTimeField
    return_time = DateTimeField
    max_divers = PositiveIntegerField
    price_per_diver = DecimalField
    currency = CharField
    status = CharField(choices=STATUS_CHOICES)  # scheduled, boarding, in_progress, completed, cancelled
    completed_at = DateTimeField(null=True)
    created_by = FK(User)
```

### Services (services.py)
| Service | Lines | Action |
|---------|-------|--------|
| `book_trip()` | 87-182 | Create booking + optional invoice |
| `check_in()` | 184-250 | Create roster entry |
| `start_trip()` | 253-298 | Transition to in_progress |
| `complete_trip()` | 301-345 | Transition to completed |

### Selectors (selectors.py)
| Selector | Lines | Returns |
|----------|-------|---------|
| `list_upcoming_trips()` | 25-60 | Future trips for shop |
| `get_trip_with_roster()` | 79-108 | Trip + roster prefetch |
| `list_shop_trips()` | 189-230 | All trips for shop |
| `get_trip_with_requirements()` | 293-320 | Trip + requirements |
| `trip_audit_feed()` | 384-420 | Audit events for trip |

### Views (staff_views.py)
| View | Purpose |
|------|---------|
| `TripListView` | List all trips |
| `TripDetailView` | Trip detail + roster |
| `BookDiverView` | Book diver on trip |
| `CheckInView` | Check in diver |
| `StartTripView` | Start trip |
| `CompleteTripView` | Complete trip |

### Templates
| Template | Purpose |
|----------|---------|
| `trip_list.html` | Trip listing table |
| `trip_detail.html` | Trip detail page |

---

## 6. Refactor Plan

### Phase A: Introduce Excursion (Rename DiveTrip)

**Strategy**: Rename DiveTrip → Excursion with alias for backwards compatibility

1. **Create Excursion model** (new file or extend models.py)
   - Copy DiveTrip fields
   - Add `trip` FK (nullable) for package linkage
   - Add single-day constraint (departure/return same calendar day)

2. **Create Dive model**
   - `excursion` FK
   - `sequence` (dive number within excursion: 1, 2, 3)
   - `started_at`, `ended_at`
   - `max_depth_m`, `bottom_time_min`
   - `notes`

3. **Migration strategy**
   - Rename table: `diveops_divetrip` → `diveops_excursion`
   - Create alias: `DiveTrip = Excursion` for backwards compatibility
   - Update all FKs atomically

4. **Rename services**
   - `book_trip()` → `book_excursion()` (keep `book_trip` as alias)
   - `start_trip()` → `start_excursion()`
   - `complete_trip()` → `complete_excursion()`

### Phase B: Introduce Trip (Commercial Package)

1. **Create Trip model**
   ```python
   class Trip(BaseModel):
       # Identity
       name = CharField
       code = CharField (unique, from django_sequence)

       # Commerce linkage
       catalog_item = FK(CatalogItem, null=True)

       # Structure
       start_date = DateField
       end_date = DateField

       # Ownership
       dive_shop = FK(Organization)

       # Status
       status = CharField (draft, confirmed, in_progress, completed, cancelled)
   ```

2. **Create TripDay model** (optional, for multi-day structure)
   ```python
   class TripDay(BaseModel):
       trip = FK(Trip)
       day_number = PositiveSmallIntegerField
       date = DateField
       notes = TextField
   ```

3. **Link Excursion → Trip**
   - Add `trip = FK(Trip, null=True)` to Excursion
   - Add `trip_day = FK(TripDay, null=True)` to Excursion

4. **TripService**
   ```python
   def create_trip_from_basket(basket, actor) -> Trip:
       """Create Trip from committed basket, derive excursion schedule."""

   def schedule_excursion(trip, site, departure_time, return_time, actor) -> Excursion:
       """Add excursion to trip itinerary."""

   def finalize_trip(trip, actor) -> Trip:
       """Lock itinerary, notify participants."""
   ```

### Phase C: Commission Integration

1. **Create commission accounts** (use django_ledger)
   - Account per affiliate/partner with GenericFK owner
   - Account type: "commission_payable"

2. **Commission rules** (already in catalog?)
   - Default commission rate per catalog item
   - Override rules per affiliate

3. **Post commission on fulfillment**
   ```python
   def post_trip_commission(trip, actor):
       """Called when trip.status → completed"""
       for line_item in trip.line_items:
           if line_item.has_commission:
               record_commission_entry(...)
   ```

### Phase D: API/UI Compatibility

1. **Operator UI** → Shows "Excursions"
   - Rename "Trips" → "Excursions" in staff templates
   - Update URLs: `/trips/` stays working but internally routes to excursions

2. **Sales UI** → Shows "Trips" (packages)
   - New views for Trip package management
   - Trip builder: select dates, add excursions

3. **API endpoints**
   - `/api/trips/` → deprecated, redirect to `/api/excursions/`
   - `/api/excursions/` → new canonical endpoint
   - `/api/packages/` → Trip packages (new)

---

## 7. File-Level Changes

| File | Action |
|------|--------|
| `models.py` | Add Excursion (alias DiveTrip), Dive, Trip, TripDay, TripLineItem |
| `services.py` | Add ExcursionService, TripService; alias old names |
| `selectors.py` | Rename trip_ → excursion_; add trip package selectors |
| `audit.py` | Add excursion/dive/trip audit actions |
| `staff_views.py` | Rename TripXxxView → ExcursionXxxView; add TripPackageViews |
| `staff_urls.py` | Add /excursions/ routes; keep /trips/ as alias |
| `templates/` | Rename trip_*.html → excursion_*.html; add trip package templates |
| `migrations/` | Multi-step rename + new tables |

---

## 8. Migration Strategy

### Step 1: Add new models (non-breaking)
```python
# 0011_add_excursion_models.py
- Create Excursion table (copy of DiveTrip structure)
- Create Dive table
- Create Trip table
- Create TripDay table
```

### Step 2: Data migration
```python
# 0012_migrate_divetrip_to_excursion.py
- Copy all DiveTrip rows to Excursion
- Update FKs in Booking, TripRoster, TripRequirement
```

### Step 3: Cleanup
```python
# 0013_remove_divetrip.py
- Drop DiveTrip table
- (Keep Python alias: DiveTrip = Excursion)
```

### Rollback Note
- Keep DiveTrip alias in Python code for 2 releases
- Log deprecation warnings on DiveTrip usage
- Remove alias in v2.0

---

## 9. Test Plan

| Test Category | Tests |
|---------------|-------|
| Excursion single-day constraint | departure/return must be same calendar day |
| Excursion state transitions | scheduled→boarding→in_progress→completed |
| Dive belongs to Excursion | FK constraint, cascade delete |
| Trip multi-day container | start_date ≤ end_date |
| Trip contains Excursions | 1..N relationship |
| Excursion standalone | Excursion without Trip (walk-ins) |
| Backwards compat | `DiveTrip` alias works |
| Backwards compat | `/trips/` endpoints work |
| Audit events | All mutations logged |
| Commission posting | Ledger entries on completion |

---

## 10. Acceptance Criteria

- [ ] Excursion model with single-day constraint
- [ ] Dive model as atomic loggable unit
- [ ] Trip model as multi-day commercial package
- [ ] Excursion can exist standalone (walk-ins)
- [ ] Trip contains 1..N Excursions
- [ ] DiveTrip alias works (backwards compat)
- [ ] /trips/ endpoints work (backwards compat)
- [ ] Operator UI shows "Excursions"
- [ ] Sales UI shows "Trips" (packages)
- [ ] All CRUD emits audit events
- [ ] Commission posting on trip completion
- [ ] Tests for all constraints
