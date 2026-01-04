# Tier 2: Infrastructure - Deep Review

**Review Date:** 2026-01-02
**Reviewer:** Claude Code (Opus 4.5)
**Packages:** django-decisioning, django-audit-log

---

## 1. django-decisioning

### Purpose
Provides decision surface contracts, idempotency enforcement, and time semantics for mission-critical operations.

### Architecture
```
Core Models (plain models, not BaseModel - intentional):
├── IdempotencyKey
│   ├── scope + key (unique together)
│   ├── state machine: pending → processing → succeeded/failed
│   ├── response_snapshot (cached result for replay)
│   └── result reference (GenericFK with CharField for UUID)
│
└── Decision
    ├── effective_at / recorded_at (time semantics)
    ├── actor_user / on_behalf_of_user / authority_context
    ├── target (GenericFK with CharField for UUID)
    ├── action + snapshot + outcome
    └── finalized_at (immutability marker)

Supporting Components:
├── @idempotent decorator
├── TimeSemanticsMixin / EffectiveDatedMixin
├── EventAsOfQuerySet / EffectiveDatedQuerySet
└── Exceptions: DecisioningError, IdempotencyError, StaleRequestError
```

### What Should NOT Change

1. **Plain models.Model** - Correct; these are infrastructure, not domain models. No soft-delete needed.
2. **IdempotencyKey state machine** - pending/processing/succeeded/failed is the right pattern
3. **select_for_update() in @idempotent** - Correct for race condition prevention
4. **Decision immutability via finalized_at** - Correct pattern for audit trail
5. **GenericFK with CharField** - Correct for UUID support (documented in POSTGRES_GOTCHAS)
6. **PROTECT on actor_user** - Correct; don't lose audit trail if user deleted
7. **Time semantics: effective_at vs recorded_at** - Critical business pattern, correct

---

### Opportunity 1: Add CheckConstraint for IdempotencyKey state values

**Current State:**
State is CharField with TextChoices. Invalid states are possible via raw SQL or bulk operations.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB enforces valid states | Impossible to create invalid state | Minor; already enforced by choices in admin/forms |
| B) Keep as-is | TextChoices provides form validation | Simpler | Raw SQL can bypass |

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(state__in=['pending', 'processing', 'succeeded', 'failed']),
    name="idempotencykey_valid_state",
)
```

**Risk/Reward:** Low risk, low reward (TextChoices already validates in most paths)
**Effort:** S (small)
**Recommendation:** **DEFER** - Low priority; TextChoices is sufficient for normal use

---

### Opportunity 2: Add index for stale lock detection

**Current State:**
`locked_at` has no index. Stale lock detection query (`locked_at < X AND state = 'processing'`) would benefit.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add composite index | `(state, locked_at)` | Fast stale lock queries | Extra write overhead |
| B) Add partial index | Index only processing state | Smaller index; faster writes | Postgres-specific |
| C) Keep as-is | No stale lock detection yet | Simpler | Feature not implemented anyway |

**Risk/Reward:** Low risk, low reward (feature not implemented yet)
**Effort:** S (small)
**Recommendation:** **DEFER** - Add when implementing stale lock detection feature

---

### Opportunity 3: Add expires_at cleanup job pattern

**Current State:**
`expires_at` field exists but no cleanup mechanism documented.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add management command | `cleanup_idempotency_keys` | Simple; schedulable via cron | Manual setup |
| B) Add Celery task | Periodic cleanup task | Automatic if Celery available | Adds dependency |
| C) Keep as-is | Document manual cleanup | No code change | Unbounded growth |

**Risk/Reward:** Medium risk (operational), medium reward (prevents table bloat)
**Effort:** S (small - management command)
**Recommendation:** **ADOPT** - Add management command for cleanup (discussion only, no code change now)

---

### Opportunity 4: Decision.clean() actor validation

**Current State:**
`clean()` requires `actor_user`. But `clean()` is only called by forms, not by `save()`.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB enforces actor_user NOT NULL | Guaranteed at all entry points | Already has null=True for flexibility |
| B) Override save() | Call clean() in save() | Consistent validation | Performance overhead; may break valid use cases |
| C) Keep as-is | clean() for forms only | Flexible; allows system decisions | Service layer must enforce |

**Risk/Reward:** High risk (may break valid use cases), medium reward
**Effort:** S (small)
**Recommendation:** **AVOID** - The null=True on actor_user is intentional for system-initiated decisions. Document the expectation instead.

---

### Opportunity 5: Idempotent decorator timeout implementation

**Current State:**
`timeout` parameter exists but is documented as "not yet implemented". Stale processing states are allowed through without timeout check.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Implement timeout | Check locked_at age, force retry if stale | Recover from crashed workers | Complex; needs careful testing |
| B) Remove timeout param | Don't promise what isn't implemented | Honest API | Loses planned feature |
| C) Keep as-is | Document limitation | No code change | Confusing API |

**Risk/Reward:** Medium risk, high reward (operational reliability)
**Effort:** M (medium - needs careful design)
**Recommendation:** **DEFER** - Document limitation; implement when needed operationally

---

## 2. django-audit-log

### Purpose
Append-only, immutable audit logging for compliance and accountability.

### Architecture
```
AuditLog (plain Model, NOT BaseModel - intentional)
├── id: UUID primary key
├── Time: created_at / effective_at (time semantics)
├── Actor: actor_user (FK) + actor_display (snapshot)
├── Action: action (create/update/delete/view/login/etc.)
├── Target: model_label + object_id + object_repr (snapshots)
├── Changes: JSON diff {"field": {"old": x, "new": y}}
├── Request: ip_address, user_agent, request_id, trace_id
├── Metadata: metadata JSON, sensitivity, is_system
└── Immutability: save() prevents updates, delete() raises error

