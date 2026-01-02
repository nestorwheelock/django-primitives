# Chapter 1: The Programming Operating System

## Claude Is Not a Brain. It's an Operating System With Applications.

Most confusion around AI-assisted coding does not come from model quality. It comes from **misunderstanding how instructions are loaded, scoped, and enforced**.

If you treat Claude like a genius junior developer who "reads everything you give it," you will get inconsistent behavior, broken invariants, and hallucinated confidence. If you treat Claude like an operating system with strict boot-time rules and on-demand applications, it becomes predictable, safe, and shockingly effective.

This chapter explains that mental model—and then extends it to something more powerful: building your own Programming Operating System for business software.

---

## Part I: The Instruction Stack

Claude does not process instructions as a single blob. It processes them as a **stack**, loaded in a specific order, with different persistence guarantees.

Think less "prompt" and more "runtime environment."

### The Four Layers of Instruction

```
CONVERSATION START
│
├─ 1. Global CLAUDE.md (always loaded)
│
├─ 2. Project CLAUDE.md (auto-loaded in repo)
│
├─ 3. Your message (explicit instruction)
│
└─ 4. Tool results (files Claude actually reads)
```

Each layer has a different purpose. Mixing them is how teams accidentally sabotage themselves.

---

### Layer 1: Global CLAUDE.md

**"How Claude Should Behave, Always"**

This file is **automatic and unconditional**. Claude loads it for *every* conversation before you say a word.

That means it must be:

- Short
- Stable
- Behavioral, not procedural

**What belongs here:**

- Universal development rules
- Non-negotiable constraints
- Safety and quality bars

```markdown
# Development Standards

## TDD (Mandatory)
1. Write failing test first
2. Run pytest, confirm failure
3. Write minimal code to pass
4. Refactor while green

## Git
- Conventional commits: type(scope): description
- Never force push to main
- Never auto-close bug issues

## Code Quality
- >95% test coverage
- No TODO comments in shipped code
```

**What does NOT belong here:**

- Project specs
- File templates
- Package descriptions
- Workflows
- Checklists
- Anything that changes frequently

If this file grows large, you are turning your operating system into an application, and everything becomes brittle.

**Target size: ~50 lines.**

---

### Layer 2: Project CLAUDE.md

**"What This Codebase Believes"**

This file is also auto-loaded, but only when Claude is working inside a specific project directory.

This is **project context**, not task context.

**What belongs here:**

- Architectural rules
- Layer boundaries
- Shared patterns
- Naming conventions
- Project philosophy

```markdown
# Django Primitives

Monorepo of 18 Django packages for ERP/business applications.

## Dependency Rule
Never import from a higher layer.

## Model Patterns
All models use UUID primary keys.
Domain models add soft delete.
Events add time semantics (effective_at/recorded_at).

## Creating Packages
Use the per-package prompts in docs/prompts/
```

This file should explain *how the project thinks*, not *what to build next*.

**Target size: ~100 lines.**

---

### Layer 3: Your Message

**"What I Want You to Do Now"**

This is the only part most people think about.

Your message should:

- Name the task
- Reference the documents to load
- Avoid restating rules already enforced elsewhere

**Good:**

> "Rebuild django-worklog using docs/prompts/django-worklog.md"

**Bad:**

> "Here are all the rules again, and also the spec, and also the architecture, and also remember to use TDD and also..."

Redundancy weakens enforcement. Claude already has the rules if you put them in the right place.

---

### Layer 4: Tool Results

**"The Only Specs That Actually Matter"**

Claude does **not** read your repository by default.

It only knows what:

- You paste
- You explicitly tell it to read
- It opens via tools

This is where **specs, prompts, and architecture documents belong**.

These files can be:

- Long
- Detailed
- Exhaustive
- Task-specific

Because they are loaded **on demand**, not globally.

This is the equivalent of launching an application on top of the OS.

---

### The Critical Mistake

Most teams treat CLAUDE.md like a **master prompt**.

They put specs, templates, workflows, examples, architecture, and checklists into files that are **always loaded**.

The result:

- Thousands of lines of context before a task even begins
- Claude "following" some rules and ignoring others
- Conflicting instructions
- Slower, less reliable output

This is not Claude being dumb. This is you booting Photoshop inside the kernel.

---

### The Correct Mental Model

| Concept | Claude Equivalent |
|---------|-------------------|
| Operating system | Global CLAUDE.md |
| Project config | Project CLAUDE.md |
| Application | Prompt / spec document |
| Program execution | Your message |
| I/O | Tool reads |

You do not put your entire application into the operating system.

You put **rules** in the OS. You load **apps** when you need them.

---

## Part II: Vibe Coding With Constraints

The phrase "vibe coding" has become shorthand for reckless AI-assisted development: paste requirements, hope for the best, ship whatever compiles.

That is not what this book teaches.

**Vibe coding with constraints** means:

