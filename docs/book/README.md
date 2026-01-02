# Constrained AI and ERP Primitives

**Working Title:** *The Boring Revolution: Building Business Software With Constrained AI*

## Thesis

> *If you constrain AI to compose known primitives, you can build almost anything safely.
> If you let it invent abstractions, it will invent bugs.*

ERP primitives are not a business domain. They're physics.

## Audience

Non-technical idea makers who want to learn how to develop working software. Business owners. Entrepreneurs. Anyone who understands their domain but has been told they need to "learn to code" or "hire a team" before they can build.

---

## Book Structure

### Introduction: Vibe Coding With Constraints

| Section | Status |
|---------|--------|
| Who This Book Is For | **Draft** |
| The LLM Liberation | **Draft** |
| The End of Trivial Arguments | **Draft** |
| You Are the Manager | **Draft** |
| The Two Ways to Fail | **Draft** |
| The Primitives Preview | **Draft** |
| How to Read This Book | **Draft** |

### Part I: The Lie

| Chapter | Title | Status |
|---------|-------|--------|
| 1 | Modern Software Is Old | **Draft** |
| 2 | AI Does Not Understand Business | Planned |
| 3 | You Will Not Refactor Later | Planned |

### Part II: The Primitives

| Chapter | Title | django-primitives Package | Status |
|---------|-------|---------------------------|--------|
| 3.5 | Setting Up Your Project (Interlude) | Project structure guide | **Draft** |
| 4 | Identity | django-parties, django-rbac | **Draft** |
| 5 | Time | django-decisioning | **Draft** |
| 6 | Agreements | django-agreements | **Draft** |
| 7 | Catalog | django-catalog | **Draft** |
| 8 | Ledger | django-ledger, django-money | **Draft** |
| 9 | Workflow | django-encounters | **Draft** |
| 10 | Decisions | django-decisioning | **Draft** |
| 11 | Audit | django-audit-log | **Draft** |

### Part III: Constraining the Machine

| Chapter | Title | Status |
|---------|-------|--------|
| 12 | The Instruction Stack | **Draft** |
| 13 | Prompt Contracts | **Draft** |
| 14 | Schema-First Generation | **Draft** |
| 15 | Forbidden Operations | **Draft** |

### Part IV: Composition

| Chapter | Title | Status |
|---------|-------|--------|
| 16 | Build a Clinic | **Draft** |
| 17 | Build a Marketplace | **Draft** |
| 18 | Build a Subscription Service | **Draft** |
| 19 | Build a Government Form Workflow | **Draft** |

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
│   ├── ch03a-project-structure.md    # Interlude
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

- **Total Chapters:** 20 (including interlude)
- **Drafted:** 17
- **Planned:** 3

### Completed Chapters

| Part | Chapter | Title |
|------|---------|-------|
| I | 1 | Modern Software Is Old |
| II | 3.5 | Setting Up Your Project (Interlude) |
| II | 4 | Identity |
| II | 5 | Time |
| II | 6 | Agreements |
| II | 7 | Catalog |
| II | 8 | Ledger |
| II | 9 | Workflow |
| II | 10 | Decisions |
| II | 11 | Audit |
| III | 12 | The Instruction Stack |
| III | 13 | Prompt Contracts |
| III | 14 | Schema-First Generation |
| III | 15 | Forbidden Operations |
| IV | 16 | Build a Clinic |
| IV | 17 | Build a Marketplace |
| IV | 18 | Build a Subscription Service |
| IV | 19 | Build a Government Form Workflow |

### Remaining Chapters

| Part | Chapter | Title |
|------|---------|-------|
| I | 2 | AI Does Not Understand Business |
| I | 3 | You Will Not Refactor Later |
