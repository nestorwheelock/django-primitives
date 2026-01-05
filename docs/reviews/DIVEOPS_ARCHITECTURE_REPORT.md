# DiveOps Current Architecture Report

**Purpose**: Context for evaluating ChatGPT's DivePlan proposal against what's already built.

---

## Model Hierarchy (Already Implemented)

```
ExcursionType (Product Template)
    │
    └── ExcursionTypeDive[] (Dive Templates, 1..N per type)
            │
            ▼ [instantiates]
Excursion (Scheduled Event)
    │
    ├── Dive[] (Actual Dives, 1..N per excursion)
    │       │
    │       └── DiveAssignment[] (Diver ↔ Dive participation + status)
    │               │
    │               └── DiveLog (Personal dive record, overlay pattern)
    │
    └── Booking[] (Customer registrations)
```

---

## What Each Model Does

### 1. ExcursionType (Product Catalog Template)

**Already exists.** Defines a bookable product offering.

```python
ExcursionType:
    name: str              # "Morning 2-Tank Boat Dive"
    slug: str              # "morning-2-tank-boat"
    description: text
    dive_mode: enum        # boat | shore | cenote | cavern
    time_of_day: enum      # day | night | dawn | dusk
    max_depth_meters: int
    typical_duration_minutes: int
    dives_per_excursion: int
    min_certification_level: FK(CertificationLevel)
    requires_cert: bool
    is_training: bool      # for DSD
    suitable_sites: M2M(DiveSite)
    base_price: Decimal
    is_active: bool
```

### 2. ExcursionTypeDive (Dive Template within Product)

**Already exists.** Defines individual dive specifications within a product type.

```python
ExcursionTypeDive:
    excursion_type: FK(ExcursionType)
    sequence: int                    # 1, 2, 3...
    name: str                        # "First Tank", "Deep Dive"
    description: text
    planned_depth_meters: int
    planned_duration_minutes: int
    offset_minutes: int              # Time from departure
    min_certification_level: FK      # Per-dive override
```

**Constraint**: Unique (excursion_type, sequence)

### 3. Excursion (Scheduled Operational Event)

**Already exists.** A single-day dive outing instance.

```python
Excursion:
    dive_shop: FK(Organization)
    dive_site: FK(DiveSite) nullable   # Primary site
    excursion_type: FK(ExcursionType)  # Product template
    trip: FK(Trip) nullable            # Multi-day package
    encounter: FK(Encounter)           # Workflow tracking
    departure_time: datetime
    return_time: datetime
    max_divers: int
    price_per_diver: Decimal
    status: enum                       # scheduled | boarding | in_progress | completed | cancelled
    created_by: FK(User)
```

**Constraint**: Same calendar day, return > departure

### 4. Dive (Individual Dive Instance)

**Already exists.** An atomic dive within an excursion.

```python
Dive:
    excursion: FK(Excursion)
    dive_site: FK(DiveSite)          # May differ from excursion site
    sequence: int
    # Planned
    planned_start: datetime
    planned_duration_minutes: int
    # Actual (logged after dive)
    actual_start: datetime
    actual_end: datetime
    max_depth_meters: int
    bottom_time_minutes: int
    # Environmental (logged after dive)
    visibility_meters: int
    water_temp_celsius: Decimal
    surface_conditions: enum
    current: enum
    notes: text
    # Audit
    logged_by: FK(User)
    logged_at: datetime
```

**Constraint**: Unique (excursion, sequence)

### 5. DiveAssignment (Diver Participation + Status)

**Just implemented.** Links divers to specific dives with real-time tracking.

```python
DiveAssignment:
    dive: FK(Dive)
    diver: FK(DiverProfile)
    role: enum                       # diver | guide | instructor | student
    buddy: FK(DiverProfile) nullable
    # Planning overrides
    planned_max_depth: int
    planned_bottom_time: int
    # Real-time status
    status: enum                     # assigned → briefed → gearing_up → in_water → surfaced → on_boat | sat_out | aborted
    entered_water_at: datetime
    surfaced_at: datetime
    last_known_bearing: str
```

**Constraint**: Unique (dive, diver)

### 6. DiveLog (Personal Dive Record)

**Just implemented.** Diver's permanent record using overlay pattern.

```python
DiveLog:
    dive: FK(Dive)                   # Master record
    diver: FK(DiverProfile)
    assignment: OneToOne(DiveAssignment)
    buddy / buddy_name
    # Overlay fields (null = inherit from Dive)
    max_depth_meters: Decimal
    bottom_time_minutes: int
    # Personal equipment
    air_start_bar / air_end_bar: int
    weight_kg: Decimal
    suit_type: enum
    tank_size_liters: int
    nitrox_percentage: int
    notes: text
    dive_number: int                 # This diver's cumulative count
    # Verification
    verified_by: FK(User)
    verified_at: datetime
```

