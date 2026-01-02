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

But here's what nobody wants to admit: most human developers don't understand your business either.

I've watched senior engineers build invoicing systems that allowed invoices to be deleted. I've reviewed code from expensive consultancies that stored currency as floating-point numbers. I've inherited systems from "expert" contractors that had no audit trail, no immutability, no concept of the regulatory environment they operated in.

The developer understood Python. The developer understood Django. The developer did not understand that an invoice is a legal document, that tax authorities have opinions about disappearing records, that the numbers in financial software must add up to the penny every single time.

This is not a new problem. This is the oldest problem in software development.

The business owner knows the constraints. The developer knows the syntax. The gap between them has destroyed projects since the first line of commercial code was written.

AI didn't create this gap. AI made it faster.

AI does not understand your business. AI does not understand any business. AI predicts what text would plausibly come next, based on patterns in its training data. That's it. That's the whole trick.

When you ask an AI to build an invoicing system, it doesn't think about invoices. It doesn't imagine your customers. It doesn't consider your tax jurisdiction or your audit requirements. It looks at the statistical patterns of text that followed similar prompts in its training data, and it generates more text that fits those patterns.

The output is fluent. The output sounds right. The output may even work—for a while. But the output is not based on understanding. It's based on pattern matching.

A junior developer does the same thing. They copy patterns from Stack Overflow, from tutorials, from the last codebase they worked on. They don't understand your business either. They understand patterns. The difference is speed: the junior developer takes a week to produce bad code, and you might catch it in review. The AI produces bad code in seconds, and it looks so professional that you might not review it at all.

This distinction is not academic. It's the difference between a system that survives an audit and a system that collapses under scrutiny.

---

## What AI Actually Does

Large Language Models work by predicting the next token.

Given a sequence of text, the model calculates probabilities for what token should come next. Not what token is *correct*. What token is *statistically likely* given the patterns in the training data.

"The customer's balance is calculated by" → most likely next tokens might be "summing all transactions" or "subtracting payments from charges" or "looking up the balance field."

The model doesn't know which is right for your system. It doesn't even know what "right" means. It knows that in the billions of text samples it was trained on, certain words tend to follow other words.

This works remarkably well for generating plausible text. It works remarkably poorly for generating correct systems.

But here's the thing that makes AI genuinely revolutionary for software development: it works *spectacularly* well for generating code.

Not because AI understands programming. It doesn't. But because code isn't like natural language. Code is *constrained*. Code has grammar that compilers enforce. Code has patterns that repeat across millions of repositories. Code has archetypes—shapes that appear so consistently that predicting the next token becomes almost deterministic.

When you write `for item in`, the next token is almost certainly `items` or `collection` or `list`. When you write `def __init__(self,`, what follows is parameter definitions. When you write `try:` in Python, an `except:` block is coming. The patterns are rigid. The variations are finite. The structure is predictable in ways that English prose never is.

This is why AI can write code so fast it feels like magic.

A human developer typing `class Invoice:` has to think about what fields an invoice needs, what methods it should have, how it relates to other classes. An AI seeing `class Invoice:` has seen ten million invoice classes. It knows that invoices have line items, totals, dates, statuses, and customer references—not because it understands invoicing, but because that's what invoice classes look like in the training data. The pattern is so strong that the prediction is almost automatic.

Consider a database query. When you write `SELECT * FROM orders WHERE`, the model doesn't need to understand your business to predict reasonable completions. `status = 'pending'` or `customer_id = ?` or `created_at > ?` are all statistically likely because that's what WHERE clauses on order tables look like. Everywhere. In every codebase. The archetype is universal.

---

## Predictions: Right and Wrong

To understand what AI gets right and what it gets catastrophically wrong, you need to see both in action.

**Predictions the AI nails:**

"Write a Django model for a blog post."

The AI produces a model with title, slug, body, author, created_at, updated_at, and published status. This is correct. Not because the AI understands blogs, but because this is what every blog model looks like. The archetype is burned into the training data. The prediction is almost deterministic.

"Add pagination to this API endpoint."

The AI adds page and page_size parameters, calculates offset, returns total count. Correct. Pagination is pagination. The pattern hasn't changed since the 90s.

"Create a login form with email and password."

