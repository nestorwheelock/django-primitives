# Chapter 1: Vibe Coding With Constraints

## Chapter Summary

This chapter establishes the book's central thesis: you can move fast with LLMs while building systems that are fundamentally correct—if you lock down the right constraints before you start. It introduces "vibe coding with constraints" as a methodology, explains why ERP systems are the perfect test case, and sets up Django as the implementation platform.

---

## 1.1 The Two Ways to Fail

### Opening Hook

Two startups build inventory systems with Claude/GPT in the same week.

**Startup A** prompts: "Build me an inventory tracking system in Django."
- Gets working code in 2 hours
- Ships to customers in 2 weeks
- Month 3: Customer reports negative inventory quantities
- Month 4: Audit finds inventory movements with no audit trail
- Month 6: Accountant quits because the books don't reconcile
- Month 8: Rewrite begins

**Startup B** prompts: "Build an inventory system using double-entry ledger semantics where quantities move between location accounts via balanced transactions. No UPDATE or DELETE on movement records. Include idempotency keys on all mutations."
- Gets working code in 4 hours
- Ships to customers in 3 weeks
- Month 3: Customer requests inventory as-of-date reporting (already supported)
- Month 6: Passes audit with complete transaction history
- Month 12: Same codebase, new features

The difference isn't the LLM. It's the constraints in the prompt.

### The Spectrum of Failure

1. **Move fast, break things** → Things break, nobody knows why, rewrite
2. **Move slow, overengineer** → Never ship, or ship something nobody needs
3. **Move fast inside constraints** → Ship quickly, survive contact with reality

This book is about option 3.

---

## 1.2 What "Vibe Coding" Actually Means

### The Bad Reputation

"Vibe coding" became a pejorative because people confused it with:
- Shipping without tests
- Trusting LLM output without review
- Ignoring edge cases
- Building demos instead of systems

### The Reclamation

Vibe coding, done correctly, means:
- **Intuition-driven exploration**: Let the LLM draft approaches quickly
- **Rapid iteration**: Don't overthink the first version
- **Flow state**: Stay in the creative zone, don't context-switch to boilerplate
- **Trust but verify**: Review output against known constraints

The key insight: **vibes are fine for tactics, not for laws of physics**.

You can vibe on:
- UI layouts
- Variable names
- Which Django package to use
- API response formats

You cannot vibe on:
- Whether money balances
- Whether history is mutable
- Whether retries create duplicates
- Whether time has one meaning or two

### The Constitution Metaphor

Before the United States wrote any laws, it wrote a Constitution—the constraints that all future laws must satisfy.

Before you write any Django models, you write a constitution—the constraints that all future code must satisfy.

The LLM can draft legislation all day. Your job is to be the Supreme Court.

---

## 1.3 Why ERP Systems?

### The Definition

ERP (Enterprise Resource Planning) systems manage the core operations of a business:
- Who are our customers, vendors, employees? (Identity)
- What do we own and owe? (Accounting)
- What have we promised and delivered? (Agreements)
- What happened and when? (Audit)

### Why ERP Is the Hardest Test

ERP systems fail in ways that other software doesn't:

| Failure Mode | Typical App | ERP System |
|--------------|-------------|------------|
| Duplicate record | Annoying | Fraudulent (double-billing) |
| Lost update | User retries | Missing $50,000 payment |
| Mutable history | "Weird bug" | Audit failure, legal liability |
| Time confusion | Wrong timestamp | Incorrect financial statements |

If your primitives survive ERP, they survive anything.

### The Reuse Thesis

The same primitives that run a veterinary clinic run:
- Property management (leases are agreements, rent is ledger entries)
- Dive operations (tanks are inventory, certifications are temporal records)
- Water delivery (routes are schedules, gallons are ledger quantities)
- Pizza delivery (orders are events, refunds are reversals)

**Build the primitives once. Apply them forever.**

---

## 1.4 Why Django?

### The Boring Technology Thesis

Django is boring. That's the point.

- **Stable**: Major versions don't break your code
- **Opinionated**: Fewer decisions to make, more constraints by default
- **Batteries included**: Auth, admin, ORM, migrations, testing
- **Documented**: Every pattern has been written about extensively
- **LLM-friendly**: Massive training data corpus, reliable generations

### Django's Built-in Constraints

Django already enforces some constraints for you:
- **Migrations**: Schema changes are versioned and reversible
- **Transactions**: `@transaction.atomic` gives you ACID by default
- **Auth**: User model, permissions, groups out of the box
- **Admin**: Free audit UI for every model

### What Django Doesn't Give You

The primitives in this book fill Django's gaps:
- **Bitemporality**: Django has `auto_now`, not Snodgrass
- **Immutability**: Django's ORM encourages UPDATE
- **Ledgers**: No double-entry pattern built-in
- **Event sourcing**: Signals exist but aren't event stores
- **Idempotency**: No built-in pattern

This book adds the missing constraints.

---

## 1.5 The Role of the LLM

### What LLMs Are Good At