- Fast iteration *inside* rigid rules
- AI writes the code, you enforce the invariants
- Speed comes from elimination, not improvisation

The counterintuitive truth: **constraints increase speed long-term**.

When Claude knows:

- Every model uses UUID primary keys
- Every mutation goes through a service function
- Every state change is append-only
- Every test is written before implementation

...it stops inventing. It stops "being creative." It becomes a precise executor of well-specified work.

The goal is not to make Claude think less. The goal is to make Claude think about the right things.

---

## Part III: What Is a Primitive?

A primitive is a **non-negotiable capability** required to build business software.

Not a feature. Not a vertical. Not an opinionated UI.

A primitive answers the question: *What does every business system need, regardless of domain?*

### Examples of Primitives

| Primitive | Capability |
|-----------|------------|
| Parties | Who are the actors? (people, organizations, groups) |
| RBAC | What can each actor do? |
| Catalog | What can be ordered/scheduled/tracked? |
| Ledger | What money moved and why? |
| Agreements | What was promised and when? |
| Encounters | What interactions occurred? |

### Examples of NOT Primitives

| Not a Primitive | Why |
|-----------------|-----|
| Notifications | Infrastructure concern, not a domain capability |
| Search | Infrastructure concern |
| Scheduling | Composed from ledger + agreements + time semantics |
| Pizza half-toppings | Domain-specific configuration, not a capability |

The test: **If removing it would cripple every business you might build, it's a primitive.**

---

## Part IV: The Tiered Primitive Model

Primitives are not equal. They have dependencies. Some must exist before others make sense.

### Tier 0: Django + Postgres Givens

These are not your primitives. They are your platform.

- Users and authentication
- Database and migrations
- HTTP request/response
- Admin interface

You do not rebuild these. You build on top of them.

### Tier 1: Base Identity and Time

**Packages:** basemodels, parties, rbac, singleton

These answer:

- How do we identify things? (UUIDs, soft delete)
- Who are the actors? (Party pattern)
- What can they do? (Role-based access)
- What configuration is global? (Singletons)

Everything else depends on these existing.

### Tier 2: Decision Surfaces

**Packages:** decisioning, agreements, audit-log

These answer:

- When did something actually happen vs. when was it recorded?
- What was promised and by whom?
- What is the immutable audit trail?

Business logic lives here. These packages enforce **time semantics** and **idempotency**.

### Tier 3: Money and Obligations

**Packages:** money, ledger, sequence

These answer:

- How do we represent currency correctly?
- How do we track financial transactions?
- How do we generate sequential identifiers?

Double-entry accounting. No floating point. No mutable balances.

### Tier 4: Composition Layers

**Packages:** catalog, worklog, encounters, documents, notes

These answer:

- What can be ordered? (Catalog)
- What work was done? (Worklog)
- What interactions occurred? (Encounters)
- What files are attached? (Documents)
- What comments exist? (Notes)

These packages *compose* the lower tiers into usable domain surfaces.

### Edge Primitives

**Packages:** geo

Optional. Not every business needs location awareness. But when you do, you need:

- Coordinates with proper precision
- Service area boundaries
- Distance calculations

Edge primitives are real primitives—they just have narrower applicability.

---

## Part V: The Dependency Map

```
                    ┌─────────────────┐
                    │   Applications  │
                    │  (Pizza, Vet,   │
                    │   Dive, Rental) │
                    └────────┬────────┘
                             │ uses
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Catalog │         │Encounter│         │ Worklog │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        └─────────┬─────────┴─────────┬─────────┘
                  │                   │
                  ▼                   ▼
            ┌──────────┐        ┌──────────┐
            │  Ledger  │        │Agreements│
            └────┬─────┘        └────┬─────┘
                 │                   │
                 └─────────┬─────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Decisioning │
                    │ (time, idem)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
         ┌────────┐   ┌────────┐   ┌────────┐
         │ Parties│   │  RBAC  │   │  Audit │
         └───┬────┘   └───┬────┘   └───┬────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │ BaseModels │
                   │ (UUID, ts) │
                   └────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │  Django +  │
                   │  Postgres  │
                   └────────────┘
```

This map is a **development map**, not a filesystem layout.

Dependencies flow *conceptually*. You cannot build Catalog without understanding Ledger. You cannot build Ledger without understanding Decisioning. You cannot build Decisioning without understanding Parties.

But each package remains **independently installable**. A project that only needs Parties does not install Catalog. The dependency is conceptual, not runtime.

---

## Part VI: One System, Many Domains

The primitives do not change. The domains do.

### Pizza Ordering

| Domain Concept | Primitive Used |
|----------------|----------------|
| Customer | parties.Person |
| Pizzeria | parties.Organization |
| Menu items | catalog.CatalogItem |
| Order | catalog.Basket → catalog.Order |
| Payment | ledger.Transaction |
| Delivery zone | geo.ServiceArea |
| Driver assignment | worklog.WorkSession |

