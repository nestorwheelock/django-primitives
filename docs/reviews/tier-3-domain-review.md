# Tier 3: Domain - Deep Review

**Review Date:** 2026-01-02
**Reviewer:** Claude Code (Opus 4.5)
**Packages:** django-catalog, django-encounters, django-worklog, django-geo, django-ledger

---

## 1. django-catalog

### Purpose
Order catalog with basket→commit→workitem workflow for clinical/retail operations.

### Architecture
```
CatalogItem (definition layer)
    ↓ added to
Basket (encounter-scoped, editable until committed)
    ↓ contains
BasketItem (references CatalogItem, snapshots on commit)
    ↓ spawns on commit
WorkItem (executable task with board routing)
    ↓ completes to
DispenseLog (pharmacy dispensing record)

CatalogSettings (singleton configuration)
```

### What Should NOT Change

1. **CatalogBaseModel extends BaseModel** - Gets UUID, timestamps, soft-delete
2. **BasketItem snapshots on commit** - `display_name_snapshot`, `kind_snapshot` preserve state
3. **WorkItem idempotency via UniqueConstraint** - `(basket_item, spawn_role)` prevents duplicate spawns
4. **DispenseLog OneToOneField to WorkItem** - Enforces one dispense per workitem
5. **Configurable FKs via add_to_class** - `INVENTORY_ITEM_MODEL`, `PRESCRIPTION_MODEL` are correctly optional
6. **PROTECT on CatalogItem→BasketItem** - Don't delete catalog items with basket references
7. **Time semantics** - `effective_at` vs `recorded_at` is correct

---

### Opportunity 1: Add CheckConstraint for Basket.status values

**Current State:**
Status is CharField with choices. Invalid states possible via raw SQL.

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(status__in=['draft', 'committed', 'cancelled']),
    name="basket_valid_status",
)
```

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - Low priority; choices validation is sufficient

---

### Opportunity 2: Add CheckConstraint for WorkItem.status values

**Current State:**
Status is CharField with choices. No DB enforcement.

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(status__in=['pending', 'in_progress', 'blocked', 'completed', 'cancelled']),
    name="workitem_valid_status",
)
```

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - Low priority

---

### Opportunity 3: Add UniqueConstraint for one active basket per encounter

**Current State:**
Docstring says "One active basket per encounter at a time" but no constraint enforces this.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add partial UniqueConstraint | One draft basket per encounter | Enforces documented invariant | Complex with soft-delete |
| B) Service layer enforcement | Check in create_basket() | Flexible | Race conditions possible |
| C) Keep as-is | Document limitation | Simple | Invariant not enforced |

**Constraint Example:**
```python
models.UniqueConstraint(
    fields=['encounter'],
    condition=Q(status='draft') & Q(deleted_at__isnull=True),
    name="unique_active_basket_per_encounter",
)
```

**Risk/Reward:** Medium risk (may break valid use cases), high reward (enforces contract)
**Effort:** M
**Recommendation:** **ADOPT** - This is a documented invariant; should be enforced

---

### Opportunity 4: Add CheckConstraint for CatalogItem kind/service_category

**Current State:**
`service_category` should only be set when `kind='service'`. No DB enforcement.

**Constraint Example:**
```python
models.CheckConstraint(
    check=(
        Q(kind='stock_item', service_category='') |
        Q(kind='service')
    ),
    name="catalogitem_service_category_only_for_services",
)
```

**Risk/Reward:** Medium risk (migration complexity), medium reward
**Effort:** M
**Recommendation:** **DEFER** - Add model clean() validation first; DB constraint later

---

### Opportunity 5: Add NOT NULL to WorkItem.display_name

**Current State:**
`display_name` is CharField without explicit NOT NULL. Should never be empty.

**Risk/Reward:** Zero risk (verify only)
**Effort:** S
**Recommendation:** **ADOPT** - Verify migration; add blank=False if missing

---

## 2. django-encounters

### Purpose
State machine-driven encounter workflow with audit trail.

### Architecture
```
EncounterDefinition (reusable state machine graph)
    ↓ used by
Encounter (instance attached to any subject via GenericFK)
    ↓ logged via
EncounterTransition (audit log of state changes)
```

