# Chapter 15: Forbidden Operations

## The $125 Million Typo

On September 21, 1999, NASA's Mars Climate Orbiter approached Mars after a 286-day journey. As it prepared for orbital insertion, the spacecraft fired its thrusters. But instead of entering orbit, it descended too low into the atmosphere and disintegrated.

The investigation revealed the cause: a software module provided thrust calculations in pound-force seconds. The navigation software expected newton-seconds. Nobody caught the unit mismatch. The spacecraft, worth $125 million, was lost because one team used Imperial units and another used metric.

The error was not in the math. The math worked perfectly—in two different unit systems. The error was that nothing in the system forbade mixing unit systems. There was no constraint that said "all thrust values must be in SI units."

The fix was not "be more careful." The fix was to make mixing units forbidden at the system level.

This chapter is about forbidden operations: the rules that prevent disaster by making certain actions impossible.

---

## The Power of "Never"

Instructions tell AI what to do. Contracts specify boundaries. But forbidden operations are different. They are absolute prohibitions that override everything else.

**Instruction:** "Use Decimal for monetary amounts."
- AI might use float "just for this calculation" and round at the end.
- AI might say "float is fine for display purposes."
- AI might invent edge cases where float seems reasonable.

**Forbidden operation:** "NEVER use float for any value that represents, calculates, or displays money, at any step, for any reason."
- No exceptions. No edge cases. No "just this once."
- If the AI uses float for money, it has violated a forbidden operation.
- The code is wrong, regardless of whether it produces correct results.

Forbidden operations close loopholes. They eliminate the creative workarounds that AI systems excel at finding.

---

## The Forbidden Operations List

Every business software system has operations that should never happen. Here is the comprehensive list for ERP-grade primitives.

### Data Integrity

| Forbidden Operation | Why It's Forbidden | What to Do Instead |
|--------------------|--------------------|--------------------|
| Auto-increment primary keys | Breaks replication, merging, distributed systems | UUID primary keys |
| Float for money | Rounding errors compound over time | DecimalField |
| Delete audit logs | Destroys accountability, breaks compliance | Append-only logs |
| Mutate posted transactions | Corrupts financial history | Post reversals |
| Edit agreements | Destroys contract history | Version with new record |
| Hard-delete domain objects | Loses historical references | Soft delete (deleted_at) |
| Null out fields to simulate deletion | Data loss without audit trail | Soft delete + keep data |
| Cascade delete on critical FKs | Unintended data loss | PROTECT or SET_NULL |

### Time

| Forbidden Operation | Why It's Forbidden | What to Do Instead |
|--------------------|--------------------|--------------------|
| Naive datetimes | Timezone bugs, DST failures | Always use timezone-aware |
| Assume "now" = "when it happened" | Late recordings misrepresent history | Separate effective_at and recorded_at |
| Backdate recorded_at | Destroys audit trail integrity | Only backdate effective_at |
| Query without temporal context | Returns wrong state for point-in-time queries | Use as_of() queries |
| Store dates as strings | Sorting, comparison, calculation failures | DateField or DateTimeField |
| Ignore business time | Lose the "when it really happened" | Always capture effective_at |

### Identity

| Forbidden Operation | Why It's Forbidden | What to Do Instead |
|--------------------|--------------------|--------------------|
| Hard-delete parties | Orphans all historical references | Soft delete |
| Assume one user = one person | Shared accounts, role-based access | Separate User and Party |
| Store roles in user table | Role changes become audit gaps | Separate Role model with time bounds |
| Skip relationship time bounds | Can't query "who was connected when?" | valid_from, valid_to on relationships |
| Embed identity in business objects | Duplicated data, sync problems | Reference Parties by FK |
| Delete user without preserving history | Loses actor information in audit logs | Capture actor_repr at event time |

### Architecture

| Forbidden Operation | Why It's Forbidden | What to Do Instead |
|--------------------|--------------------|--------------------|
| Import from higher layers | Creates circular dependencies | Strict layer hierarchy |
| Business logic in models | Hard to test, hard to change | Service layer |
| Business logic in views | Untestable, duplicated | Service layer |
| Invent new primitives | Duplication, inconsistency | Compose existing primitives |
| Skip the service layer | Direct model access bypasses rules | All mutations through services |
| GenericForeignKey without owner_id string | UUID compatibility issues | CharField for target_id |