Uses: EventAsOfQuerySet from django-decisioning
```

### What Should NOT Change

1. **Plain models.Model** - Correct; audit logs don't need soft-delete (they're immutable)
2. **UUID primary key** - Correct for distributed systems
3. **save() immutability check** - Critical; audit logs must be append-only
4. **delete() raises error** - Critical; audit logs must not be deleted
5. **SET_NULL on actor_user** - Correct; preserve log even if user deleted (actor_display has snapshot)
6. **actor_display snapshot** - Critical; preserves identity even if user changes name/email
7. **Time semantics** - effective_at vs created_at distinction is correct
8. **Depends on django-decisioning** - Uses EventAsOfQuerySet; tier dependency is correct (Tier 2 → Tier 2)

---

### Opportunity 6: Add CheckConstraint for sensitivity values

**Current State:**
Sensitivity is CharField with choices. No DB-level enforcement.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB enforces valid sensitivity | Data integrity | Low value; already validated by choices |
| B) Keep as-is | Choices provides validation | Simpler | Raw SQL can bypass |

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(sensitivity__in=['normal', 'high', 'critical']),
    name="auditlog_valid_sensitivity",
)
```

**Risk/Reward:** Low risk, low reward
**Effort:** S (small)
**Recommendation:** **DEFER** - Low priority; choices validation is sufficient

---

### Opportunity 7: Add NOT NULL constraint on action field

**Current State:**
`action` is CharField with db_index but no explicit NOT NULL (Django CharField default is NOT NULL, but verify).

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Verify and document | Check migration has NOT NULL | Documentation | None |
| B) Add blank=False explicitly | Make intent clear | Self-documenting | Already default |

**Risk/Reward:** Zero risk, documentation value
**Effort:** S (small - verify only)
**Recommendation:** **ADOPT** - Verify migration; action should never be empty

---

### Opportunity 8: Add composite index for common queries

**Current State:**
Has good indexes: `(actor_user, created_at)`, `(model_label, created_at)`, `(action, created_at)`, `(object_id, model_label)`, `(effective_at)`.

**Potential Missing Query:**
- "All logs for object X" uses `(object_id, model_label)` - correct
- "Recent logs for user X" uses `(actor_user, created_at)` - correct
- "Logs for model X action Y" would need `(model_label, action, created_at)` - not present

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add 3-column index | `(model_label, action, created_at)` | Faster combined queries | Storage; write overhead |
| B) Keep as-is | Existing indexes cover most cases | Simpler | May need index intersection |

**Risk/Reward:** Low risk, unknown reward
**Effort:** S (small)
**Recommendation:** **DEFER** - Wait for production query analysis

---

### Opportunity 9: Retention policy / archival pattern

**Current State:**
No archival or retention mechanism. Table will grow unbounded.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add management command | Archive old logs to cold storage | Controlled growth | Manual scheduling |
| B) Add partitioning | Partition by created_at | Native DB archival | Postgres-specific |
| C) Add retention field | `archived_at` for soft archive | Query flexibility | Doesn't reduce table size |
| D) Keep as-is | Document table growth | No code change | Operational burden |

