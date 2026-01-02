# Introduction: Vibe Coding With Constraints

> You can move fast with LLMs while building systems that are fundamentally correct—if you lock down the right constraints before you start.

---

## Who This Book Is For

**For the non-technical idea maker:**

This book is for business owners who are tired of explaining their domain to developers who don't get it.

I've watched it happen dozens of times. You sit in a meeting room with someone half your age who keeps interrupting to ask questions you answered ten minutes ago. You explain your business—the one you built, the one you've run for years—and they nod while typing. Three months later, you get software that technically does what you asked for but somehow misses the point entirely.

The invoices are correct but confusing.
The workflow is logical but backwards.
The reports are accurate but useless.

They didn't listen. Or they listened but didn't understand. Or they understood but didn't care. It doesn't matter which. The result is the same. You paid for software that doesn't fit.

This book is for the entrepreneur who knows exactly what the system *should* do—but has been told they need to hire a team, raise money, or learn to code before they're allowed to build it.

You don't.

You don't need a computer science degree.
You don't need perfect recall of programming languages.
You don't need to memorize algorithms or understand Big-O notation.
You don't need to pass a whiteboard interview.

What you need is something far more valuable: **clarity about your business**.

Most failed software projects don't fail because of bad code. They fail because the business logic was never made precise enough to survive translation. Somewhere between "this is how we actually work" and "here's the system we shipped," meaning is lost. Edge cases get rounded off. Exceptions become bugs. Workarounds become features. Reality gets simplified until it breaks.

Developers aren't stupid. They're just trained to think in abstractions. Business owners live in exceptions.

This book is about closing that gap.

It's about taking what you already know—your rules, your constraints, your "we never do it that way"—and expressing it in a form that software can't misunderstand. Not by turning you into a programmer, but by giving you primitives. Simple, durable building blocks that map cleanly to how real businesses operate.

And here's the part nobody tells you: once those primitives are clear, modern AI tools can do most of the mechanical work. Not the thinking. Not the judgment. The typing. The wiring. The boring parts that used to require a team and a budget.

The mistake is letting AI think for you.
The leverage is making it obey.

This book will not teach you how to code. It will teach you how to **describe your business so precisely that code becomes inevitable**.

Once you can do that, the rest stops being magic.

**For the technical professional:**

You've heard the predictions.

AI will replace programmers. Junior roles will disappear. The industry is over.

I don't believe that. But I do believe the job is changing.

The developers who thrive won't be the ones who memorize syntax or type the fastest. They'll be the ones who know what the code *should* do before it's written. The ones who can look at generated output and say "that's wrong" before the tests even run. The ones who translate messy human requirements into precise, enforceable constraints.

This is what senior developers have always done. Now it's the entire job.

The typing is automated. The judgment is not.

If you've spent years learning to code, that's not wasted. You learned to think precisely. To anticipate edge cases. To recognize when something will break before it breaks. Those skills are more valuable now, not less.

You just apply them differently.

You stop being the person who writes the code. You become the person who knows whether the code is right. That's a promotion, not a demotion.

This book shows you where the value moves: from implementation to specification. From coding to constraint definition. From building to verifying.

**For everyone:**

I'm not really a programmer. Not in the traditional sense.

I can't recite sorting algorithms from memory. I couldn't pass a technical interview at a big tech company. I've never worked at one. I've never wanted to.

But I've built systems that handle real money. Real customers. Real audits.

I've been doing this since 2006. I've watched methodologies come and go. Waterfall. Agile. Scrum. DevOps. Each one promised to fix what was broken. Each one was partially right.

Here's what I can do: I can describe what I need. I can recognize correct behavior when I see it. I can define constraints. I can say "this must never happen" and "this must always be true."

That's enough now.

It wasn't enough before.

---

## The LLM Liberation

Large Language Models have changed the economics of software development.

Most people haven't fully absorbed this yet.

An LLM is not artificial intelligence in the science fiction sense. It doesn't understand your business. It doesn't have opinions about architecture. It doesn't know what's correct. It only knows what's *statistically likely* based on patterns in its training data.

But "statistically likely" turns out to be powerful when:

The problem has been solved before. Most have.
The patterns are well-documented. Most frameworks are.
You can verify the output. Tests exist.
You provide the constraints. That's your job.

