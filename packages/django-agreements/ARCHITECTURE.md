# Architecture: django-agreements

**Status:** Alpha / v0.2.0

---

## Design Intent

- **Append-only**: Agreements are historical facts. Amendments create versions, they don't overwrite.
- **Temporal**: Every agreement has a validity period. Query with `.current()` or `.as_of(date)`.
- **Auditable**: Complete version history preserved in AgreementVersion.
- **Infrastructure**: This is a fact store, not a workflow engine.

---

## What This Provides

| Component | Purpose |
|-----------|---------|
| Agreement | The contract between two parties with effective dating |
| AgreementVersion | Immutable amendment history (the ledger) |
| create_agreement() | Create agreement with initial version |
| amend_agreement() | Amend terms, create new version |
| terminate_agreement() | End agreement by setting valid_to |
| get_terms_as_of() | Get terms recorded by a timestamp |

---

## What This Does NOT Do

- **Approval workflows**: No draft/pending/approved states
- **Signatures**: No signature capture or verification
- **Document generation**: No PDF output
- **Notifications**: No "agreement expiring" alerts
- **Templates**: No agreement template management

If you need these, build them on top of this primitive.

---

## Hard Rules

1. **Never delete agreements** - Soft delete only. Agreements are legal evidence.
2. **Never edit terms directly** - Use `amend_agreement()`. Direct model edits bypass versioning.
3. **Never edit AgreementVersion** - It's a ledger. Append-only.
4. **valid_from is required** - No implicit defaults. Be explicit about when agreements start.
5. **valid_to > valid_from** - Enforced by database constraint.

---

## Write Authority

**Services are the only supported write path.**

```python
# CORRECT - use services
from django_agreements.services import create_agreement, amend_agreement

agreement = create_agreement(
    party_a=vendor,
    party_b=customer,
    scope_type='service_contract',
    terms={'value': 10000},
    agreed_by=user,
    valid_from=timezone.now(),
)

updated = amend_agreement(
    agreement=agreement,
    new_terms={'value': 12000},
    reason="Price adjustment",
    amended_by=user,
)
```

```python
# WRONG - bypasses versioning and invariants
agreement.terms = {'value': 12000}
agreement.save()  # NO - version not created, current_version not incremented
```

**Bypassing services voids invariants.** The system will not behave correctly.

---

## Projection vs Ledger

This package uses a **projection + ledger** pattern:

| Component | Role | Mutability |
|-----------|------|------------|
| Agreement.terms | Current projection | Updated on amend |
| AgreementVersion | Immutable ledger | Append-only |

**Why?**

- **Projection** (Agreement.terms): Fast queries for "what are the current terms?"
- **Ledger** (AgreementVersion): Complete history for "what were the terms on date X?"

The service layer keeps them in sync. If you bypass services, they drift.

---

## Concurrency

**Amendments lock the Agreement row.**

```python
# Inside amend_agreement():
agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)
```

This prevents:
- Lost updates from concurrent amendments
- Version number collisions
- Inconsistent terms/version state

**Note:** `select_for_update()` requires a real database (Postgres, MySQL). SQLite ignores it.

---

## Invariants

These must always be true:

1. **Agreement.current_version == max(versions.version)**
   - The denormalized counter matches the ledger

2. **len(versions) == current_version**
   - Every version from 1 to current_version exists

3. **valid_to is NULL or valid_to > valid_from**
   - Enforced by database constraint

4. **Agreement.terms == versions.get(version=current_version).terms**
   - The projection matches the latest ledger entry

---

## Dependencies

- **Depends on:** django-basemodels (BaseModel, SoftDeleteManager)
- **Depended on by:** (none yet)

---

## QuerySet Methods

| Method | Returns |
|--------|---------|
| `.for_party(obj)` | Agreements where obj is party_a or party_b |
| `.current()` | Agreements valid right now |
| `.as_of(timestamp)` | Agreements valid at a specific time |

All methods respect soft-delete (exclude deleted agreements by default).

---

## Database Schema

```
Agreement
├── id (UUID, PK)
├── party_a_content_type, party_a_id (GenericFK)
├── party_b_content_type, party_b_id (GenericFK)
├── scope_type (CharField)
├── scope_ref_content_type, scope_ref_id (GenericFK, optional)
├── terms (JSONField) ← current projection
├── valid_from (DateTimeField, required)
├── valid_to (DateTimeField, nullable)
├── agreed_at (DateTimeField)
├── agreed_by (FK to User)
├── current_version (PositiveIntegerField)
├── created_at, updated_at, deleted_at (from BaseModel)
└── CONSTRAINT: valid_to IS NULL OR valid_to > valid_from

AgreementVersion
├── id (UUID, PK)
├── agreement (FK to Agreement)
├── version (PositiveIntegerField)
├── terms (JSONField) ← immutable snapshot
├── created_by (FK to User)
├── reason (TextField)
├── created_at, updated_at, deleted_at (from BaseModel)
└── UNIQUE: (agreement, version)
```

---

## Future Considerations

If you need true temporal term applicability (not just "recorded by"):
- Add `effective_at` to AgreementVersion
- Update `get_terms_as_of()` to use it

If you need multi-party agreements:
- Create an AgreementParty junction table
- Keep Agreement as the anchor

If you need approval workflows:
- Build a separate workflow primitive
- Link to Agreement after approval
