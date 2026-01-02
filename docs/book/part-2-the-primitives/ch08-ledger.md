# Chapter 8: Ledger

> Double-entry or don't bother.

## The Primitive

**Ledger** answers: What money moved, from where, to where, and why?

- Every transaction has two sides
- Debits equal credits, always
- Reversals, never edits
- If it doesn't balance, it's lying

## django-primitives Implementation

- `django-ledger`: Account, Transaction, Entry
- `django-money`: Money value object (amount + currency)

## Historical Origin

Double-entry bookkeeping. Invented in 1494 by Luca Pacioli. Every financial system that survives uses it. Every system that doesn't eventually fails an audit.

## Failure Mode When Ignored

- Single-entry "balances" that drift
- Floating point currency (0.1 + 0.2 ≠ 0.3)
- Mutable transaction history
- No audit trail
- Reconciliation becomes guesswork

## Minimal Data Model

```python
class Account(models.Model):
    id = UUIDField(primary_key=True)
    account_type = CharField()  # asset, liability, equity, revenue, expense
    name = CharField()
    parent = ForeignKey('self', null=True)  # Chart of accounts hierarchy

class Transaction(models.Model):
    id = UUIDField(primary_key=True)
    effective_at = DateTimeField()
    recorded_at = DateTimeField(auto_now_add=True)
    description = TextField()
    metadata = JSONField()

class Entry(models.Model):
    transaction = ForeignKey(Transaction)
    account = ForeignKey(Account)
    amount = DecimalField(max_digits=19, decimal_places=4)
    entry_type = CharField()  # debit, credit
    # Constraint: sum(debits) == sum(credits) per transaction
```

## Invariants That Must Never Break

1. Every transaction balances (debits = credits)
2. Transactions are immutable
3. Corrections are reversals + new entries
4. Currency is Decimal, never float
5. Account balances are computed, not stored

---

*Status: Planned*
