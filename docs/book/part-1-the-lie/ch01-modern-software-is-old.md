# Chapter 1: Modern Software Is Old

> Every "revolutionary" system eventually converges to the same primitives that COBOL systems used in 1970.

---

**Core idea:** There are no new primitives. Only new interfaces to old ones.

**Failure mode:** Treating every project as novel, then rediscovering identity, time, money, and agreements the hard way.

**What to stop doing:** Building infrastructure. Start composing primitives.

---

## The Lie

"We're building something new."

No. You're building identity, time, money, and agreements. Again.

Every pitch deck promises disruption. Every startup claims to reinvent an industry. Every framework announces a paradigm shift.

And underneath every single one of them sits the same data structures that have existed since before you were born.

Users. Accounts. Transactions. Schedules. Documents. Permissions.

The React frontend is new. The GraphQL API is new. The Kubernetes cluster is new.

But the entities those technologies serve? Ancient.

Your "revolutionary fintech platform" is a double-entry ledger with a mobile app.

Your "AI-powered scheduling solution" is a calendar with machine learning on top.

Your "next-generation CRM" is a contact database with better CSS.

This is not cynicism. This is observation.

---

## What Actually Changes

Technology changes how we build software. It does not change what we build.

Object-oriented programming. The web. Mobile. Cloud. Microservices. Serverless. AI.

Each wave promised transformation. Each wave delivered better tools for the same job.

The job is: track who did what, when, for how much, under what terms.

That job hasn't changed since Babylonian merchants scratched tallies into clay tablets.

---

## The Evidence

Consider the companies everyone calls revolutionary.

**Uber** moves people from one place to another for money.

Identity: drivers and riders.
Agreements: fare calculations, terms of service.
Money: payments and payouts.
Time: pickup times, trip duration, surge windows.

The innovation was GPS and a smartphone app. The primitives were unchanged.

**Airbnb** lets people rent rooms to strangers.

Identity: hosts and guests.
Agreements: booking terms, house rules, cancellation policies.
Money: payments, deposits, refunds.
Time: check-in, check-out, availability calendars.

The innovation was photos and trust signals. The primitives were unchanged.

**Stripe** processes payments over the internet.

Identity: merchants and customers.
Agreements: payment terms, dispute policies.
Money: the entire product.
Time: transaction timestamps, settlement periods.

The innovation was a clean API. The primitives were unchanged.

None of these companies invented new primitives. They composed existing primitives better than incumbents, wrapped them in better interfaces, and scaled them with modern infrastructure.

The disruption was in the interface. Not in the entity model.

---

## The Four Primitives

Across dozens of projects—restaurants, medical practices, logistics companies, government contracts—the same four primitives appeared every time.

**Identity** — Who is this?

Users, accounts, parties. Who are the actors in this system?

This hasn't changed since the first census. Every business system starts with the same question: who?

The same person appears as customer, vendor, and employee. The same company has five names and three tax IDs. Identity is messier than a single row in a database. It always has been.

**Time** — When did this happen?

When something happened. When we recorded it. The difference between those two.

This hasn't changed since humans started keeping calendars. Every audit, every legal proceeding, every financial reconciliation depends on getting time right.

Business time is not system time. The sale closed on Friday. The system recorded it Monday. Both facts matter. Confuse them and you fail audits.

**Money** — Where did it go?

Double-entry ledgers. Debits equal credits. Balances are computed, never stored.

This hasn't changed since Luca Pacioli formalized it in 1494. Every business that handles money either uses double-entry accounting or eventually fails an audit.

Money doesn't move. It transforms. Cash becomes inventory. Inventory becomes receivables. Receivables become cash. The total never changes. If it does, someone is lying or confused.

**Agreements** — What did we promise?

Contracts, terms, obligations. What was promised, by whom, under what conditions.

This hasn't changed since Hammurabi carved laws into stone. Every transaction more complex than a cash sale requires an agreement.

Terms change over time. The terms that applied when the order was placed are the terms that govern the order. Never point to current terms from historical transactions.

---

## Why Projects Reinvent Primitives

Every development team eventually builds identity, time, money, and agreements.

Most build them badly.

Not because developers are incompetent. Because extracting and generalizing these primitives used to cost more than rebuilding them.

I learned this firsthand.

In 2006, my partner and I started building systems for clients. We used Sharpie markers and index cards. Clients would write user stories. We'd stick them on a metal wall with magnets. Pennies, nickels, dimes, and quarters glued to magnets showed the budget.

It worked. Clients could see exactly what they were getting each sprint. Scope creep was contained. Dependencies were visible.

But the documentation tax was brutal.

Specifications. Test plans. Requirements documents. Most of the energy went into planning and writing, not building. Every project started from scratch. Every project reimplemented the same patterns.

Identity. Authentication. Roles. Permissions. Transactions. Audit trails.

We knew these were the same across projects. We just couldn't afford to extract them.

---

## What Changed

AI changed the economics.

Not because AI understands business. It doesn't.

Not because AI invents better primitives. It can't.

But because AI writes documentation, tests, and boilerplate at speeds that make extraction economical.

The same primitives that existed in 1970 can now be captured, tested, and packaged in hours instead of months.

The patterns that every developer rediscovers can be encoded once and composed forever.

This book is about those primitives. Not because they're new. Because they're finally capturable.

---

## The Uncomfortable Truth

Your React frontend is a thin skin over the same data structures that ran on mainframes.

The only difference is you have worse documentation.

Those mainframe systems had specifications. They had audit trails. They had test plans. They had the documentation tax paid in full, because the cost of failure was obvious.

Modern systems skip the documentation. They ship faster. They fail slower. The failures are harder to trace because nobody wrote down what the system was supposed to do.

AI doesn't fix this automatically. AI makes it possible to fix.

The primitives still need to be correct. The constraints still need to be defined. The audit trails still need to exist.

AI just removes the excuse that documentation is too expensive.

---

## What To Do Instead

Stop building infrastructure. Start composing primitives.

When you start a new project, ask:

Who are the parties? That's Identity.
What terms govern their interactions? That's Agreements.
What did they owe and when? That's Money and Time.

These questions have answers. The answers are not novel.

The novel part is your domain. The pizzeria. The veterinary clinic. The property management company. The government permit office.

The primitives are the same. The configuration is different.

Build the primitives once. Apply them forever.

---

## Why This Matters Later

This chapter established that software primitives are not new. They are ancient. The patterns that "disruptive" companies use are the same patterns that mainframes used, that paper ledgers used, that clay tablets used.

The next chapter addresses the second lie: that AI understands your business.

It doesn't.

AI is a very fast typist with no judgment. But that's exactly what makes it useful—if you constrain it properly.

Understanding that primitives are physics, not features, is the first constraint. AI can implement identity, time, money, and agreements. But only if you tell it to. Left to its own devices, it will build something clever instead.

Clever breaks under audit.

Boring survives.

---

*Status: Draft*
