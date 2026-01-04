# DiveOps Application Review

**Review Date:** 2026-01-04
**Reviewer:** Claude Code (Opus 4.5)
**Scope:** Application-layer code built on django-primitives
**Status:** Review Template / Prompt

---

## Overview

This review covers the **diveops** testbed application, which is built on top of the django-primitives ecosystem. Unlike the tier reviews (which audit the primitives themselves), this review focuses on:

1. **Correct usage of primitives** - Is the application using primitives correctly?
2. **Domain-specific patterns** - Are diveops models, services, and views well-designed?
3. **Integration correctness** - Are cross-primitive integrations sound?
4. **Security & authorization** - Are views properly protected?
5. **Audit logging completeness** - Are all auditable events captured?

**Non-Goal:** This review does not re-evaluate primitive design or implementation correctness. The primitives have been audited separately. This review assumes primitives are correct and focuses solely on application-layer usage.

**What's Already Reviewed (Primitives):**
| Primitive | Tier | Review Status |
|-----------|------|---------------|
| django_parties.Person | 1 | Audited |
| django_parties.Organization | 1 | Audited |
| django_encounters.Encounter | 3 | Audited |
| django_documents.Document | 4 | Audited |
| django_agreements.Agreement | 4 | Audited |
| django_catalog.Basket | 3 | Audited |
| django_audit_log.log() | 2 | Audited |
| django_geo.Place | 3 | Audited |
| django_sequence.next_sequence() | 5 | Audited |

---

## Hard Rules (Stop-Ship)

These are non-negotiable. Violations are defects, not style choices.

### 1. All domain models MUST inherit from BaseModel

Manual UUIDs, timestamps, and soft-delete in an application that claims to use primitives is architectural debt. This is not an "opportunity" - it's a requirement.

```python
# WRONG - manual fields
class MyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

# CORRECT - inherit from primitive
from django_basemodels import BaseModel

class MyModel(BaseModel):
    # BaseModel provides id, created_at, updated_at, deleted_at, soft-delete manager
    pass
```

### 2. Any write path without an audit event is a defect

If a service function changes state and does not emit an audit event, it is broken. Silent state changes are the single most important operational risk.

```python
# WRONG - silent state change
@transaction.atomic
def do_thing(entity, actor):
    entity.status = "done"
    entity.save()
    return entity  # No audit event = defect

# CORRECT - audited state change
@transaction.atomic
def do_thing(entity, actor):
    entity.status = "done"
    entity.save()
    log_event(action=Actions.THING_DONE, target=entity, actor=actor)
    return entity
```

---

## 1. Domain Models (models.py)

### Architecture

```
CertificationLevel (reference data)
    └── DiverCertification (normalized M2M)
            └── DiverProfile (extends Person)
                    └── Booking (links to DiveTrip)
                            └── TripRoster (check-in record)

DiveSite (location with diving metadata)
    └── DiveTrip (scheduled trip)
            └── TripRequirement (eligibility rules)
```

### What Should NOT Change

1. **UUID primary keys on all models** - Consistent with primitives
2. **SoftDeleteManager pattern** - Matches django-basemodels
3. **PROTECT on critical FKs** - dive_shop, dive_site, diver, created_by
4. **CheckConstraints on all models** - DB-level invariant enforcement
5. **UniqueConstraint with conditions** - Proper partial unique patterns
6. **Coordinate validation** - DiveSite matches django-geo patterns

### Review: CertificationLevel

**Strengths:**
- Agency-scoped via FK to Organization
- Rank-based comparison enables cross-agency equivalence
- Proper partial unique: `(agency, code)` where `deleted_at IS NULL`
- CheckConstraint for rank > 0 and max_depth > 0

**Concerns:**
1. **No BaseModel inheritance** - Uses plain models.Model with manual UUID/timestamps/soft-delete. This duplicates django-basemodels. Should inherit from BaseModel.

**Defect: Does not inherit from BaseModel**

