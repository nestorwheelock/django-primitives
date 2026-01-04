# Tier 1: Identity - Deep Review

**Review Date:** 2026-01-02
**Reviewer:** Claude Code (Opus 4.5)
**Packages:** django-parties, django-rbac

---

## 1. django-parties

### Purpose
Implements the Party Pattern - an enterprise architecture pattern for modeling entities (Person, Organization, Group) and their relationships.

### Architecture
```
Party (abstract base)
├── Person (BaseModel + Party)
├── Organization (BaseModel + Party)
└── Group (BaseModel + Party)

Contact Models (normalized, multi-FK pattern):
├── Address → person/organization/group
├── Phone → person/organization/group
├── Email → person/organization/group
└── PartyURL → person/organization/group

Relationships:
└── PartyRelationship (from_person/from_org → to_person/to_org/to_group)
```

### What Should NOT Change

1. **Party abstract base pattern** - Correct inheritance design
2. **Person/User separation** - Person is real-world identity, User is auth; this is the right model
3. **CASCADE on relationships** - Explicitly documented, intentionally mutable state
4. **BaseModel inheritance on concrete classes** - Gets UUID, timestamps, soft-delete
5. **`clean()` validation on PartyRelationship** - Model-level invariants are correct

---

### Opportunity 1: Add CheckConstraint for exactly-one-party FK pattern

**Current State:**
Contact models (Address, Phone, Email, PartyURL) and PartyRelationship use multi-FK pattern where exactly one FK must be set. Validation is only in `clean()` (if present) - not enforced at DB level.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB-level enforcement of exactly-one-FK | Data integrity guaranteed at all entry points; catches bulk_create/raw SQL bugs | Slightly complex constraint expression; migration required |
| B) Keep as-is | Rely on model `clean()` only | No migration; simpler | Bulk operations can create invalid data; no DB-level guarantee |

**Constraint Example:**
```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=(
                Q(person__isnull=False, organization__isnull=True, group__isnull=True) |
                Q(person__isnull=True, organization__isnull=False, group__isnull=True) |
                Q(person__isnull=True, organization__isnull=True, group__isnull=False)
            ),
            name="%(class)s_exactly_one_party",
        ),
    ]
```

**Risk/Reward:** Low risk (additive, non-breaking), high reward (data integrity)
**Effort:** S (small - add constraint to 5 models)
**Recommendation:** **ADOPT** - Add to Address, Phone, Email, PartyURL, and PartyRelationship

---

### Opportunity 2: Add UniqueConstraint for primary contact per party

**Current State:**
Address, Phone, Email all have `is_primary` boolean. Nothing prevents multiple `is_primary=True` for the same party.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add partial UniqueConstraint | DB enforces max one primary per party per model | Prevents data corruption; enables `.get(is_primary=True)` without `.first()` | Need 3 constraints per model (one per party type); partial unique on nullable FK is DB-dependent |
| B) Use unique_together with condition | Postgres-specific partial index | Clean enforcement | Not portable to SQLite/MySQL for tests |
| C) Keep as-is, add application logic | Use `save()` to clear other primaries | Flexible; no migration | Race conditions possible; N+1 update pattern |

**Constraint Example (Postgres):**
```python
models.UniqueConstraint(
    fields=["person"],
    condition=Q(is_primary=True) & Q(person__isnull=False),
    name="unique_primary_phone_per_person",
)
```

**Risk/Reward:** Medium risk (DB portability), medium reward (cleaner queries)
**Effort:** M (medium - 3 constraints × 4 models = 12 constraints, test portability)
**Recommendation:** **DEFER** - Wait until Postgres is confirmed as production DB; meanwhile add service-layer enforcement

---

### Opportunity 3: Denormalize Party inline contact fields

**Current State:**
Party abstract has inline contact fields (`email`, `phone`, `address_line1`, etc.) AND normalized tables (Address, Phone, Email). This is intentional for "quick entry" but creates sync issues.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Remove inline from Party | All contact info in normalized tables only | Single source of truth; no sync issues | More joins for simple display; migration to move data |
| B) Keep both, add sync trigger | Auto-copy primary contact to inline fields | Both use cases covered | Complexity; potential data drift if sync fails |
| C) Keep as-is (current) | Inline for quick entry, normalized for full | Flexible for different contexts | Manual sync responsibility; confusing which to use |

**Risk/Reward:** High risk (breaking change), medium reward (cleaner model)
**Effort:** L (large - data migration, API changes)
**Recommendation:** **AVOID** - The current design serves a legitimate quick-entry use case. Document the pattern instead of changing it.

---

### Opportunity 4: Add NOT NULL to required contact fields

**Current State:**
- `Address.line1` - CharField, not explicitly NOT NULL (Django default is NOT NULL for CharField)
- `Address.city` - CharField, not explicitly NOT NULL
- `Phone.number` - CharField, not explicitly NOT NULL

These are implicitly NOT NULL but worth verifying migration reflects this.

