# Prompt: DiveOps delta audit using existing architecture prompts

## Context
We are working in a repository that already contains:
- a set of architecture, audit, and primitives design prompts in the current working directory
- a mature, audited primitives layer (django-parties, django-geo, django-encounters, django-catalog, django-documents, django-audit, etc.)

IMPORTANT:
- The primitives have already undergone extensive architectural and audit review.
- You must NOT re-review, redesign, or second-guess the primitives.
- Your scope is LIMITED to the DiveOps domain code added on top of primitives.

## Task 1: Read the existing prompts
1) Read ALL prompts in the current working directory.
2) Extract the explicit rules, invariants, and architectural decisions they define, especially regarding:
   - audit logging
   - database constraints
   - service-layer mutation boundaries
   - use of primitives vs domain code
   - prohibition on stringly-typed fields
3) Treat these prompts as authoritative constraints, not suggestions.

Deliverable: a concise list of enforced architectural rules derived from the prompts.

## Task 2: Identify DiveOps delta surface
Identify ALL code that exists in DiveOps that:
- does not exist in primitives
- extends or orchestrates primitives
- introduces new state, workflow, or decisioning

Examples (not exhaustive):
- DiverProfile
- CertificationLevel / DiverCertification
- TripRequirement
- DiveTrip domain fields
- Booking services
- Eligibility decisioning
- Audit emission logic
- Forms/admin/views added for DiveOps

Deliverable: a clear list of DiveOps-owned models, services, selectors, and UI paths.

## Task 3: Audit DiveOps code against architectural rules
For EACH DiveOps-owned component, verify:

### A) Database correctness
- Are timeless invariants enforced via Postgres constraints?
- Are there any invariants incorrectly enforced only in Python?
- Are there any stringly-typed fields where normalized relations are required?

### B) Primitive boundaries
- Does DiveOps duplicate responsibilities already owned by primitives?
- Are documents handled exclusively via django-documents?
- Are identities handled exclusively via django-parties?
- Is lifecycle state delegated to django-encounters?

### C) Audit integration
- Are ALL diver-related and trip-related mutations emitting audit events?
- Are audit events emitted at explicit mutation boundaries (services/forms), not signals?
- Are audit actions using stable action strings?
- Do audit payloads include IDs (not names only)?
- Are deletions (soft or hard) audited correctly?

### D) Services and decisioning
- Are all mutations routed through services (or a single canonical mutation path)?
- Is decisioning side-effect free?
- Are required_actions machine-readable and complete?

### E) Selectors and performance
- Are selectors used instead of ad-hoc ORM queries?
- Are select_related / prefetch_related used correctly to avoid N+1?
- Are any queries leaking primitive internals into UI layers?

Deliverable: a structured review with:
- PASS / FAIL per category
- specific code locations for failures
- concrete recommendations to fix failures

## Task 4: Identify missing audit coverage
Produce a checklist of DiveOps actions that SHOULD emit audit events, and mark:
- implemented
- missing
- partially implemented

Do NOT include primitive-level events (assume primitives already emit their own audit logs).

## Task 5: Produce an actionable remediation plan
Based on findings, produce:
- a prioritized list of fixes
- which fixes require DB migrations
- which fixes require service refactors
- which fixes require UI/form changes
- which fixes require new tests

Keep the plan DiveOps-scoped only.

## Constraints (DO NOT VIOLATE)
- Do NOT re-audit primitives.
- Do NOT propose new primitives.
- Do NOT move logic into primitives.
- Do NOT introduce local audit tables.
- Treat existing prompts as binding architectural law.

## Output format
1) Architectural rules summary
2) DiveOps delta inventory
3) Audit findings (by category)
4) Missing audit coverage checklist
5) Remediation plan

Be precise. Cite code locations. No speculation.