This is a stop-ship issue, not an opportunity. See Hard Rules section.

**Required Action:** Migrate to BaseModel inheritance.
**Effort:** M (migration required)

---

### Review: DiverCertification

**Strengths:**
- Normalized M2M pattern (diver → level → agency)
- Proof document FK to django_documents.Document
- Verification tracking (is_verified, verified_by, verified_at)
- CheckConstraint: expires_on > issued_on

**Concerns:**
1. **No BaseModel inheritance** - Same as CertificationLevel. Stop-ship issue.

---

### Review: TripRequirement

**Strengths:**
- Multi-type requirements (certification, medical, gear, experience)
- Proper FK to CertificationLevel for cert requirements
- Partial unique: one requirement type per trip (not deleted)
- Model clean() validates cert level for cert requirements

**Concerns:**
1. **No CheckConstraint for requirement_type values** - TextChoices but no DB enforcement

**Opportunity 3: Add CheckConstraint for requirement_type**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB enforces valid types | Data integrity | Low value - choices validates |
| B) Keep as-is | TextChoices provides validation | Simpler | Raw SQL can bypass |

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - TextChoices sufficient

---

### Review: DiverProfile

**Strengths:**
- OneToOneField to Person (extends identity)
- LEVEL_HIERARCHY for certification comparison
- is_waiver_valid() with configurable expiry
- CheckConstraint: total_dives >= 0

**Concerns:**
1. **Legacy certification fields** - `certification_level`, `certification_agency`, `certification_number`, `certification_date` are marked deprecated but still exist
2. **No BaseModel inheritance** - Manual timestamps. Stop-ship issue.

**Cleanup (Low Priority):** Remove deprecated certification fields when safe. Wait until no code uses legacy fields.

---

### Review: DiveSite

**Strengths:**
- Proper coordinate validation (lat -90..90, lon -180..180) matching django-geo
- CheckConstraint: max_depth_meters > 0
- Optional FK to django_geo.Place
- Proper indexes on query paths

**Concerns:**
None identified. Well-designed.

---

### Review: DiveTrip

**Strengths:**
- PROTECT on dive_shop, dive_site, created_by
- CheckConstraint: return_time > departure_time
- CheckConstraint: max_divers > 0, price_per_diver >= 0
- Optional OneToOneField to Encounter for workflow
- Composite index: (dive_shop, status)

**Concerns:**
1. **No CheckConstraint for status values** - TextChoices but no DB enforcement

**Opportunity 5: Add CheckConstraint for DiveTrip.status**

Same pattern as Opportunity 3.
**Recommendation:** **DEFER** - TextChoices sufficient

---

### Review: Booking

**Strengths:**
- PROTECT on trip, diver, booked_by
- Conditional unique: one active booking per (trip, diver)
- SET_NULL on optional commerce links (basket, invoice, waiver_agreement)
- Proper indexes

**Concerns:**
None identified. Well-designed conditional unique constraint.

---

### Review: TripRoster

**Strengths:**
- OneToOneField to Booking (one roster entry per booking)
- UniqueConstraint: (trip, diver) - enforces one check-in per trip
- Role tracking (DIVER, DM, INSTRUCTOR)
- PROTECT on critical FKs

**Concerns:**
None identified.

---

## 2. Services (services.py)

### What Should NOT Change

1. **@transaction.atomic on all write operations** - Correct atomicity
2. **select_for_update() on race-critical paths** - book_trip locks trip
3. **Service-layer validation before DB ops** - Proper order
4. **Audit logging after successful operations** - Correct pattern

### Review: book_trip()

**Strengths:**
- Locks trip with select_for_update() before capacity check
- Validates eligibility via decisioning module
- Creates basket/invoice via billing adapter
- Proper exception hierarchy (TripCapacityError, DiverNotEligibleError)

**Status:** ✓ Fixed - Now emits BOOKING_CREATED audit event.

---

### Review: check_in()