The LLM has read every Stack Overflow answer. Every tutorial. Every GitHub repository. It can synthesize that knowledge faster than any human can search for it.

You don't need to remember the syntax. The LLM remembers.
You don't need to recall the algorithm. The LLM recalls.
You don't need to know the best practice. The LLM knows many practices.

Your job is to pick the right one.

**The LLM is a very fast typist with no judgment. You provide the judgment.**

The framework in this book is Django. The language is Python. This choice is deliberate.

Python is readable. Even if you've never programmed, you can follow what's happening. The code reads almost like English.

Django is proven. It's been running production systems since 2005. Instagram. Pinterest. Mozilla. It's not exciting. It's reliable.

Django is flexible. It has opinions where you want them and gets out of the way where you don't.

AI assistants know Django better than almost anything else. There's more Python and Django in their training data than most other languages. When you ask for Django code, the LLM has seen your pattern a hundred thousand times. That makes its suggestions reliable.

Django developers are everywhere. When you need human help—and eventually you will—you can throw a stick at any job board and hit a few hundred. The ecosystem is mature. The talent pool is deep. You're not betting on an obscure technology that three people understand.

But the primitives outlive the framework.

They worked before Django existed. They'll work after Django is forgotten. Django is the implementation vehicle, not the idea. If you prefer Rails, Laravel, or Spring, the primitives translate. The constraints are universal.

And when it's time to make things fast—really fast—you profile, find the bottlenecks, and rewrite those pieces in Rust. The boring Django system that "just works" becomes the foundation. The primitives stay the same. The hot paths get optimized.

This is how real systems scale: correct and boring first, fast later, in the places that actually matter.

---

## The End of Trivial Arguments

Anyone who has worked on a development team knows the arguments.

I once watched two senior engineers spend forty-five minutes debating whether a variable should be called `userId` or `user_id`. Neither was wrong. Neither was right. It didn't matter. But they were both convinced it did, and neither would back down.

Forty-five minutes of combined salary. Probably $200 worth of engineering time. Spent on a decision that affects nothing.

Multiply that by every team. Every day. Every year.

The industry has burned billions of dollars on formatting preferences.

Tabs or spaces?
Should this be a class or a function?
Is this helper too clever?
Do we really need that abstraction?

Hours lost to bikeshedding. Careers defined by style preferences. Teams fractured over formatting. I've seen friendships end over curly brace placement.

AI ends this.

The LLM picks a convention and sticks to it. It doesn't care about your opinions. It doesn't have ego. It generates code in whatever style you specify. If you don't specify, it picks something reasonable and moves on.

The arguments that remain are the ones that actually matter:

Does this data model represent reality correctly?
Can this operation be safely retried?
What happens when this fails?
Who is allowed to see this?

These are the arguments worth having. These are the constraints this book teaches you to define. These are the things that actually matter to business people.

---

## You Are the Manager

Think of the LLM as an employee. Fast. Tireless. Has read everything.

Will do exactly what you tell it to do.

That's the problem.

I learned this the hard way. Early on, I asked an LLM to build an invoicing system. It built one. It worked. Customers could create invoices, edit them, delete them.

Delete them.

Three months later, a customer asked why their tax records didn't match their bank statements. The answer: they had "cleaned up" their invoice list by deleting the ones they'd already paid.

The data was gone.
The audit trail was gone.
The evidence was gone.

The LLM didn't know that invoices shouldn't be deletable. I didn't tell it. So it did the obvious thing—it made them deletable, because most things in software are deletable. It was statistically likely.

**You are the manager. The LLM is the agent.**

A bad manager says "build this."

A sophisticated manager says:

Build this, but invoices can never be deleted, only voided.
Build this, but every change must be logged with who did it and when.
Build this, but the same request twice must not create duplicates.

This book teaches you to be that sophisticated manager.

Not by teaching you to code. By teaching you the fundamentals that any business owner should know about their business system. The things that are true whether you use AI or hire developers or build it yourself.

These fundamentals are the physics of business software. Violate them and the system eventually fails. An audit. A lawsuit. An angry accountant. A customer charged twice.

