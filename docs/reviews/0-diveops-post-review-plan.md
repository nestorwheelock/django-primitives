kkPrompt: DiveOps Post-Review Remediation Plan (Primitive-Compliant, TDD-Strict)
Role

You are a senior Django architect executing a post-review remediation plan for the DiveOps application.

DiveOps is an application, not a primitive.

You are correcting issues identified in the post-review document. You are not redesigning architecture, not inventing patterns, and not re-reviewing primitives.

Mandatory Pre-Reading (NO CODE UNTIL DONE)

Before planning or modifying code, you MUST re-read and summarize:

claude.md

Especially:

TDD workflow rules

Service-layer requirements

Architectural prohibitions

DiveOps / Primitives architecture documentation, including:

Any ARCHITECTURE.md

docs/architecture*.md

ADRs or design decision docs

Any docs describing:

service layer rules

audit adapter usage

BaseModel expectations

Deliverable (Required)

Produce a short Constraints Recap section listing:

Hard architectural rules

TDD requirements

Forbidden patterns (e.g. local soft delete, direct audit calls)

Do not proceed without this section.

Method Constraints (IMPORTANT)

You must follow these rules when planning and implementing fixes:

Architecture docs and claude.md are the source of truth

Prefer Django official documentation patterns

Prefer existing repository conventions

Do NOT justify choices using:

“community upvotes”

“training data popularity”

“common StackOverflow practice”

If a pattern is chosen, justify it by:

existing repo usage, or

Django docs section (by name)

No invented abstractions. No trend chasing.

Scope

Work ONLY in the DiveOps application code:

models.py

services.py

decisioning.py

audit.py (adapter only)

forms.py

views

tests

migrations

DO NOT modify primitive package internals.

Remediation Objectives

Your plan must fully address the post-review findings, including:

H-001 / H-002: All DiveOps models must inherit from django_basemodels.BaseModel

M-001: Forms must call services, not emit audit events

M-002: Remove legacy certification fields

L-001: Remove duplicate decisioning v1

L-002: Remove unused direct AuditLog import

Add missing tests (booking race, form→service enforcement)

Preserve passing test suite throughout

Required Plan Structure
Phase 1: Constraint Re-Load

Re-read required docs

Produce Constraints Recap

Phase 2: Baseline Verification

git status

run full test suite

confirm clean baseline

Phase 3: BaseModel Migration (ALL MODELS)

All DiveOps models must be migrated, not just a subset.

For EACH model class in diveops/models.py:

Identify duplicated base concerns:

UUID

timestamps

soft delete

managers

.delete() overrides

Write or adjust tests first to lock behavior

Migrate model to inherit BaseModel

Remove duplicated fields/managers/methods

Update migrations safely

Run tests incrementally

Deliverable:

Checklist confirming 100% of models migrated

Phase 4: Service-Layer Enforcement for Forms

Identify forms that:

create/update models directly

emit audit events directly

Add tests enforcing:

forms call services

services emit audit events

Refactor forms to delegate to services only

No mocks unless repo standards explicitly allow them.

Phase 5: Legacy Certification Field Removal

Locate all references to legacy fields

Migrate all callers to normalized models

Create migration to drop fields and indexes

Remove dead code

Phase 6: Decisioning Cleanup

Identify all callers of v1 decisioning

Migrate to v2

Delete v1

Run tests

Phase 7: Code Hygiene Cleanup

Remove:

unused imports

dead code

duplicate helpers

Ensure audit adapter is the sole audit entry point

Phase 8: Missing Test Coverage

Add tests for:

booking race condition (best deterministic approximation)

form → service enforcement

Tests must assert behavior, not implementation trivia.

Phase 9: Final Verification

Full test suite

Migration sanity check

Update docs:

“DiveOps models MUST inherit BaseModel”

“No local soft delete or audit logging”

Prepare clean, reviewable commits.

Guardrails (Non-Negotiable)

No primitive internals touched

No writes outside services

No audit events outside services

No local soft delete logic

No “quick fixes” that re-introduce duplication

Incremental, test-first changes only

Output Requirements

Produce:

The remediation plan structured by phases

Task list with file references

Estimated effort per phase

Explicit confirmation when ready to execute Phase 1
