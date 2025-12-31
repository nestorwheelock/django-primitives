# Architectural Contract

**Status:** Authoritative
**Scope:** All django-primitives packages

These rules are non-negotiable. If implementation violates this file, the implementation is wrong.

---

## 1. Identity (Party Pattern)

```
RULE: Party Pattern is foundational.
```

- **Person**: Real-world human identity
- **Organization**: Legal entity (business, clinic, etc.)
- **Group**: Arbitrary collection of parties
- **PartyRelationship**: All ownership, employment, guardianship, billing flows through relationships

Do NOT collapse Person/Organization/Group into a single model.

### User vs Person

| Concept | Model | Purpose |
|---------|-------|---------|
| User | `accounts.User` | Authentication/login account |
| Person | `parties.Person` | Real-world human identity |

**Constraints:**
- One Person can have multiple Users (email + Google + phone logins)
- Person can exist without User (contacts, leads, patients)
- User can exist without Person (API/service accounts)
- `User.person` FK is **nullable**

---

## 2. RBAC Hierarchy

```
RULE: Users can only manage users with LOWER hierarchy levels.
```

`Role.hierarchy_level` defines numeric power (10-100):

| Level | Role | Description |
|-------|------|-------------|
| 100 | Superuser | System admin |
| 80 | Administrator | Full system access |
| 60 | Manager | Team leads |
| 40 | Professional | Licensed professionals |
| 30 | Technician | Support staff |
| 20 | Staff | Front desk |
| 10 | Customer | End users |

**Prohibitions:**
- No escalation via convenience flags
- All escalation requires explicit role assignment
- No "is_superuser" shortcuts that bypass hierarchy

---

## 3. BaseModel + Soft Delete

```
RULE: All domain models inherit from BaseModel.
```

**BaseModel provides:**
- `id` (UUID primary key)
- `created_at` (auto-set on create)
- `updated_at` (auto-set on save)
- `deleted_at` (null = active, set = soft-deleted)

**Behaviors:**
- Default manager excludes soft-deleted records
- `delete()` sets `deleted_at`, does not remove row
- `restore()` clears `deleted_at`
- `hard_delete()` for permanent removal (rare, audited)

**Prohibition:**
- Never redefine `created_at`/`updated_at` on child models
- Never use Django's default `id` (integer) for domain models

---

## 4. Separation of Concerns

```
RULE: Clinical truth != operational tasks != inventory != accounting.
```

| Domain | Owns | Does NOT Own |
|--------|------|--------------|
| Clinical (EMR) | Medical records, diagnoses, treatments | Task execution, stock levels, money |
| Operations | Task boards, work execution, scheduling | Clinical decisions, pricing |
| Inventory | Stock truth, cost of goods | When to consume (that's Operations) |
| Accounting | Financial records, invoices, payments | Blocking clinical/operational flows |

**Key constraint:** Accounting is downstream and **never blocks** operations or clinical work.

---

## 5. Ownership Boundaries

```
RULE: Each domain owns specific data and behaviors.
```

| Owner | Owns |
|-------|------|
| Encounters | In-clinic flow only (patient physically present) |
| WorkItems | Execution of work (tasks, jobs) |
| Catalog | Definitions of orderable things |
| Inventory | Stock and cost truth |
| HR | All time tracking |
| Accounting/COGS | Observational only (derived, not authoritative) |

---

## 6. Absolute Prohibitions

These patterns are **always wrong**:

| Prohibition | Rationale |
|-------------|-----------|
| Practice storing/calculating time | HR owns time |
| SOAP/Vitals triggering tasks, inventory, or COGS | Clinical docs are passive |
| Inventory decrementing at order time | Consumption happens on WorkItem completion |
| Encounter state mirroring task boards automatically | Encounters end when patient leaves |
| Cancel/No-Show as pipeline columns | These are scheduling actions, not workflow states |

---

## 7. Trigger Rules

```
RULE: Side effects happen at specific, explicit moments.
```

| Event | Trigger Point |
|-------|---------------|
| Tasks spawn | Basket commit only |
| Inventory consumption | WorkItem completion only |
| Labor cost calculation | HR TimeEntry records only |

**No implicit triggers.** No signals that spawn work. No model.save() overrides that have side effects.

---

## 8. Append-Only Medical Records

```
RULE: Medical records are append-only with soft corrections.
```

- Never delete clinical data
- Corrections use "entered in error" pattern with reason
- All changes create audit trail entries
- Original data remains accessible for legal/compliance

---

## 9. AI Usage

```
RULE: AI may assist but never author medical truth.
```

- AI-generated content must be marked as AI-generated
- AI suggestions require explicit human acceptance
- Never auto-save AI output into medical records
- AI can read, summarize, suggest - humans approve and commit

---

## Enforcement

These rules are enforced by:
1. CI checks (see `/scripts/check_contracts.py`)
2. Code review checklist
3. Test assertions in primitive packages

Violations are bugs, not features.
