# PostgreSQL Integrity Sweep Report

**Date:** 2026-01-02
**Scope:** All 18 django-primitives packages
**Status:** Analysis Complete

---

## Executive Summary

| Category | Count |
|----------|-------|
| Existing DB Constraints | 24 |
| Gaps Identified | 11 |
| P0 (Critical) | 4 |
| P1 (Important) | 4 |
| P2 (Nice-to-have) | 3 |

---

## Current State: Existing DB Constraints

### django-agreements
| Constraint | Type | Description |
|------------|------|-------------|
| `agreements_valid_to_after_valid_from` | CHECK | valid_to > valid_from OR NULL |
| `unique_agreement_version` | UNIQUE | (agreement, version) |

### django-catalog
| Constraint | Type | Description |
|------------|------|-------------|
| `unique_active_basket_per_encounter` | Partial UNIQUE | One draft basket per encounter |
| `unique_workitem_per_basketitem_role` | UNIQUE | (basket_item, spawn_role) |

### django-geo
| Constraint | Type | Description |
|------------|------|-------------|
| `place_valid_latitude` | CHECK | -90 <= latitude <= 90 |
| `place_valid_longitude` | CHECK | -180 <= longitude <= 180 |
| `servicearea_valid_latitude` | CHECK | -90 <= center_latitude <= 90 |
| `servicearea_valid_longitude` | CHECK | -180 <= center_longitude <= 180 |
| `servicearea_positive_radius` | CHECK | radius_km > 0 |

### django-ledger
| Constraint | Type | Description |
|------------|------|-------------|
| `entry_amount_positive` | CHECK | amount > 0 |

### django-modules
| Constraint | Type | Description |
|------------|------|-------------|
| `unique_org_module_state` | UNIQUE | (org, module) |

### django-notes
| Constraint | Type | Description |
|------------|------|-------------|
| `objecttag_unique_per_target` | UNIQUE | (target_content_type, target_id, tag) |
| Tag.slug | UNIQUE (field) | Globally unique slug |

### django-parties
| Constraint | Type | Description |
|------------|------|-------------|
| `address_exactly_one_party` | CHECK | XOR: person/org/group |
| `phone_exactly_one_party` | CHECK | XOR: person/org/group |
| `email_exactly_one_party` | CHECK | XOR: person/org/group |
| `partyurl_exactly_one_party` | CHECK | XOR: person/org/group |

### django-rbac
| Constraint | Type | Description |
|------------|------|-------------|
| `role_hierarchy_level_range` | CHECK | 10 <= hierarchy_level <= 100 |

### django-sequence
| Constraint | Type | Description |
|------------|------|-------------|
| `sequence_unique_per_scope_org` | UNIQUE | (scope, org_content_type, org_id) |

### django-worklog
| Constraint | Type | Description |
|------------|------|-------------|
| `unique_active_session_per_user` | Partial UNIQUE | One active session per user |
| `worksession_duration_consistency` | CHECK | (stopped_at, duration) both null or both set |

---

## Gap Analysis: Python-Only Enforcement

### P0 - Critical (Data Corruption Risk)

#### G-001: BasketItem quantity must be positive

**Package:** django-catalog
**Model:** BasketItem
**Field:** quantity (PositiveIntegerField)
**Current State:** Allows 0 (meaningless)
**Risk:** Invalid basket items with qty=0
**Solution:** Add CHECK(quantity > 0)

```python
models.CheckConstraint(
    condition=models.Q(quantity__gt=0),
    name="basketitem_quantity_positive",
)
```

#### G-002: WorkItem priority range 0-100

**Package:** django-catalog
**Model:** WorkItem
**Field:** priority (PositiveSmallIntegerField)
**Current State:** Help text says 0-100, not enforced
**Risk:** Priority values outside expected range
**Solution:** Add CHECK(priority >= 0 AND priority <= 100)

```python
models.CheckConstraint(
    condition=models.Q(priority__gte=0) & models.Q(priority__lte=100),
    name="workitem_priority_range",
)
```

#### G-003: DispenseLog quantity must be positive

