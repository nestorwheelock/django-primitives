# Chapter 3: You Will Refactor Later

> Technical debt is like a loan—except you don't get to choose the interest rate, and the bank can foreclose without warning.

---

**Core idea:** You will not refactor later. The shortcuts you take now become the architecture you're stuck with. AI makes this worse by generating plausible shortcuts faster than you can recognize them.

**Failure mode:** Shipping "temporary" solutions that become permanent. Believing that speed now doesn't cost quality later.

**What to stop doing:** Accepting shortcuts without explicit payback plans. Treating technical debt as free money.

---

## The Lie

"We'll clean this up later."

Every developer has said it. Every manager has accepted it. Every project plan has a line item for "refactoring" that gets pushed to the next sprint, then the next quarter, then never.

The lie is seductive because it's half true. You *could* refactor later. The code would allow it. Nothing in the compiler prevents you from rewriting that hacky workaround into a proper solution. The technical capability exists.

But you won't.

Not because you're lazy. Not because you don't care. Because by the time "later" arrives, the world has changed. The hacky workaround has other code depending on it. The shortcut has become load-bearing. The temporary solution has grown tentacles into parts of the system you didn't expect.

And now refactoring isn't a cleanup task. It's a rewrite. And rewrites have a way of killing companies.

---

## The Numbers Don't Lie

Technical debt isn't a metaphor. It's a measurable cost that researchers and industry analysts have quantified with uncomfortable precision.

The Consortium for Information & Software Quality estimated that technical debt costs U.S. companies **$2.41 trillion annually**. Not million. Trillion. That's roughly the GDP of France, lost every year to code that was supposed to be fixed "later."

According to Stripe's 2024 Developer Coefficient report, developers spend **42% of their working week** dealing with technical debt and bad code—approximately 17 hours per developer per week. Across the global developer population, this represents **$85 billion in lost productivity annually**.

McKinsey's research found that technical debt accounts for **up to 40% of the entire technology estate** at many companies, and **87% of CTOs cite technical debt as their top impediment to innovation**. They can't build new features because they're trapped maintaining the shortcuts from three years ago.

JetBrains' 2025 developer survey found that engineers spend **2 to 5 working days per month** on technical debt—up to 25% of their engineering budget, vanishing into maintenance instead of creation.

The compounding is brutal. A feature that would take two weeks in a clean codebase takes **4 to 6 weeks** when built on significant technical debt. Sprint commitments are missed **60% more often** in debt-heavy codebases. And once technical debt exceeds critical thresholds, productivity losses reach **40%**.

These aren't theoretical numbers. They're measured in real companies, by real researchers, tracking real developer time.

---

## The Shortcut Tax

The IBM Systems Science Institute documented what every experienced developer knows intuitively: bugs get more expensive the longer they live.

A defect caught during design costs one unit of effort to fix. The same defect caught during implementation costs **6 times more**. Caught during testing, **15 times more**. And a bug discovered in production—the same bug that could have been fixed for one unit of effort—costs **up to 100 times more** to resolve.

This is the shortcut tax. Every corner cut during initial development accrues interest. The interest compounds. And the payment comes due at the worst possible time: when the system is in production, when users depend on it, when the team that wrote the original code has moved on.

Software maintenance accounts for **50% to 80%** of total lifetime expenditure on any system. The code you write in the first three months will be maintained for years, sometimes decades. Every shortcut you take in those three months generates maintenance costs for the entire remaining lifetime of the system.

This is why "we'll fix it later" is not a plan. It's a loan application with terms you don't know, interest rates you can't predict, and a lender who will collect regardless of whether you're ready to pay.

---

## Rewrites: The Graveyard of Companies

When technical debt becomes unbearable, teams reach for the ultimate solution: the rewrite. Start fresh. Do it right this time. Learn from our mistakes.

It almost never works.

**Netscape (1997-2000)**

In 1997, Netscape Navigator was the dominant web browser. It was also, according to its developers, a mess—accumulated code from years of rapid development, hacks layered on hacks, features bolted onto features.

The solution seemed obvious: rewrite it from scratch. The Netscape 5.0 project would be clean, modern, maintainable. It would be everything Navigator wasn't.

Joel Spolsky, in his famous essay "Things You Should Never Do," called this decision "the single worst strategic mistake that any software company can make."

The rewrite took three years. There was never a Netscape 5.0—the version number was skipped entirely. The next major release, Netscape 6.0, shipped in November 2000, almost three years after the rewrite began.

