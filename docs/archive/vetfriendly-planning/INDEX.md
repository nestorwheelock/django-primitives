# VetFriendly Planning Document Index

**Archived:** 2025-12-31
**Source:** `/home/nwheelo/projects/vetfriendly/planning/`
**Total Documents:** 172

---

## Category Summary

| Category | Count | Status |
|----------|-------|--------|
| Contract | 14 | Superseded by `/docs/architecture/` |
| Specs | 42 | Reference only |
| Plan | 81 | Reference only |
| Notes/History | 18 | Historical context |
| Config | 17 | Superseded |

---

## CONTRACT Documents (Superseded)

These defined architectural rules. Now superseded by django-primitives canonical docs.

| Original | Status | Replaced By |
|----------|--------|-------------|
| `SYSTEM_CHARTER.md` | Superseded | `CONTRACT.md` |
| `planning/SYSTEM_EXECUTION_RULES.md` | Superseded | `CONTRACT.md` |
| `planning/ARCHITECTURE_ENFORCEMENT.md` | Superseded | `DEPENDENCIES.md` |
| `planning/CODING_STANDARDS.md` | Superseded | `CONVENTIONS.md` |
| `planning/TDD_STOP_GATE.md` | Superseded | `TDD_CYCLE.md` |
| `planning/AI_CHARTER.md` | Superseded | `CONTRACT.md` (AI rules) |
| `planning/catalog/CATALOG_OVERVIEW.md` | Reference | Future `django-catalog` |
| `planning/workitems/WORKITEM_SPAWNER_RULES.md` | Reference | Future `django-workitems` |
| `planning/emr/ENCOUNTER_BOARD_SPEC_V1.md` | Reference | Future `django-encounters` |
| `planning/emr/TRANSITION_RULES_TABLE.md` | Reference | Future `django-encounters` |
| `planning/adr/ADR-001-commercial-licensing.md` | Reference | Licensing decisions |
| `planning/LICENSING.md` | Reference | Licensing |
| `planning/MODULE_INTERFACES.md` | Superseded | `CONVENTIONS.md` |
| `planning/ARCHITECTURE_DECISIONS.md` | Superseded | `DECISIONS.md` |

---

## SPECS Documents (Reference Only)

User stories and UI specifications. Preserved for context.

### User Stories (36)

| File | Description |
|------|-------------|
| `S-001-foundation-ai-core.md` | Foundation + AI Core |
| `S-002-ai-chat-interface.md` | AI Chat Interface |
| `S-003-pet-profiles-medical-records.md` | Pet Profiles + Medical Records |
| `S-004-appointment-booking-ai.md` | Appointment Booking via AI |
| `S-005-ecommerce-store.md` | E-commerce Store |
| `S-006-omnichannel-communications.md` | Omnichannel Communications |
| `S-007-crm-intelligence.md` | CRM Intelligence |
| `S-008-practice-management.md` | Practice Management |
| `S-009-competitive-intelligence.md` | Competitive Intelligence |
| `S-010-pharmacy-management.md` | Pharmacy Management |
| `S-011-knowledge-base-admin.md` | Knowledge Base Admin |
| `S-012-notifications-reminders.md` | Notifications & Reminders |
| `S-013-document-management.md` | Document Management |
| `S-014-reviews-testimonials.md` | Reviews & Testimonials |
| `S-015-emergency-services.md` | Emergency Services |
| `S-016-loyalty-rewards.md` | Loyalty & Rewards |
| `S-017-reports-analytics.md` | Reports & Analytics |
| `S-018-seo-content-marketing.md` | SEO & Content Marketing |
| `S-019-email-marketing.md` | Email Marketing |
| `S-020-billing-invoicing.md` | Billing & Invoicing |
| `S-021-external-services.md` | External Services |
| `S-022-travel-certificates.md` | Travel Certificates |
| `S-023-data-migration.md` | Data Migration |
| `S-024-inventory-management.md` | Inventory Management |
| `S-025-referral-network.md` | Referral Network |
| `S-025b-customer-referral-program.md` | Customer Referral Program |
| `S-026-accounting.md` | Accounting |
| `S-027-delivery-module.md` | Delivery Module |
| `S-027-security-hardening.md` | Security Hardening (NUMBER CONFLICT) |
| `S-028-error-monitoring.md` | Error Monitoring |
| `S-079-audit-logging-staff-actions.md` | Audit Logging |
| `S-080-profile-icon-portal-routing.md` | Profile Icon Portal Routing |
| `S-081-hr-time-tracking.md` | HR Time Tracking |
| `S-082-task-time-tracking.md` | Task Time Tracking |
| `S-083-practice-hr-integration.md` | Practice HR Integration |
| `S-100-unified-people-architecture.md` | Unified People Architecture |