**Package:** django-catalog
**Model:** DispenseLog
**Field:** quantity (PositiveIntegerField)
**Current State:** Allows 0 (meaningless for dispensing)
**Risk:** Invalid dispense records
**Solution:** Add CHECK(quantity > 0)

```python
models.CheckConstraint(
    condition=models.Q(quantity__gt=0),
    name="dispenselog_quantity_positive",
)
```

#### G-004: Sequence current_value non-negative

**Package:** django-sequence
**Model:** Sequence
**Field:** current_value (PositiveBigIntegerField)
**Current State:** Field type prevents negative, but explicit constraint is good practice
**Risk:** Low (field type handles it)
**Solution:** Defer - PositiveBigIntegerField is sufficient

---

### P1 - Important (Business Logic Integrity)

#### G-005: UserRole valid_to after valid_from

**Package:** django-rbac
**Model:** UserRole
**Fields:** valid_from, valid_to
**Current State:** No constraint
**Risk:** Invalid date ranges for role assignments
**Solution:** Add CHECK(valid_to > valid_from OR valid_to IS NULL)

```python
models.CheckConstraint(
    condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=models.F('valid_from')),
    name="userrole_valid_to_after_valid_from",
)
```

#### G-006: Agreement valid_from required (NOT NULL)

**Package:** django-agreements
**Model:** Agreement
**Field:** valid_from (DateTimeField)
**Current State:** Field is NOT NULL, but explicit constraint documents intent
**Risk:** Low (already NOT NULL)
**Solution:** Defer - field is NOT NULL

#### G-007: PartyRelationship exactly-one-from constraint

**Package:** django-parties
**Model:** PartyRelationship
**Fields:** from_person, from_organization
**Current State:** Python clean() validates, no DB constraint
**Risk:** Invalid relationships via raw SQL
**Solution:** Add CHECK constraint

```python
models.CheckConstraint(
    condition=(
        (models.Q(from_person__isnull=False) & models.Q(from_organization__isnull=True)) |
        (models.Q(from_person__isnull=True) & models.Q(from_organization__isnull=False))
    ),
    name="partyrelationship_exactly_one_from",
)
```

#### G-008: PartyRelationship exactly-one-to constraint

**Package:** django-parties
**Model:** PartyRelationship
**Fields:** to_person, to_organization, to_group
**Current State:** Python clean() validates, no DB constraint
**Risk:** Invalid relationships via raw SQL
**Solution:** Add CHECK constraint

```python
models.CheckConstraint(
    condition=(
        (models.Q(to_person__isnull=False) & models.Q(to_organization__isnull=True) & models.Q(to_group__isnull=True)) |
        (models.Q(to_person__isnull=True) & models.Q(to_organization__isnull=False) & models.Q(to_group__isnull=True)) |
        (models.Q(to_person__isnull=True) & models.Q(to_organization__isnull=True) & models.Q(to_group__isnull=False))
    ),
    name="partyrelationship_exactly_one_to",
)
```

---

### P2 - Nice to Have (Defense in Depth)

#### G-009: AuditLog immutability

**Package:** django-audit-log
**Model:** AuditLog
**Current State:** save() raises on update, delete() raises always
**Risk:** Raw SQL can bypass
**Solution:** PostgreSQL trigger (complex, deferred)
**Status:** WONT_FIX - Python enforcement sufficient for intended use

#### G-010: EncounterTransition immutability

**Package:** django-encounters
**Model:** EncounterTransition
**Current State:** save() raises on update
**Risk:** Raw SQL can bypass
**Solution:** PostgreSQL trigger (complex, deferred)
**Status:** WONT_FIX - Python enforcement sufficient

#### G-011: Document checksum immutability

**Package:** django-documents
**Model:** Document
**Current State:** save() prevents checksum modification
**Risk:** Raw SQL can bypass
**Solution:** PostgreSQL trigger (complex, deferred)
**Status:** WONT_FIX - Python enforcement sufficient

---

## Implementation Plan

### Sprint 3: P0 Constraints