**Risk/Reward:** High reward (operational), medium risk (data retention policy needed)
**Effort:** M (medium - needs business decision on retention)
**Recommendation:** **ADOPT** - Document retention strategy; add management command (discussion only)

---

### Opportunity 10: Immutability bypass via QuerySet.update()

**Current State:**
`save()` prevents updates, but `AuditLog.objects.filter(...).update(...)` would bypass this.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Custom manager with update() override | Raise error on update() | Complete protection | May break legitimate admin tasks |
| B) Add DB trigger | BEFORE UPDATE trigger raises | DB-level protection | Postgres-specific; complex |
| C) Keep as-is | Document the limitation | Simple | Bypass possible |

**Risk/Reward:** Medium risk (code can bypass), medium reward
**Effort:** S (small for manager) / L (large for trigger)
**Recommendation:** **DEFER** - Document limitation; trust application layer for now

---

### Opportunity 11: Bulk insert for high-volume logging

**Current State:**
Each log entry is a separate INSERT. High-volume systems may need batching.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add bulk_log() function | Batch inserts with bulk_create | Performance | Loses per-record immutability check in save() |
| B) Keep as-is | One insert per log | Simple; guaranteed immutability | Slower for bulk |

**Risk/Reward:** Low risk, conditional reward (only if performance issue observed)
**Effort:** M (medium)
**Recommendation:** **DEFER** - Premature optimization; add if needed

---

## Tier 2 Summary

### django-decisioning

| Opportunity | Action | Effort | Risk | DB Constraint? |
|-------------|--------|--------|------|----------------|
| 1. State CheckConstraint | DEFER | S | Low | Yes |
| 2. Stale lock index | DEFER | S | Low | Yes - Index |
| 3. Cleanup command | **ADOPT** | S | Low | No |
| 4. Decision actor validation | AVOID | S | High | No |
| 5. Timeout implementation | DEFER | M | Medium | No |

### django-audit-log

| Opportunity | Action | Effort | Risk | DB Constraint? |
|-------------|--------|--------|------|----------------|
| 6. Sensitivity CheckConstraint | DEFER | S | Low | Yes |
| 7. Verify action NOT NULL | **ADOPT** | S | Zero | Yes - verify |
| 8. 3-column composite index | DEFER | S | Low | Yes - Index |
| 9. Retention/archival | **ADOPT** | M | Medium | No |
| 10. Update bypass protection | DEFER | S/L | Medium | No |
| 11. Bulk logging | DEFER | M | Low | No |

---

## Immediate Action Items (ADOPT)

### 1. Add cleanup management command (django-decisioning)

```python
# management/commands/cleanup_idempotency_keys.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        deleted, _ = IdempotencyKey.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        self.stdout.write(f"Deleted {deleted} expired keys")
```

### 2. Verify action NOT NULL (django-audit-log)

Run: `python manage.py sqlmigrate django_audit_log 0001` and verify `action` is NOT NULL.

### 3. Document retention strategy (django-audit-log)

Add to ARCHITECTURE.md:
- Recommended retention period (e.g., 7 years for compliance)
- Archival strategy (cold storage, partition by year)
- Cleanup command for expired sensitivity-based retention

---

## Cross-Package Observation

**django-audit-log depends on django-decisioning:**
- Uses `EventAsOfQuerySet` from django_decisioning.querysets
- Both are Tier 2, so this is allowed
- However, this creates an installation order dependency

**Consider:** Should EventAsOfQuerySet be in a shared utility, or is the dependency acceptable?

**Recommendation:** Acceptable as-is. Both packages are infrastructure and likely installed together.

---

## Overall Tier 2 Assessment

**Verdict: Production-ready for mission-critical operations.**

Both packages implement sophisticated patterns correctly:
- Idempotency with proper locking and state machine
- Append-only audit logging with immutability enforcement
- Time semantics (effective vs recorded) for backdating support

**Key Architectural Strengths:**
- Plain models.Model (not BaseModel) is correct for infrastructure
- GenericFK with CharField for UUID support
- Immutability enforcement in save()/delete()
- PROTECT on actor references preserves audit integrity

**Key Operational Needs:**
- Cleanup job for IdempotencyKey (prevents unbounded growth)
- Retention strategy for AuditLog (compliance + storage)
- Document timeout limitation in @idempotent

**What NOT to change:**
- Immutability patterns (save/delete overrides)
- Time semantics fields
- GenericFK implementation
- State machine in IdempotencyKey