**Risk/Reward:** Zero risk (verify only), low reward (documentation)
**Effort:** S (small - verify migrations)
**Recommendation:** **ADOPT** - Verify and document; no change needed if correct

---

### Opportunity 5: Add indexes for common queries

**Current State:**
No explicit indexes beyond FK auto-indexes and `is_primary` ordering.

**Likely Common Queries:**
- Find all contacts for a person: `Address.objects.filter(person=x)` - has FK index
- Find primary address: `Address.objects.filter(person=x, is_primary=True)` - no composite index
- Search people by name: `Person.objects.filter(last_name__icontains=x)` - no index

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add composite indexes | `(person, is_primary)` on contact models | Faster primary lookup | More write overhead; storage |
| B) Add name search indexes | `db_index=True` on `last_name`, `first_name` | Faster search | May not help with `__icontains` (needs trigram/full-text) |
| C) Keep as-is | Rely on FK indexes only | Simpler; avoid premature optimization | May need later if queries slow |

**Risk/Reward:** Low risk (additive), unknown reward (depends on query patterns)
**Effort:** S (small - add `db_index=True` to key fields)
**Recommendation:** **DEFER** - Wait for production query analysis; don't premature optimize

---

### Opportunity 6: Person `display_name` auto-generation

**Current State:**
`save()` auto-generates `display_name` if empty. This runs on every save.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Use `__init__` + property | Compute on read if not set | No save overhead | Property can't be queried efficiently |
| B) Use `pre_save` signal | Separate from model | Cleaner model; explicit | Another moving part |
| C) Keep as-is | Auto-generate in `save()` | Simple; works | Minor overhead on every save |

**Risk/Reward:** Zero risk, zero reward (current is fine)
**Effort:** N/A
**Recommendation:** **AVOID** - Current implementation is correct and simple

---

## 2. django-rbac

### Purpose
Role-based access control with hierarchy enforcement. Users can only manage users with lower hierarchy levels.

### Architecture
```
Role (BaseModel)
├── name, slug, description
├── hierarchy_level (10-100)
├── group → Django Group (for permissions)
└── is_active

UserRole (BaseModel + effective dating)
├── user → AUTH_USER_MODEL
├── role → Role
├── assigned_by → User
├── valid_from / valid_to (effective dating)
├── is_primary
└── SoftDeleteEffectiveDatedManager

View Mixins:
├── ModulePermissionMixin (check module.action permission)
├── HierarchyPermissionMixin (check can_manage_user)
├── CombinedPermissionMixin (both checks)
└── HierarchyLevelMixin (minimum level required)
```

### What Should NOT Change

1. **Hierarchy level enforcement** - Core security invariant, correctly implemented
2. **Role → Group linkage** - Bridges to Django's permission system correctly
3. **Effective dating on UserRole** - Enables historical queries and revocation without deletion
4. **`assigned_by` tracking** - Audit trail for role changes
5. **View mixins pattern** - Clean separation of permission concerns

---

### Opportunity 7: Add UniqueConstraint for active role assignment

**Current State:**
A user can have multiple active (not expired, not deleted) assignments of the same role. This may or may not be intended.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add partial UniqueConstraint | One active assignment per (user, role) | Prevents duplicate active roles; cleaner queries | Constraint is complex with effective dating; may break valid historical re-assignment |
| B) Keep as-is | Allow multiple active assignments | Flexible; historical assignments preserved | `current().filter(user=x, role=y)` might return multiple |
| C) Add application-layer check | Validate in `save()` | Explicit; can log warnings | Not DB-enforced; race conditions |

**Constraint Example (Complex):**
```python
# Only allow one "currently valid" assignment per user+role
# This is hard to express in CheckConstraint without stored procedures
```

**Risk/Reward:** High risk (complex constraint, may break valid use cases), medium reward
**Effort:** M (medium - design decision needed)
**Recommendation:** **DEFER** - Document expected behavior first; add constraint only if duplicates are confirmed as bugs

---

### Opportunity 8: Add CheckConstraint for hierarchy_level range