### What Should NOT Change

1. **EncountersBaseModel extends BaseModel** - Correct
2. **EncounterDefinition.clean() validates graph** - Critical for state machine integrity
3. **GenericFK on Encounter** - Domain-agnostic subject attachment is correct
4. **EncounterTransition as audit log** - Append-only intent, CASCADE on encounter
5. **PROTECT on definition** - Don't delete definitions with active encounters
6. **Time semantics** - `effective_at` vs `recorded_at` is correct

---

### Opportunity 6: Encounter.subject_id should be CharField

**Current State:**
`subject_id = models.PositiveIntegerField()` - Doesn't support UUID subjects.

**Issue:** All other GenericFKs in the codebase use CharField for UUID support. This is inconsistent.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Change to CharField | Consistent with other packages | UUID support | Migration required; breaking change |
| B) Keep as-is | No migration | Simple | UUID subjects won't work |

**Risk/Reward:** Medium risk (migration), high reward (consistency, UUID support)
**Effort:** M
**Recommendation:** **ADOPT** - This is a bug; should be CharField for UUID support

---

### Opportunity 7: Add CheckConstraint for Encounter.state must be in definition.states

**Current State:**
No DB-level enforcement that state is valid per definition.

**Challenge:** Cross-table constraint is hard in most DBs without triggers.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add DB trigger | Validate on insert/update | True DB enforcement | Postgres-specific; complex |
| B) Model clean() only | Python validation | Simple | Bypassed by raw SQL |
| C) Keep as-is | Trust service layer | Simple | Invalid states possible |

**Risk/Reward:** High risk (trigger complexity), medium reward
**Effort:** L
**Recommendation:** **AVOID** - Keep validation in service layer; cross-table constraints are complex

---

### Opportunity 8: Add immutability to EncounterTransition

**Current State:**
Transitions are intended as audit log but can be modified.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Override save() | Prevent updates | Matches audit-log pattern | Code change |
| B) Keep as-is | Trust application | Simple | Audit log can be tampered |

**Risk/Reward:** Low risk, high reward (audit integrity)
**Effort:** S
**Recommendation:** **ADOPT** - Add immutability check like django-audit-log

---

## 3. django-worklog

### Purpose
Server-side work session timing for any context.

### Architecture
```
WorkSession (BaseModel)
├── user: FK to AUTH_USER_MODEL
├── context: GenericFK to any model
├── started_at / stopped_at / duration_seconds
└── effective_at / recorded_at (time semantics)
```

### What Should NOT Change

1. **WorklogBaseModel extends BaseModel** - Correct
2. **GenericFK with CharField** - Correct for UUID support
3. **Server-side timestamps** - `started_at = auto_now_add` prevents client manipulation
4. **Index on (user, stopped_at)** - Correct for "active session" queries
5. **Time semantics** - Correct

---

### Opportunity 9: Add UniqueConstraint for one active session per user

**Current State:**
Docstring says "One active session per user" but no constraint enforces this.

**Constraint Example:**
```python
models.UniqueConstraint(
    fields=['user'],
    condition=Q(stopped_at__isnull=True) & Q(deleted_at__isnull=True),
    name="unique_active_session_per_user",
)
```

**Risk/Reward:** Low risk, high reward (enforces documented invariant)
**Effort:** S
**Recommendation:** **ADOPT** - Documented invariant should be enforced

---

### Opportunity 10: Add CheckConstraint for duration consistency

**Current State:**
`duration_seconds` should be null when `stopped_at` is null, and set when stopped.

**Constraint Example:**
```python
models.CheckConstraint(
    check=(
        Q(stopped_at__isnull=True, duration_seconds__isnull=True) |
        Q(stopped_at__isnull=False, duration_seconds__isnull=False)
    ),
    name="worksession_duration_consistency",
)
```

**Risk/Reward:** Low risk, medium reward (data consistency)
**Effort:** S
**Recommendation:** **ADOPT** - Enforces logical invariant

---

## 4. django-geo

### Purpose
Geographic primitives: places and service areas with distance calculations.

