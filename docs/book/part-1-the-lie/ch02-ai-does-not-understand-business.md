# Chapter 2: AI Does Not Understand Business

> AI is a very fast typist with no judgment.

---

**Core idea:** AI predicts plausible text. It does not understand your business, your constraints, or your invariants.

**Failure mode:** Trusting fluent output as correct output. Assuming AI "gets it."

**What to stop doing:** Delegating without constraints. Treating AI as a junior developer instead of a very fast typist.

---

## The Lie

"AI understands what I need."

I hear this constantly. Founders who think their prompt was clear enough. Developers who assume Claude read between the lines. Business owners who believe the confident tone means the output is correct.

They're all wrong.

AI does not understand your business. AI does not understand any business. AI predicts what text would plausibly come next, based on patterns in its training data.

That's it. That's the whole trick.

When you ask an AI to build an invoicing system, it doesn't think about invoices. It doesn't imagine your customers. It doesn't consider your tax jurisdiction or your audit requirements. It looks at the statistical patterns of text that followed similar prompts in its training data, and it generates more text that fits those patterns.

The output is fluent. The output sounds right. The output may even work—for a while. But the output is not based on understanding. It's based on pattern matching.

This distinction is not academic. It's the difference between a system that survives an audit and a system that collapses under scrutiny.

---

## What AI Actually Does

Large Language Models work by predicting the next token.

Given a sequence of text, the model calculates probabilities for what token should come next. Not what token is *correct*. What token is *statistically likely* given the patterns in the training data.

"The customer's balance is calculated by" → most likely next tokens might be "summing all transactions" or "subtracting payments from charges" or "looking up the balance field."

The model doesn't know which is right for your system. It doesn't even know what "right" means. It knows that in the billions of text samples it was trained on, certain words tend to follow other words.

This works remarkably well for generating plausible text. It works remarkably poorly for generating correct systems.

---

## Fluency Is Not Correctness

The most dangerous property of AI-generated code is that it reads well.

A human developer writing bad code often writes *obviously* bad code. The variable names are wrong. The structure is confused. The comments don't match the implementation. You can tell at a glance that something is off.

AI-generated code is fluent. The variable names are reasonable. The structure follows conventions. The comments accurately describe what the code does. Everything *looks* professional.

But the code can still be catastrophically wrong.

I once reviewed an AI-generated invoicing system that was beautifully structured. Clean separation of concerns. Proper use of Django models. Well-documented API endpoints. It was a pleasure to read.

It also allowed invoices to be deleted. Not archived. Not voided. Deleted. Completely removed from the database.

The AI didn't know that invoices are legal documents. The AI didn't know that tax authorities require you to maintain records. The AI didn't know that accountants have opinions about disappearing financial records.

The AI just generated code that looked like invoicing systems it had seen before. Some of those systems were demos. Some were tutorials. Some were badly designed production systems that nobody should copy.

The output was fluent. The output was wrong.

---

## No Object Permanence

AI has no memory of constraints from one response to the next.

You can tell an AI "all financial transactions are immutable" in one message. In the next message, it might generate an UPDATE statement that modifies transaction records. Not because it's rebellious. Because it doesn't remember. Each response is generated fresh, based on the current context window.

This is not a bug. It's how the technology works.

The context window—the text the AI can see when generating a response—is limited. Even with large context windows, the AI doesn't *understand* what's in the context. It pattern-matches against it. If your constraint isn't prominently stated, or if the patterns from training data suggest something different, the AI will follow the patterns.

I've seen this happen dozens of times:

- "Money should use Decimal" in the spec. Float64 in the generated code.
- "All changes require audit logging" in the requirements. No audit logging in the implementation.
- "Users can have multiple roles" in the design. A single role field in the schema.

The AI read the constraints. The AI didn't internalize them. The patterns from training data were stronger than the explicit instruction.

---

## Why AI Invents

Left to its own devices, AI invents.

Not intentionally. Not creatively. It invents because invention is the default behavior of a system optimized to generate plausible text.

When you ask for an invoicing system, the AI doesn't assemble known-good primitives. It generates text that looks like an invoicing system. If that text includes novel approaches, clever optimizations, or creative data structures, that's just what the pattern matching produced.

Sometimes the invention is harmless. A slightly unusual naming convention. A helper function organized differently than you'd expect.

Sometimes the invention is catastrophic. A "clever" caching strategy that returns stale data. An "optimized" query that skips the audit trail. A "simplified" data model that violates third normal form in ways that will corrupt data over time.

The AI doesn't know the difference. It doesn't evaluate its output against correctness criteria. It generates plausible text and stops.

Your job is to be the judge.

---

## The Invoice Test

Want to see this in action? Ask any AI to build an invoicing system. Don't provide constraints. Just say: "Build me an invoicing system in Django."

Then count the invariant violations:

**Mutable history:** Can invoices be edited after they're sent? In most AI-generated systems, yes. In a correct system, never. Sent invoices are legal documents. Corrections are new invoices (credit notes, adjustments), not edits to existing records.

**Floating-point currency:** Does the code use Float or Double for money? In most AI-generated systems, yes. In a correct system, never. Binary floating-point cannot exactly represent decimal values. $0.10 + $0.20 might equal $0.30000000000000004. Accountants notice.