Lou Montulli, one of the original Navigator developers, later reflected on the decision: "I laughed heartily as I got questions from one of my former employees about FTP code he was rewriting. It had taken 3 years of tuning to get code that could read the 60 different types of FTP servers, those 5000 lines of code may have looked ugly, but at least they worked."

Those three years were a death sentence. While Netscape sat on their hands, unable to add features or respond to market changes, Microsoft's Internet Explorer captured the browser market. By the time Netscape 6.0 shipped, the browser wars were over. Netscape was gone.

The old code looked ugly because it had learned things. It had encountered the sixty different types of FTP servers and figured out how to handle each one. The knowledge was in the code, not in any document. The rewrite threw away that knowledge and had to rediscover it, one painful bug report at a time.

**Knight Capital (August 1, 2012)**

Knight Capital Group was one of the largest traders in U.S. equities, with a 17% market share on NYSE and 16.9% on NASDAQ. Their algorithms processed millions of trades daily.

On August 1, 2012, Knight deployed a software update to seven of their eight servers. The eighth server didn't receive the update. That server still contained code for a feature called "Power Peg" that had been retired in 2003—nine years earlier. The old code was never removed, just commented out.

The deployment reused a flag that had previously activated Power Peg. When the market opened, the eighth server interpreted incoming orders as Power Peg requests and began executing trades wildly—buying high, selling low, at massive volumes.

In 45 minutes, Knight Capital lost **$440 million**. The company's stock dropped 75%. Within days, they required a $400 million rescue financing package that diluted existing shareholders to near-zero. The company that had been worth billions was sold for parts within a year.

The root cause wasn't the deployment error. The root cause was technical debt: dead code that should have been removed nine years earlier, still sitting in production, waiting for something to wake it up.

The SEC later charged Knight Capital with violating market access rules. Their finding: Knight "did not have adequate safeguards in place to limit the risks posed by its access to the markets."

Nine years of "we'll clean this up later." Forty-five minutes to bankruptcy.

**Healthcare.gov (October 2013)**

When Healthcare.gov launched on October 1, 2013, it was supposed to be the flagship of the Affordable Care Act—a modern, user-friendly marketplace where Americans could shop for health insurance.

On launch day, **six users** successfully completed their applications. Six. Out of 250,000 who tried.

The original budget was $93.7 million. By launch, it had grown to $500 million. By the time the site was functional, total costs exceeded **$2.1 billion**—a 22x cost overrun.

The U.S. Government Accountability Office found that CMS had received **18 written warnings** over two years that the project was mismanaged and off course. The warnings included inadequate planning, deviations from IT standards, and insufficient testing. Every warning was ignored. The launch date was fixed; the shortcuts were variable.

The site couldn't handle its traffic because capacity planning was never completed. The login system bottlenecked the entire site—and the same login system was used by technicians trying to troubleshoot, meaning the people who could fix the site couldn't get into it. Specifications arrived so late that contractors didn't start writing code until spring 2013, six months before launch.

This was the "we'll figure it out later" mentality applied at national scale, with national consequences.

---

## Legacy Code: The Bill Comes Due

The disasters above were visible, dramatic, newsworthy. But the slower, quieter disasters are more common and collectively more costly.

**Delta Airlines (August 2016)**

A power outage at Delta's Atlanta data center caused a small fire that was quickly extinguished. The outage lasted less than six hours. The airline grounded its entire fleet worldwide. More than 2,000 flights were cancelled over three days. The cost: over **$100 million** in lost revenue and reputation damage.

The root cause wasn't the power outage—those happen, and airlines have backup systems. The problem: 300 of Delta's 7,000 servers weren't connected to backup power. When those servers went down, the entire reservation and crew management system cascaded into failure.

One travel expert noted that airline systems are "legacy systems grafted onto other legacy systems"—decades of mergers and patches creating interconnections that nobody fully understands. Delta had merged with Northwest years earlier, and by some accounts the computer systems had still not been fully synchronized.

This is what technical debt looks like at scale: systems so complex and interdependent that a single point of failure—servers that weren't wired to backup power—brings down global operations. The fix would have been straightforward years earlier. By 2016, the complexity had become a trap.

**Equifax (September 2017)**

Equifax disclosed a data breach affecting 148 million Americans—names, Social Security numbers, birth dates, addresses, and driver's license numbers. It was one of the worst data breaches in history.

The vulnerability was in Apache Struts, an open-source framework. A patch had been available for months. It wasn't applied because Equifax's systems were so complex and interconnected that patching was considered risky. The GAO found that Equifax had recognized the security risks of their legacy infrastructure and had begun a modernization effort—but "this effort came too late to prevent the breach."

