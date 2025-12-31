# Phase 0: Planning Document Inventory Report

**Project:** django-primitives
**Date:** 2025-12-31
**Source:** /home/nwheelo/projects/vetfriendly/planning/*

---

## Summary Counts

| Category | Count | Description |
|----------|-------|-------------|
| **Contract** | 14 | Architecture rules, invariants, enforcement policies |
| **Specs** | 42 | User stories, UI specs, workflow definitions |
| **Plan** | 81 | Tasks, milestones, work items |
| **Notes/History** | 18 | Research, decisions, exploration, transcripts |
| **Config** | 17 | Claude commands, settings, process docs |
| **TOTAL** | 172 | (excluding identical duplicates) |

---

## Categorized Inventory

### CONTRACT (14 docs) - Rules that must be true

| File | Purpose |
|------|---------|
| `SYSTEM_CHARTER.md` | **Source of truth** - Non-negotiable architectural rules |
| `planning/SYSTEM_EXECUTION_RULES.md` | Ownership/trigger invariants (Encounters, WorkItems, Catalog) |
| `planning/ARCHITECTURE_ENFORCEMENT.md` | Import rules, CI enforcement, allowlist format |
| `planning/CODING_STANDARDS.md` | TDD, style, commit format |
| `planning/TDD_STOP_GATE.md` | 26-step cycle enforcement |
| `planning/AI_CHARTER.md` | AI usage rules |
| `planning/catalog/CATALOG_OVERVIEW.md` | Catalog ownership boundaries |
| `planning/workitems/WORKITEM_SPAWNER_RULES.md` | WorkItem spawn invariants |
| `planning/emr/ENCOUNTER_BOARD_SPEC_V1.md` | Encounter board behavior contract |
| `planning/emr/TRANSITION_RULES_TABLE.md` | State transition validation rules |
| `planning/adr/ADR-001-commercial-licensing.md` | Licensing architecture decision |
| `planning/LICENSING.md` | License rules |
| `planning/MODULE_INTERFACES.md` | Package API contracts |
| `planning/ARCHITECTURE_DECISIONS.md` | ADR-001 target architecture |

### SPECS (42 docs) - User-facing behavior/workflows

**User Stories (36):**
- `planning/stories/S-001-foundation-ai-core.md`
- `planning/stories/S-002-ai-chat-interface.md`
- `planning/stories/S-003-pet-profiles-medical-records.md`
- `planning/stories/S-004-appointment-booking-ai.md`
- `planning/stories/S-005-ecommerce-store.md`
- `planning/stories/S-006-omnichannel-communications.md`
- `planning/stories/S-007-crm-intelligence.md`
- `planning/stories/S-008-practice-management.md`
- `planning/stories/S-009-competitive-intelligence.md`
- `planning/stories/S-010-pharmacy-management.md`
- `planning/stories/S-011-knowledge-base-admin.md`
- `planning/stories/S-012-notifications-reminders.md`
- `planning/stories/S-013-document-management.md`
- `planning/stories/S-014-reviews-testimonials.md`
- `planning/stories/S-015-emergency-services.md`
- `planning/stories/S-016-loyalty-rewards.md`
- `planning/stories/S-017-reports-analytics.md`
- `planning/stories/S-018-seo-content-marketing.md`
- `planning/stories/S-019-email-marketing.md`
- `planning/stories/S-020-billing-invoicing.md`
- `planning/stories/S-021-external-services.md`
- `planning/stories/S-022-travel-certificates.md`
- `planning/stories/S-023-data-migration.md`
- `planning/stories/S-024-inventory-management.md`
- `planning/stories/S-025-referral-network.md`
- `planning/stories/S-025b-customer-referral-program.md`
- `planning/stories/S-026-accounting.md`
- `planning/stories/S-027-delivery-module.md`
- `planning/stories/S-027-security-hardening.md` (NUMBERING CONFLICT)
- `planning/stories/S-028-error-monitoring.md`
- `planning/stories/S-079-audit-logging-staff-actions.md`
- `planning/stories/S-080-profile-icon-portal-routing.md`
- `planning/stories/S-081-hr-time-tracking.md`
- `planning/stories/S-082-task-time-tracking.md`
- `planning/stories/S-083-practice-hr-integration.md`
- `planning/stories/S-100-unified-people-architecture.md`

**EMR Specs (6):**
- `planning/emr/ENCOUNTER_TYPE_MATRIX.md`
- `planning/emr/WORK_ITEM_ROUTING_TABLE.md`
- `planning/emr/vitals/00_overview.md`
- `planning/emr/vitals/10_data_model.md`
- `planning/emr/vitals/20_ui_spec.md`
- `planning/emr/vitals/30_worklog_integration.md`
- `planning/emr/vitals/40_endpoint_contract.md`
- `planning/emr/clinical_popup/00_overview.md`
- `planning/emr/clinical_popup/10_wireframes.md`
- `planning/emr/clinical_popup/20_task_breakdown.md`
- `planning/emr/clinical_popup/30_access_control.md`

### PLAN (81 docs) - Work items/milestones

**Tasks (77):** `planning/tasks/T-001` through `T-109` (with gaps)

**Bugs (10):**
- `planning/bugs/B-007-csp-blocking-alpinejs.md`
- `planning/bugs/B-008-cart-icon-not-linked.md`
- `planning/bugs/B-050-missing-pet-delete-archive.md`
- `planning/bugs/B-051-missing-appointment-reschedule.md`
- `planning/bugs/B-052-missing-order-cancellation.md`
- `planning/bugs/B-053-missing-invoice-payment.md`
- `planning/bugs/B-054-missing-refill-cancellation.md`
- `planning/bugs/B-055-missing-email-change.md`
- `planning/bugs/B-056-pet-photo-upload-issues.md`
- `planning/bugs/CRUD-GAP-SUMMARY.md`

**Issues (2):**
- `planning/issues/I-001-cart-quantity-input-with-max.md`
- `planning/issues/MISSING_CUSTOMER_URLS.md`

**Indexes (4):**
- `planning/TASK_INDEX.md`
- `planning/TASK_BREAKDOWN.md`
- `planning/SPEC_SUMMARY.md`
- `planning/STORY_TO_TASK_CHECKLIST.md`

### NOTES/HISTORY (18 docs)

| File | Purpose |
|------|---------|
| `planning/PREPOCH.md` | Pre-development history |
| `planning/EHRNOTES.md` | EHR research notes |
| `planning/EMR_ARCHITECTURE.md` | Model duplication analysis |
| `planning/emr/DESIGN_DECISIONS_AND_RATIONALE.txt` | Decision log |
| `planning/emr/WORKITEM_SYSTEM_CURRENT_STATE.md` | Implementation status |
| `planning/emr/WORKITEM_SPAWN_AUDIT.md` | Audit results |
| `planning/ROADMAP_IDEAS.md` | Future exploration |
| `planning/devops/CHATGPT_CONTEXT.md` | DevOps context |
| `planning/continuity/README.md` | Continuity overview |
| `planning/continuity/backup_pipeline.md` | Backup procedures |
| `planning/continuity/clinic_vault.md` | Vault design |
| `planning/continuity/continuity_overview.md` | Business continuity |
| `planning/continuity/export_from_backup.md` | Export procedures |
| `planning/continuity/license_notes.md` | License notes |
| `planning/continuity/offline_mode.md` | Offline capability |
| `planning/continuity/restore_runbook.md` | Restore procedures |
| `planning/continuity/self_hosting.md` | Self-hosting guide |
| `planning/continuity/threat_model.md` | Security threats |

### CONFIG (17 docs)

| File | Purpose |
|------|---------|
| `CLAUDE.md` (vetfriendly root) | Project-specific Claude instructions |
| `~/.claude/CLAUDE.md` | Global Claude workflow (63KB) |
| `~/.claude/settings.json` | Permissions config |
| `~/.claude/commands/autonomous.md` | Mode 3 skill |
| `~/.claude/commands/bugs.md` | Bug scanning skill |
| `~/.claude/commands/hybrid.md` | Mode 2 skill |
| `~/.claude/commands/init-workflow.md` | Workflow init skill |
| `~/.claude/commands/install-hooks.md` | Git hooks skill |
| `~/.claude/commands/ludicrous.md` | Mode 5 skill |
| `~/.claude/commands/lunacy.md` | YOLO mode skill |
| `~/.claude/commands/mode.md` | Show mode skill |
| `~/.claude/commands/new-project.md` | New project skill |
| `~/.claude/commands/normal.md` | Mode 2 skill |
| `~/.claude/commands/safe.md` | Mode 1 skill |
| `~/.claude/commands/supervised.md` | Mode 1 skill |
| `~/.claude/commands/sync-workflow.md` | Sync workflow skill |
| `~/.claude/commands/yolo.md` | Mode 4 skill |

---

## Top 10 Duplicates Identified

| # | Files | Status |
|---|-------|--------|
| 1 | `planning/CLAUDE_IMPLEMENTATION_PROMPT.md` vs `planning/planning/CLAUDE_IMPLEMENTATION_PROMPT.md` | **IDENTICAL** - nested duplicate |
| 2 | `planning/emr/vitals/*` vs `planning/planning/emr/vitals/*` | **IDENTICAL** - 5 duplicate files |
| 3 | `planning/worklog/*` vs `planning/planning/worklog/*` | **IDENTICAL** - 5 duplicate files |
| 4 | `S-027-delivery-module.md` vs `S-027-security-hardening.md` | **NUMBERING CONFLICT** - same S-number |
| 5 | `TASK_INDEX.md` vs `TASK_BREAKDOWN.md` | **CONTENT OVERLAP** - both list all tasks |
| 6 | `CODING_STANDARDS.md` vs `TDD_STOP_GATE.md` | **REDUNDANT** - TDD rules in both |
| 7 | `SYSTEM_CHARTER.md` vs `CLAUDE.md` (vetfriendly) | **SUMMARY DUPLICATION** - CLAUDE.md summarizes Charter |
| 8 | `ARCHITECTURE_ENFORCEMENT.md` vs `CODING_STANDARDS.md` | **CROSS-REF** - import rules in both |
| 9 | `planning/catalog/WORKITEM_ROUTING.md` vs `planning/emr/WORK_ITEM_ROUTING_TABLE.md` | **TOPIC OVERLAP** - same subject |
| 10 | `TDD_STOP_GATE.md` refs 23-step vs `~/.claude/CLAUDE.md` refs 26-step | **VERSION MISMATCH** |

---

## Top 5 Contradictions Identified

| # | Contradiction | Files | Resolution Needed |
|---|--------------|-------|-------------------|
| 1 | **Step count mismatch**: TDD_STOP_GATE says "26-step cycle" but section headers say "23-step" | `TDD_STOP_GATE.md`, global `CLAUDE.md` | Standardize to 26-step |
| 2 | **Multilingual rule conflict**: SYSTEM_CHARTER says "Translations must not duplicate records" but notes current implementation uses field duplication (name, name_es, name_en) | `SYSTEM_CHARTER.md:102-104` | Decide: refactor or update rule |
| 3 | **Package structure confusion**: CODING_STANDARDS references `packages/appointments/` but current code uses `apps/` | `CODING_STANDARDS.md` vs actual codebase | Update docs to match reality |
| 4 | **WorkItem location**: WORKITEM_SYSTEM_CURRENT_STATE says models are in `apps/catalog/models.py` but WORKITEM_SPAWNER_RULES implies separate module | Planning docs | Verify actual implementation |
| 5 | **TASK_INDEX shows 65 tasks / 280 hours**, but actual task files number up to T-109 with gaps | `TASK_INDEX.md` | Reconcile counts |

---

## Stale Documents (Clearly Superseded)

| File | Reason |
|------|--------|
| `planning/planning/*` (entire nested directory) | Duplicate of parent - can be deleted |
| `planning/emr/CLAUDE_HANDOFF_V1.txt` | Superseded by `CLAUDE_HANDOFF_PROTOCOL.md` |
| `planning/emr/USER_STORIES_V1.txt` | Superseded by `planning/stories/S-*.md` files |
| `planning/emr/BUTTON_MATRIX_V1.txt` | Superseded by `BUTTON_STATE_MODEL_V2.txt` |
| `planning/MODULE_EXTRACTION_PLAN_COMPLETE.md` | Historical - extraction completed |

---

## Recommendations

1. **Delete `planning/planning/` directory** - All 11 files are exact duplicates
2. **Fix S-027 numbering conflict** - Rename one story
3. **Consolidate TDD docs** - Merge TDD_STOP_GATE into CODING_STANDARDS or vice versa
4. **Update step count** - Standardize on 26-step cycle everywhere
5. **Archive V1 `.txt` files** - Move to `planning/archive/` or delete
6. **Reconcile TASK_INDEX** - Update to match actual T-XXX files

---

## Extraction Candidates for Django-Primitives

Based on this inventory, the following patterns are candidates for extraction into reusable Django packages:

### Tier 1: Core Architectural Patterns (extract first)

| Pattern | Source Docs | Package Name |
|---------|-------------|--------------|
| **Party Pattern** | SYSTEM_CHARTER.md | `django-party` |
| **Soft Delete / BaseModel** | SYSTEM_CHARTER.md | `django-softdelete` |
| **RBAC Hierarchy** | SYSTEM_CHARTER.md | `django-rbac` |
| **Audit Trail** | SYSTEM_CHARTER.md, S-079 | `django-audit` |

### Tier 2: Domain Patterns (extract after Tier 1)

| Pattern | Source Docs | Package Name |
|---------|-------------|--------------|
| **Catalog System** | catalog/*.md | `django-catalog` |
| **WorkItem/Task Spawning** | workitems/*.md | `django-workitems` |
| **Encounter Pipeline** | emr/ENCOUNTER_*.md | `django-encounters` |
| **WorkSession Timing** | worklog/*.md | `django-worklog` |

### Tier 3: Infrastructure Patterns

| Pattern | Source Docs | Package Name |
|---------|-------------|--------------|
| **Module Configuration** | SYSTEM_CHARTER.md | `django-modules` |
| **Singleton Settings** | SYSTEM_CHARTER.md | `django-singleton` |
| **Layer Enforcement** | ARCHITECTURE_ENFORCEMENT.md | `django-layers` |

---

## Contract Rules Summary (for django-primitives)

### From SYSTEM_CHARTER.md

```
IDENTITY
- Party Pattern is foundational (Person/Organization/Group/PartyRelationship)
- User (auth) is separate from Person (identity)
- One Person can have multiple Users
- User.person FK is nullable

RBAC
- Role.hierarchy_level defines power (10-100)
- Users can only manage users with LOWER hierarchy levels
- No escalation via convenience flags

DATA INTEGRITY
- All domain models inherit BaseModel with soft delete
- Medical records are append-only with soft corrections
- All stock movements must be source-linked

SEPARATION
- Clinical truth != operational tasks != inventory != accounting
- Accounting is downstream, never blocks operations
```

### From SYSTEM_EXECUTION_RULES.md

```
OWNERSHIP
- Encounters own in-clinic flow only
- WorkItems own execution of work
- Catalog owns definitions of orderable things
- Inventory owns stock and cost truth
- HR owns all time tracking
- Accounting/COGS is observational only

ABSOLUTE PROHIBITIONS
- Practice must never store or calculate time
- SOAP and Vitals must never trigger tasks, inventory, or COGS
- Inventory must never decrement at order time
- Encounter state must never mirror task boards automatically
- Cancel and No-Show must never be pipeline columns

TRIGGERS
- Tasks spawn only on Basket commit
- Inventory consumption occurs only on WorkItem completion
- Labor cost is derived only from HR TimeEntries
```

---

## Next Steps

1. Review this inventory with stakeholder
2. Decide which patterns to extract first
3. Create `planning/` directory structure in django-primitives
4. Begin Phase 1: Define contracts for first extraction target