The LLM just makes it possible for you to encode these fundamentals directly. Without learning to program. Without hiring a team. Without hoping someone else understands your constraints as well as you do.

---

## The Two Ways to Fail

Two startups build inventory systems with Claude in the same week.

**Startup A** prompts: "Build me an inventory tracking system in Django."

Gets working code in 2 hours.
Ships to customers in 2 weeks.
Month 3: Customer reports negative inventory quantities.
Month 4: Audit finds inventory movements with no trail.
Month 6: Accountant quits because the books don't reconcile.
Month 8: Rewrite begins.

I know the founder of Startup A. Or rather, I know a dozen founders of Startup A. They're smart. They're driven. They moved fast. They just didn't know what they didn't know.

The system did exactly what they asked for. It just wasn't what they needed.

**Startup B** prompts: "Build an inventory system using double-entry ledger semantics where quantities move between location accounts via balanced transactions. No UPDATE or DELETE on movement records. Include idempotency keys on all mutations."

Gets working code in 4 hours.
Ships to customers in 3 weeks.
Month 3: Customer requests inventory as-of-date reporting. Already supported.
Month 6: Passes audit with complete transaction history.
Month 12: Same codebase, new features.

The difference isn't the LLM. It's the constraints in the prompt.

Startup B's founder spent two extra hours learning what constraints matter for inventory systems. That investment paid for itself a thousand times over.

---

## What "Vibe Coding" Actually Means

"Vibe coding" became a pejorative because people confused it with recklessness.

Shipping without tests.
Trusting LLM output without review.
Ignoring edge cases.
Building demos instead of systems.

That's not vibe coding. That's negligence.

Vibe coding, done correctly, means staying in flow.

Let the LLM draft approaches quickly. Don't overthink the first version. Stay in the creative zone instead of context-switching to boilerplate. Review output against known constraints.

The key insight: **vibes are fine for tactics, not for physics**.

You can vibe on UI layouts. Variable names. Which library to use. API response formats.

You cannot vibe on whether money balances. Whether history is mutable. Whether retries create duplicates. Whether time has one meaning or two.

If a solution feels clever, it's probably wrong.

Boring is a virtue. The primitives in this book are aggressively boring. They solve problems that were solved centuries ago. They just encode those solutions in software.

---

## The Constitution Metaphor

Before the United States wrote any laws, it wrote a Constitution.

The constraints that all future laws must satisfy.

Before you write any code, you write a constitution. The constraints that all future code must satisfy.

The LLM can draft legislation all day.

Your job is to be the Supreme Court.

Your constitution might include:

All records use UUID primary keys, never auto-increment.
All money uses Decimal, never floating point.
Financial records are append-only. Corrections are reversals, not edits.
All timestamps distinguish "when it happened" from "when we recorded it."
All operations that can be retried must produce the same result.

These constraints aren't features. They're physics. The LLM must work within them.

---

## Why ERP Systems?

ERP stands for Enterprise Resource Planning. Fancy name for a simple question: how does this business actually work?

Who are our customers, vendors, employees? That's Identity.
What do we own and owe? That's Accounting.
What have we promised and delivered? That's Agreements.
What happened and when? That's Audit.

Every business that survives long enough builds an ERP system. Whether they call it that or not.

The spreadsheet that tracks customers. The notebook that records deliveries. The filing cabinet full of contracts. That's ERP.

ERP systems don't fail because they're complex. They fail because they encode business reality incorrectly.

And when they fail, they fail hard.

A duplicate record in a typical app is annoying. In an ERP system, it's fraudulent double-billing.

A lost update in a typical app means the user retries. In an ERP system, it's a missing $50,000 payment.

Mutable history in a typical app is a weird bug. In an ERP system, it's audit failure and legal liability.

I've seen a restaurant lose $30,000 because their inventory system allowed negative quantities. I've seen a medical practice face an audit because their billing system edited records instead of creating corrections. I've seen a property manager sued because their lease system couldn't prove what terms were agreed to when.

These aren't edge cases. They're what happens when you violate the physics.

**If your primitives survive ERP, they survive anything.**

The same primitives that run a veterinary clinic run property management. Leases are agreements. Rent is ledger entries.

The same primitives run dive operations. Tanks are inventory. Certifications are temporal records.

