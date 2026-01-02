# Chapter 20: Prompt Contracts

## The $440 Million Misunderstanding

In 2012, Knight Capital Group deployed new trading software that contained a bug. In 45 minutes, the software executed millions of erroneous trades. By the time anyone understood what was happening, the firm had lost $440 million.

The bug was not complex. During deployment, technicians failed to copy a software update to one of eight servers. The old code, dormant for years, suddenly activated and began buying high and selling low at enormous volumes.

The postmortem revealed something instructive: the system had no clear contract about what the trading algorithm was allowed to do. It had instructions about what to do, but no constraints about what it must never do.

Knight Capital filed for bankruptcy protection four days later.

---

## The Difference Between Instructions and Contracts

Instructions tell a system what to do:
- "Execute trades based on market signals"
- "Build me an invoicing system"
- "Create a model for tracking orders"

Contracts tell a system what it must and must not do, regardless of instructions:
- "Never execute more than $X in trades per minute"
- "Invoices are immutable after posting"
- "Orders must always reference a ledger transaction"

Instructions are generative. They produce output.

Contracts are restrictive. They prevent disaster.

When you work with AI coding assistants, you need both. Most people only provide instructions.

---

## The Anatomy of a Prompt Contract

A prompt contract has four sections. Each serves a different purpose.

### Must Do (Positive Constraints)

These are non-negotiable requirements. They are not suggestions or best practices. They are laws.

```markdown
## Must Do

- Use UUID primary keys for all models
- Implement soft delete (deleted_at field) for domain objects
- Add time semantics (effective_at, recorded_at) to all events
- Use DecimalField for all monetary amounts
- Inherit domain models from BaseModel
- Wrap mutations in @transaction.atomic
```

A Must Do constraint is something you would reject code for violating. If you would accept code that uses auto-increment IDs "just this once," then UUID primary keys is not a Must Do. It's a preference.

Be honest about what you will actually enforce.

### Must Not Do (Negative Constraints)

These are forbidden operations. They are more powerful than Must Do constraints because they explicitly close loopholes.

```markdown
## Must Not Do

- Never use auto-increment primary keys
- Never store currency as float
- Never mutate historical records (post reversals instead)
- Never delete audit logs
- Never hard-delete parties
- Never import from higher architectural layers
- Never use naive datetimes
```

Negative constraints prevent the creative workarounds that AI systems are particularly good at finding. If you say "use Decimal for money," an AI might still use float for "intermediate calculations." If you say "never use float for anything related to currency," the loophole closes.

### Invariants (System Properties)

Invariants are properties that must always be true, regardless of what operations occur.

```markdown
## Invariants

- Ledger transactions always balance (debits = credits)
- Agreements are append-only (no edits, only versions)
- Parties are never physically deleted from the database
- Every encounter has exactly one current state
- Audit log entries cannot be modified after creation
- Sum of entries in any transaction equals zero
```

Invariants differ from constraints because they describe the entire system, not individual operations. A constraint says "don't do X." An invariant says "X must always be true, no matter what."

### Acceptable Outputs (Exit Criteria)

These define what a correct implementation looks like. They prevent the AI from claiming something is "done" when it doesn't meet your standards.

```markdown
## Acceptable Outputs

- All models inherit from UUIDModel or appropriate base
- All service functions use @transaction.atomic for mutations
- All domain models have soft delete capability
- Test coverage exceeds 95%
- All tests pass
- Migrations are included and reversible
- README includes usage examples
```

Acceptable Outputs create a checklist. If any item is not true, the work is not complete.

---

## Why Contracts Work Better Than Instructions

Consider two ways to ask for an invoicing system:

### Instructions Only

```
Build me an invoicing system with:
- Customers and vendors
- Line items
- Tax calculation
- PDF generation
- Email sending
```

This produces an invoicing system. It will probably work. It will also probably have:
- Auto-increment invoice numbers (breaks on replication)
- Mutable invoices (audit nightmare)
- Float-based amounts (rounding errors)
- No audit trail (compliance failure)
- Prices pulled live from products (historical prices lost)

The AI did exactly what you asked. You asked for features. You got features.

### Contract + Instructions

```
Build me an invoicing system.

## Must Do
- Invoice numbers use sequential IDs from django-sequence
- Line items snapshot price at creation time
- All amounts use DecimalField with max_digits=19, decimal_places=4
- Invoices reference ledger transactions

## Must Not Do
- Never allow invoice modification after posting
- Never use float for amounts
- Never delete invoices (soft delete only)
- Never recalculate totals from live product prices

## Invariants
- Posted invoices are immutable
- Invoice total equals sum of line items plus tax
- Every posted invoice has a ledger transaction

## Acceptable Outputs
- All tests pass
- Invoice + line item models with proper constraints
- Post operation creates ledger entries
- Void operation creates reversal entries
```

