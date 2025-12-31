# Architectural Decisions

**Status:** Authoritative
**Purpose:** Explicit resolution of contradictions and key decisions

---

## Resolved Contradictions

These contradictions existed in VetFriendly planning docs. Each is now resolved with a clear decision.

---

### 1. TDD Step Count: 23 vs 26

**Contradiction:**
- `TDD_STOP_GATE.md` header says "26-step cycle"
- Some section headers referenced "23-step"
- Global `~/.claude/CLAUDE.md` mentioned both

**Decision:** **26 steps is canonical.**

**Rationale:**
The 26-step version explicitly separates:
- Step 24: Ship to repository
- Step 25: Deploy to staging
- Step 26: Deploy to production (manual only)

The 23-step version bundled these, leading to confusion about when production deploys happen.

**Canonical doc:** `/docs/process/TDD_CYCLE.md`

**Action:** All references to "23-step" are superseded.

---

### 2. Multilingual: Translation Tables vs Field Duplication

**Contradiction:**
- SYSTEM_CHARTER.md says: "Translations must not duplicate records"
- Actual implementation uses field duplication: `name`, `name_es`, `name_en`

**Decision:** **Field duplication is allowed for early versions. Translation tables are the target state.**

**Rationale:**
- Field duplication is simpler to implement and query
- Translation tables add complexity (joins, cache invalidation)
- For MVP/early versions, duplication is acceptable
- Refactor to translation tables when scaling to 5+ languages

**Migration path:**
1. Current: `name`, `name_es`, `name_en` fields (acceptable)
2. Future: `TranslatedContent` model with `language`, `field`, `value`
3. Trigger: When adding 4th language, migrate to table pattern

**Canonical doc:** Updated CONTRACT.md to allow both patterns with clear guidance.

**Action:** SYSTEM_CHARTER rule updated to: "Translations should use translation tables when supporting 4+ languages. Field duplication is acceptable for 2-3 languages."

---

### 3. Package Structure: `packages/` vs `apps/`

**Contradiction:**
- CODING_STANDARDS.md references `packages/appointments/`
- Actual codebase uses `apps/` directory
- ADR-001 describes future `packages/` structure

**Decision:** **`apps/` is current reality. `packages/` is future target. Docs reflect current state.**

**Rationale:**
- Documentation should match what exists, not aspirations
- ADR-001 describes migration path, not current state
- Confusing developers with future structure is counterproductive

**Canonical state:**
- Current: `apps/{app_name}/` for all Django apps
- Future: `packages/{package_name}/` for extracted primitives
- Transition: Happens per-package as extraction completes

**Action:** CODING_STANDARDS updated to reference `apps/` with note about future `packages/` migration.

---

### 4. WorkItem Model Location

**Contradiction:**
- WORKITEM_SYSTEM_CURRENT_STATE.md says models are in `apps/catalog/models.py`
- WORKITEM_SPAWNER_RULES.md implies a separate `apps/workitems/` module
- Planning docs inconsistent about ownership

**Decision:** **WorkItem lives in `apps/catalog/` until extracted to `django-workitems`.**

**Rationale:**
- WorkItems are spawned from BasketItems (Catalog domain)
- Keeping them together simplifies the commit_basket transaction
- When extracted, they become `django-workitems` package

**Current location:** `apps/catalog/models.py` (Basket, BasketItem, WorkItem)

**Future location:** `django-workitems` package (Tier 2 extraction)

**Action:** Planning docs updated to reflect current location.

---

### 5. Task Index Count Mismatch

**Contradiction:**
- TASK_INDEX.md shows "65 tasks / 280 hours"
- Actual task files number up to T-109 with gaps
- Count doesn't match file reality

**Decision:** **TASK_INDEX.md is superseded. Task files are source of truth.**

**Rationale:**
- Index documents become stale
- Task files (T-XXX.md) are the actual work items
- Maintaining a separate index adds overhead

**Action:**
- TASK_INDEX.md moved to archive
- Task files remain in `planning/tasks/`
- No separate index maintained (query filesystem for tasks)

---

## Key Architectural Decisions (ADRs)

### ADR-001: Monorepo with Extractable Packages

**Status:** Accepted

**Context:** VetFriendly started as a monolithic Django project. As patterns stabilized, reusable primitives emerged.

**Decision:** Extract reusable patterns into standalone pip-installable packages while maintaining a monorepo for the application.

**Structure:**
```
vetfriendly/           # Application monorepo
├── apps/              # VetFriendly-specific apps
└── requirements.txt   # Includes django-* primitives

django-primitives/     # Primitives monorepo (or separate repos)
├── django-basemodels/
├── django-party/
├── django-rbac/
└── ...
```

**Consequences:**
- Primitives must have no VetFriendly-specific code
- Primitives must be independently testable
- VetFriendly becomes a consumer of primitives

---

### ADR-002: Soft Delete by Default

**Status:** Accepted

**Context:** Medical/legal requirements demand audit trails. Hard deletes lose history.

**Decision:** All domain models inherit BaseModel with soft delete. Hard delete is explicit and audited.

**Consequences:**
- Default queryset excludes soft-deleted records
- Queries for "all including deleted" require explicit `.all_with_deleted()`
- Storage grows over time (acceptable trade-off)

---

### ADR-003: Party Pattern for Identity

**Status:** Accepted

**Context:** Users, customers, staff, organizations all have overlapping identity concepts.

**Decision:** Use Party Pattern (Person, Organization, Group, PartyRelationship) as the foundation for all identity.

**Consequences:**
- No separate Customer/Staff/Vendor models
- Relationships (ownership, employment) flow through PartyRelationship
- User (auth) is separate from Person (identity)

---

### ADR-004: Separation of Clinical/Operational/Financial

**Status:** Accepted

**Context:** Veterinary software often conflates medical records, task execution, and billing.

**Decision:** Strict separation:
- Clinical: Medical truth (EMR)
- Operational: Task execution (WorkItems)
- Financial: Accounting (downstream, observational)

**Consequences:**
- Clinical actions don't trigger inventory or accounting directly
- Triggers happen at explicit points (basket commit, workitem completion)
- Accounting never blocks clinical or operational work

---

### ADR-005: 26-Step TDD Cycle

**Status:** Accepted

**Context:** AI assistants often skip TDD despite reminders.

**Decision:** Explicit 26-step cycle with mandatory checkpoints and output confirmations.

**Consequences:**
- Every task follows the same cycle
- TDD STOP GATE must be output before implementation
- Production deploy is always manual (Step 26)

---

## Decision Log Format

Future decisions follow this format:

```markdown
### ADR-XXX: [Title]

**Status:** Proposed | Accepted | Deprecated | Superseded

**Context:** What problem or situation prompted this decision?

**Decision:** What is the decision and why?

**Consequences:** What are the results of this decision?
```

---

## Superseded Documents

These VetFriendly docs are superseded by django-primitives canonical docs:

| Superseded | Replaced By |
|------------|-------------|
| `SYSTEM_CHARTER.md` (rules) | `docs/architecture/CONTRACT.md` |
| `CODING_STANDARDS.md` | `docs/architecture/CONVENTIONS.md` |
| `ARCHITECTURE_ENFORCEMENT.md` | `docs/architecture/DEPENDENCIES.md` |
| `TDD_STOP_GATE.md` | `docs/process/TDD_CYCLE.md` |
| `TASK_INDEX.md` | Archived (query filesystem) |

The VetFriendly originals are preserved in `/docs/archive/vetfriendly-planning/`.
