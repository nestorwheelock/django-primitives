# Constrained AI and ERP Primitives

**Working Title:** *The Boring Revolution: Building Business Software With Constrained AI*

## Thesis

> *If you constrain AI to compose known primitives, you can build almost anything safely.
> If you let it invent abstractions, it will invent bugs.*

ERP primitives are not a business domain. They're physics.

---

## Book Structure

### Part I: The Lie

| Chapter | Title | Status |
|---------|-------|--------|
| 1 | Modern Software Is Old | Planned |
| 2 | AI Does Not Understand Business | Planned |
| 3 | You Will Not Refactor Later | Planned |

### Part II: The Primitives

| Chapter | Title | django-primitives Package | Status |
|---------|-------|---------------------------|--------|
| 4 | Identity | django-parties, django-rbac | Planned |
| 5 | Time | django-decisioning | Planned |
| 6 | Agreements | django-agreements | Planned |
| 7 | Catalog | django-catalog | Planned |
| 8 | Ledger | django-ledger, django-money | Planned |
| 9 | Workflow | django-encounters | Planned |
| 10 | Decisions | django-decisioning | Planned |
| 11 | Audit | django-audit-log | Planned |

### Part III: Constraining the Machine

| Chapter | Title | Status |
|---------|-------|--------|
| 12 | The Instruction Stack | **Draft** |
| 13 | Prompt Contracts | Planned |
| 14 | Schema-First Generation | Planned |
| 15 | Forbidden Operations | Planned |

### Part IV: Composition

| Chapter | Title | Status |
|---------|-------|--------|
| 16 | Build a Clinic | Planned |
| 17 | Build a Marketplace | Planned |
| 18 | Build a Subscription Service | Planned |
| 19 | Build a Government Form Workflow | Planned |

---

## File Structure

```
docs/book/
├── README.md                    # This file
├── BOOK_NOTES.md               # Raw notes and framing
├── part-1-the-lie/
│   ├── ch01-modern-software-is-old.md
│   ├── ch02-ai-does-not-understand-business.md
│   └── ch03-you-will-not-refactor-later.md
├── part-2-the-primitives/
│   ├── ch04-identity.md
│   ├── ch05-time.md
│   ├── ch06-agreements.md
│   ├── ch07-catalog.md
│   ├── ch08-ledger.md
│   ├── ch09-workflow.md
│   ├── ch10-decisions.md
│   └── ch11-audit.md
├── part-3-constraining-the-machine/
│   ├── ch12-the-instruction-stack.md
│   ├── ch13-prompt-contracts.md
│   ├── ch14-schema-first-generation.md
│   └── ch15-forbidden-operations.md
└── part-4-composition/
    ├── ch16-build-a-clinic.md
    ├── ch17-build-a-marketplace.md
    ├── ch18-build-a-subscription-service.md
    └── ch19-build-a-government-form-workflow.md
```

---

## Visual Assets Required

| Diagram | Format | Source |
|---------|--------|--------|
| Monolithic vs Postmodern ERP | SVG, PNG, PDF | Architecture comparison |
| Bitemporal History | SVG, PNG, PDF | Martin Fowler style |
| Double-Entry Accounting | SVG, PNG, PDF | T-accounts and flow |
| Event Sourcing | SVG, PNG, PDF | Append-only stream |
| Primitive Dependency Map | SVG, PNG, PDF | Tier diagram |
| Instruction Stack | SVG, PNG, PDF | Four layers |

---

## Writing Guidelines

- Write like a senior engineer explaining to another senior engineer
- No hype, no buzzwords
- No apologizing for opinions
- Use diagrams, tables, and short examples
- Assume technical but skeptical reader
- Show decisions, not debates

---

## Progress

- **Total Chapters:** 19
- **Drafted:** 1
- **Planned:** 18
