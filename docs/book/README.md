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

### Part I: The Lie (Chapters 1-3)

| Chapter | Title | Status |
|---------|-------|--------|
| 1 | Modern Software Is Old | **Draft** |
| 2 | AI Does Not Understand Business | **Draft** |
| 3 | You Will Not Refactor Later | **Draft** |

### Part II: The Primitives (Chapters 4-18)

| Chapter | Title | django-primitives Package | Status |
|---------|-------|---------------------------|--------|
| 4 | Project Structure | Project structure guide | **Draft** |
| 5 | Foundation Layer | django-basemodels, django-singleton, django-modules, django-layers | **Draft** |
| 6 | Identity | django-parties, django-rbac | **Draft** |
| 7 | Time | django-decisioning | **Draft** |
| 8 | Agreements | django-agreements | **Draft** |
| 9 | Catalog | django-catalog | **Draft** |
| 10 | Ledger | django-ledger, django-money | **Draft** |
| 11 | Workflow | django-encounters | **Draft** |
| 12 | Decisions | django-decisioning | **Draft** |
| 13 | Audit | django-audit-log | **Draft** |
| 14 | Worklog | django-worklog | **Draft** |
| 15 | Geography | django-geo | **Draft** |
| 16 | Documents | django-documents | **Draft** |
| 17 | Notes | django-notes | **Draft** |
| 18 | Sequence | django-sequence | **Draft** |

### Part III: Constraining the Machine (Chapters 19-22)

| Chapter | Title | Status |
|---------|-------|--------|
| 19 | The Instruction Stack | **Draft** |
| 20 | Prompt Contracts | **Draft** |
| 21 | Schema-First Generation | **Draft** |
| 22 | Forbidden Operations | **Draft** |

### Part IV: Composition (Chapters 23-26)

| Chapter | Title | Status |
|---------|-------|--------|
| 23 | Build a Clinic | **Draft** |
| 24 | Build a Marketplace | **Draft** |
| 25 | Build a Subscription Service | **Draft** |
| 26 | Build a Government Form Workflow | **Draft** |

### Conclusion

| Chapter | Title | Status |
|---------|-------|--------|
| 27 | Conclusion | **Draft** |

---

## File Structure

```
docs/book/
├── README.md                    # This file
├── BOOK_NOTES.md               # Raw notes and framing
├── 00-title.md                 # Title page
├── 00-copyright.md             # Copyright page
├── 00-introduction.md          # Introduction
├── part-1-the-lie/
│   ├── ch01-modern-software-is-old.md
│   ├── ch02-ai-does-not-understand-business.md
│   └── ch03-you-will-refactor-later.md
├── part-2-the-primitives/
│   ├── ch04-project-structure.md
│   ├── ch05-foundation-layer.md
│   ├── ch06-identity.md
│   ├── ch07-time.md
│   ├── ch08-agreements.md
│   ├── ch09-catalog.md
│   ├── ch10-ledger.md
│   ├── ch11-workflow.md
│   ├── ch12-decisions.md
│   ├── ch13-audit.md
│   ├── ch14-worklog.md
│   ├── ch15-geo.md
│   ├── ch16-documents.md
│   ├── ch17-notes.md
│   └── ch18-sequence.md
├── part-3-constraining-the-machine/
│   ├── ch19-the-instruction-stack.md
│   ├── ch20-prompt-contracts.md
│   ├── ch21-schema-first-generation.md
│   └── ch22-forbidden-operations.md
├── part-4-composition/
│   ├── ch23-build-a-clinic.md
│   ├── ch24-build-a-marketplace.md
│   ├── ch25-build-a-subscription-service.md
│   └── ch26-build-a-government-form-workflow.md
└── ch27-conclusion.md
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

- **Total Chapters:** 27 (covering all 18 django-primitives packages)
- **Drafted:** 27
- **Planned:** 0

### All Chapters Complete

| Part | Chapter | Title | Packages Covered |
|------|---------|-------|------------------|
| Intro | - | Introduction: Vibe Coding With Constraints | - |
| I | 1 | Modern Software Is Old | - |
| I | 2 | AI Does Not Understand Business | - |
| I | 3 | You Will Not Refactor Later | - |
| II | 4 | Project Structure | - |
| II | 5 | Foundation Layer | django-basemodels, django-singleton, django-modules, django-layers |
| II | 6 | Identity | django-parties, django-rbac |
| II | 7 | Time | django-decisioning |
| II | 8 | Agreements | django-agreements |
| II | 9 | Catalog | django-catalog |
| II | 10 | Ledger | django-ledger, django-money |
| II | 11 | Workflow | django-encounters |
| II | 12 | Decisions | django-decisioning |
| II | 13 | Audit | django-audit-log |
| II | 14 | Worklog | django-worklog |
| II | 15 | Geography | django-geo |
| II | 16 | Documents | django-documents |
| II | 17 | Notes | django-notes |
| II | 18 | Sequence | django-sequence |
| III | 19 | The Instruction Stack | - |
| III | 20 | Prompt Contracts | - |
| III | 21 | Schema-First Generation | - |
| III | 22 | Forbidden Operations | - |
| IV | 23 | Build a Clinic | - |
| IV | 24 | Build a Marketplace | - |
| IV | 25 | Build a Subscription Service | - |
| IV | 26 | Build a Government Form Workflow | - |
| - | 27 | Conclusion | - |