### Operations

| Forbidden Operation | Why It's Forbidden | What to Do Instead |
|--------------------|--------------------|--------------------|
| Force push to main | Loses history, breaks collaboration | Regular push or rebase carefully |
| Skip pre-commit hooks | Bypasses quality gates | Fix issues, then commit |
| Commit secrets to code | Security vulnerability | Environment variables |
| SQL string concatenation | SQL injection vulnerability | Parameterized queries |
| eval() or exec() on user input | Code injection vulnerability | Never evaluate untrusted input |
| Disable SSL in production | Man-in-the-middle attacks | Always use TLS |

---

## Enforcement Mechanisms

Forbidden operations are only useful if they're enforced. There are five levels of enforcement, from weakest to strongest.

### Level 1: Prompt (Weakest)

Put the forbidden operation in CLAUDE.md or the task prompt:

```markdown
## Must Not Do
- Never use float for money
- Never delete audit logs
- Never mutate posted transactions
```

**Strength:** Easy to add. AI reads it at session start.
**Weakness:** AI may "forget" in long sessions. No runtime enforcement.

### Level 2: Code

Enforce in the model or service code:

```python
class AuditLog(models.Model):
    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLogError(
                "Audit log entries cannot be modified after creation."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError(
            "Audit log entries cannot be deleted."
        )
```

**Strength:** Fails at runtime. Works even if prompt is forgotten.
**Weakness:** Can be bypassed with direct SQL or `Model.objects.filter().delete()`.

### Level 3: Database

Enforce with database constraints and triggers:

```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=~models.Q(amount=Decimal('0')),
            name='ledger_entry_non_zero'
        ),
    ]
```

For immutability, use PostgreSQL triggers:

```sql
CREATE OR REPLACE FUNCTION prevent_audit_log_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update_audit_log
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_update();
```

**Strength:** Survives direct SQL, ORM bypasses, any client.
**Weakness:** Requires database access to set up. Migration complexity.

### Level 4: Test

Write tests that prove forbidden operations fail:

```python
class TestForbiddenOperations:
    """Tests that verify forbidden operations are blocked."""

    def test_cannot_update_audit_log(self):
        """Updating audit log entries is forbidden."""
        log = AuditLog.objects.create(
            target=document,
            action='create',
            actor=user
        )

        log.message = "Trying to modify"
        with pytest.raises(ImmutableLogError):
            log.save()

    def test_cannot_delete_audit_log(self):
        """Deleting audit log entries is forbidden."""
        log = AuditLog.objects.create(
            target=document,
            action='create',
            actor=user
        )

        with pytest.raises(ImmutableLogError):
            log.delete()

    def test_cannot_bulk_delete_audit_logs(self):
        """Bulk deletion of audit logs is forbidden."""
        AuditLog.objects.create(target=document, action='create')
        AuditLog.objects.create(target=document, action='update')

        # This should be blocked by database trigger
        with pytest.raises(Exception):  # DatabaseError or custom
            AuditLog.objects.all().delete()

    def test_cannot_use_float_for_money(self):
        """Money fields must be Decimal, never float."""
        # This test documents the requirement
        amount_field = Transaction._meta.get_field('amount')
        assert isinstance(amount_field, models.DecimalField)
        assert not isinstance(amount_field, models.FloatField)
```

**Strength:** Documents requirements. Catches regressions. Runs in CI.
**Weakness:** Only catches violations at test time, not at development time.

### Level 5: Static Analysis (Strongest)

Use linters and type checkers to catch violations before runtime:

```python
# mypy.ini
[mypy]
disallow_any_explicit = True

# Custom mypy plugin for money types
from decimal import Decimal
Money = Decimal  # Type alias

def calculate_total(amounts: list[Money]) -> Money:
    return sum(amounts, Decimal('0'))

# This would be caught by type checker:
# calculate_total([1.5, 2.5])  # Error: expected Money, got float
```

For layer violations:

```yaml
# layers.yaml
layers:
  - name: infrastructure
    packages:
      - django_basemodels
      - django_singleton

  - name: domain
    packages:
      - django_parties
      - django_catalog
    allowed_imports:
      - infrastructure

  - name: application
    packages:
      - vetfriendly
    allowed_imports:
      - domain
      - infrastructure
```

