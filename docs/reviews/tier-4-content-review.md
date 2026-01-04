# Tier 4: Content - Deep Review

**Review Date:** 2026-01-02
**Reviewer:** Claude Code (Opus 4.5)
**Packages:** django-documents, django-notes, django-agreements

---

## 1. django-documents

### Purpose
File attachments with checksum verification, retention policies, and expiration tracking.

### Architecture
```
Document (BaseModel)
├── target: GenericFK to any model (CharField for UUID)
├── file: FileField with upload path
├── filename, content_type, file_size
├── document_type (classification)
├── checksum: SHA-256 for integrity verification
├── retention_days, retention_policy, expires_at
└── metadata: JSON for extensibility

DocumentQuerySet:
├── for_target(obj) → documents for object
├── expired() → past expiration
└── not_expired() → valid documents

Services:
├── attach_document() → create with computed checksum
└── verify_document_integrity() → check checksum
```

### What Should NOT Change

1. **Document extends BaseModel** - Gets UUID, timestamps, soft-delete
2. **GenericFK with CharField** - Correct for UUID support
3. **Checksum computation pattern** - SHA-256 is appropriate
4. **Service layer for attach** - Computes checksum atomically
5. **Retention as policy, not hard delete** - Correct pattern
6. **Indexes on target, document_type, checksum** - Good for queries

---

### Opportunity 1: Add CheckConstraint for positive file_size

**Current State:**
`file_size` is PositiveBigIntegerField but could be 0 for a valid file.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint ≥ 0 | Enforce non-negative | Matches PositiveBigIntegerField | Already implicit in field type |
| B) Keep as-is | PositiveBigIntegerField already validates | Simple | None |

**Risk/Reward:** Zero risk, zero reward (already enforced by field type)
**Effort:** N/A
**Recommendation:** **Already Done** - PositiveBigIntegerField enforces ≥ 0

---

### Opportunity 2: Add index on expires_at for cleanup queries

**Current State:**
No index on `expires_at`. Cleanup queries (`expires_at < now`) would do full table scan.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add simple index | `db_index=True` on expires_at | Fast cleanup queries | Extra write overhead |
| B) Add partial index | Index only non-null expires_at | Smaller index | Postgres-specific |
| C) Keep as-is | No index | Simple | Slow cleanup at scale |

**Risk/Reward:** Low risk, medium reward (operational efficiency)
**Effort:** S
**Recommendation:** **ADOPT** - Add `db_index=True` to expires_at

---

### Opportunity 3: Make checksum immutable after initial save

**Current State:**
Checksum can be modified via `save()`. Once computed, it should never change.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add save() check | Raise if checksum changes after create | Data integrity | Code change |
| B) Rely on service layer | Trust attach_document() is only entry | Flexible | Bypass possible |

**Risk/Reward:** Low risk, high reward (document integrity)
**Effort:** S
**Recommendation:** **ADOPT** - Prevent checksum modification in save()

---

### Opportunity 4: Add CheckConstraint for retention_policy values

**Current State:**
`retention_policy` is CharField with default 'standard'. No DB enforcement.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add TextChoices + CheckConstraint | DB enforces valid policies | Data integrity | Limits extensibility |
| B) Keep as-is | Flexible for custom policies | Extensible | No validation |

**Risk/Reward:** Low risk, low reward (extensibility may be desired)
**Effort:** S
**Recommendation:** **DEFER** - Keep flexible; validate in service layer

---

## 2. django-notes

### Purpose
Attachable notes and tagging system for any model.

### Architecture
```
Note (BaseModel)
├── target: GenericFK (CharField for UUID)
├── content: TextField
├── author: FK to User (SET_NULL)
├── visibility: TextChoices (public/internal/private)
└── metadata: JSON

Tag (BaseModel)
├── name, slug (unique), color, description
└── Simple categorization taxonomy

ObjectTag (BaseModel)
├── target: GenericFK
├── tag: FK to Tag
├── tagged_by: FK to User (SET_NULL)
└── unique_together: [content_type, target_id, tag]
```

### What Should NOT Change

