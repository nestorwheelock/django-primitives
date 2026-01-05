# DiveLog System Specification (Final)

## 1) Problem Statement

The existing `Dive` model captures the **shop's operational record** of a dive (planned/actual group info). But divers need **personal dive logs** that:

1. Form permanent dive history for the diver
2. Store diver-specific metrics (depth/time/air/equipment) which can differ from group
3. Support certification requirements (e.g., "25 logged dives")
4. Incorporate dive computer data

Current gap:

* Booking/Excursion indicates "diver was on the excursion"
* But not "diver completed *this specific dive* with *these metrics*"

---

## 2) Design Intent

### 2.1 Template Cascade (Inheritance-by-null / Overlay Pattern)

Values flow downward and can be overridden per layer:

```
DiveSite → ExcursionTypeDive → Dive → DiveLog
```

* **DiveSite:** reference characteristics (max depth, difficulty, conditions typical)
* **ExcursionTypeDive:** template per product type (planned depths/durations/offsets)
* **Dive:** operational instance for that specific excursion (guide logs actual group outcome)
* **DiveLog:** diver's personal overlay (null fields inherit from Dive)

**Key rule:**

* `DiveLog` fields are nullable.
* **Null = inherit from Dive.**
* **Non-null = diver override.**

Benefits:

* guide logs once for the group
* diver can personalize without forcing divergence in the master record
* supports mixed-ability groups (some divers shallower/shorter)

---

## 3) Model Specifications

## 3.1 Enhanced `Dive` Model (Guide Master Record)

Add environmental + logging audit fields.

### Additions to `Dive`

* Environmental:

  * `visibility_meters` (int)
  * `water_temp_celsius` (decimal 4,1)
  * `surface_conditions` (enum: calm/slight/moderate/rough)
  * `current` (enum: none/mild/moderate/strong)
* Logging audit:

  * `logged_by` FK to staff user
  * `logged_at` datetime

**Ownership rule:** Dive is the **authoritative operational record** entered by staff/guide.

---

## 3.2 `DiveAssignment` Model (Diver ↔ Dive Participation + Real-Time Status)

### Purpose

A diver may participate in some dives in an excursion and sit out others. Also enables real-time status tracking.

### Core fields

* `dive` FK (CASCADE)
* `diver` FK (PROTECT)
* `role` (diver/guide/instructor/student)
* buddy pairing:

  * `buddy` FK to DiverProfile (nullable)

### Planning fields (optional overrides of dive plan)

* `planned_max_depth` (nullable)
* `planned_bottom_time` (nullable)

### Real-time status state machine

`status` choices (single enum, not "participation status" + "realtime status" split):

* assigned
* briefed
* gearing_up
* in_water
* surfaced
* on_boat
* sat_out
* aborted (optional but useful)

Timestamps:

* `entered_water_at` nullable
* `surfaced_at` nullable

Safety field (optional):

* `last_known_bearing` (short string)

Constraints:

* Unique `(dive, diver)`

Indexes:

* `(dive, status)`, `(diver)`

---

## 3.3 `DiveLog` Model (Per-Diver Record)

### Purpose

Per-diver personal dive record that references the master Dive and can override metrics. This is the diver's permanent history.

### Core fields

* `dive` FK to Dive (PROTECT)
* `diver` FK to DiverProfile (PROTECT)
* `assignment` OneToOne to DiveAssignment (nullable but expected when created through ops)
* Buddy info:

  * `buddy` FK DiverProfile nullable
  * `buddy_name` string blank

### Personal override metrics (nullable)

* `max_depth_meters` decimal (null = use Dive)
* `bottom_time_minutes` int (null = use Dive)

### Air consumption

* `air_start_bar` int nullable
* `air_end_bar` int nullable

Constraint: end < start when both present

### Equipment used (diver-specific)

* `weight_kg` decimal nullable
* `suit_type` enum (none/shorty/3mm/5mm/7mm/dry)
* `tank_size_liters` int nullable
* `nitrox_percentage` int nullable (constraint 21–40)

### Dive computer import

* `computer_data` JSON nullable (raw import payload)
* computed fields (optional):

  * `computer_max_depth` decimal nullable
  * `computer_avg_depth` decimal nullable
  * `computer_bottom_time` int nullable
  * `computer_dive_time` int nullable

### Notes

* `notes` text blank

### Dive numbering

* `dive_number` int nullable (auto-assigned, but allow manual override later if needed)

### Verification (for credit / training)

* `verified_by` FK staff nullable
* `verified_at` datetime nullable

### Source tracking

* `source` enum (shop/manual) - distinguishes system-generated from manual historical entry

Constraints:

* Unique `(dive, diver)`
* air constraint
* nitrox range constraint

Indexes:

* `diver + dive date` (for listing)
* `verified_at` (queue)

Computed properties (template overlay pattern):

* effective depth/time = personal override OR Dive value
* air consumed
* derived SAC rate (optional helper)

---

