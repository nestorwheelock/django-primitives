# Book Notes: Constrained AI and ERP Primitives

## Thesis (the uncomfortable truth)

**ERP primitives are not a business domain. They're physics.**

Identity, time, money, agreements, inventory, and decisions exist whether you're running a hospital, a tattoo shop, or a Mars colony with bad Wi-Fi. AI does not invent these. AI can only assemble them faster if you don't let it hallucinate structure.

> *If you constrain AI to compose known primitives, you can build almost anything safely.
> If you let it invent abstractions, it will invent bugs.*

That's the spine.

---

## The Primitive Stack (non-negotiable)

These are not optional. Every ERP system that survives more than five years converges here whether it likes it or not.

### 1. Identity

* Parties, roles, and authority
* Humans, organizations, service accounts
* Never deleted, only deprecated

### 2. Time

* Effective dating
* Bitemporal reality
* "As of" is more important than "now"

### 3. Agreements

* Two or more parties
* Terms as data, not prose
* Amendments are append-only

### 4. Catalog

* Things that can be sold, performed, or consumed
* Services, goods, labor, abstractions
* No workflows here. Just definitions.

### 5. Ledger

* Double-entry or don't bother
* Reversals, not edits
* If it doesn't balance, it's lying

### 6. Inventory

* Quantity, location, state
* Reservation is not consumption
* Shrinkage is a fact of life

### 7. Workflow

* State machines
* Explicit transitions
* Humans are unreliable nodes

### 8. Decisions

* Who decided what, when, and why
* Auditable intent
* Reproducible outcomes

### 9. Communication

* Messages are events
* Delivery is best-effort
* Read receipts are political fiction

### 10. Audit

* Everything emits a trail
* Silence is suspicious
* Logs are legal documents in disguise

---

## Why Constrained AI Works Here

Unconstrained AI tries to be clever. Clever gets you bespoke snowflakes that melt on contact with reality.

Constrained AI:

* Cannot invent new primitives
* Cannot mutate history
* Cannot violate invariants
* Can only compose

This is why ERP is the foundation. It gives the AI nowhere to hide.

---

## Proposed Book Structure

### Part I: The Lie

* "Modern software is new"
* "AI understands business"
* "We'll refactor later"

Spoiler: no, it isn't, it doesn't, and you won't.

### Part II: The Primitives

One chapter per primitive:

* Historical origin
* Failure mode when ignored
* Minimal data model
* Invariants that must never break

### Part III: Constraining the Machine

* Prompt contracts
* Schema-first generation
* Append-only mandates
* Forbidden operations list

### Part IV: Composition

Build:

* A clinic
* A marketplace
* A subscription service
* A government form workflow

Same primitives. Different paint.

---

## Visual Requirements

Include these diagram types:

1. **Monolithic vs Postmodern ERP** - architecture comparison
2. **Bitemporal History** - Martin Fowler style timeline
3. **Double-Entry Accounting** - T-accounts and flow
4. **Event Sourcing** - append-only event stream

Format requirements:

* SVG for precision
* PDF for humans
* PNG for slides
* No Figma-only nonsense

---

## Why This Actually Matters

Most people think they're bad at software. They're not. They're just standing on quicksand abstractions someone invented in a startup pitch deck.

This book says:

* Stop inventing
* Start composing
* Respect time
* Fear edits
* Trust append-only truth

That's not trendy. It's durable.

---

## Mapping Notes to django-primitives Packages

| Primitive Stack | django-primitives Package |
|-----------------|---------------------------|
| Identity | django-parties, django-rbac |
| Time | django-decisioning (TimeSemanticsMixin) |
| Agreements | django-agreements |
| Catalog | django-catalog |
| Ledger | django-ledger, django-money |
| Inventory | (future: django-inventory) |
| Workflow | django-encounters (state machine) |
| Decisions | django-decisioning |
| Communication | (future: django-notifications) |
| Audit | django-audit-log |

**Current coverage:** 8/10 primitives implemented
**Missing:** Inventory, Communication (intentionally deferred as infrastructure)

---

## Research: ERP Success/Failure Statistics

### The Case for ERP (and Primitives)

Businesses that use ERP systems generally experience higher success rates:

| Attribute | Businesses Using ERP | Businesses Not Using ERP |
|-----------|---------------------|--------------------------|
| Success Rate | ~88% successful | Often below 50% |
| Failure Rate | 10-20% failure | Higher due to lack of integration |
| Operational Efficiency | Improved, streamlined | Inefficiencies and silos |
| Data Management | Centralized, accurate | Fragmented, inconsistent |
| Scalability | Easily scalable | Limited adaptability |

**Sources:** datixinc.com, erpadvisorsgroup.com

### But ERP Implementations Are Hard

According to Gartner:
- **55-75%** of ERP projects fail to meet their objectives
- **67%** of implementations take longer than expected
- **64%** of implementations go over budget

### Why ERP Implementations Fail

1. **Choosing the wrong implementation partner**
2. **Inadequate planning and scoping** - insufficient upfront planning is a leading cause
3. **Lack of user adoption** - insufficient training and buy-in
4. **Ineffective project team** - lacking skills, experience, or commitment
5. **Lack of leadership buy-in** - insufficient resources and direction
6. **Insufficient resource allocation** - rushed timelines, overworked teams

### Why Constrained Primitives Help

The primitive approach addresses several failure modes:

- **Clear scope**: Primitives are finite and well-defined
- **Proven patterns**: Based on decades of ERP evolution
- **Composable**: Build complex systems from simple, tested parts
- **No invention**: AI composes rather than creates novel abstractions

**Key insight:** Organizations fail not because ERP is bad, but because they try to invent their own abstractions instead of using proven primitives. The 55-75% failure rate is largely about *implementation*, not the underlying patterns.

### Rand Group Statistics (for contrast)

- **100%** implementation success rate
- **60%** of clients came after failed implementations elsewhere
- **20+** years in business

Their success comes from: expertise, commitment, and **getting it right the first time**.

**Lesson for the book:** The primitives ARE "getting it right the first time." They encode the patterns that successful ERP implementations converge on anyway.