Half toppings? Catalog configuration. Slices? Catalog configuration. Combo deals? Agreements + catalog pricing rules.

No new primitives required.

### Veterinary Clinic

| Domain Concept | Primitive Used |
|----------------|----------------|
| Pet owner | parties.Person |
| Patient (pet) | parties.Person (yes, really) |
| Clinic | parties.Organization |
| Appointment | encounters.Encounter |
| Services rendered | catalog.BasketItem |
| Invoice | ledger.Transaction |
| Medical notes | notes.Note |
| Lab results | documents.Document |

Vaccination schedules? Agreements. Treatment protocols? Catalog + encounters state machine.

No new primitives required.

### Dive Operations

| Domain Concept | Primitive Used |
|----------------|----------------|
| Diver | parties.Person |
| Dive shop | parties.Organization |
| Boat | catalog.CatalogItem (resource type) |
| Trip booking | catalog.Basket → encounters.Encounter |
| Waiver | agreements.Agreement |
| Payment | ledger.Transaction |
| Dive site | geo.Place |
| Dive log | worklog.WorkSession + notes.Note |

Certification tracking? Agreements with valid_from/valid_to. Equipment rental? Catalog items with availability rules.

No new primitives required.

### The Pattern

Every vertical business is a **composition** of the same primitives with different:

- Configuration
- Workflows
- UI
- Business rules

The primitives provide capabilities. The application provides decisions.

---

## Part VII: Why Correctness Beats Cleverness

Six principles that make the system trustworthy:

### 1. Idempotency

Every operation that can be retried must produce the same result.

```python
@idempotent(key_func=lambda basket_id, **_: f"commit:{basket_id}")
def commit_basket(basket_id):
    # Safe to call twice
```

Network failures, user double-clicks, retry queues—none of these corrupt state.

### 2. Time Semantics

Two timestamps, always:

```python
effective_at = models.DateTimeField()  # When it happened in reality
recorded_at = models.DateTimeField()   # When we learned about it
```

A vet visit on Monday recorded on Tuesday: `effective_at = Monday`, `recorded_at = Tuesday`.

Backdating is not fraud. It is **accuracy**.

### 3. Snapshots Over Live State

When an order is placed, copy the price. Do not reference the catalog.

```python
class OrderLine(models.Model):
    unit_price_snapshot = models.DecimalField()  # Frozen at order time
    # NOT: price = catalog_item.current_price
```

Prices change. Orders must not.

### 4. Reversals Over Edits

Wrong transaction? Do not edit it. Post a reversal.

```python
# Wrong:
transaction.amount = corrected_amount
transaction.save()

# Right:
Transaction.objects.create(
    amount=-original_amount,
    reverses=original_transaction
)
Transaction.objects.create(
    amount=corrected_amount
)
```

History is immutable. The audit trail is sacred.

### 5. Append-Only Where It Matters

Audit logs cannot be edited or deleted:

```python
def save(self, *args, **kwargs):
    if self.pk:
        raise ImmutableLogError()
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise ImmutableLogError("Audit logs cannot be deleted")
```

Some tables are ledgers. Treat them that way.

### 6. Soft Delete for Domain Objects

Nothing is truly deleted. Everything is marked:

```python
deleted_at = models.DateTimeField(null=True, blank=True)

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
```

"Deleted" means "hidden from normal queries." The data remains for audit, recovery, and legal compliance.

---

## Part VIII: Why This Is a Personal ERP OS

This is not a SaaS pitch. This is not a framework for others to adopt. This is not open source marketing.

This is a **personal operating system** for building business software.

The goal:

- Build the primitives once
- Test them thoroughly (815 tests across 18 packages)
- Reuse them for every future business

Next year's project—whatever it is—starts with:

```python
INSTALLED_APPS = [
    'django_basemodels',
    'django_parties',
    'django_rbac',
    'django_catalog',
    'django_ledger',
    # ... already built, already tested
]
```

The primitives are boring. The primitives are correct. The primitives do not need to be rebuilt.

All future effort goes into **domain-specific decisions**, not infrastructure.

That is the operating system. Everything else is just apps.

---

## Summary

| Principle | Implementation |
|-----------|----------------|
| Instruction hygiene | CLAUDE.md for rules, prompts for specs |
| Constraints enable speed | Rigid patterns, fast iteration within them |
| Primitives are capabilities | 14 core + 1 edge, not features |
| Dependencies are conceptual | Tiered model, independent packages |
| Domains are compositions | Same primitives, different configuration |
| Correctness beats cleverness | Idempotency, time semantics, immutability |

The reader who understands this chapter sees the operating system.

Everything that follows—Catalog, Ledger, Agreements, Encounters—is just installing applications.

---

*Next chapter: The Catalog Primitive—Orders, Baskets, and the Workflow That Runs Everything*