**Constraints**:
- Unique (dive, diver)
- air_end_bar < air_start_bar (when both present)
- nitrox_percentage BETWEEN 21 AND 40 (when present)

**Overlay Pattern**: `effective_max_depth` property returns `max_depth_meters if not None else dive.max_depth_meters`

---

## Template → Instance Flow (Current)

```
ExcursionType: "Morning 2-Tank Boat Dive"
    ├── ExcursionTypeDive 1: "Shallow Reef", 18m max, 45min
    └── ExcursionTypeDive 2: "Deep Wall", 30m max, 35min
            │
            ▼ [create_excursion service]
Excursion: Jan 15, 2025, 8:00 AM departure
    ├── Dive 1: Shallow Reef, 8:30 AM planned
    └── Dive 2: Deep Wall, 10:00 AM planned
            │
            ▼ [assign divers via DiveAssignment]
            ▼ [log_dive_results service after completion]
            │
    DiveLog per participating diver
```

---

## What's NOT Built Yet

### Missing: Pre-Excursion Dive Planning Details

Current ExcursionTypeDive has:
- `planned_depth_meters`
- `planned_duration_minutes`
- `description`

**Not present** (ChatGPT's DivePlan fields):
- `gas` (air/EAN32/EAN36)
- `equipment_requirements`
- `skills` (for training dives)
- `route` / `dive_profile`
- `hazards`
- `briefing_text` (publishable briefing content)
- `published_at` / `published_by`
- `status` (draft → published → retired)

### Missing: Briefing Snapshot

Currently: No mechanism to **freeze what was communicated** to divers.

ChatGPT suggests:
- `Dive.plan_snapshot` JSON field
- `Dive.plan_locked_at` timestamp
- Changes to template don't retroactively change scheduled dives

### Missing: Publishable Lifecycle

Current ExcursionType has `is_active` but no:
- Draft state for work-in-progress
- Published timestamp for briefing communication
- Retired state for archived products

---

## Services Already Implemented

```python
# Excursion lifecycle
create_excursion(actor, dive_shop, departure_time, ...)
update_excursion(actor, excursion, ...)
cancel_excursion(actor, excursion, reason)
start_excursion(excursion, started_by)
complete_excursion(excursion, completed_by)

# Dive CRUD
create_dive(actor, excursion, dive_site, sequence, planned_start, ...)
update_dive(actor, dive, ...)
delete_dive(actor, dive)

# Dive templates
create_dive_template(actor, excursion_type, sequence, name, ...)
update_dive_template(actor, dive_template, ...)
delete_dive_template(actor, dive_template)

# Dive logging (just implemented)
log_dive_results(actor, dive, actual_start, actual_end, max_depth, ...)
update_diver_status(actor, assignment, new_status)
verify_dive_log(actor, dive_log)
update_dive_log(actor, dive_log, ...)

# Booking
book_excursion(diver, excursion, booked_by, ...)
check_in(booking, actor)
cancel_booking(booking, cancelled_by, ...)
```

---

## Audit Events

All mutations emit audit events to `django_audit_log.AuditLog`:
- EXCURSION_CREATED, EXCURSION_UPDATED, EXCURSION_CANCELLED, etc.
- DIVE_CREATED, DIVE_UPDATED, DIVE_DELETED, DIVE_LOGGED
- DIVER_STATUS_CHANGED
- DIVE_LOG_VERIFIED, DIVE_LOG_UPDATED
- BOOKING_CREATED, BOOKING_CANCELLED, etc.

---

## Question for ChatGPT

Given that we already have:
1. **ExcursionType** as the product template
2. **ExcursionTypeDive** as the dive template within products
3. **Dive** as the operational instance
4. **DiveAssignment** with planning overrides
5. **DiveLog** with the overlay pattern

**Do we need a separate DivePlan model**, or can we:
- Extend ExcursionTypeDive with briefing/planning fields
- Add a `plan_snapshot` JSON + `plan_locked_at` to Dive
- Add draft/published lifecycle to ExcursionType

The existing structure already has the template → instance cascade. The question is whether "plans for briefing" are:
1. Just richer ExcursionTypeDive records (extend existing)
2. A separate publishable artifact (new DivePlan model)

What's the minimal change to support advance planning and briefing communication?

---

## Constraints

- PostgreSQL only (CHECK constraints, JSONB, etc.)
- All models inherit BaseModel (UUID pk, soft delete, timestamps)
- Service layer pattern (all writes atomic, audited)
- Overlay pattern for inheritance-by-null
- Test-driven development (64 tests for DiveLog system)