This produces an invoicing system that survives audits.

---

## Contract Layers: Where Rules Live

Not all contracts belong in the same place. The instruction stack from Chapter 19 determines where each rule lives.

### Global CLAUDE.md: Universal Rules

Rules that apply to every project, every file, every task:

```markdown
# Development Standards (Global)

## Code Quality
- Test coverage > 95%
- No TODO comments in production code
- No print statements in production code

## Git
- Conventional commits only
- Never force push to main
- Never skip pre-commit hooks

## Security
- No secrets in code
- No SQL string concatenation
- No eval() or exec()
```

These are operating system rules. They never change.

### Project CLAUDE.md: Project Rules

Rules that apply to this codebase but might differ in other projects:

```markdown
# Django Primitives Rules (Project)

## Architecture
- Never import from higher layers
- Domain logic lives in services, not models
- Views are thin (call services)

## Patterns
- UUID primary keys for all models
- Soft delete for domain entities
- Time semantics for events
- GenericForeignKey for polymorphic targets

## Dependencies
- BaseModels is foundation (import from)
- Parties provides identity (import from)
- Catalog depends on Ledger concepts
```

These are project configuration. They might change between major versions.

### Per-Package Prompts: Specific Contracts

Rules for rebuilding a specific package:

```markdown
# django-ledger Contract

## Must Do
- Transaction has multiple entries
- Entry has account, amount, entry_type
- Entries balance (sum of amounts = 0)
- Posted transactions are immutable

## Must Not Do
- Never allow negative transaction IDs
- Never store balance on Account (calculate it)
- Never allow entry modification after transaction posts
- Never delete transactions

## Invariants
- Every transaction balances
- Account balance = sum of entries in that account
- Posted transactions cannot be modified
```

These are application specifications. They are completely rewritten when the package is rebuilt.

---

## Enforcement: How Contracts Become Code

A contract that isn't enforced is a suggestion. Enforcement happens at four levels.

### Level 1: Prompt Enforcement

The AI reads the contract and follows it. This is the weakest enforcement because it relies on the AI understanding and remembering.

To strengthen prompt enforcement:
- Put critical rules in the global CLAUDE.md (always loaded)
- Repeat critical constraints at the start of each task
- Use explicit negative constraints ("never") not just positive ("prefer")

### Level 2: Code Enforcement

The generated code enforces the contract through Django model constraints:

```python
class Invoice(BaseModel):
    """An invoice that becomes immutable once posted."""

    status = models.CharField(max_length=20, choices=InvoiceStatus.choices)
    posted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            original = Invoice.objects.get(pk=self.pk)
            if original.status == 'posted':
                raise ImmutableInvoiceError(
                    "Posted invoices cannot be modified. Post a reversal instead."
                )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == 'posted':
            raise ImmutableInvoiceError(
                "Posted invoices cannot be deleted. Post a void instead."
            )
        # Soft delete for non-posted invoices
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])
```

Code enforcement is stronger than prompt enforcement because it fails at runtime, even if the AI "forgets" the rule in a later session.

### Level 3: Database Enforcement

The database enforces the contract through constraints and triggers:

```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=~models.Q(amount=0),
            name='ledger_entry_non_zero_amount'
        ),
        models.CheckConstraint(
            check=models.Q(entry_type__in=['debit', 'credit']),
            name='ledger_entry_valid_type'
        ),
    ]
```

For critical financial invariants, PostgreSQL triggers provide the strongest enforcement:

```sql
CREATE OR REPLACE FUNCTION check_transaction_balance()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT SUM(amount) FROM ledger_entry
        WHERE transaction_id = NEW.transaction_id) != 0 THEN
        RAISE EXCEPTION 'Transaction does not balance';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

Database enforcement survives even direct SQL manipulation.

### Level 4: Test Enforcement

Tests verify that contracts are upheld. Every forbidden operation should have a test that proves it fails:

```python
def test_posted_invoice_immutable():
    """Posted invoices cannot be modified."""
    invoice = Invoice.objects.create(
        customer=customer,
        status='posted',
        posted_at=timezone.now()
    )

    invoice.total = Decimal('999.99')
    with pytest.raises(ImmutableInvoiceError):
        invoice.save()

def test_posted_invoice_not_deletable():
    """Posted invoices cannot be deleted."""
    invoice = Invoice.objects.create(
        customer=customer,
        status='posted',
        posted_at=timezone.now()
    )

    with pytest.raises(ImmutableInvoiceError):
        invoice.delete()