- Generating boilerplate quickly
- Translating patterns from one context to another
- Writing test cases when given the edge cases to cover
- Explaining code and suggesting improvements
- Drafting documentation

### What LLMs Are Bad At

- Knowing which constraints matter for your domain
- Choosing correct patterns when not explicitly asked
- Catching their own errors
- Maintaining consistency across a large codebase
- Saying "this is a bad idea"

### The Collaboration Model

```
You: Define constraints (constitution)
LLM: Draft implementation (legislation)
You: Review against constraints (judicial review)
LLM: Revise based on feedback
You: Write tests for edge cases
LLM: Implement tests
You: Run tests, verify behavior
```

The LLM is a fast, tireless junior developer who has read everything but understood nothing. Your job is to provide the understanding.

---

## 1.6 The Primitives Preview

This section briefly introduces each primitive covered in the book:

### Identity
> "Who is this, really?"

The same person can appear as customer, vendor, and employee. The same company can have five names. Identity is a graph, not a row.

### Ledgers
> "Where did the money go?"

Balances are computed, not stored. Every movement has an equal and opposite movement. The books must balance.

### Bitemporality
> "What did we know, and when did we know it?"

When something happened (business time) is different from when we recorded it (system time). Both matter.

### Immutability
> "What happened, happened."

History doesn't change. Corrections are new facts, not edits to old facts. The audit trail is sacred.

### Idempotency
> "Do it once, no matter how many times you ask."

Networks fail. Clients retry. The same request twice must not charge the customer twice.

### Events
> "Decisions are facts."

State is derived from what happened. Events are the source of truth. Projections are convenient views.

### Reversals
> "Undo without erasing."

Refunds don't delete payments. Cancellations don't delete orders. New facts negate old facts.

### Agreements
> "What did we promise?"

Terms change over time. The terms that applied when the order was placed are the terms that govern the order.

### Sequences
> "What number is next?"

Invoice numbers must be sequential. Gaps must be explained. Auditors will ask.

### Permissions
> "Who's allowed to do this?"

Access must be justified. Permissions must be reviewed. The departed employee's account must be disabled.

---

## 1.7 How to Read This Book

### If You're Building From Scratch

Read Part I (Constraints) completely. Absorb the primitives. Then work through Part II (Implementation) as you build.

### If You're Rescuing an Existing System

Jump to the specific primitive chapters that address your pain:
- Duplicate records? → Chapter on Identity
- Audit failures? → Chapters on Immutability and Events
- Financial reconciliation issues? → Chapter on Ledgers
- "The data was different yesterday" → Chapter on Bitemporality

### If You're Evaluating the Approach

Read this chapter and Chapter 2 (Why Systems Fail). If the failure modes don't resonate, this book isn't for you. If they do, you'll want the solutions.

### The Code Repository

All code examples are available at [repository URL]. Each chapter has a corresponding branch showing the system at that stage of development.

The repository is itself a demonstration of the methodology—developed using Claude with the constraint-first prompting approach.

---

## 1.8 The VetFriendly Story

### The Origin

[This section tells the story of VetFriendly—the veterinary practice management system from which the primitives were extracted. Personal narrative about why it was built, what went wrong initially, what survived, and how it became the template for everything else.]

Key beats:
- Initial naive implementation
- First audit/reconciliation failure
- Discovery of the patterns (Snodgrass, Pacioli, etc.)
- Refactoring to primitives
- Reuse in property management, other domains

### The Extraction

The primitives in this book aren't theoretical. They're the patterns that survived VetFriendly and replicated across:
- Property lease management
- Dive operation scheduling
- Water delivery routing
- [Other Nestor domains]

### The Thesis Tested

Each case study in Part IV shows the same primitives solving different domain problems. The constraints are the product. The domains are just configuration.

---

## 1.9 Chapter Summary

- **Vibe coding** is fast iteration within constraints, not reckless shipping
- **Constraints** are defined before code, like a constitution
- **ERP systems** are the hardest test because failures are financial and legal
- **Django** provides the right foundation: boring, stable, LLM-friendly
- **LLMs** are fast drafters that need constitutional guidance
- **The primitives** (identity, ledgers, time, immutability, etc.) are the constraints
- **This book** teaches you to prompt for correctness and verify the output

---

## Exercises

1. **Audit your current system**: Pick a system you've built or maintained. Which of the primitives does it violate? What failures have you seen as a result?

2. **Prompt comparison**: Ask an LLM to "build an inventory system" with no constraints. Then ask it to "build an inventory system using double-entry ledger semantics with immutable transaction records." Compare the outputs.

3. **Find your constitution**: Before building anything, write down 3-5 constraints that all code must satisfy. These are your non-negotiables.

---

## Key Terms Introduced

- **Vibe coding**: Rapid, intuition-driven development within defined constraints
- **Constitution**: The set of inviolable constraints defined before implementation
- **Primitive**: A foundational pattern that solves a category of problems
- **Constraint-first prompting**: Specifying constraints in LLM prompts before describing features

---

## What's Next

Chapter 2 examines why ERP systems fail in detail—the specific failure modes that each primitive prevents. Understanding the failures makes the solutions obvious.