**Current State:**
`hierarchy_level` is IntegerField with no DB-level range check. Docstring says 10-100 but nothing enforces it.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB enforces 10-100 range | Invalid data impossible | Migration required; needs test update if testing with invalid values |
| B) Add model `clean()` | Python-level validation | Works for forms/admin | Bulk operations can bypass |
| C) Keep as-is | Docstring only | Flexible for future changes | No guarantee |

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(hierarchy_level__gte=10) & Q(hierarchy_level__lte=100),
    name="role_hierarchy_level_range",
)
```

**Risk/Reward:** Low risk (additive), high reward (enforces documented contract)
**Effort:** S (small - one constraint)
**Recommendation:** **ADOPT** - Add constraint; this is a documented invariant

---

### Opportunity 9: Add unique constraint on Role.slug

**Current State:**
`slug = models.SlugField(unique=True)` - Already correct! Django SlugField with `unique=True` creates a unique index.

**Risk/Reward:** N/A
**Effort:** N/A
**Recommendation:** **Already Done** - No change needed

---

### Opportunity 10: SoftDeleteEffectiveDatedManager efficiency

**Current State:**
Custom manager/queryset combines soft-delete with effective dating. The `get_queryset()` applies `deleted_at__isnull=True` filter. Methods like `as_of()` add more filters.

**Potential Issue:**
The `with_deleted()` implementation returns a new manager queryset which may not chain properly with `as_of()`.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Verify chaining works | Test `with_deleted().as_of(date)` | Ensures feature works | May find bug |
| B) Refactor to single queryset | All methods on queryset, manager delegates | Cleaner; predictable chaining | Refactor work |
| C) Keep as-is | Current implementation | Works for primary use cases | Edge cases may break |

**Risk/Reward:** Medium risk (behavioral change), low reward (edge case fix)
**Effort:** M (medium - refactor + test)
**Recommendation:** **DEFER** - Add test coverage for chaining patterns; fix only if tests fail

---

### Opportunity 11: Add is_primary unique per user constraint

**Current State:**
`UserRole.is_primary` is a boolean. Nothing prevents multiple `is_primary=True` for the same user.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add partial UniqueConstraint | One primary role per user | Clean data model | Complex with effective dating |
| B) Add save() logic | Clear other primaries on save | Flexible | Race conditions; N+1 pattern |
| C) Keep as-is | Allow multiple primaries | Simplest | Query for "primary role" may return multiple |

**Risk/Reward:** Medium risk, medium reward
**Effort:** M (medium)
**Recommendation:** **DEFER** - Same as Opportunity 2; add service-layer logic first

---

### Opportunity 12: Index valid_from and valid_to

**Current State:**
Already has `db_index=True` on both fields. Correct!

**Risk/Reward:** N/A
**Effort:** N/A
**Recommendation:** **Already Done** - No change needed

---

## Tier 1 Summary

### django-parties

| Opportunity | Action | Effort | Risk | DB Constraint? |
|-------------|--------|--------|------|----------------|
| 1. Exactly-one-party CheckConstraint | **ADOPT** | S | Low | Yes - CheckConstraint |
| 2. Primary contact UniqueConstraint | DEFER | M | Medium | Yes - Partial Unique |
| 3. Remove inline contact fields | AVOID | L | High | No |
| 4. Verify NOT NULL on required fields | **ADOPT** | S | Zero | Yes - verify existing |
| 5. Add query indexes | DEFER | S | Low | Yes - Index |
| 6. display_name auto-generation | AVOID | N/A | Zero | No |

### django-rbac

| Opportunity | Action | Effort | Risk | DB Constraint? |
|-------------|--------|--------|------|----------------|
| 7. Active role assignment unique | DEFER | M | High | Yes - Complex |
| 8. hierarchy_level range CheckConstraint | **ADOPT** | S | Low | Yes - CheckConstraint |
| 9. Role.slug unique | Already Done | N/A | N/A | Yes |
| 10. Manager chaining efficiency | DEFER | M | Medium | No |
| 11. is_primary unique per user | DEFER | M | Medium | Yes - Partial Unique |
| 12. Index valid_from/valid_to | Already Done | N/A | N/A | Yes |

---

## Immediate Action Items (ADOPT)

### 1. Add CheckConstraint for exactly-one-party (django-parties)

Apply to: `Address`, `Phone`, `Email`, `PartyURL`, `PartyRelationship`

```python
# Example for Address
class Meta:
    constraints = [
        models.CheckConstraint(
            check=(
                Q(person__isnull=False, organization__isnull=True, group__isnull=True) |
                Q(person__isnull=True, organization__isnull=False, group__isnull=True) |
                Q(person__isnull=True, organization__isnull=True, group__isnull=False)
            ),
            name="address_exactly_one_party",
        ),
    ]
```

### 2. Add CheckConstraint for hierarchy_level range (django-rbac)

```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=Q(hierarchy_level__gte=10) & Q(hierarchy_level__lte=100),
            name="role_hierarchy_level_range",
        ),
    ]
```

### 3. Verify NOT NULL constraints in migrations (django-parties)

Run: `python manage.py sqlmigrate django_parties 0001` and verify `line1`, `city`, `number` are NOT NULL.

---

## Overall Tier 1 Assessment

**Verdict: Production-ready with minor hardening opportunities.**

Both packages implement their patterns correctly. The main gaps are DB-level constraints that would enforce documented invariants. These are low-risk, high-value additions.

**Key Architectural Strengths:**
- Person/User separation is correct
- Hierarchy enforcement is correct
- Effective dating enables audit without losing data
- View mixins provide clean permission checking

**Key Documentation Needs:**
- Document multi-FK pattern and when to use inline vs normalized contacts
- Document expected behavior for multiple active role assignments
- Document cascade behavior explicitly
