# Chapter 5: Time

> "What did the President know, and when did he know it?"
>
> — Senator Howard Baker, Watergate Hearings, 1973

---

Every system that records facts about the world faces the same problem: the world doesn't wait for your database.

A sale happens on Friday, but the data entry clerk is out sick until Monday. A customer cancels an order at 11:47 PM, but the batch process that updates inventory runs at midnight. A doctor performs a procedure on March 3rd, but the hospital's billing system doesn't receive the claim until March 15th. An employee's raise is approved retroactive to January 1st, but it's recorded on February 28th.

In each case, there are two different points in time that matter. When did it happen? When did we learn about it?

Most systems conflate these. They have a single `created_at` timestamp that records when the row was inserted. This works until it doesn't—until someone asks a question the system can't answer.

## The Watergate Question

Senator Howard Baker's question during the 1973 Watergate hearings wasn't just about politics. It was a precise formulation of the accountability problem: separating what someone knew from when they knew it.

This question appears everywhere in business:

- **Auditors ask**: "What was your reported revenue on December 31st, before the correction on January 15th?"
- **Regulators ask**: "When did you become aware of the product defect?"
- **Lawyers ask**: "What was the account balance at the time of the disputed transaction?"
- **Executives ask**: "What did our forecast show on the day we made the acquisition decision?"

A system with only `created_at` cannot answer these questions. It only knows the current state. The history of what you knew, when you knew it, is gone.

## The Two-Dimensional Nature of Time

Computer scientist Richard Snodgrass spent decades formalizing this problem. His work, culminating in the 2011 SQL standard's temporal extensions, established that business data inherently lives in two time dimensions:

**Valid time** (also called business time): When the fact is true in the real world. A contract is valid from January 1st to December 31st. An employee's salary is effective starting their hire date. A product's price is valid until the next price change.

**Transaction time** (also called system time): When the fact was recorded in the database. The contract might be entered on January 3rd. The salary record might be created on the employee's first day. The price might be updated three days before it takes effect.

Snodgrass called systems that track both dimensions *bitemporal*. Most systems aren't. They track only one dimension—usually transaction time, hidden in a `created_at` field that few people query.

## The Cost of Getting It Wrong

The consequences of single-time systems range from inconvenient to catastrophic.

### The Options Backdating Scandal

Between 2005 and 2007, more than 130 publicly traded companies were investigated for backdating stock option grants. The scheme was simple: executives would grant themselves options dated to a day when the stock price was low, making the options more valuable.

The Wall Street Journal's investigation, which won a Pulitzer Prize, used statistical analysis to identify suspicious patterns. Apple, Broadcom, UnitedHealth, and dozens of other companies were implicated. The SEC extracted over $700 million in settlements. Several executives faced criminal charges. Brocade's CEO was sentenced to 21 months in prison.

The technical failure underlying the scandal was a system that allowed `effective_at` dates to be set without any record of when the grant was actually entered into the system. Companies claimed options were granted months earlier, and their systems couldn't prove otherwise.

A bitemporal system would have recorded both dates: when the grant took effect (the claimed date) and when it was entered (the actual date). The gap between them would have been immediately visible—not just to investigators years later, but to auditors in real time.

### The Enron Problem

Enron's accounting fraud relied heavily on timing manipulation. The company would recognize revenue in the current quarter for deals that hadn't actually closed, then adjust the numbers later. When auditors asked what the company knew at quarter-end, the answer was murky because the system didn't cleanly separate business time from system time.

The Sarbanes-Oxley Act of 2002, passed in response to Enron and similar scandals, requires public companies to maintain accurate financial records that can be reconstructed for any given point in time. Section 802 makes it a crime to alter, destroy, or conceal records with intent to obstruct an investigation.

Compliance isn't optional. The law requires that you can answer the Watergate question about your financial data.

### The Patriot Missile Failure

On February 25, 1991, an Iraqi Scud missile struck an American Army barracks in Dhahran, Saudi Arabia, killing 28 soldiers. The Patriot missile battery that should have intercepted it failed to track the incoming missile.

