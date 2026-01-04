# DiveOps Security Review and Test Plan (App Only, Evidence-Based)

## Role

You are a senior application security reviewer for a Django project. Your job is to test and verify the security posture of the DiveOps application in `testbed/primitives_testbed/diveops/`.

---

## Current Authorization Reality

**Read this first. It will save you time.**

The current auth model is **staff-only (coarse)**. There is no object-level authorization, no org-scoping, no per-shop permissions. Any authenticated staff user can access any diver, trip, or booking.

This review will:
1. **Verify staff-only enforcement now** - unauthenticated users must be denied
2. **Record object-level authorization as a tracked gap** - not a finding to repeat 19 times
3. **Test what exists, document what doesn't**

Do not produce a report full of "missing object-level auth" on every endpoint. That's known. Document it once, move on.

---

## Scope and Constraints

**IN SCOPE:** DiveOps application code only:

views (staff portal / staff views)

forms

services

decisioning

integrations

audit adapter usage (diveops/audit.py)

templates (if any)

tests and test data

OUT OF SCOPE: internal review of primitives (django-* packages). Assume primitives are correct, but verify DiveOps uses them correctly.

Do not perform destructive actions or anything resembling exploitation outside the test environment. This is defensive validation using code inspection + automated tests.

Mandatory Pre-Reading

Before writing any security tests, re-read:

claude.md (TDD rules, architecture constraints)

relevant architecture docs for:

RBAC rules

service layer contract (writes must go through services)

audit adapter contract (single entry point)
Provide a short "Security Constraints Recap" (bullet list).

---

## Security Objectives (What You Must Verify)

### 1) Authorization is enforced (staff-only for now)

**Current state:** Coarse staff-only authorization. No object-level permissions.

Verify:
- All mutating endpoints require authenticated staff user
- Unauthenticated requests are denied (redirect to login or 403)
- No endpoints accidentally left unprotected