```bash
# Check layer violations
python -m django_layers check
```

**Strength:** Catches violations before code runs. Integrates with IDE.
**Weakness:** Requires setup. Not all violations are statically detectable.

---

## The Negative Test Pattern

For every forbidden operation, write a test that proves it fails:

```python
# tests/test_forbidden_operations.py

"""
Tests for forbidden operations.

These tests document what the system must NEVER do.
Each test should fail if the forbidden operation is allowed.
"""

import pytest
from decimal import Decimal
from django.db import models

from django_audit_log.models import AuditLog
from django_audit_log.exceptions import ImmutableLogError
from django_ledger.models import Transaction, Entry
from django_ledger.exceptions import ImmutableTransactionError


class TestAuditLogForbiddenOperations:
    """Audit logs are immutable."""

    def test_update_forbidden(self, audit_log):
        """Cannot modify an audit log after creation."""
        audit_log.message = "Modified"
        with pytest.raises(ImmutableLogError):
            audit_log.save()

    def test_delete_forbidden(self, audit_log):
        """Cannot delete an audit log."""
        with pytest.raises(ImmutableLogError):
            audit_log.delete()


class TestTransactionForbiddenOperations:
    """Posted transactions are immutable."""

    def test_update_posted_transaction_forbidden(self, posted_transaction):
        """Cannot modify a posted transaction."""
        posted_transaction.memo = "Modified"
        with pytest.raises(ImmutableTransactionError):
            posted_transaction.save()

    def test_delete_posted_transaction_forbidden(self, posted_transaction):
        """Cannot delete a posted transaction."""
        with pytest.raises(ImmutableTransactionError):
            posted_transaction.delete()

    def test_modify_entries_after_post_forbidden(self, posted_transaction):
        """Cannot add or modify entries after posting."""
        with pytest.raises(ImmutableTransactionError):
            Entry.objects.create(
                transaction=posted_transaction,
                account=some_account,
                amount=Decimal('100'),
                entry_type='debit'
            )


class TestMoneyForbiddenOperations:
    """Money must never use float."""

    def test_amount_is_decimal_field(self):
        """Transaction amount must be DecimalField."""
        field = Transaction._meta.get_field('amount')
        assert isinstance(field, models.DecimalField), \
            "Money fields must use DecimalField, not FloatField"

    def test_entry_amount_is_decimal_field(self):
        """Entry amount must be DecimalField."""
        field = Entry._meta.get_field('amount')
        assert isinstance(field, models.DecimalField), \
            "Money fields must use DecimalField, not FloatField"
```

These tests serve three purposes:

1. **Documentation**: Anyone reading the tests understands what's forbidden.
2. **Regression**: If someone accidentally allows a forbidden operation, the test fails.
3. **Enforcement**: CI blocks merges that violate forbidden operations.

---

## Forbidden Operation Cheat Sheet

Copy this into your CLAUDE.md:

```markdown
# Forbidden Operations

## NEVER (no exceptions)

### Data Integrity
- NEVER use auto-increment primary keys (use UUID)
- NEVER use float for money (use Decimal)
- NEVER delete audit logs (append-only)
- NEVER mutate posted transactions (post reversals)
- NEVER hard-delete domain objects (soft delete)

### Time
- NEVER use naive datetimes (always timezone-aware)
- NEVER assume now = when it happened (use effective_at)
- NEVER backdate recorded_at (only backdate effective_at)

### Identity
- NEVER hard-delete parties (soft delete)
- NEVER store roles in user table (separate Role model)
- NEVER skip relationship time bounds (valid_from/valid_to)

### Architecture
- NEVER import from higher layers (strict hierarchy)
- NEVER put business logic in models (use services)
- NEVER invent new primitives (compose existing)

### Security
- NEVER commit secrets to code (use env vars)
- NEVER use SQL string concatenation (parameterize)
- NEVER use eval() on user input (never)
```

---

## Handling Edge Cases

Sometimes someone will ask: "But what if I really need to..."

### "But what if I need to delete test data?"

```python
# Test cleanup is different from production deletion
# Use raw SQL or special test fixtures

# In tests/conftest.py
@pytest.fixture(autouse=True)
def reset_database(db):
    """Clean database between tests."""
    yield
    # Django's test runner handles this
```

### "But what if I need to fix a transaction error?"