1. **All models extend BaseModel** - Correct
2. **GenericFK with CharField** - Correct for UUID support
3. **SET_NULL on author/tagged_by** - Preserves notes if user deleted
4. **Tag.slug unique** - Already enforced
5. **unique_together on ObjectTag** - Prevents duplicate tagging
6. **Indexes on target, visibility, author, tag** - Good coverage

---

### Opportunity 5: Convert unique_together to UniqueConstraint

**Current State:**
`unique_together = ['target_content_type', 'target_id', 'tag']` - Deprecated syntax.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Use UniqueConstraint | Modern Django syntax | Future-proof; consistent | Migration required |
| B) Keep as-is | Works correctly | No change | Deprecated syntax |

**Constraint Example:**
```python
models.UniqueConstraint(
    fields=['target_content_type', 'target_id', 'tag'],
    name='objecttag_unique_target_tag'
)
```

**Risk/Reward:** Low risk, low reward (stylistic, deprecated syntax)
**Effort:** S
**Recommendation:** **ADOPT** - Modernize to UniqueConstraint

---

### Opportunity 6: Add CheckConstraint for Note.visibility values

**Current State:**
TextChoices but no DB enforcement.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint | DB enforces valid visibility | Data integrity | Low value |
| B) Keep as-is | TextChoices validates in forms | Simple | Raw SQL can bypass |

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(visibility__in=['public', 'internal', 'private']),
    name='note_valid_visibility'
)
```

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - TextChoices sufficient

---

### Opportunity 7: Add CheckConstraint for Tag.color format

**Current State:**
`color` is CharField(max_length=7) with default '#808080'. No format validation.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add regex CheckConstraint | Validate hex format | Data integrity | Complex regex in DB |
| B) Add model clean() | Python validation | Simple | Bypassed by bulk ops |
| C) Keep as-is | Trust application | Flexible | Invalid colors possible |

**Risk/Reward:** Low risk, medium reward (UI consistency)
**Effort:** S (clean() is easier than regex constraint)
**Recommendation:** **DEFER** - Add clean() validation if needed; DB regex is overkill

---

### Opportunity 8: Add NOT NULL check for Note.content

**Current State:**
`content = TextField()` - Django TextField is NOT NULL by default but verify.

**Risk/Reward:** Zero risk (verify only)
**Effort:** S
**Recommendation:** **ADOPT** - Verify migration has NOT NULL

---

## 3. django-agreements

### Purpose
Temporal fact store for agreements between parties with immutable version history.

### Architecture
```
Agreement (BaseModel)
├── party_a, party_b: GenericFK to any party (PROTECT)
├── scope_type, scope_ref: Agreement classification
├── terms: JSON (projection of current version)
├── valid_from, valid_to: Effective dating
├── agreed_at, agreed_by: Decision surface fields
├── current_version: Denormalized counter
└── CheckConstraint: valid_to > valid_from

AgreementVersion (BaseModel, IMMUTABLE)
├── agreement: FK (CASCADE)
├── version: PositiveIntegerField
├── terms: JSON snapshot (frozen)
├── created_by, reason
└── UniqueConstraint: (agreement, version)

Services:
├── create_agreement() → atomic with initial version
├── amend_agreement() → new version, update projection
├── terminate_agreement() → set valid_to, record version
└── get_terms_as_of() → historical term lookup
```

### What Should NOT Change

1. **Extends BaseModel** - Correct for domain model
2. **PROTECT on party FKs** - Don't delete party with active agreements
3. **GenericFK with CharField** - Correct for UUID support
4. **CheckConstraint for valid_to > valid_from** - Already implemented!
5. **UniqueConstraint on (agreement, version)** - Already implemented!
6. **Service layer with select_for_update()** - Correct for concurrent amendments
7. **Version as ledger pattern** - Create-only, never modify

---

### Opportunity 9: Add immutability to AgreementVersion save()

**Current State:**
AgreementVersion is documented as immutable but can be modified via save().

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Override save() | Raise on update if pk exists | Enforces immutability | Code change |
| B) Keep as-is | Trust service layer | Flexible | Updates possible |

**Example:**
```python
def save(self, *args, **kwargs):
    if self.pk and AgreementVersion.objects.filter(pk=self.pk).exists():
        raise RuntimeError("AgreementVersion is immutable after creation")
    super().save(*args, **kwargs)