The Government Accountability Office investigation found a timing error in the system's software. The Patriot system tracked time in tenths of seconds using a 24-bit integer. This representation introduced a small floating-point error—about 0.000000095 seconds per tenth of a second. After 100 hours of continuous operation, the error had accumulated to 0.34 seconds.

A Scud missile travels at approximately 1,676 meters per second. In 0.34 seconds, it moves over 500 meters—more than enough to disappear from the Patriot's tracking window.

This wasn't a bitemporal problem per se, but it illustrates how systems that treat time as a single, simple dimension can fail catastrophically. Time is more complex than a single counter. Systems that acknowledge this complexity are more robust than those that don't.

## The Two Timestamps

The solution is simpler than the problem might suggest. Every fact needs two timestamps:

**`effective_at`**: When did this become true in the business world? This is the date that matters for business logic. When did the sale happen? When did the employee's raise take effect? When did the patient receive the treatment?

**`recorded_at`**: When did the system learn about this? This is immutable—it records when the row was actually inserted, regardless of when the underlying event occurred.

```python
class TimeSemanticsMixin(models.Model):
    effective_at = DateTimeField(default=timezone.now)
    recorded_at = DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
```

That's it. Two fields. But the implications are profound.

### Backdating Is Not Fraud

When `effective_at` and `recorded_at` are separate, backdating becomes a normal, transparent operation. The data entry clerk who enters Friday's sale on Monday simply sets `effective_at` to Friday. The `recorded_at` automatically records that the entry happened on Monday.

There's no deception, no hidden manipulation. Anyone who queries the data can see both dates. Auditors can ask: "Show me everything that was effective in Q4 but recorded in Q1." The answer is readily available.

Contrast this with a single-timestamp system where someone changes the `created_at` date to Friday. Now the audit trail is compromised. The system lies about when it learned the information. This is the pattern that enabled the options backdating scandal.

### "As Of" Queries

With both timestamps, you can answer questions that single-timestamp systems cannot:

**"What was the state of this account on December 31st?"**

This is the valid-time query. You want all facts where `effective_at <= December 31st`, regardless of when they were recorded.

**"What did we know about this account on December 31st?"**

This is the transaction-time query. You want all facts where `recorded_at <= December 31st`, regardless of when they took effect.

**"What did we believe the account state was on December 31st, as of our January 15th closing?"**

This is the bitemporal query. You want all facts where `effective_at <= December 31st` AND `recorded_at <= January 15th`. This answers questions like: "What did our year-end close show before the corrections we made in February?"

## Effective Dating for Ranges

Some facts aren't points in time—they're valid for a range. A subscription is active from March 1st to March 31st. An insurance policy covers you from today until next year. An employee's salary is what it is until the next raise.

For these, you need validity periods:

```python
class EffectiveDatedMixin(TimeSemanticsMixin):
    valid_from = DateTimeField()
    valid_to = DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
```

Notice that this inherits from `TimeSemanticsMixin`. You still have `effective_at` and `recorded_at` for the fact of the validity period itself. But now you also have `valid_from` and `valid_to` defining when the fact applies.

The `valid_to` field is nullable. A `NULL` value means "until further notice"—the fact remains valid indefinitely until something explicitly supersedes it.

### The Close-Then-Open Pattern

When updating an effective-dated record, never modify the existing record. Instead:

1. Set the old record's `valid_to` to the transition point
2. Create a new record with `valid_from` at the transition point

This preserves history. You can always reconstruct what was true at any point in time because you never destroyed the previous state.

```python
# Employee gets a raise effective April 1st
# Current salary record: valid_from=Jan 1, valid_to=None

# Step 1: Close the current record
old_salary.valid_to = april_1st
old_salary.save()

# Step 2: Create the new record
new_salary = Salary.objects.create(
    employee=employee,
    amount=new_amount,
    valid_from=april_1st,
    valid_to=None
)
```

After this, you have two records: one valid from January 1st to April 1st, another valid from April 1st onward. Query "as of March 15th" and you get the old salary. Query "as of April 15th" and you get the new one. Query "current" and you get the one where `valid_from <= now` and `valid_to IS NULL OR valid_to > now`.

## The Regulatory Reality

Time semantics aren't just about clean architecture. They're legally required in many industries.

### Financial Services

