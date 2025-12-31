# VetFriendly Planning Archive

**Status:** Archived
**Date:** 2025-12-31
**Purpose:** Historical preservation of VetFriendly planning documents

---

## Why This Archive Exists

VetFriendly produced 172 planning documents over its development. Many were useful during active development but are now superseded by django-primitives canonical docs.

This archive preserves history without cluttering the active documentation.

---

## What's Archived

### Superseded by Canonical Docs

| Archived Doc | Replaced By |
|--------------|-------------|
| SYSTEM_CHARTER.md | `/docs/architecture/CONTRACT.md` |
| CODING_STANDARDS.md | `/docs/architecture/CONVENTIONS.md` |
| ARCHITECTURE_ENFORCEMENT.md | `/docs/architecture/DEPENDENCIES.md` |
| TDD_STOP_GATE.md | `/docs/process/TDD_CYCLE.md` |
| TASK_INDEX.md | Filesystem query |
| TASK_BREAKDOWN.md | Filesystem query |

### Duplicate Files Removed

| Duplicate Location | Canonical Location |
|--------------------|-------------------|
| `planning/planning/*` | `planning/*` (parent) |

The nested `planning/planning/` directory was an exact duplicate and is not preserved.

### Historical/Research Docs

These are preserved for context but not actively used:

- `PREPOCH.md` - Pre-development history
- `EHRNOTES.md` - EHR research notes
- `EMR_ARCHITECTURE.md` - Model analysis
- `emr/DESIGN_DECISIONS_AND_RATIONALE.txt` - Decision log
- `ROADMAP_IDEAS.md` - Future exploration
- `continuity/*.md` - Business continuity planning

### Config Docs

Claude configuration that was project-specific:

- `CLAUDE.md` (vetfriendly root)
- `CLAUDE_IMPLEMENTATION_PROMPT.md`
- `CLAUDE_HANDOFF_PROTOCOL.md`

---

## How to Use This Archive

1. **Don't edit archived docs** - They're historical snapshots
2. **Reference for context** - Understand why decisions were made
3. **Link to canonical docs** - For current rules, use `/docs/architecture/`

---

## Archive Structure

```
archive/vetfriendly-planning/
├── README.md (this file)
├── INDEX.md (full inventory with categories)
├── contracts/ (superseded contract docs)
├── plans/ (superseded task/story lists)
├── research/ (historical research)
└── config/ (old Claude configs)
```

---

## Adding to Archive

When archiving a document:

1. Copy to appropriate subdirectory
2. Add header to the copy:

```markdown
---
ARCHIVED: 2025-12-31
REASON: Superseded by /docs/architecture/CONTRACT.md
STATUS: Do not edit. Historical reference only.
---

[Original content below]
```

3. Update INDEX.md with the new entry