## 4) Workflow

### 4.1 Pre-dive: Assignments

1. Excursion created with multiple Dives
2. Staff assigns divers to dives (DiveAssignment)

   * set individual planned limits
   * buddy pairing
   * mark sit-outs

### 4.2 Post-dive: Guide logging

When excursion/dive completes:

1. Guide logs Dive master outcomes:

   * actual start/end
   * max depth
   * bottom time
   * environmental conditions
2. System auto-creates DiveLogs for **participated** assignments:

   * pre-fill buddy from assignment
   * auto-assign dive_number

### 4.3 Diver customization

Diver edits personal log:

* personal depth/time (shallower/shorter)
* air start/end
* gear and notes
* import computer data (writes computer_*)

### 4.4 Verification

Staff verifies log for certification requirements:

* sets verified_by, verified_at
* log counts toward "verified dive count"

---

## 5) Service Layer Requirements

### 5.1 `log_dive_results()`

* updates Dive master fields
* sets logged_by/logged_at
* creates DiveLog for each participated DiveAssignment (idempotent get_or_create)
* emits audit event

### 5.2 `update_dive_log()`

* only updates allowed per-diver fields
* emits audit event with tracked changes
* must enforce permissions (diver can only edit their log; staff can edit any)

### 5.3 `verify_dive_log()`

* staff-only
* sets verified_by/verified_at
* emits audit event

### 5.4 `update_diver_status()`

* updates DiveAssignment.status
* sets timestamps on status transitions
* emits audit event with changes

---

## 6) UI Requirements

### Staff Portal

1. Excursion detail: "Assign Divers to Dives"
2. Dive status board (Kanban per Dive)
3. "Log Dive Results" action post-completion
4. DiveLog verification queue

### Customer Portal (future)

1. My Dive Logs list view (filter by date/site/verified)
2. Dive Log detail (edit personal fields + import computer data)
3. Export/print logbook (PDF)

---

## 7) Audit Events

Add Actions:

* DIVE_LOGGED (Dive master logged)
* DIVE_LOG_CREATED (per-diver log created)
* DIVE_LOG_UPDATED
* DIVE_LOG_VERIFIED
* DIVE_ASSIGNMENT_CREATED
* DIVE_ASSIGNMENT_UPDATED
* DIVER_STATUS_CHANGED

Every service mutation emits audit events. No form/view direct saves.

---

## 8) Migration Path

1. Migration: add new fields to Dive
2. Migration: create DiveAssignment
3. Migration: create DiveLog
4. Data migration (optional):

   * for historical completed excursions, create DiveLogs from roster participation

---

## 9) Decisions (Resolved)

### Q1: Link DiveLog to Booking?

**Decision:** Do not hard-require Booking.
Keep traceability via `DiveAssignment.booking` later (nullable), and reach it through assignment when available.

### Q2: Dive computer import formats

**Default MVP:**

* Subsurface export (CSV/JSON)
* Shearwater Cloud CSV
* Generic CSV template you control

UDDF later if needed, but don't pretend you'll parse the universe on day 1.

### Q3: Manual historical dive entry

**Decision:** Allow staff/diver to create a Dive + DiveLog marked as `source="manual"`, not a DiveLog with no Dive. Every DiveLog has a Dive parent.

---

## 10) Implementation Stop-Gates

### Phase 1: Models + Migrations
- [ ] Add fields to Dive model
- [ ] Create DiveAssignment model
- [ ] Create DiveLog model
- [ ] Run makemigrations, verify migration files
- [ ] Run migrate on test database
- [ ] **STOP: Verify schema correct before proceeding**

### Phase 2: Tests (Write First)
- [ ] test_dive_assignment_unique_constraint
- [ ] test_dive_log_overlay_pattern (null inherits from Dive)
- [ ] test_dive_log_air_constraint
- [ ] test_dive_log_nitrox_range
- [ ] test_log_dive_results_creates_logs
- [ ] test_update_diver_status_timestamps
- [ ] test_verify_dive_log
- [ ] **STOP: All tests fail (implementation doesn't exist)**

### Phase 3: Services
- [ ] Implement log_dive_results()
- [ ] Implement update_dive_log()
- [ ] Implement verify_dive_log()
- [ ] Implement update_diver_status()
- [ ] **STOP: All tests pass**

### Phase 4: Audit Events
- [ ] Add audit actions to Actions class
- [ ] Add audit helpers (log_dive_log_event, log_assignment_event)
- [ ] Verify services emit events
- [ ] **STOP: Audit coverage complete**

### Phase 5: Staff Portal UI
- [ ] Dive assignment UI (excursion detail)
- [ ] Dive status board (kanban)
- [ ] Log dive results form
- [ ] Verification queue
- [ ] **STOP: Manual testing complete**

### Phase 6: Customer Portal (Future)
- [ ] My Dive Logs list
- [ ] Dive Log detail/edit
- [ ] Computer data import
- [ ] PDF export