The Financial Industry Regulatory Authority (FINRA) requires broker-dealers to maintain records "in a manner that permits the records to be recreated by date." Rule 4511 specifies that records must be preserved in non-erasable, non-rewritable format for specified retention periods.

The Commodity Futures Trading Commission (CFTC) Rule 1.31 requires that records be "readily accessible" and capable of reproducing the information for any historical date. Firms must be able to answer: "What was the position on this date?"

### Healthcare

The Health Insurance Portability and Accountability Act (HIPAA) requires covered entities to maintain an audit trail of who accessed what protected health information and when. But it also requires that medical records reflect the actual date of service, not just when the record was created.

A doctor's note entered on March 15th about an examination on March 10th must clearly indicate both dates. The treatment date affects medical decisions and billing; the entry date affects the audit trail.

### Tax and Accounting

The IRS requires that businesses maintain records sufficient to substantiate income and deductions. For accrual-basis taxpayers, this means being able to determine when income was earned or expenses were incurred, regardless of when they were recorded.

Generally Accepted Accounting Principles (GAAP) require that transactions be recorded in the period in which they occurred. An adjusting entry made in February for a December transaction must clearly indicate that it affects December's financials.

## The Decision Record

Some events aren't just facts—they're decisions. A loan is approved. An insurance claim is paid. A discount is authorized. A refund is issued.

Decisions need more than timestamps. They need evidence of what was known at the time the decision was made. This protects against both fraud and honest mistakes.

```python
class Decision(TimeSemanticsMixin):
    # Who made the decision
    actor_user = ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)
    on_behalf_of_user = ForeignKey(AUTH_USER_MODEL, null=True, blank=True)

    # What the decision was about
    target_type = ForeignKey(ContentType, on_delete=PROTECT)
    target_id = CharField(max_length=255)

    # What was decided
    action = CharField(max_length=50)

    # Evidence: snapshot of state at decision time
    snapshot = JSONField()

    # Result of the decision
    outcome = JSONField(default=dict)

    # When the decision became irreversible
    finalized_at = DateTimeField(null=True, blank=True)
```

The `snapshot` field is critical. It captures the state of the world at the moment the decision was made. If the underlying data changes later—the customer's address is updated, the product's price changes, the account balance is corrected—the snapshot preserves what was known at decision time.

This is audit protection. When a regulator asks "Why did you approve this loan?", you can show exactly what information the approver saw. Changes made after the decision are irrelevant to whether the decision was justified at the time it was made.

## Idempotency and Time

Network failures and retries create temporal complexity. A customer clicks "Submit" on a payment form. The request reaches your server, the payment is processed, but the response is lost. The customer clicks "Submit" again. Without protection, they pay twice.

The solution is idempotency—ensuring that repeated requests with the same key produce the same effect as a single request.

```python
class IdempotencyKey(models.Model):
    scope = CharField(max_length=100)
    key = CharField(max_length=255)
    state = CharField(choices=State.choices)
    created_at = DateTimeField(auto_now_add=True)
    locked_at = DateTimeField(null=True)
    response_snapshot = JSONField(null=True)

    class Meta:
        unique_together = ['scope', 'key']
```

The first request creates an `IdempotencyKey` in `PROCESSING` state. It executes the operation and stores the result in `response_snapshot`. Any subsequent request with the same key returns the cached response without re-executing the operation.

This is another form of time semantics: tracking when an operation first occurred so that later duplicates can be detected and handled correctly.

## Building It Correctly

The pattern for time-aware systems is straightforward:

1. **Use TimeSemanticsMixin for all business facts.** Every table that records something that happened should have `effective_at` and `recorded_at`.

2. **Use EffectiveDatedMixin for things with validity periods.** Subscriptions, agreements, role assignments, prices—anything that's valid for a range of time.

3. **Never modify history.** When something changes, close the old record and open a new one. Never update `effective_at` or `valid_from` on existing records.

4. **Make `recorded_at` immutable.** It's `auto_now_add=True` and never updated. This is your audit trail.

5. **Capture snapshots for decisions.** When a decision is made, store the evidence that justified it. Don't rely on being able to reconstruct it later.

