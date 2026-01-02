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