### EMR Specs (6+)

| File | Description |
|------|-------------|
| `emr/ENCOUNTER_TYPE_MATRIX.md` | Encounter types |
| `emr/WORK_ITEM_ROUTING_TABLE.md` | Work item routing |
| `emr/vitals/*.md` (5 files) | Vitals workflow |
| `emr/clinical_popup/*.md` (4 files) | Clinical popup UI |

---

## PLAN Documents (Reference Only)

Task breakdowns and work items. Query filesystem for current state.

### Task Files (77)

Files `T-001` through `T-109` with gaps. Located in `planning/tasks/`.

### Bug Files (10)

Files `B-007` through `B-056`. Located in `planning/bugs/`.

### Superseded Indexes

| File | Status |
|------|--------|
| `TASK_INDEX.md` | Superseded - counts don't match reality |
| `TASK_BREAKDOWN.md` | Superseded - duplicate of index |
| `SPEC_SUMMARY.md` | Superseded - query stories directly |
| `STORY_TO_TASK_CHECKLIST.md` | Reference |

---

## NOTES/HISTORY Documents (Historical Context)

These provide context for decisions but are not actively used.

| File | Purpose |
|------|---------|
| `PREPOCH.md` | Pre-development history |
| `EHRNOTES.md` | EHR research notes |
| `EMR_ARCHITECTURE.md` | Model duplication analysis |
| `emr/DESIGN_DECISIONS_AND_RATIONALE.txt` | Decision log |
| `emr/WORKITEM_SYSTEM_CURRENT_STATE.md` | Implementation status |
| `emr/WORKITEM_SPAWN_AUDIT.md` | Audit results |
| `ROADMAP_IDEAS.md` | Future exploration |
| `devops/CHATGPT_CONTEXT.md` | DevOps context |
| `continuity/*.md` (10 files) | Business continuity |

---

## CONFIG Documents (Superseded)

Claude configurations. Superseded by django-primitives process docs.

| File | Status |
|------|--------|
| `CLAUDE.md` (vetfriendly root) | Project-specific, superseded |
| `CLAUDE_IMPLEMENTATION_PROMPT.md` | Superseded |
| `emr/CLAUDE_HANDOFF_PROTOCOL.md` | Superseded |
| `emr/CLAUDE_HANDOFF_V1.txt` | Superseded (older version) |

---

## DUPLICATE Documents (Removed)

These were exact duplicates and are not preserved:

| Duplicate | Reason |
|-----------|--------|
| `planning/planning/CLAUDE_IMPLEMENTATION_PROMPT.md` | Identical to parent |
| `planning/planning/emr/vitals/*` (5 files) | Identical to parent |
| `planning/planning/worklog/*` (5 files) | Identical to parent |

---

## STALE Documents (V1 Versions)

Older versions superseded by V2 or later:

| Stale | Superseded By |
|-------|---------------|
| `emr/CLAUDE_HANDOFF_V1.txt` | `CLAUDE_HANDOFF_PROTOCOL.md` |
| `emr/USER_STORIES_V1.txt` | `planning/stories/S-*.md` |
| `emr/BUTTON_MATRIX_V1.txt` | `BUTTON_STATE_MODEL_V2.txt` |
| `MODULE_EXTRACTION_PLAN_COMPLETE.md` | Historical (extraction done) |

---

## Accessing Original Files

Original files remain in VetFriendly repo:
```
/home/nwheelo/projects/vetfriendly/planning/
```

This archive provides the index and context. Copy specific files here only if needed for reference.