6. **Use "as of" queries by default.** Your codebase should make it easy to ask "what was true at time X" and awkward to ask "what is true now" without specifying what "now" means.

### The Constraint for AI

When using AI to generate code, the constraint is explicit:

```
Every model that records business facts must inherit from TimeSemanticsMixin.
Every query that retrieves business data must specify "as of" unless explicitly fetching current state.
recorded_at must never be modified after initial insert.
Historical records must never be updated or deleted.
```

An AI given these constraints will generate bitemporal code by default. An AI without them will generate systems that can't answer the Watergate question.

## What AI Gets Wrong

Without explicit constraints, AI-generated code typically:

1. **Uses a single timestamp** called `created_at` that conflates business time and system time

2. **Updates records in place** rather than closing and opening new versions

3. **Deletes old data** during "cleanup" operations, destroying audit trails

4. **Ignores backdating** by rejecting dates in the past rather than recording them with appropriate `recorded_at`

5. **Queries "current state"** without considering that "current" is a point in time, not an absolute truth

The fix is the same as always: explicit constraints. Tell the AI what time semantics mean in your domain. Tell it that every fact needs two timestamps. Tell it that history is immutable. The AI will follow these rules consistently—more consistently than human developers who might cut corners under deadline pressure.

## Why This Matters Later

Time semantics are the foundation for:

- **The Ledger**: Every accounting entry has effective dates and recorded dates. You must be able to reconstruct what the books showed at any point in time.

- **Agreements**: Contracts have effective periods. Version changes create new records with new validity dates. You must be able to show what terms applied when.

- **Documents**: Attachments and evidence are immutable once created. Their relationship to business events is tracked temporally.

- **Workflows**: State machines track transitions over time. You must be able to reconstruct the sequence of events and when each transition occurred.

Get time wrong, and every system that depends on temporal queries will be compromised. Get it right, and you can answer any question about what happened, when it happened, and when you learned about it.

---

## How to Rebuild This Primitive

Time semantics are handled by `django-decisioning` which provides bitemporal tracking:

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-decisioning | `docs/prompts/django-decisioning.md` | ~50 tests |

### Using the Prompt

```bash
cat docs/prompts/django-decisioning.md | claude

# Request: "Start with the temporal mixin that provides
# effective_at and recorded_at fields, then add the as_of() queryset method."
```

### Key Constraints

- **Two timestamps always**: `effective_at` (when it happened) and `recorded_at` (when logged)
- **Immutable recorded_at**: Set once on creation, never changes
- **as_of() method**: Query state at any point in time
- **current() method**: Filter to currently-effective records

If Claude stores only a single timestamp or allows `recorded_at` to be modified, that's a constraint violation.

---

## Sources and References

1. **Snodgrass, R.T.** (1999). *Developing Time-Oriented Database Applications in SQL*. Morgan Kaufmann.

2. **SQL:2011 Standard** - ISO/IEC 9075:2011, specifically Part 2 (Foundation) which introduced temporal table support.

3. **Watergate Hearings** - Baker's famous question was posed on June 28, 1973. *The New York Times*, June 29, 1973.

4. **Options Backdating** - "The Perfect Payday," *Wall Street Journal*, March 18, 2006. The investigation that launched the scandal, later winning the 2007 Pulitzer Prize for Public Service.

5. **SEC Actions on Options Backdating** - SEC Litigation Releases, 2006-2007. Apple settled for $14 million (2007), Brocade executives were criminally charged.

6. **Patriot Missile Failure** - "Patriot Missile Defense: Software Problem Led to System Failure at Dhahran, Saudi Arabia," GAO Report GAO/IMTEC-92-26, February 1992.

7. **Sarbanes-Oxley Act** - Public Law 107-204, 116 Stat. 745, enacted July 30, 2002. Section 802 addresses record retention and penalties.

8. **FINRA Rule 4511** - Books and Records, requiring maintenance of records in retrievable format for specified retention periods.

9. **CFTC Rule 1.31** - Regulatory recordkeeping and reporting requirements for commodity futures trading.

10. **HIPAA Security Rule** - 45 CFR Part 164, Subpart C, requiring audit controls for electronic protected health information.

---

*Status: Complete*