The same primitives run pizza delivery. Orders are events. Refunds are reversals.

The same primitives run government permits. Applications are workflows. Approvals are decisions.

Primitives don't solve businesses. They make businesses composable.

Build the primitives once. Apply them forever.

---

## The Primitives Preview

This book covers the core primitives that every business system eventually needs. Some are foundational—you can't build anything without them. Some are compositional—they combine other primitives into higher-level patterns.

The exact count matters less than understanding what category your problem belongs to.

**Identity** — Who is this, really?

The same person can appear as customer, vendor, and employee. The same company can have five names. Identity is a graph, not a row.

**Time** — What did we know, and when did we know it?

When something happened is different from when we recorded it. Both matter. This distinction has saved companies from lawsuits.

**Money** — Where did the money go?

Balances are computed, not stored. Every movement has an equal and opposite movement. The books must balance. Luca Pacioli figured this out in 1494.

**Agreements** — What did we promise?

Terms change over time. The terms that applied when the order was placed are the terms that govern the order. Never point to current terms from historical transactions.

**Catalog** — What can be sold?

Products. Services. Bundles. Definitions, not instances. Pricing rules, not prices.

**Workflow** — What stage is this in?

State machines. Explicit transitions. Humans are unreliable nodes in any process.

**Decisions** — Who decided, and why?

Auditable intent. Reproducible outcomes. When regulators ask questions, you need answers.

**Audit** — What happened?

Everything emits a trail. Silence is suspicious. Logs are legal documents in disguise.

**Ledger** — Did the books balance?

Double-entry or don't bother. Reversals, not edits. If it doesn't balance, it's lying.

Underlying all of these is a principle, not a primitive: **Immutability**.

History doesn't change. Corrections are new facts, not edits to old facts. This rule applies across all primitives that touch money, time, or decisions.

---

## The Collaboration Model

Here's how you work with an LLM to build correct systems:

```
You:  Define constraints (constitution)
LLM:  Draft implementation (legislation)
You:  Review against constraints (judicial review)
LLM:  Revise based on feedback
You:  Specify edge cases to test
LLM:  Write the tests
You:  Run tests, verify behavior
LLM:  Fix what fails
```

The LLM is a fast, tireless junior developer who has read everything but understood nothing.

Your job is to provide the understanding.

**A warning.**

If you skip the review step, you are no longer managing. You are delegating authority without oversight.

The LLM will confidently build systems that violate your constraints. It will never tell you it's doing so. It doesn't know your constraints unless you specify them. It doesn't check your constraints unless you ask.

Every failure I've seen in AI-assisted development came from skipping review.

Every success came from treating review as non-negotiable.

---

## How to Read This Book

**If you're a business owner:**

Read Part I (The Lie) to understand why software fails. Read Part IV (Composition) to see how the primitives solve real business problems. Refer to Part II (The Primitives) when you need the details.

**If you're building from scratch:**

Read Part I completely. Absorb the primitives in Part II. Work through Part III (Constraining the Machine) as you build.

**If you're rescuing an existing system:**

Jump to the specific primitive chapters that address your pain.

Duplicate records? Identity.
Audit failures? Audit and Decisions.
Financial reconciliation issues? Ledger.
"The data was different yesterday"? Time.

**If you're evaluating the approach:**

Read this introduction and Chapter 1. If the failure modes don't resonate, this book isn't for you. If they do, you'll want the solutions.

---

## The Promise

By the end of this book, you will be able to:

Define constraints that prevent the most common business software failures.
Prompt an LLM to generate code that respects those constraints.
Verify that generated code actually works.
Build systems that survive audits, lawsuits, and accountant scrutiny.
Reuse the same primitives across any business domain.

You don't need to become a programmer.

You need to become a **constraint definer** and an **output verifier**.

The LLM does the typing.

You do the thinking.

---

## What's Next

Chapter 1 explains why modern software isn't actually modern.

The same primitives that ran on mainframes in 1970 still run every "revolutionary" startup today. The punch cards my father brought home from the Air Force contained the same fundamental operations we execute today with touchscreens and voice commands.

Understanding this history makes the constraints obvious. What seems like arbitrary rules becomes inevitable physics.

---

*Status: Draft*
