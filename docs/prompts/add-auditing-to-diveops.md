# Prompt: Enforce comprehensive audit logging for all diver and trip actions in DiveOps

## Context
DiveOps (`diveops`) is a domain app built on django-primitives.
`django-audit` is installed and is the canonical audit/event log.

REQUIREMENT:
- EVERY creation, modification, and deletion of:
  - Diver-related objects
  - Trip-related objects
  MUST emit an audit event.
- EVERY action associated with trips and divers MUST be auditable.
- DiveOps must emit audit events explicitly.
- DiveOps must NOT store audit data locally.

No exceptions. No “we’ll add it later.”

## Scope: Objects that MUST be audited

### Diver-related
- django_parties.Person (when acting as a diver)
- DiverProfile
- DiverCertification
- Certification proof documents (when linked/unlinked)
- Diver activation / deactivation
- Certification verification / unverification
- Certification add / update / remove

### Trip-related
- DiveTrip
- TripRequirement
- Booking
- TripRoster
- Trip lifecycle transitions (via django-encounters)
- Booking lifecycle (booked, paid, cancelled, refunded)
- Check-in / no-show / completion
- Manual overrides (eligibility overrides, forced add/remove)

If it changes diver or trip state, it is audited.

## Task 1: Confirm django-audit API
1) Locate django-audit and confirm:
   - import path
   - how to emit an event (e.g. AuditLog.objects.log)
   - expected fields: action, target, actor, data
2) Confirm whether actor should be:
   - Django User
   - django_parties.Person
   - or GenericFK (support both if possible)

Document findings briefly in comments.

## Task 2: Define the audit action taxonomy (STABLE CONTRACT)
Create a single authoritative list of audit actions.

### Diver actions
- diver_created
- diver_updated
- diver_deleted
- diver_activated
- diver_deactivated

### Certification actions
- certification_added
- certification_updated
- certification_removed
- certification_verified
- certification_unverified
- certification_proof_uploaded
- certification_proof_removed

### Trip actions
- trip_created
- trip_updated
- trip_deleted
- trip_published
- trip_cancelled
- trip_rescheduled

### Booking / roster actions
- booking_created
- booking_cancelled
- booking_paid
- booking_refunded
- diver_checked_in
- diver_no_show
- diver_completed_trip
- diver_removed_from_trip

### Eligibility / override actions
- eligibility_checked
- eligibility_failed
- eligibility_overridden

These action strings are a public contract. Do not rename them later.

## Task 3: Implement a single audit adapter
Create `diveops/audit.py` with:

    log_event(
        *,
        action: str,
        target: Model,
        actor: Optional[Model],
        data: dict
    ) -> None

Rules:
- Thin wrapper around django-audit
- No business logic
- Include IDs in `data` (never names only)
- Fail loudly if django-audit is misconfigured
- This adapter is the ONLY place that imports django-audit

## Task 4: Wire audit logging into ALL mutation paths

### A) Services layer (primary)
Instrument all service functions that mutate diver or trip state:
- create/update/delete diver
- add/update/remove certifications
- verify/unverify certifications
- book trip
- cancel booking
- check-in
- complete trip
- override eligibility

Each mutation MUST:
- emit exactly one audit event
- emit it AFTER successful DB transaction
- include:
  - actor
  - target
  - structured data with IDs:
    - diver_id
    - diver_party_id
    - trip_id
    - booking_id
    - agency_id
    - level_id
    - document_id (if applicable)

### B) Admin / form-based mutations
If mutations occur outside services (admin/forms):
- centralize mutation logic into services
- or explicitly emit audit events in form save() / admin hooks
DO NOT rely on Django signals.

## Task 5: Deletion semantics
For deletions:
- Emit audit event BEFORE delete if hard delete
- Emit audit event AFTER flag change if soft delete
- Include previous state snapshot in data where feasible (IDs + key fields)

## Task 6: Audit selectors (read-only)
Add selectors to retrieve audit history:
- `diver_audit_feed(diver_profile_id)`
- `trip_audit_feed(trip_id)`

Selectors must:
- query django-audit
- be optimized (no N+1)
- return events ordered by timestamp desc

If UI exists:
- show audit history on diver profile and trip detail pages
Else:
- expose selectors for API/admin use

## Task 7: Tests (MANDATORY)
Add tests proving:
1) Creating a diver emits `diver_created`
2) Updating diver emits `diver_updated`
3) Deleting diver emits `diver_deleted`
4) Creating a trip emits `trip_created`
5) Booking a trip emits `booking_created`
6) Certification unverify emits `certification_unverified`

Testing rules:
- Mock ONLY the audit adapter boundary
- Assert action string, target type, and required data keys
- Do NOT test django-audit internals

## Constraints (DO NOT VIOLATE)
- No local audit tables
- No signals
- No free-form audit messages
- All mutations audited
- Use primitives correctly (audit owns storage)

## Output
- diveops/audit.py
- updated services/forms/admin hooks
- updated ARCHITECTURE.md (Audit section)
- tests proving coverage