### Architecture
```
Place (BaseModel)
├── coordinates: latitude/longitude (DecimalField 9,6)
├── address fields
└── as_geopoint() → GeoPoint value object

ServiceArea (BaseModel)
├── center: latitude/longitude
├── radius_km
└── contains(point) → bool

GeoPoint (dataclass, value object)
└── distance_to(other) → km
```

### What Should NOT Change

1. **Both models extend BaseModel** - Correct
2. **DecimalField(9,6) precision** - ~0.1m accuracy, appropriate
3. **GeoPoint as value object** - Immutable, no DB storage
4. **ServiceArea.code unique** - Already has unique=True
5. **PlaceQuerySet / ServiceAreaQuerySet** - Custom querysets are correct pattern

---

### Opportunity 11: Add CheckConstraint for valid coordinate ranges

**Current State:**
Latitude must be -90 to 90, longitude -180 to 180. No DB enforcement.

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(latitude__gte=-90) & Q(latitude__lte=90) &
          Q(longitude__gte=-180) & Q(longitude__lte=180),
    name="place_valid_coordinates",
)
```

**Risk/Reward:** Low risk, high reward (prevents invalid geo data)
**Effort:** S
**Recommendation:** **ADOPT** - Invalid coordinates are obvious bugs

---

### Opportunity 12: Add NOT NULL to required Place fields

**Current State:**
`city`, `state`, `postal_code` are CharField without explicit NOT NULL.

**Risk/Reward:** Zero risk (verify only)
**Effort:** S
**Recommendation:** **ADOPT** - Verify migrations

---

### Opportunity 13: Add CheckConstraint for positive radius

**Current State:**
`radius_km` could be negative. No constraint.

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(radius_km__gt=0),
    name="servicearea_positive_radius",
)
```

**Risk/Reward:** Low risk, high reward
**Effort:** S
**Recommendation:** **ADOPT** - Negative radius is meaningless

---

## 5. django-ledger

### Purpose
Double-entry accounting ledger with immutable entries.

### Architecture
```
Account (BaseModel)
├── owner: GenericFK (CharField for UUID)
├── account_type, currency, name
└── AccountQuerySet with for_owner(), by_type(), by_currency()

Transaction (plain Model)
├── description, posted_at, effective_at, recorded_at
├── is_posted property
└── entries M2M via Entry FK

Entry (plain Model, IMMUTABLE after posted)
├── transaction: FK
├── account: FK
├── amount: DecimalField(19,4)
├── entry_type: debit/credit
├── reverses: self-FK for reversals
└── save() raises if transaction.is_posted
```

### What Should NOT Change

1. **Account extends BaseModel** - Correct (accounts are mutable domain objects)
2. **Transaction/Entry are plain models** - Correct (append-only ledger, not soft-delete)
3. **Entry immutability via save()** - Critical for audit integrity
4. **PROTECT on all FKs** - Correct for ledger integrity
5. **GenericFK with CharField** - Correct for UUID support
6. **DecimalField(19,4) for amounts** - Good precision for accounting
7. **Time semantics** - Correct

---

### Opportunity 14: Add CheckConstraint for Entry.entry_type values

**Current State:**
TextChoices but no DB enforcement.

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(entry_type__in=['debit', 'credit']),
    name="entry_valid_type",
)
```

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - TextChoices sufficient

---

### Opportunity 15: Add CheckConstraint for positive amounts

**Current State:**
`amount` could be negative. Accounting typically uses debit/credit, not negative amounts.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Require amount > 0 | Standard accounting pattern | Clear semantics | Breaking if negative used |
| B) Allow negative | Flexible | Some systems use negative | Confusing with debit/credit |

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(amount__gt=0),
    name="entry_positive_amount",
)
```

**Risk/Reward:** Medium risk (may break use cases), high reward (clean accounting)
**Effort:** S
**Recommendation:** **ADOPT** - Standard accounting; debit/credit handles direction

---

### Opportunity 16: Add transaction balance validation

**Current State:**
Balanced transactions are documented but not enforced at DB level.