**Strengths:**
- Validates booking status
- Validates waiver if required
- Creates TripRoster atomically
- Updates booking status

**Status:** ✓ Fixed - Now emits DIVER_CHECKED_IN audit event.

---

### Review: start_trip() / complete_trip()

**Strengths:**
- Proper state transition validation
- Creates encounter if missing
- Increments dive counts atomically
- Syncs encounter state

**Status:** ✓ Fixed - Now emits TRIP_STARTED, TRIP_COMPLETED, and DIVER_COMPLETED_TRIP audit events.

---

### Review: Certification Services

**Strengths:**
- All operations use @transaction.atomic
- All operations emit audit events via log_certification_event()
- Proper validation (duplicate check, deleted check)
- Change tracking for updates

**Concerns:**
None identified. Exemplary pattern for other services.

---

## 3. Audit Adapter (audit.py)

### What Should NOT Change

1. **Single import point for django_audit_log** - Correct adapter pattern
2. **Stable action constants (class Actions)** - Public contract
3. **Domain-specific metadata builders** - Consistent structure

### Review: Actions Constants

**Strengths:**
- Comprehensive action vocabulary
- Grouped by domain (diver, certification, trip, booking, eligibility)
- Clear naming convention

**Status:** ✓ Fixed - All defined actions are now emitted by their corresponding service functions.

---

### Review: Metadata Builders

**Strengths:**
- Consistent structure across all builders
- Proper null checks before accessing related objects
- Includes both IDs and display names for context

**Concerns:**
None identified. Well-designed.

---

## 4. Decisioning (decisioning.py)

### What Should NOT Change

1. **EligibilityResult dataclass** - Clean return type
2. **Temporal evaluation (as_of parameter)** - Correct time semantics
3. **Two versions (legacy and v2)** - Migration path

### Review: can_diver_join_trip()

**Strengths:**
- Checks trip status, departure time, capacity, certification, medical
- Returns actionable required_actions
- Uses as_of for temporal correctness

**Concerns:**
1. **Uses legacy certification fields** - Should use DiverCertification model

**Opportunity 10: Migrate to v2 decisioning**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Deprecate v1, use v2 | can_diver_join_trip_v2 becomes default | Uses normalized models | Migration path needed |
| B) Keep both | v1 for legacy, v2 for new | Backwards compatible | Two code paths |

**Risk/Reward:** Medium risk, high reward
**Effort:** M
**Recommendation:** **ADOPT** - Migrate services to v2, deprecate v1

---

### Review: can_diver_join_trip_v2()

**Strengths:**
- Uses TripRequirement model
- Uses DiverCertification model
- Supports multiple requirement types
- Proper prefetch of certifications

**Concerns:**
1. **Gear requirements not implemented** - Comment notes this

**Opportunity 11: Implement gear requirement checking**

**Recommendation:** **DEFER** - Implement when gear tracking is added

---

## 5. Integrations (integrations.py)

### What Should NOT Change

1. **Centralized imports** - Single location for primitive imports
2. **Billing adapter functions** - Clean abstraction over primitives
3. **__all__ exports** - Explicit public API

### Review: create_trip_basket()

**Strengths:**
- Creates EncounterDefinition if missing
- Links basket to encounter
- Proper content type handling

**Concerns:**
None identified.

---

### Review: create_booking_invoice()

**Strengths:**
- Uses django_sequence for invoice numbers
- Commits basket atomically
- Creates line items from priced basket items

**Concerns:**
1. **Hardcoded currency fallback** - Uses "USD" if no priced items

**Opportunity 12: Get currency from trip**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Use trip.currency | Invoice currency matches trip | Consistent | Minor code change |
| B) Keep as-is | USD fallback | Works | Inconsistent for non-USD trips |

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **ADOPT** - Use trip.currency as fallback

---

## 6. Views (staff_views.py)

### What Should NOT Change

1. **StaffPortalMixin on all views** - Consistent authorization
2. **Use of services for write operations** - Proper separation
3. **Use of selectors for read operations** - N+1 prevention