```python
# Post a reversal, then post the correct transaction
def fix_transaction_error(wrong_transaction, correct_amount):
    """Fix a transaction by reversing and reposting."""
    # Reverse the wrong transaction
    reverse(wrong_transaction)

    # Create new correct transaction
    return Transaction.objects.create(
        amount=correct_amount,
        memo=f"Correction for {wrong_transaction.id}",
        relates_to=wrong_transaction,
    )
```

### "But what if the audit log has incorrect data?"

```python
# Post a correction event, don't modify the original
def correct_audit_error(original_log, correction_note):
    """Document that an audit log entry was incorrect."""
    return AuditLog.objects.create(
        target=original_log.target,
        action='correction',
        message=f"Correction to log {original_log.id}: {correction_note}",
        metadata={
            'corrects': str(original_log.id),
            'original_message': original_log.message,
        }
    )
```

The pattern is always the same: **don't modify, add corrections**.

---

## Hands-On Exercise: The Forbidden Operations Audit

Review your codebase for forbidden operation violations.

**Step 1: Check for Float Money**

```bash
grep -r "FloatField" --include="*.py" | grep -i "price\|amount\|cost\|fee\|total"
```

**Step 2: Check for Hard Deletes**

```bash
grep -r "\.delete()" --include="*.py" | grep -v "soft_delete\|test"
```

**Step 3: Check for Naive Datetimes**

```bash
grep -r "datetime.now()" --include="*.py"
grep -r "datetime.utcnow()" --include="*.py"
# Should use timezone.now() instead
```

**Step 4: Check for Auto-Increment**

```bash
grep -r "AutoField\|BigAutoField" --include="*.py" | grep -v "django/db"
```

**Step 5: Check for Layer Violations**

```bash
# In a higher-layer app, check for imports from lower layers
grep -r "from django_" --include="*.py" apps/vetfriendly/
```

Document every violation found. Create tickets to fix them.

---

## What AI Gets Wrong About Forbidden Operations

### Exception Requests

AI may argue that a constraint shouldn't apply:

> "In this case, using float is fine because we're just displaying the value and not doing calculations."

**Response:** The constraint is absolute. No exceptions. If there's a display context where float seems fine today, there will be a calculation context tomorrow where it causes bugs.

### Partial Compliance

AI may enforce some constraints but not others:

```python
class Transaction(models.Model):
    amount = models.DecimalField(...)  # Correct!

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)  # Wrong! Should be forbidden
```

**Response:** Use the complete forbidden operations list. Check every item.

### Workarounds

AI may find creative ways around constraints:

> "You said never delete records. So I set all fields to None and kept the row."

**Response:** Add explicit prohibitions for workarounds:
```markdown
- NEVER delete records
- NEVER null out fields to simulate deletion
- NEVER move records to "archive" tables
- NEVER set is_deleted flags without preserving original data
```

---

## Why This Matters Later

Forbidden operations are the safety rails of your system.

Without them:
- Someone will use float for money "just this once"
- Someone will delete an audit log "to clean up test data"
- Someone will modify a posted transaction "because the client asked"

With them:
- The system prevents these actions at multiple levels
- Violations are caught in tests, in code, in the database
- New developers can't accidentally break invariants

In Part IV, we'll compose primitives to build real applications. Every composition will respect the forbidden operations from this chapter. The safety rails remain in place, no matter how complex the application becomes.

---

## Summary

| Concept | Purpose |
|---------|---------|
| Forbidden operations | Absolute prohibitions that override all other rules |
| Prompt enforcement | CLAUDE.md rules (weakest) |
| Code enforcement | Model save/delete overrides |
| Database enforcement | Constraints and triggers |
| Test enforcement | Negative tests that prove violations fail |
| Static analysis | Linters and type checkers (strongest) |
| Negative test pattern | Every forbidden operation has a test |
| No exceptions | Constraints are absolute, no edge cases |

The Mars Climate Orbiter was lost because nothing in the system forbade mixing unit systems.

Your business software should not suffer the same fate. Make the dangerous operations impossible, and the safe operations easy.

---

## Sources

- Stephenson, A. G. et al. (1999). *Mars Climate Orbiter Mishap Investigation Board Phase I Report*. NASA.
- NASA. (1999). "Mars Climate Orbiter Failure Board Releases Report." Press Release 99-134.