**Known gap (document once, don't repeat):**
- No object-level authorization (any staff can access any object)
- No org/shop scoping
- This is tracked for future RBAC integration

Deliverables:
- A matrix of staff endpoints → auth check present → test coverage
- Tests that verify unauthenticated access is denied on all endpoints
- Single documented finding for missing object-level auth (not per-endpoint)

### 2) Service-layer is the only write path

DiveOps should not mutate state via:
- Forms calling model `.save()` directly
- Views performing business logic directly
- Direct audit events from forms/views bypassing services

**Service-layer auth contract:**

Services must not assume the caller is authorized. Either:
- Services perform permission checks via explicit `actor` parameter, OR
- Architecture explicitly guarantees services are only called by authorized views

Verify which contract applies and test accordingly. If views are the auth boundary, test that services cannot be imported and called from unauthorized contexts (or document that they can).

Deliverables:
- Tests that assert mutation endpoints call services (behavior-based)
- Static scan results listing any direct `.save()`, `.create()`, `.update()` usage in views/forms
- Documented answer: "Where is the authorization boundary? View or service?"

### 3) Input validation and injection resistance

Focus on the real app-level risk areas:
- User-supplied fields in forms
- Any dynamic queries (raw SQL, extra, annotate with raw)
- Template rendering of user content (XSS risk)
- Any file upload handling (certification proof docs)

Required tests:
- Attempt HTML/JS payloads in text fields and verify output is escaped
- Attempt path traversal patterns in any file or document-related inputs
- Attempt suspicious strings in fields that are used in queries

Deliverables:
- List of any raw SQL usage or unsafe query construction
- XSS posture summary: "escaped by default" vs any explicit `mark_safe` rendering

### 4) CSRF and HTTP method safety

Verify:
- All mutating endpoints require POST (or appropriate methods)
- CSRF protection is present and not accidentally disabled on staff actions
- GET requests do not mutate state

Deliverables:
- Tests that confirm GET cannot mutate state (expect 405/403)
- Tests that verify CSRF is enforced where expected

### 5) Secrets, sensitive data, and audit logging

Verify:
- No credentials/API keys in repo
- Audit metadata contains IDs and minimal context only (no PII leakage)
- Logs/audit don't leak secrets or raw documents
- No medical info, waiver contents, or PII beyond IDs in audit metadata

**Audit as a security control (not just compliance):**

Audit logging is part of detection and response. Verify:
- Failed/denied attempts are logged (at least authentication failures)
- Audit metadata includes enough to investigate incidents (actor, target, action)
- Audit adapter is the single entry point (no direct `django_audit_log` imports outside `diveops/audit.py`)

Deliverables:
- Scan results for suspicious strings ("SECRET", "API_KEY", "PASSWORD", tokens)
- Audit metadata review: list action events and confirm fields are appropriate
- Confirm integrations don't import audit primitive directly (must use adapter)
- Test that at least one denial scenario produces an audit event (or document gap)

### 6) File upload / documents handling

DiveOps uses `django_documents` for certification proofs and waivers. This is the most likely place a real leak happens.

Verify:
- Files stored through the documents primitive (not ad hoc filesystem)
- Size/type checks exist (or are delegated appropriately)
- No direct serving of private files without authorization checks
- Documents tied to a diver/booking cannot be fetched without staff auth

**Test hard for IDOR on document downloads:**
- Can an unauthenticated user access a document by ID/URL?
- Can a user access a document belonging to a different diver?
- Are document IDs exposed in templates or URLs in a guessable way?

Deliverables:
- Tests that unauthorized users cannot access uploaded docs
- Tests for file validation rules (or a documented gap)
- IDOR test specifically for document download endpoints
- List of any document URLs exposed in templates

### 7) ID guessing / enumeration

Even with UUIDs, people do dumb things. Given `django_sequence` is used for invoice numbering:

Verify:
- Endpoints don't allow enumerating invoices/bookings by sequence number
- Sequence values aren't used as authorization keys
- No sequential IDs exposed in URLs that could be enumerated
- Internal IDs aren't leaked in templates or error messages

Deliverables:
- Scan templates for exposed IDs (invoice numbers, sequence values)
- Test that sequential values (invoice numbers) can't be used to access other records
- Document any enumeration risks

### 8) Concurrency and integrity attacks (race conditions)

Verify booking capacity cannot be exceeded via rapid parallel actions.

Use `transaction.atomic` + `select_for_update` patterns if present.

Deliverables:
- A concurrency/race test (best deterministic approximation for your DB/test harness)
- Clear statement: safe / unsafe / uncertain, with evidence

### 9) Domain integrity abuse cases

These are "security" because they're integrity attacks, not just confidentiality. Test business logic boundaries:

**Booking/Trip lifecycle:**
- Can you cancel a booking after trip has started?
- Can you check in without a valid booking?
- Can you complete a trip without starting it?
- Can you book on a cancelled trip?
- Can you book on a past trip?

**Certification abuse:**
- Can you add a certification proof to the wrong diver?
- Can you verify/unverify certifications without staff auth?
- Can you modify a deleted certification?

**Eligibility bypass:**
- Can you book a diver who fails eligibility by calling services directly?
- Does `skip_eligibility_check=True` require special authorization?

Deliverables:
- Tests for each abuse scenario above
- Document any gaps where business logic doesn't enforce constraints

---

## Execution Plan (What You Must Produce)

### A) Quick Static Review (no guessing)

Run and summarize ripgrep for dangerous patterns:

```bash
# CSRF bypass
rg "csrf_exempt|@csrf_exempt" testbed/primitives_testbed/diveops/

# Raw SQL
rg "raw\(|extra\(|cursor\.execute|RawSQL" testbed/primitives_testbed/diveops/

# Unsafe template rendering
rg "mark_safe|\|safe" testbed/primitives_testbed/diveops/

# Filesystem access
rg "open\(" testbed/primitives_testbed/diveops/

# Code execution
rg "eval\(|exec\(" testbed/primitives_testbed/diveops/

# Direct model writes in views/forms (should go through services)
rg "\.save\(|\.create\(|\.update\(" testbed/primitives_testbed/diveops/views testbed/primitives_testbed/diveops/forms.py

# Direct audit imports (should only be in audit.py)
rg "from django_audit_log|import django_audit_log" testbed/primitives_testbed/diveops/ --glob '!audit.py'
```

Run dependency check if tooling exists (`pip-audit` / `safety`) and report results.

### B) Security Test Suite Additions (TDD strict)

Add tests in `diveops/tests/` using Django TestCase + client.

**Minimum required tests:**
- Staff-only deny tests for each mutating endpoint (unauthenticated → denied)
- CSRF enforcement tests for staff mutations
- GET-is-safe tests (no state changes)
- XSS escape tests for any user-displayed fields
- Document IDOR test (access proof doc without auth)
- Booking race test (concurrent booking at capacity)
- Domain abuse tests (cancel after start, check-in without booking, etc.)

### C) Findings Report (Evidence-Based)

Output:
- Executive summary: Pass / Partial / Fail
- Findings ranked by severity (Critical / High / Medium / Low)

Each finding must include:
- File/line references
- Reproduction steps (test or code path)
- Recommended fix aligned with repo architecture

### D) Non-negotiable Rules

- No changes to primitive internals
- All fixes must maintain the service-layer and audit adapter contracts
- Tests must be deterministic and run under CI

---

## Success Criteria

You are done when:
1. Security tests are added and passing
2. Staff-only authorization is demonstrably enforced on all endpoints
3. CSRF is enforced on all mutations
4. Document access is protected
5. Domain integrity abuse cases are tested
6. Any gaps are clearly documented with concrete remediation steps
7. Object-level auth gap is documented exactly once (not per-endpoint)