def test_transaction_must_balance():
    """Transactions with unbalanced entries fail."""
    with pytest.raises(ValidationError):
        Transaction.objects.create(
            entries=[
                Entry(account=cash, amount=Decimal('100'), entry_type='debit'),
                Entry(account=revenue, amount=Decimal('99'), entry_type='credit'),
            ]
        )
```

Test enforcement is the final safety net. When everything else fails, tests catch violations before deployment.

---

## The Contract Template

Use this template for every primitive package:

```markdown
# Contract: [Package Name]

## Purpose
[One sentence: what problem this package solves]

## Dependencies
[Packages this depends on, both runtime and conceptual]

## Must Do
- [ ] [Positive constraint 1]
- [ ] [Positive constraint 2]
- [ ] [Positive constraint 3]

## Must Not Do
- [ ] Never [forbidden operation 1]
- [ ] Never [forbidden operation 2]
- [ ] Never [forbidden operation 3]

## Invariants
- [ ] [System property that must always be true 1]
- [ ] [System property that must always be true 2]

## Models Specification
[Exact fields, types, constraints for each model]

## Service Functions
[Exact function signatures and behaviors]

## Test Cases
[Numbered list of tests that must pass]

## Acceptable Outputs
- [ ] All tests pass
- [ ] Coverage > 95%
- [ ] Migrations included
- [ ] README with examples
```

---

## Hands-On Exercise: Write a Contract

Take a feature you're planning to build. Before writing any code, write its contract.

**Step 1: Define Must Do**

What are the non-negotiable requirements? If the implementation doesn't have these, it's wrong.

**Step 2: Define Must Not Do**

What would make this implementation dangerous? What shortcuts could an AI take that would cause problems later?

**Step 3: Define Invariants**

What properties must always be true? If an operation violates these, the system is corrupt.

**Step 4: Define Acceptable Outputs**

How will you know it's done? What are the concrete deliverables?

**Step 5: Test Your Contract**

Give your contract to an AI without additional instructions. Does the output meet your standards? If not, your contract has gaps.

---

## What AI Gets Wrong About Contracts

AI systems are excellent at following instructions. They are less reliable at maintaining constraints across long sessions or multiple files.

### Contract Drift

In a long session, the AI may "forget" earlier constraints and revert to defaults:
- Session starts with "never use auto-increment"
- Three hours later, AI generates `id = models.AutoField()`
- Why? Context window limitations, or the constraint was stated once and never reinforced

**Solution:** Put critical constraints in always-loaded files (CLAUDE.md), and repeat them when starting related tasks.

### Creative Workarounds

AI finds unexpected solutions that technically satisfy constraints but violate their intent:
- Constraint: "Never delete records"
- AI solution: `UPDATE table SET all_fields = NULL WHERE id = X`
- Technically not a DELETE statement. Data is gone.

**Solution:** Use explicit negative constraints. "Never delete records AND never null out fields to simulate deletion AND never move records to archive tables."

### Confident Violations

AI may confidently explain why a constraint doesn't apply in this case:
- Constraint: "Never use float for money"
- AI: "For this intermediate calculation, float is fine because we round at the end"
- This is wrong, but sounds reasonable

**Solution:** Make constraints absolute. "Never use float for money, in any calculation, at any step, for any reason."

---

## Why This Matters Later

Contract thinking changes how you approach AI-assisted development.

Without contracts, you write prompts and hope for the best. You catch bugs in review, in testing, in production. Each bug teaches you something you should have specified.

With contracts, you specify constraints upfront. Bugs become visible before code is written. The AI has clear boundaries. Your review process becomes "does this match the contract?" instead of "does this seem reasonable?"

In the next chapter, we'll see how contracts combine with schema-first generation to create truly reproducible AI-generated packages.

---

## Summary

| Concept | Purpose |
|---------|---------|
| Must Do | Non-negotiable requirements |
| Must Not Do | Explicitly forbidden operations |
| Invariants | System properties that must always hold |
| Acceptable Outputs | Exit criteria for completion |
| Prompt enforcement | AI follows rules from context |
| Code enforcement | Runtime exceptions on violations |
| Database enforcement | Constraints that survive direct SQL |
| Test enforcement | Automated verification of contracts |

The goal is not to constrain AI creativity. The goal is to channel that creativity within safe boundaries.

Knight Capital had no constraints. They had features. They shipped fast. Then they shipped $440 million out the door in 45 minutes.

Constraints are not the enemy of productivity. They are the precondition for safety.

---

## Sources

- SEC. (2013). *In the Matter of Knight Capital Americas LLC: Administrative Proceeding File No. 3-15570*. https://www.sec.gov/litigation/admin/2013/34-70694.pdf
- Patterson, S. (2012). "Knight Capital Says Trading Glitch Cost It $440 Million." *The Wall Street Journal*.