The GAO identified five key factors that led to the breach: failures in identification, detection, segmentation, data governance, and rate-limiting. Had any single factor been handled correctly, the breach might not have occurred. Instead, every safeguard failed.

The cost of cleanup exceeded **$1.4 billion**. The CEO, CIO, and CSO all resigned. Equifax paid $425 million to affected consumers and $100 million in civil fines.

The patch wasn't applied because the system was too fragile and poorly understood. The modernization effort was started too late. The complexity accumulated over years of "we'll fix it later" had become a barrier to basic security hygiene.

This is how "we'll refactor later" ends: not with a decision to finally fix it, but with an external event that forces the issue at the worst possible time and the highest possible cost.

---

## Why You Won't Refactor

The promise to refactor later fails for predictable, systemic reasons.

**The code grows dependencies**

Every day your shortcut runs in production, other code starts to depend on it. The hacky API response format gets parsed by three different clients. The weird date handling becomes expected behavior that users work around. The temporary database schema gets filled with millions of rows that would need migration.

Refactoring one month after shipping is a cleanup. Refactoring one year after shipping is a project. Refactoring three years after shipping is a crisis.

**The team changes**

The developer who understood why the shortcut was taken—and what a proper solution would look like—left six months ago. The new team inherited the code without the context. They don't know what was intentional design and what was expedient hacking. To them, the ugly code just looks like... code.

Research shows that developers spend **50% of their maintenance time** just trying to understand the code they're working on. When the original authors are gone and documentation is sparse, understanding becomes the dominant cost, and refactoring becomes nearly impossible.

**The priorities shift**

The product roadmap doesn't include "make the code prettier." It includes features, integrations, and bug fixes that customers are actually asking for. Technical debt is invisible to customers. New features are visible.

Every sprint planning session becomes a negotiation: "We could add the feature the sales team is screaming for, or we could refactor that module nobody understands." The feature wins. Every time.

**The fear sets in**

Legacy code is scary. It runs in production. Customers depend on it. It was written by people who aren't here to ask. It has no tests, or tests that don't actually test anything useful.

Refactoring scary code is high-risk, low-reward. If you succeed, nothing visible changes—the system does exactly what it did before, just with cleaner internals. If you fail, you break production and everybody knows it was your fault.

Rational developers avoid refactoring scary code. The code stays scary. The cycle continues.

---

## AI Makes It Worse

AI-generated code exacerbates every aspect of the technical debt problem.

**Speed without understanding**

AI can generate a working prototype in hours. That prototype ships. The team moves on. Nobody fully understands what was generated, because understanding wasn't part of the process—speed was.

When it's time to refactor, there's no institutional knowledge. The AI didn't attend the design meeting (there wasn't one). The AI didn't document its decisions (it doesn't have decisions, only outputs). The generated code is as mysterious as any legacy system, except it was created last month.

**Plausible shortcuts everywhere**

AI is excellent at generating code that works. It's also excellent at generating shortcuts that look professional. The shortcut isn't obviously a shortcut—it follows naming conventions, has reasonable structure, passes the tests (which the AI also wrote).

Recognizing AI-generated shortcuts requires understanding what the correct solution would look like. But the team didn't build the correct solution—the AI did it, and the AI took a shortcut. The shortcut is invisible until it becomes a problem.

**Volume overwhelms review**

AI generates code faster than humans can review it. If the AI produces ten features and nine are fine, finding the one with hidden technical debt is hard. If the AI produces a hundred features and ninety-five are fine, finding the five problematic ones is nearly impossible.

Every AI-generated shortcut that slips through review becomes a future maintenance burden. And AI generates shortcuts at machine speed.

---

## Constrained AI: The Antidote

Here's the twist: AI can also be the solution.

The same tool that generates shortcuts at machine speed can generate correct code at machine speed—if you constrain it properly. The same tool that produces mysterious legacy code can produce well-documented, well-tested, well-structured code—if you demand it.

The difference is discipline. The difference is constraints.

**AI can write documentation**

The documentation tax was one reason teams skipped correct implementations. Writing specifications, user stories, and test plans took as long as writing the code. Teams chose speed over documentation.

AI changes this equation. You describe what you want in plain language. The AI produces:

- User stories with acceptance criteria
- Technical specifications
- API documentation
- Code comments
- README files
- Architecture decision records

The documentation that used to take days takes minutes. The excuse for skipping it disappears.

**AI can write tests first**

Test-driven development (TDD) has been proven to reduce defects and improve design. But writing tests before implementation requires discipline—and time. Teams under deadline pressure skip tests, promising to add them later.

