## Prompt: DiveOps Application Code Review (Primitive-Aware, TDD-Enforced)

### Role

You are a senior software architect performing a **deep code review** of the **DiveOps application**.
DiveOps is an **application**, not a primitive.

### Scope Rules (READ CAREFULLY)

* **DO NOT review primitive packages internally.**

  * Assume `django-basemodels`, `django-parties`, `django-rbac`, `django-encounters`, `django-documents`, `django-agreements`, `django-catalog`, `django-audit-log`, etc. are already reviewed and correct.
* **DO review how DiveOps uses primitives.**

  * Your job is to ensure primitives are used correctly, consistently, and not reimplemented or bypassed.
* Review only DiveOps domain code:

  * `models.py`
  * `services.py`
  * `decisioning.py`
  * `audit.py` (adapter only)
  * `integrations.py`
  * `views / staff_views.py`
  * `forms.py`
  * `tests/`

---

## Review Objectives

### 1. Primitive Usage & Anti-Reimplementation Audit

Identify any place where DiveOps:

* Reimplements functionality already provided by primitives
* Bypasses primitives through local logic
* Introduces “almost-the-same” abstractions (UUID models, soft delete, audit logging, RBAC, encounter state, etc.)

Deliverable:

* A table of **Local Code → Primitive That Should Be Used → Action (Remove / Refactor / Justify)**

---

### 2. Domain Model Review (models.py)

Verify that DiveOps models:

* Inherit from `django_basemodels.BaseModel` (no manual UUIDs/timestamps/soft delete)
* Use DB-level constraints for real invariants
* Use correct FK semantics (`PROTECT` where required)
* Avoid nullable FKs unless domain-justified
* Do not embed business logic in `.save()`

Flag:

* Missing constraints
* Domain invariants enforced only in UI or Python
* Soft-delete breaking uniqueness

---

### 3. Service Layer Review (services.py)

Review **all write paths**.

Ensure:

* All writes go through service functions (no business logic in views/forms)
* All write services are `@transaction.atomic`
* Race-critical paths use `select_for_update()`
* Validation occurs before side effects
* Errors propagate cleanly
* **Every write service emits an audit event**

Deliverable:

* A list of all write services and the audit action they emit
* Missing or inconsistent audit logging flagged as defects

---

### 4. Audit Adapter Review (audit.py)

Review only the adapter layer.

Verify:

* Single import point for `django_audit_log`
* Stable action constants (public contract)
* Structured, consistent metadata
* No sensitive data leakage
* No direct calls to audit primitives outside the adapter

---

### 5. Decisioning Review (decisioning.py)

Ensure:

* Eligibility rules are explicit and centralized
* Decisions are deterministic and testable
* No duplicated decision logic across views/services
* Decisions are auditable (inputs + outcome identifiable)

---

### 6. Views & Forms Review (staff_views.py, forms.py)

Check for **intern-grade mistakes**:

* Fat views doing business logic
* Missing RBAC enforcement
* Permission checks only in decorators, not services
* Repeated validation logic
* Silent exception handling
* Direct model saves bypassing services

---

### 7. Code Quality & Hygiene

Identify:

* Unused code (functions, classes, imports)
* Duplicate logic across modules
* Commented-out or fossilized code
* Magic strings instead of constants
* N+1 query patterns
* Naive datetime usage
* Missing pagination/filtering on list views

Deliverable:

* “Safe to delete” list
* “Should consolidate” list

---

### 8. Test & TDD Verification (tests/)

Assume TDD is a requirement. Verify it.

Check:

* Tests exist for every service write path
* Tests assert invariants, not just happy paths
* Permission boundaries are tested
* Audit events are asserted (action + metadata)
* Concurrency edge cases are covered where relevant
* No superficial tests that only assert HTTP 200

Deliverable:

* Feature → test coverage matrix
* Test gaps that violate TDD expectations

---

## Output Format (STRICT)

Produce:

### A. Executive Summary

* Overall quality assessment
* Highest-risk issues (top 5)

### B. Findings by Category

* Primitive misuse
* Models
* Services
* Audit
* Decisioning
* Views/Forms
* Tests
* Code hygiene

### C. Required Fixes (Ranked)

* Severity: Critical / High / Medium / Low
* File + line references
* Clear remediation guidance

### D. Primitive Compliance Summary

* Which primitives are used
* Where integration points exist
* Any forbidden local implementations found

### E. TDD Assessment

* Pass / Partial / Fail
* Evidence
* Required test additions

---

## Tone & Standards

* Be precise, technical, and critical.
* Do not praise unless justified by evidence.
* Treat missing audit logs, missing tests, or primitive bypasses as **defects**, not preferences.