**Challenge:** Sum of debits must equal sum of credits per transaction. Hard to enforce at DB level.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add post() method validation | Check balance before posting | Clean API | Service layer only |
| B) Add DB trigger | Check on entry insert | True enforcement | Complex; Postgres-specific |
| C) Keep as-is | Document requirement | Simple | Unbalanced possible |

**Risk/Reward:** High effort for DB, low effort for service layer
**Effort:** S (service) / L (trigger)
**Recommendation:** **ADOPT** - Add post() method that validates balance before setting posted_at

---

### Opportunity 17: Transaction should have UUID PK

**Current State:**
Transaction uses default auto-increment PK. Inconsistent with rest of codebase.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add UUID PK | Consistent with codebase | Distributed-safe | Migration complexity |
| B) Keep as-is | Working | Simple | Inconsistent |

**Risk/Reward:** Medium risk (migration), medium reward (consistency)
**Effort:** M
**Recommendation:** **DEFER** - Working as-is; address in future version

---

## Tier 3 Summary

### django-catalog

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 1. Basket.status CheckConstraint | DEFER | S | Yes |
| 2. WorkItem.status CheckConstraint | DEFER | S | Yes |
| 3. Unique active basket per encounter | **ADOPT** | M | Yes - Partial Unique |
| 4. CatalogItem kind/service_category | DEFER | M | Yes |
| 5. WorkItem.display_name NOT NULL | **ADOPT** | S | Yes - verify |

### django-encounters

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 6. subject_id → CharField | **ADOPT** | M | No - schema change |
| 7. State must be in definition | AVOID | L | Yes - trigger |
| 8. EncounterTransition immutability | **ADOPT** | S | No - save() override |

### django-worklog

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 9. Unique active session per user | **ADOPT** | S | Yes - Partial Unique |
| 10. Duration consistency | **ADOPT** | S | Yes - CheckConstraint |

### django-geo

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 11. Valid coordinate ranges | **ADOPT** | S | Yes - CheckConstraint |
| 12. Place required fields NOT NULL | **ADOPT** | S | Yes - verify |
| 13. ServiceArea positive radius | **ADOPT** | S | Yes - CheckConstraint |

### django-ledger

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 14. Entry.entry_type CheckConstraint | DEFER | S | Yes |
| 15. Entry positive amount | **ADOPT** | S | Yes - CheckConstraint |
| 16. Transaction balance validation | **ADOPT** | S | No - post() method |
| 17. Transaction UUID PK | DEFER | M | No - schema |

---

## Immediate Action Items (ADOPT)

### High Priority (Documented Invariants)

1. **django-catalog:** Add UniqueConstraint for one active basket per encounter
2. **django-worklog:** Add UniqueConstraint for one active session per user
3. **django-encounters:** Change subject_id to CharField for UUID support

### Medium Priority (Data Integrity)

4. **django-geo:** Add CheckConstraint for valid coordinates
5. **django-geo:** Add CheckConstraint for positive radius
6. **django-worklog:** Add CheckConstraint for duration consistency
7. **django-ledger:** Add CheckConstraint for positive amounts
8. **django-ledger:** Add post() method with balance validation
9. **django-encounters:** Add immutability to EncounterTransition

### Low Priority (Verification)

10. **django-catalog:** Verify WorkItem.display_name NOT NULL
11. **django-geo:** Verify Place required fields NOT NULL

---

## Overall Tier 3 Assessment

**Verdict: Production-ready with targeted hardening needed.**

All five packages implement their patterns correctly. Key gaps are:
1. **Documented invariants not DB-enforced:** active basket, active session
2. **UUID support inconsistency:** Encounter.subject_id should be CharField
3. **Audit integrity:** EncounterTransition should be immutable
4. **Accounting correctness:** Entry amounts should be positive

**Key Architectural Strengths:**
- BaseModel inheritance consistent across all packages
- Time semantics (effective_at/recorded_at) used correctly
- GenericFK with CharField pattern (except Encounter)
- Snapshot-on-commit pattern for immutable records
- Custom querysets for domain-specific queries

**Key Pattern: Idempotency**
- WorkItem: UniqueConstraint on (basket_item, spawn_role)
- DispenseLog: OneToOneField to WorkItem
- This pattern should be documented as the standard for spawn operations