### Review: Authorization

**Strengths:**
- All views use StaffPortalMixin
- POST-only for state changes (CheckInView, StartTripView, etc.)

**Concerns:**
1. **No permission checks beyond staff** - Any staff can do any operation

**Opportunity 13: Add role-based permissions**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add permission decorators | Check specific permissions | Proper RBAC | Complexity |
| B) Keep as-is | Staff = full access | Simple | Over-permissive |

**Risk/Reward:** Medium risk, high reward (security)
**Effort:** M
**Recommendation:** **ADOPT** - Integrate with django-rbac for role checks

---

### Review: Form Handling

**Strengths:**
- Proper actor passing to forms (form.save(actor=self.request.user))
- Success messages via Django messages framework
- Redirect after POST

**Concerns:**
None identified.

---

### Review: BookDiverView

**Strengths:**
- Checks eligibility before booking
- Re-renders with eligibility result on failure
- Uses decisioning module

**Concerns:**
1. **No audit logging for eligibility check** - Failed eligibility not logged

**Opportunity 14: Log eligibility failures**

**Recommendation:** **ADOPT** - Emit ELIGIBILITY_FAILED for audit/debugging

---

## 7. Forms (forms.py)

### What Should NOT Change

1. **@transaction.atomic on save()** - Correct atomicity
2. **Audit logging in save()** - Proper event emission
3. **Proper validation in clean()** - Date comparisons, uniqueness

### Review: DiverForm

**Strengths:**
- Creates Person + DiverProfile + DiverCertification atomically
- Handles proof document upload
- Uses ContentType for GenericFK
- Logs certification_added event

**Concerns:**
1. **No diver_created audit event** - Only certification is logged

**Opportunity 15: Add diver_created audit event**

**Recommendation:** **ADOPT** - Log when new diver is created

---

### Review: DiverCertificationForm

**Strengths:**
- Tracks changes for update events
- Creates Document for proof file
- Logs add and update events

**Concerns:**
1. **Document target_id = "pending"** - Temporary value before certification saved

**Opportunity 16: Use transaction savepoint for document creation**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Create document after cert | Save cert first, then document | Clean target_id | Two saves |
| B) Keep as-is | Pending then update | Works | Minor inconsistency |

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - Current pattern works, update is immediate

---

## 8. Selectors (selectors.py)

### What Should NOT Change

1. **select_related for FK traversal** - Prevents N+1
2. **prefetch_related with Prefetch for M2M** - Efficient queries
3. **Annotate for computed fields** - Avoids Python loops

### Review: Query Optimization

**Strengths:**
- All selectors use proper prefetching
- Consistent pattern across all selectors
- Proper soft-delete filtering (deleted_at__isnull=True)

**Concerns:**
None identified. Well-designed.

---

## 9. Exceptions (exceptions.py)

### Review

**Strengths:**
- Clear hierarchy (DiveOpsError base)
- Specific exceptions for specific failures
- Proper inheritance (TripCapacityError extends BookingError)

**Concerns:**
None identified.

---

## Summary Tables

### Models

| Model | BaseModel? | Constraints | Audit? | Status |
|-------|-----------|-------------|--------|--------|
| CertificationLevel | No | Yes | N/A | **STOP-SHIP** - Must inherit BaseModel |
| DiverCertification | No | Yes | Yes | **STOP-SHIP** - Must inherit BaseModel |
| TripRequirement | No | Yes | No | **STOP-SHIP** - Must inherit BaseModel |
| DiverProfile | No | Partial | No | **STOP-SHIP** - Must inherit BaseModel |
| DiveSite | No | Yes | N/A | **STOP-SHIP** - Must inherit BaseModel |
| DiveTrip | No | Yes | No | **STOP-SHIP** - Must inherit BaseModel |
| Booking | No | Yes | No | **STOP-SHIP** - Must inherit BaseModel |
| TripRoster | No | Yes | N/A | **STOP-SHIP** - Must inherit BaseModel |