AI can write the tests first. You describe the behavior. The AI produces failing tests. Then you (or the AI) write the implementation to make them pass. The tests exist from the beginning, not as an afterthought.

"Write tests for an Invoice model where: invoices cannot be deleted (only voided), totals are computed from line items, and all monetary amounts use Decimal."

The AI produces tests. You run them. They fail (no implementation yet). Now you have a specification that executes.

**AI can enforce constraints in prompts**

The shortcuts AI takes come from its training data—tutorials, Stack Overflow answers, random GitHub repositories. The patterns in that data include good practices and bad practices, with no way for the AI to distinguish them.

But when you provide explicit constraints in your prompts, those constraints override the statistical patterns. The AI follows your rules instead of inventing its own.

"Build an invoicing system. Constraints: No DELETE operations on any model—use soft delete with deleted_at timestamp. All monetary values use Decimal, never float. Totals are always computed from line items, never stored. Every change is logged with actor and timestamp."

The AI follows these rules. Not because it understands why they matter, but because you told it to. The constraints are your knowledge, encoded as instructions.

**AI can review code against primitives**

Code review catches shortcuts—if reviewers know what to look for. AI can be that reviewer.

"Review this code against the following invariants: No floating-point currency. No mutable history. All models have soft delete. All timestamps distinguish business time from system time."

The AI scans the code and reports violations. The human decides what to do. The review happens at machine speed.

---

## The Discipline: Build It Right the First Time

The solution is not to avoid AI. The solution is to use AI within constraints that prevent technical debt from forming.

**Step 1: Document before coding**

Before generating any code, generate the documentation.

- What is this system supposed to do? (User stories)
- What must never happen? (Constraints and invariants)
- How will we verify it works? (Acceptance criteria)
- What data structures do we need? (Schema specification)

AI can draft all of this. You review and refine. The documentation becomes the specification the AI must satisfy.

**Step 2: Test before implementing**

Write tests (or have AI write tests) that verify the constraints before writing implementation code.

- Test that invoices cannot be deleted
- Test that totals equal the sum of line items
- Test that monetary values have correct precision
- Test that soft delete sets deleted_at instead of removing rows

Run the tests. They should fail—there's no implementation yet. Now you have executable specifications.

**Step 3: Constrain the generation**

When you ask AI to generate implementation code, include the constraints explicitly.

"Implement the Invoice model. It must pass all tests in test_invoice.py. Constraints: Soft delete only. Decimal for money. Computed totals. Audit logging on all changes."

The AI generates code. You run the tests. They pass—or they don't, and you iterate.

**Step 4: Review against physics**

Before shipping, review every generated file against the primitives.

- Identity: Are parties distinct from users? Are roles hierarchical? Are relationships temporal?
- Time: Is business time separate from system time? Can we query as-of any date?
- Money: Is everything Decimal? Do ledger entries balance?
- Agreements: Are terms immutable? Can we reconstruct what was agreed at any point in time?

AI can help with this review. But a human must verify. The human is the final judge of whether the constraints are satisfied.

---

## Hands-On: See the Difference

Let's make this concrete. Try these prompts yourself with any LLM.

**Exercise 1: Unconstrained Invoice System**

Ask the AI:

```
Build me a simple invoicing system in Django with Invoice and LineItem models.
```

Examine what you get. Look for:
- Can invoices be deleted? (Probably yes)
- What data type is used for amounts? (Probably FloatField or IntegerField)
- Are totals stored or computed? (Probably stored)
- Is there any audit logging? (Probably not)
- Is there soft delete? (Almost certainly not)

This is what "vibe coding" produces: functional code that accumulates technical debt from day one.

**Exercise 2: Constrained Invoice System**

Now ask the AI:

```
Build me an invoicing system in Django with Invoice and LineItem models.

Constraints:
1. No model may be physically deleted. Implement soft delete with a deleted_at DateTimeField. Override the delete() method to set deleted_at instead of removing the row. Add a manager that excludes soft-deleted records by default.

2. All monetary amounts must use DecimalField with max_digits=19 and decimal_places=4. Never use FloatField for money.

3. Invoice totals must be computed from line items using a property or method, not stored as a field. The total is always the sum of (quantity * unit_price) for all line items.

4. All changes must be logged. Add created_at (auto_now_add), updated_at (auto_now), and created_by/updated_by fields to track who made changes and when.

5. Invoices have a status field with choices: draft, sent, paid, voided. Once an invoice leaves 'draft' status, it cannot be modified—only voided.

Include tests that verify each constraint.
```