```

**Risk/Reward:** Low risk, high reward (ledger integrity)
**Effort:** S
**Recommendation:** **ADOPT** - Enforce immutability in save() like django-audit-log

---

### Opportunity 10: Add CheckConstraint for scope_type values

**Current State:**
`scope_type` is CharField with no validation. Documented examples: order, subscription, consent.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add TextChoices + CheckConstraint | DB enforces valid types | Data integrity | Limits extensibility |
| B) Keep as-is | Flexible for application-specific types | Extensible | No validation |

**Risk/Reward:** Medium risk (limits flexibility), low reward
**Effort:** S
**Recommendation:** **AVOID** - scope_type intentionally flexible for domain use

---

### Opportunity 11: Add index for as_of() queries

**Current State:**
Index exists: `['valid_from', 'valid_to']`. The as_of() query uses both fields correctly.

**Risk/Reward:** N/A
**Effort:** N/A
**Recommendation:** **Already Done** - Index covers the query pattern

---

### Opportunity 12: Add effective_at to AgreementVersion

**Current State:**
get_terms_as_of() filters by created_at (when recorded), not by when terms became effective. Service docstring notes this limitation.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add effective_at field | Support true temporal queries | Correct temporal semantics | Schema change; complexity |
| B) Keep as-is | created_at is sufficient for audit | Simple | Limited temporal queries |

**Risk/Reward:** Medium risk (schema change), medium reward
**Effort:** M
**Recommendation:** **DEFER** - Document limitation; add if temporal queries needed

---

## Tier 4 Summary

### django-documents

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 1. file_size positive | Already Done | N/A | Yes - field type |
| 2. Index on expires_at | **ADOPT** | S | Yes - Index |
| 3. Checksum immutability | **ADOPT** | S | No - save() override |
| 4. retention_policy values | DEFER | S | Yes |

### django-notes

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 5. unique_together → UniqueConstraint | **ADOPT** | S | Yes - style |
| 6. Visibility CheckConstraint | DEFER | S | Yes |
| 7. Tag.color format | DEFER | S | No - clean() |
| 8. Note.content NOT NULL | **ADOPT** | S | Yes - verify |

### django-agreements

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 9. AgreementVersion immutability | **ADOPT** | S | No - save() override |
| 10. scope_type values | AVOID | S | Yes |
| 11. Index for as_of() | Already Done | N/A | Yes |
| 12. effective_at field | DEFER | M | No - schema |

---

## Immediate Action Items (ADOPT)

### High Priority (Data Integrity)

1. **django-documents:** Add `db_index=True` to expires_at for cleanup queries
2. **django-documents:** Add checksum immutability check in save()
3. **django-agreements:** Add immutability to AgreementVersion save()

### Medium Priority (Modernization)

4. **django-notes:** Convert unique_together to UniqueConstraint

### Low Priority (Verification)

5. **django-notes:** Verify Note.content is NOT NULL in migration

---

## Overall Tier 4 Assessment

**Verdict: Production-ready with minor hardening opportunities.**

All three packages implement sophisticated content patterns correctly:
- GenericFK with CharField for UUID support (consistent across all)
- Service layer for complex operations (documents, agreements)
- Retention and expiration policies (documents)
- Visibility controls (notes)
- Versioned ledger pattern (agreements)

**Key Architectural Strengths:**
- BaseModel inheritance consistent
- Checksum verification for document integrity
- Append-only versioning for agreements
- Proper soft-delete via BaseModel
- Well-designed querysets (for_target, as_of, etc.)

**Key Pattern: Projection + Ledger (Agreements)**
- Agreement.terms is the projection (current state)
- AgreementVersion is the ledger (immutable history)
- Services maintain consistency between them
- This pattern should be documented as standard for versioned entities

**Key Pattern: Immutable After Creation**
- Checksum in documents should not change
- AgreementVersion should never be modified
- Both should enforce in save() like django-audit-log

**What's Already Good:**
- CheckConstraint for valid_to > valid_from (agreements)
- UniqueConstraint on (agreement, version)
- PROTECT on party FKs
- Index on [valid_from, valid_to]
- Composite indexes on GenericFK fields

**What NOT to change:**
- Service layer patterns
- GenericFK with CharField
- Retention policy flexibility
- scope_type flexibility