### Services - Audit Coverage

| Service Function | Audit Event Emitted? | Status |
|------------------|---------------------|--------|
| book_trip() | Yes | Fixed |
| check_in() | Yes | Fixed |
| start_trip() | Yes | Fixed |
| complete_trip() | Yes | Fixed |
| cancel_booking() | Yes | Fixed |
| add_certification() | Yes | OK |
| update_certification() | Yes | OK |
| remove_certification() | Yes | OK |
| verify_certification() | Yes | OK |
| unverify_certification() | Yes | OK |

**Rule:** Any service function that changes state without emitting an audit event is a defect.

### Views - Authorization

| View | Staff Check | Role Check | Action |
|------|-------------|------------|--------|
| DashboardView | Yes | No | **ADOPT** - Add read permission |
| DiverListView | Yes | No | **ADOPT** - Add read permission |
| CreateDiverView | Yes | No | **ADOPT** - Add create permission |
| EditDiverView | Yes | No | **ADOPT** - Add update permission |
| TripListView | Yes | No | **ADOPT** - Add read permission |
| BookDiverView | Yes | No | **ADOPT** - Add booking permission |
| CheckInView | Yes | No | **ADOPT** - Add checkin permission |
| StartTripView | Yes | No | **ADOPT** - Add trip.manage permission |
| CompleteTripView | Yes | No | **ADOPT** - Add trip.manage permission |

---

## Immediate Action Items

### Stop-Ship (Must Fix Before Merge)

1. **All 8 models:** Inherit from django-basemodels.BaseModel instead of manual UUID/timestamps/soft-delete. This is architectural debt, not a style choice.

### Fixed (This Review)

2. ~~**book_trip():** Add log_booking_event(BOOKING_CREATED, ...)~~ ✓
3. ~~**check_in():** Add log_roster_event(DIVER_CHECKED_IN, ...)~~ ✓
4. ~~**start_trip():** Add log_trip_event(TRIP_STARTED, ...)~~ ✓
5. ~~**complete_trip():** Add log_trip_event(TRIP_COMPLETED, ...)~~ ✓
6. ~~**cancel_booking():** Add log_booking_event(BOOKING_CANCELLED, ...)~~ ✓

### Medium Priority (Security)

7. **All views:** Integrate with django-rbac for granular permissions
8. **BookDiverView:** Log ELIGIBILITY_FAILED when eligibility check fails

### Low Priority (Cleanup)

9. **decisioning.py:** Migrate to v2, deprecate v1
10. **DiverProfile:** Remove deprecated certification fields when safe
11. **integrations.py:** Use trip.currency as invoice currency fallback

---

## Overall Assessment

**Verdict: Well-designed application with one stop-ship blocker (BaseModel inheritance) and audit gaps now fixed.**

**Key Strengths:**
- Proper use of DB constraints (CheckConstraint, UniqueConstraint)
- Correct transaction handling (@transaction.atomic, select_for_update)
- Clean separation (models, services, selectors, views)
- Exemplary certification audit logging pattern (now propagated to all services)
- N+1 prevention in selectors
- All write paths now emit audit events

**Stop-Ship Blocker:**
- Models don't inherit from BaseModel - this is architectural debt that must be fixed

**Remaining Gaps:**
- Authorization is binary (staff/not staff), no role granularity

**Pattern to Propagate:**
The certification services + audit pattern is the gold standard. All services now follow this pattern:

```python
@transaction.atomic
def some_operation(...):
    # 1. Validate
    # 2. Execute business logic
    # 3. Save
    # 4. Log audit event
    log_event(action=Actions.SOME_ACTION, target=entity, actor=user)
    return entity
```

This pattern is enforceable via code review, lint rules, or Claude instructions.

**What NOT to Change:**
- Constraint patterns on models
- Transaction handling in services
- Selector optimization patterns
- Decisioning dataclass return type
- Audit adapter architecture