The AI generates HTML with proper labels, input types, CSRF tokens, validation attributes. Correct. Login forms look the same everywhere. The archetype is universal.

**Predictions the AI invents—confidently and wrong:**

"Build an invoicing system."

The AI creates an Invoice model with a `total` field that's directly editable. Wrong. Totals should be computed from line items, not stored. A user could edit the total without changing line items. An auditor would have questions.

"Add a refund feature."

The AI deletes the original transaction and creates a new one with negative amounts. Wrong. You've just destroyed audit history. The original transaction should remain immutable. A refund is a *new* transaction that references the original.

"Handle currency conversion."

The AI stores amounts as floats and multiplies by exchange rates. Wrong on two counts. Floats introduce rounding errors. And exchange rates change—you need to store the rate *at the time of conversion*, not look it up later.

**The pattern that emerges:**

The AI gets *structure* right. Models, fields, relationships, API shapes, UI components—these are patterns it has seen millions of times. The predictions are reliable.

The AI gets *business rules* wrong. Immutability, audit requirements, temporal semantics, financial constraints—these are invisible in the code. The AI can't predict what it can't see. So it invents. And the inventions are plausible-looking violations of rules you thought were obvious.

Here's the uncomfortable truth: the more domain-specific the rule, the more likely the AI is to violate it. "A refund is a new transaction, not a deletion" is not written in any Django tutorial. "Exchange rates must be captured at transaction time" is not in the Python documentation. "Invoices cannot be modified after sending" is not a syntax error.

These are your rules. Your constraints. Your business physics.

The AI doesn't know them. The AI can't infer them. The AI will confidently generate code that violates them while following every Python convention perfectly.

This is the superpower and the trap.

The superpower: AI can produce syntactically correct, structurally sound, conventionally organized code at speeds no human can match. It can scaffold an entire application in minutes. It can implement CRUD operations, API endpoints, authentication flows, and database migrations without breaking a sweat. The patterns are so well-established that the predictions are reliable.

The trap: reliable patterns are not the same as correct systems.

The AI predicts what code *looks like*. It doesn't evaluate what code *should do*. It generates invoice classes that match the statistical shape of invoice classes—but those classes might allow deletion of sent invoices, use floating-point for currency, or store mutable totals. The patterns are right. The business logic is wrong.

This is why constraints matter so much. The AI is a pattern-completion engine of extraordinary power. Point it at a well-defined archetype with explicit constraints, and it executes flawlessly. Point it at an ambiguous problem with implicit business rules, and it invents confidently—generating code that looks professional and fails audits.

---

## The Failures Are Ancient

Every mistake AI makes, humans have made before. The failures aren't new. The speed is.

**Floating-point currency**

In 1982, the Vancouver Stock Exchange introduced a new index, set at a base value of 1000. The index was recalculated thousands of times daily, and each calculation truncated the result to three decimal places instead of rounding. By November 1983, the index had drifted down to 524.811—a 47.5% loss that existed only in the computers. The actual stocks hadn't crashed. The arithmetic had. When they finally recalculated correctly, the index jumped to 1098.892.

That's what happens when you get rounding wrong. The Vancouver Stock Exchange learned it with humans writing the code. Your AI will make the same mistake if you don't tell it otherwise.

In 1991, during the Gulf War, a Patriot missile battery in Dhahran, Saudi Arabia, failed to intercept an incoming Scud missile. Twenty-eight American soldiers died. The cause: the system tracked time as a floating-point number, and after 100 hours of continuous operation, the accumulated rounding error was 0.34 seconds—enough that the Scud had moved half a kilometer from where the system expected. The Patriot looked in the wrong place and found nothing.

Binary floating-point cannot exactly represent 0.1. This has been true since the IEEE 754 standard was published in 1985. It will remain true forever. It is not a bug. It is mathematics. The AI doesn't know this. Neither do most developers.

**Mutable history and missing audit trails**

In 2001, executives at Enron Corporation directed employees to destroy documents. Emails were deleted. Files were shredded. Arthur Andersen, Enron's auditor, joined in—their Houston office shredded over a ton of documents in a single day. When investigators came looking, the records were gone.

This is why audit trails exist. This is why financial records are immutable. This is why "delete" is a forbidden operation on anything that matters. The Sarbanes-Oxley Act of 2002 exists because humans did what AI will do if you let it: destroy evidence that shouldn't be destroyed.