**No audit trail:** Is there a log of who changed what, when? In most AI-generated systems, no. In a correct system, always. Auditors ask questions. "Who approved this write-off?" "When was this payment recorded?" "Why was this invoice voided?" Without an audit trail, you have no answers.

**Editable totals:** Are invoice totals stored as editable fields, or computed from line items? In most AI-generated systems, stored. In a correct system, computed. If the total is stored, it can drift out of sync with the line items. If it's computed, it's always consistent.

I've run this test dozens of times. The AI fails every time. Not because the AI is stupid. Because the AI doesn't know these constraints exist. Nobody told it. The patterns in its training data include good systems and bad systems, and it has no way to tell the difference.

---

## The Constraint Solution

The fix is not to avoid AI. The fix is to constrain it.

AI is excellent at implementing patterns it has seen before. It's terrible at evaluating whether those patterns are appropriate. So you separate those jobs:

You define the constraints. You know your business. You know what must never happen. You know what must always be true. You encode these as explicit rules.

AI implements within the constraints. Given explicit rules, AI is remarkably good at following them. "Never use floating-point for money" produces Decimal fields. "All changes must be logged" produces audit logging. "Invoices cannot be deleted" produces soft-delete or append-only patterns.

The constraint transforms AI from an inventor to an assembler. Instead of generating novel solutions, it composes known-good patterns. Instead of guessing what you need, it follows explicit instructions.

This is why the primitives matter. They're the constraints that every business system needs. Identity, time, money, agreements—these are not features you choose. They're physics you obey. When you encode them as explicit constraints, AI stops inventing and starts composing.

---

## Manager and Agent

Think of AI as an employee. A very unusual employee.

It has read everything. Every Stack Overflow answer. Every GitHub repository. Every tutorial, every blog post, every documentation page. It can recall and synthesize this knowledge faster than any human.

It has no judgment. It cannot evaluate whether an approach is appropriate for your situation. It cannot anticipate edge cases you haven't mentioned. It cannot recognize when its output violates business rules you consider obvious.

It does exactly what you tell it. Not approximately. Exactly. If you say "build an invoicing system," it builds what it thinks an invoicing system looks like. If you say "build an invoicing system where invoices cannot be deleted, use Decimal for all currency, log all changes with actor and timestamp, and compute totals from line items," it builds that.

You are the manager. You provide the constraints. You review the output. You catch the violations.

AI is the agent. It executes quickly. It doesn't argue. It doesn't get tired. It doesn't push back on requirements it thinks are silly.

A good manager gives clear, complete instructions. A bad manager says "just figure it out" and blames the employee when things go wrong.

The instructions are the constraints. This book teaches you what constraints matter.

---

## The Review Non-Negotiable

Every failure I've seen in AI-assisted development came from skipping review.

The founder who shipped the AI-generated code because it "looked right." The developer who trusted the test suite the AI wrote to test the code the AI wrote. The consultant who delivered the AI output directly to the client because the deadline was tight.

Every success came from treating review as non-negotiable.

AI does not understand your business. You do. Your job is not to write code—AI can do that faster than you. Your job is to verify that the generated code actually implements your constraints.

This is not optional. This is not something you do "when you have time." This is the core skill of AI-assisted development. If you skip review, you are not managing. You are delegating authority to a system that has no judgment.

The system will confidently build things that violate your constraints. It will never tell you it's doing so. It doesn't know your constraints unless you specify them. It doesn't check your constraints unless you ask.

You are the Supreme Court. The AI drafts legislation. You decide whether it's constitutional.

---

## What AI Is Good For

This chapter has focused on what AI gets wrong. But AI is remarkably useful—within the right boundaries.

**Documentation:** AI writes documentation faster than you. Given code, it generates explanations. Given explanations, it generates code. The cycle is fast.

**Boilerplate:** AI generates repetitive patterns without fatigue. The fifteenth database model is as clean as the first. The fiftieth test case follows the same conventions.

**Recall:** AI remembers everything. "What's the Django syntax for a many-to-many relationship with extra fields?" The answer is instant, accurate, and includes examples.

**Drafting:** AI generates first drafts quickly. Not final drafts—first drafts. Something to react to. Something to revise. Something better than a blank page.

**Composition:** Given explicit primitives and explicit constraints, AI assembles them correctly. It doesn't need to understand why the primitives matter. It just needs to know what they are and how they fit together.

The pattern: AI executes. You evaluate. AI revises. You approve.

This is faster than writing everything yourself. This is safer than trusting AI output directly. This is the collaboration model that works.

---

## Why This Matters Later

This chapter established that AI does not understand your business. It predicts plausible text based on patterns. It generates fluent output that may be catastrophically wrong. It has no memory of constraints across responses. It invents when it should compose.

The fix is constraints. Explicit rules that transform AI from an inventor to an assembler.

The next chapter addresses the third lie: that you'll refactor later. You won't. The shortcuts you take now become the architecture you're stuck with. AI makes this worse, because AI generates plausible shortcuts faster than you can recognize them.

Understanding that AI requires constraints—and that constraints must be explicit—is the foundation. Without this, the primitives are just ideas. With this, they're enforceable physics.

---

*Status: Draft*