| ID | Package | Model | Constraint | Migration |
|----|---------|-------|------------|-----------|
| G-001 | django-catalog | BasketItem | quantity > 0 | 0007 |
| G-002 | django-catalog | WorkItem | 0 <= priority <= 100 | 0007 |
| G-003 | django-catalog | DispenseLog | quantity > 0 | 0007 |

### Sprint 4: P1 Constraints

| ID | Package | Model | Constraint | Migration |
|----|---------|-------|------------|-----------|
| G-005 | django-rbac | UserRole | valid_to > valid_from | 0003 |
| G-007 | django-parties | PartyRelationship | exactly_one_from | 0004 |
| G-008 | django-parties | PartyRelationship | exactly_one_to | 0004 |

### Deferred: P2 (WONT_FIX)

Immutability triggers (G-009, G-010, G-011) are deferred. Python enforcement is sufficient because:
1. These models are not modified via admin/raw SQL in normal operation
2. Triggers add operational complexity
3. Python enforcement with tests provides adequate protection

---

## Test Strategy

For each new constraint, add a regression test proving enforcement:

```python
@pytest.mark.django_db
def test_basketitem_quantity_must_be_positive():
    """BasketItem cannot have quantity <= 0."""
    with pytest.raises(IntegrityError, match="basketitem_quantity_positive"):
        BasketItem.objects.create(quantity=0, ...)
```

---

## Migration Risk Assessment

| Package | Current Data | Risk | Mitigation |
|---------|--------------|------|------------|
| django-catalog | Empty (new) | None | N/A |
| django-rbac | Empty (new) | None | N/A |
| django-parties | May have data | Low | Check data before migration |

### Pre-Migration Query

```sql
-- Check for violations before applying constraints
SELECT COUNT(*) FROM django_catalog_basketitem WHERE quantity = 0;
SELECT COUNT(*) FROM django_catalog_workitem WHERE priority < 0 OR priority > 100;
SELECT COUNT(*) FROM django_rbac_userrole WHERE valid_to IS NOT NULL AND valid_to <= valid_from;
```

---

## Canonical Prompt

```
Perform a PostgreSQL Integrity Sweep on django-primitives packages:

1. Scan each package's models.py for:
   - Existing constraints (CHECK, UNIQUE, NOT NULL)
   - Python-only enforcement (clean(), save(), property validators)

2. Classify each invariant as:
   - DB-enforceable: Single-row CHECK/UNIQUE/NOT NULL
   - App-enforced: Cross-table logic, complex validation

3. For gaps (Python-only that should be DB):
   - Prioritize: P0 (data corruption), P1 (business logic), P2 (defense in depth)
   - Propose constraint with explicit name
   - Assess migration risk

4. Create implementation plan with:
   - Migration file per package
   - Regression test per constraint
   - Pre-migration data validation query

5. Document in POSTGRES_INTEGRITY_SWEEP.md
```

---

## Appendix: Models by Package

| Package | Models | Constraint Count |
|---------|--------|------------------|
| django-audit-log | AuditLog | 0 (immutable via Python) |
| django-agreements | Agreement, AgreementVersion | 2 |
| django-basemodels | BaseModel, UUIDModel, etc. | 0 (abstract) |
| django-catalog | CatalogItem, Basket, BasketItem, WorkItem, DispenseLog | 2 + 3 pending |
| django-decisioning | IdempotencyKey, Decision | 0 |
| django-documents | Document | 0 (immutable via Python) |
| django-encounters | EncounterDefinition, Encounter, EncounterTransition | 0 (immutable via Python) |
| django-geo | Place, ServiceArea | 5 |
| django-ledger | Account, Transaction, Entry | 1 |
| django-modules | Module, OrgModuleState | 1 |
| django-notes | Note, Tag, ObjectTag | 2 |
| django-parties | Person, Organization, Group, PartyRelationship, Address, Phone, Email, Demographics, PartyURL | 4 + 2 pending |
| django-rbac | Role, UserRole | 1 + 1 pending |
| django-sequence | Sequence | 1 |
| django-singleton | SingletonModel | 0 (abstract) |
| django-worklog | WorkSession | 2 |