Examine what you get. It should:
- Have soft delete implemented correctly
- Use DecimalField for all monetary amounts
- Compute totals dynamically
- Include audit fields
- Enforce immutability after leaving draft status
- Include passing tests

This is constrained AI development. Same tool, radically different output.

**Exercise 3: Test-First Development**

Try a TDD approach:

```
Write pytest tests for an Invoice model with these requirements:
1. test_invoice_soft_delete: Calling delete() should set deleted_at, not remove the record
2. test_invoice_total_computed: Invoice total should equal sum of line item amounts
3. test_invoice_uses_decimal: All monetary fields should be DecimalField
4. test_invoice_immutable_after_sent: Saving an invoice with status != 'draft' should raise an error
5. test_invoice_audit_fields: Created_at, updated_at, created_by should be populated

Do not write the implementation yet. Just the tests.
```

Run the tests. They fail. Now ask:

```
Implement the Invoice and LineItem models to make all tests in the previous response pass.
```

This is TDD with AI. The tests came first. The implementation exists to satisfy them.

**What to notice**

Compare the code from Exercise 1 to Exercise 2. The constrained version:
- Has more lines of code (constraints add complexity)
- Is harder to break (soft delete prevents data loss)
- Is auditable (you know who changed what)
- Won't accumulate currency rounding errors
- Can't be modified in ways that violate invariants

The unconstrained version is simpler—and will require a rewrite when you discover the problems. The constrained version is more complex upfront—and works correctly forever.

This is the difference between technical debt and technical investment.

---

## The Primitives Are the Payoff

This book exists because of everything in this chapter.

The primitives—identity, time, money, agreements—are not just convenient patterns. They're pre-paid technical debt. They're the refactoring you do *before* the code exists.

When you use a proven money primitive that stores amounts as Decimal and handles currency correctly, you're not taking a shortcut. You're using code that has already been refactored, tested, and proven across many projects.

When you use a proven time primitive that distinguishes business time from system time, you're not deferring a design decision. You're inheriting a decision that was made correctly, documented properly, and verified extensively.

The primitives are expensive to build once. They're essentially free to use forever.

Every project that rolls its own identity system, its own time handling, its own currency logic—they're all taking the same shortcuts, making the same mistakes, accumulating the same technical debt. And they're all making the same promise: we'll refactor later.

They won't. You won't. Nobody does.

Build it correctly the first time. Use the primitives that already exist. The refactoring you skip is the refactoring you don't need, because the code was correct from the start.

---

## Why This Matters Later

This chapter established that technical debt is not a metaphor—it's a measured, quantified cost that destroys companies, tanks stock prices, and ends careers.

The promise to "refactor later" fails because code grows dependencies, teams change, priorities shift, and fear sets in. AI accelerates every failure mode by generating plausible shortcuts faster than teams can recognize them.

The next section of this book introduces the primitives—the building blocks that have already been refactored, tested, and proven. They're the antidote to technical debt: solutions so boring, so standard, so well-understood that they don't need to be rewritten.

You won't refactor later. So don't build code that needs refactoring. Build on primitives instead.

---

## References

- Consortium for Information & Software Quality. *The Cost of Poor Software Quality in the US: A 2022 Report*. CISQ, 2022.
- Stripe. *The Developer Coefficient*. Stripe Developer Report, 2024.
- McKinsey & Company. *Tech Debt: Reclaiming Tech Equity*. McKinsey Technology Report, 2024.
- JetBrains. *The State of Developer Ecosystem 2025*. JetBrains Research, 2025.
- IBM Systems Science Institute. *Relative Cost of Fixing Defects*. IBM Research, 2008.
- Spolsky, Joel. "Things You Should Never Do, Part I." Joel on Software, April 6, 2000. https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/
- U.S. Securities and Exchange Commission. "SEC Charges Knight Capital With Violations of Market Access Rule." Press Release 2013-222, October 16, 2013. https://www.sec.gov/newsroom/press-releases/2013-222
- Dolfing, Henrico. "Case Study 4: The $440 Million Software Error at Knight Capital." Henrico Dolfing, 2019. https://www.henricodolfing.com/2019/06/project-failure-case-study-knight-capital.html
- U.S. Government Accountability Office. *Healthcare.gov: Ineffective Planning and Oversight Practices Underscore the Need for Improved Contract Management*. GAO-14-694, July 2014.
- U.S. Government Accountability Office. *Actions Taken by Equifax and Federal Agencies in Response to the 2017 Breach*. GAO-18-559, August 2018.

---

*Status: Draft*