When your AI-generated invoicing system allows invoices to be deleted, it's not making a novel mistake. It's automating the behavior that sent executives to prison and destroyed one of the largest accounting firms in the world.

**The gap between builder and business**

In 1999, the Mars Climate Orbiter approached Mars for orbital insertion and was never heard from again. Post-incident analysis revealed that one team had provided thrust data in pound-force seconds; another team's software expected newton-seconds. Nobody had verified the units. The spacecraft entered the atmosphere at the wrong angle and disintegrated. Cost: $327.6 million.

Two teams. Both competent. Both correct in isolation. Neither understood what the other was doing. The constraint—"all thrust data must use SI units"—was never explicitly stated.

This is the gap. It has always existed. It exists between departments. Between contractors. Between the business owner who knows that invoices are legal documents and the developer who thinks they're just rows in a database.

AI inherits this gap. AI cannot bridge it. Only constraints can.

---

## Fluency Is Not Correctness

The most dangerous property of AI-generated code is that it reads well.

A human developer writing bad code often writes *obviously* bad code. The variable names are wrong. The structure is confused. The comments don't match the implementation. You can tell at a glance that something is off.

AI-generated code is fluent. The variable names are reasonable. The structure follows conventions. The comments accurately describe what the code does. Everything *looks* professional.

But the code can still be catastrophically wrong.

I reviewed an invoicing system for a small manufacturing company in 2023. The code was AI-generated—the founder had been proud of how quickly they'd shipped. Clean separation of concerns. Proper use of Django models. Well-documented API endpoints. It was a pleasure to read.

It also allowed invoices to be deleted. Not archived. Not voided. Deleted. Completely removed from the database.

They discovered this during a tax audit. The auditor asked to see invoice #1247. It didn't exist. Neither did #1248, #1251, or a dozen others. The bookkeeper had "cleaned up" old invoices that had been voided and replaced—except "cleaned up" meant "deleted forever," and tax authorities don't accept "we deleted the evidence" as an explanation.

The company spent four months reconstructing records from bank statements, email confirmations, and customer files. They paid penalties. They paid accountants. They paid lawyers. The "quick ship" saved maybe two weeks of development time. The cleanup cost six figures.

The AI didn't know that invoices are legal documents. The AI didn't know that tax authorities require you to maintain records—the IRS requires seven years, HMRC requires six, and most countries have similar rules. The AI didn't know that accountants have opinions about disappearing financial records.

The AI just generated code that looked like invoicing systems it had seen before. Some of those systems were demos. Some were tutorials. Some were badly designed production systems that nobody should copy.

The output was fluent. The output was wrong. And nobody caught it until an auditor asked for a document that no longer existed.

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

The instructions are the constraints. This book teaches you what constraints matter, and how to give good instructions.

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

## References

- IEEE Computer Society. *IEEE Standard for Binary Floating-Point Arithmetic* (IEEE 754-1985). Institute of Electrical and Electronics Engineers, 1985.
- Skeel, Robert. "Roundoff Error and the Patriot Missile." *SIAM News* 25, no. 4 (July 1992): 11.
- Quinn, Michael J. *Ethics for the Information Age*. 7th ed. Pearson, 2017. (Vancouver Stock Exchange index case study)
- U.S. Government Accountability Office. *Patriot Missile Defense: Software Problem Led to System Failure at Dhahran, Saudi Arabia*. GAO/IMTEC-92-26, February 1992.
- U.S. House of Representatives. *The Role of the Board of Directors in Enron's Collapse*. S. Rep. No. 107-70, 2002.
- Stephenson, Arthur G., et al. *Mars Climate Orbiter Mishap Investigation Board Phase I Report*. NASA, November 1999.
- Internal Revenue Service. *How Long Should I Keep Records?* IRS Publication 583, 2023.
- HM Revenue & Customs. *How Long to Keep Business Records*. GOV.UK guidance, 2023.
- Sarbanes-Oxley Act of 2002, Pub. L. No. 107-204, 116 Stat. 745.
- Vaswani, Ashish, et al. "Attention Is All You Need." *Advances in Neural Information Processing Systems* 30 (2017).

---

*Status: Draft*
