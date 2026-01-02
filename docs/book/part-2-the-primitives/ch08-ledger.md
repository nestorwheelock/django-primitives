# Chapter 8: Ledger

> "For every debit, there must be a credit."
>
> — The fundamental rule of accounting, unchanged since 1494

---

In 1494, Luca Pacioli published *Summa de arithmetica*, which included the first systematic description of double-entry bookkeeping. The method wasn't new—Venetian merchants had used it for centuries—but Pacioli's documentation made it teachable and reproducible.

Five hundred and thirty years later, every serious financial system still uses the same pattern. Not because no one has tried to improve it, but because it's irreducibly correct. Double-entry bookkeeping isn't a preference or a best practice. It's a mathematical proof that money doesn't vanish.

## The Problem Double-Entry Solves

Single-entry bookkeeping records transactions as a list: "Received $100 from Customer A." "Paid $50 to Supplier B." "Received $75 from Customer C." At any point, you can sum the entries and claim to know your balance.

But single-entry systems have a fatal flaw: they can't prove themselves correct.

If your calculated balance doesn't match your bank statement, where's the error? Was an entry missed? Miscategorized? Duplicated? The system has no internal verification mechanism. Every reconciliation requires comparing against an external source.

Double-entry solves this by requiring that every transaction have at least two entries that sum to zero. Money comes from somewhere and goes somewhere. The constraint that debits equal credits is self-enforcing—if the books don't balance, something is definitely wrong.

The General Accounting Office estimated in 2019 that the federal government couldn't account for $21 billion in budgetary resources due to inadequate transaction records. These weren't missing funds—they were transactions that couldn't be traced because the systems didn't enforce double-entry discipline.

## The Two Sides of Every Transaction

Every business transaction has at least two effects:

**Sale:** Revenue increases (credit), and either cash increases (debit) or accounts receivable increases (debit).

**Payment:** Cash decreases (credit), and either accounts payable decreases (debit) or expense increases (debit).

**Refund:** Revenue decreases (debit), and cash decreases (credit).

The pattern is universal: for every flow of value, there's a source and a destination. Double-entry captures both.

```python
class Account(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    owner_id = models.CharField(max_length=255)  # CharField for UUID support
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    account_type = models.CharField(max_length=50)  # asset, liability, equity, revenue, expense
    currency = models.CharField(max_length=3)  # ISO 4217
    name = models.CharField(max_length=255, blank=True)


class Transaction(models.Model):
    description = models.TextField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)  # null = draft
    effective_at = models.DateTimeField(default=timezone.now)
    recorded_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)


class Entry(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=PROTECT, related_name='entries')
    account = models.ForeignKey(Account, on_delete=PROTECT, related_name='entries')
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    entry_type = models.CharField(choices=[('debit', 'Debit'), ('credit', 'Credit')])
    effective_at = models.DateTimeField(default=timezone.now)
    recorded_at = models.DateTimeField(auto_now_add=True)
    reverses = models.ForeignKey('self', null=True, blank=True, on_delete=PROTECT)
```

The structure is simple: Accounts hold value. Transactions group entries. Entries move value between accounts.

## The Balance Constraint

The fundamental invariant: within any transaction, the sum of debits must equal the sum of credits.

```python
@transaction.atomic
def record_transaction(description, entries, effective_at=None, metadata=None):
    # Validate balance
    debits = sum(e['amount'] for e in entries if e['entry_type'] == 'debit')
    credits = sum(e['amount'] for e in entries if e['entry_type'] == 'credit')

    if debits != credits:
        raise UnbalancedTransactionError(
            f"Transaction unbalanced: debits={debits}, credits={credits}"
        )

    tx = Transaction.objects.create(
        description=description,
        effective_at=effective_at or timezone.now(),
        metadata=metadata or {},
    )

    for entry_data in entries:
        Entry.objects.create(
            transaction=tx,
            account=entry_data['account'],
            amount=entry_data['amount'],
            entry_type=entry_data['entry_type'],
            effective_at=tx.effective_at,
        )

    tx.posted_at = timezone.now()
    tx.save()

    return tx
```

This constraint is not optional. Every financial system that skips it eventually produces books that don't reconcile.

## Immutability After Posting

Once a transaction is posted, it cannot be modified. This is not a technical limitation—it's an accounting requirement. Auditors need to know that the books you're showing them are the same books that existed at the audit date.

```python
class Entry(models.Model):
    # ...

    def save(self, *args, **kwargs):
        if self.pk and self.transaction.is_posted:
            raise ImmutableEntryError(
                f"Cannot modify entry {self.pk} - transaction is posted. "
                "Create a reversal instead."
            )
        super().save(*args, **kwargs)
```

If you made an error, you don't edit the transaction. You create a reversal—a new transaction that undoes the effect of the original:

```python
@transaction.atomic
def reverse_entry(entry, reason, effective_at=None):
    opposite_type = 'credit' if entry.entry_type == 'debit' else 'debit'

    tx = Transaction.objects.create(
        description=f"Reversal: {reason}",
        effective_at=effective_at or timezone.now(),
        metadata={'reverses_entry_id': entry.pk, 'reason': reason},
    )

    Entry.objects.create(
        transaction=tx,
        account=entry.account,
        amount=entry.amount,
        entry_type=opposite_type,
        effective_at=tx.effective_at,
        reverses=entry,
    )

    tx.posted_at = timezone.now()
    tx.save()

    return tx
```

After a reversal, the account balance is back to where it was. But the history is preserved: the original transaction, the reversal, and the reason for the reversal are all in the permanent record.

## Balances Are Computed, Not Stored

A common mistake is storing a "balance" field on accounts and updating it with each transaction. This creates synchronization problems: what if two transactions update the balance simultaneously? What if a transaction is reversed but the balance update fails?

The correct approach: balances are always computed from entries.

```python
def get_balance(account, as_of=None):
    entries = Entry.objects.filter(
        account=account,
        transaction__posted_at__isnull=False,
    )

    if as_of:
        entries = entries.filter(effective_at__lte=as_of)

    debit_sum = entries.filter(entry_type='debit').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

    credit_sum = entries.filter(entry_type='credit').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

    return debit_sum - credit_sum
```

For asset accounts (cash, receivables), balance = debits - credits. A positive balance means you have assets.

For liability accounts (payables, loans), the balance is typically negative (credits exceed debits), meaning you owe money.

The formula is consistent. The interpretation depends on the account type.

## Currency: Never Float

Currency is the domain where floating-point arithmetic fails most spectacularly.

In Python:
```python
>>> 0.1 + 0.2
0.30000000000000004
```

This isn't a bug—it's how binary floating-point works. But when you're calculating invoices, rounding errors accumulate. After thousands of transactions, your books don't balance, and you don't know why.

The fix is trivial: use `DecimalField` with at least 4 decimal places. Currency amounts like $100.25 are stored as `Decimal('100.2500')`.

For multicurrency systems, store amounts in the smallest unit (cents for USD, pence for GBP) and track currency separately:

```python
amount = models.DecimalField(max_digits=19, decimal_places=4)
currency = models.CharField(max_length=3)  # ISO 4217 code
```

Never store currency as float. Never perform arithmetic on float currency values. This constraint is absolute.

## GenericFK for Polymorphic Accounts

Accounts belong to parties. But parties can be people, organizations, departments, or any other entity. The Account model uses GenericForeignKey to support any owner type:

```python
class Account(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    owner_id = models.CharField(max_length=255)  # CharField for UUID support
    owner = GenericForeignKey('owner_content_type', 'owner_id')
```

Note: `owner_id` is CharField, not IntegerField. This supports UUID primary keys, which are standard in the primitives.

With GenericFK, you can query accounts for any party type:

```python
# Accounts for a customer
customer_accounts = Account.objects.for_owner(customer)

# Accounts for an organization
org_accounts = Account.objects.for_owner(organization)

# Accounts of a specific type
receivables = Account.objects.by_type('receivable')
```

## The Full Prompt

Here is the complete prompt to generate a double-entry ledger package. Feed this to an AI, and it will generate correct accounting primitives.

---

```markdown
# Prompt: Build django-ledger

## Instruction

Create a Django package called `django-ledger` that provides double-entry
accounting primitives with immutable posted entries.

## Package Purpose

Provide lightweight, immutable double-entry accounting:
- Account model with polymorphic owners via GenericFK
- Transaction model grouping balanced entries
- Entry model that is immutable once posted
- Balance calculation and entry reversal services

## File Structure

packages/django-ledger/
├── pyproject.toml
├── README.md
├── src/django_ledger/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_models.py
    └── test_services.py

## Exceptions Specification

### exceptions.py

class LedgerError(Exception):
    """Base exception for ledger errors."""
    pass

class UnbalancedTransactionError(LedgerError):
    """Raised when transaction entries don't balance."""
    pass

class ImmutableEntryError(LedgerError):
    """Raised when attempting to modify a posted entry."""
    pass

## Models Specification

### Account Model

- owner via GenericForeignKey (owner_content_type, owner_id)
- owner_id is CharField(max_length=255) for UUID support
- account_type: CharField(max_length=50) - receivable, payable, revenue, expense, etc.
- currency: CharField(max_length=3) - ISO 4217
- name: CharField(max_length=255, blank=True)
- created_at, updated_at timestamps

QuerySet methods:
- for_owner(owner) - filter by owner
- by_type(account_type) - filter by type
- by_currency(currency) - filter by currency

### Transaction Model

- description: TextField(blank=True)
- posted_at: DateTimeField(null=True, blank=True) - null means draft
- effective_at: DateTimeField(default=timezone.now) - business timestamp
- recorded_at: DateTimeField(auto_now_add=True) - system timestamp
- metadata: JSONField(default=dict)

Property:
- is_posted: returns True if posted_at is not None

### Entry Model

- transaction: ForeignKey(Transaction, on_delete=PROTECT)
- account: ForeignKey(Account, on_delete=PROTECT)
- amount: DecimalField(max_digits=19, decimal_places=4)
- entry_type: CharField with choices ('debit', 'credit')
- description: CharField(max_length=500, blank=True)
- effective_at: DateTimeField(default=timezone.now)
- recorded_at: DateTimeField(auto_now_add=True)
- reverses: ForeignKey('self', null=True, blank=True) - for reversal entries
- metadata: JSONField(default=dict)

CRITICAL: Override save() to prevent modification of posted entries:
- If self.pk exists AND self.transaction.is_posted, raise ImmutableEntryError

## Service Functions

### record_transaction(description, entries, effective_at=None, metadata=None)

1. Validate: sum(debits) must equal sum(credits)
2. If not balanced, raise UnbalancedTransactionError
3. Create Transaction
4. Create all Entry records
5. Set posted_at = timezone.now()
6. Return the posted Transaction

Use @transaction.atomic decorator.

### get_balance(account, as_of=None)

1. Filter entries for account where transaction.posted_at is not None
2. If as_of provided, filter effective_at <= as_of
3. Sum debits, sum credits
4. Return debits - credits as Decimal

### reverse_entry(entry, reason, effective_at=None)

1. Determine opposite entry_type
2. Create new Transaction with description "Reversal: {reason}"
3. Create Entry with opposite type, same amount, reverses=entry
4. Post the transaction
5. Return the reversal Transaction

Use @transaction.atomic decorator.

## Test Cases (48 tests minimum)

### Account Model (7 tests)
- test_account_has_owner_generic_fk
- test_account_owner_id_is_charfield (for UUID support)
- test_account_has_account_type
- test_account_has_currency
- test_account_has_name_optional
- test_account_name_defaults_to_empty
- test_account_has_timestamps

### Transaction Model (8 tests)
- test_transaction_has_description
- test_transaction_description_is_optional
- test_transaction_has_posted_at_nullable
- test_transaction_is_posted_property
- test_transaction_has_effective_at
- test_transaction_effective_at_defaults_to_now
- test_transaction_has_recorded_at
- test_transaction_has_metadata

### Entry Model (10 tests)
- test_entry_has_transaction_fk
- test_entry_has_account_fk
- test_entry_has_amount_decimal
- test_entry_has_entry_type (debit/credit)
- test_entry_has_description
- test_entry_has_effective_at
- test_entry_has_recorded_at
- test_entry_has_reverses_fk
- test_entry_reversal_entries_related_name
- test_entry_has_metadata

### Entry Immutability (2 tests)
- test_entry_can_be_modified_before_posting
- test_entry_immutable_after_posting (raises ImmutableEntryError)

### Account QuerySet (3 tests)
- test_for_owner_returns_accounts
- test_by_type_filters_accounts
- test_by_currency_filters_accounts

### record_transaction Service (7 tests)
- test_record_transaction_creates_transaction
- test_record_transaction_creates_entries
- test_record_transaction_posts_transaction
- test_record_transaction_enforces_balance (raises UnbalancedTransactionError)
- test_record_transaction_multiple_entries (3+ entries)
- test_record_transaction_with_metadata
- test_record_transaction_with_effective_at

### get_balance Service (5 tests)
- test_get_balance_returns_zero_for_empty
- test_get_balance_calculates_debit_minus_credit
- test_get_balance_credit_account (negative balance)
- test_get_balance_multiple_transactions
- test_get_balance_as_of_timestamp

### reverse_entry Service (5 tests)
- test_reverse_entry_creates_new_transaction
- test_reverse_entry_creates_opposite_entry
- test_reverse_entry_links_to_original (reverses FK)
- test_reverse_entry_nets_to_zero
- test_reverse_entry_includes_reason

### Integration (1 test)
- test_complete_sales_cycle (sale → payment → refund)

## Key Behaviors

1. Double-entry balance: debits MUST equal credits
2. Immutable posted entries: cannot modify after posting
3. Reversal pattern: create opposite entry instead of delete
4. GenericFK owners: accounts owned by any model
5. Balance = debits - credits (consistent formula)
6. Currency as Decimal, NEVER float

## Usage Example

from decimal import Decimal
from django_ledger import Account, record_transaction, get_balance, reverse_entry

# Create accounts
receivable = Account.objects.create(
    owner=customer, account_type='receivable', currency='USD'
)
revenue = Account.objects.create(
    owner=org, account_type='revenue', currency='USD'
)

# Record sale
tx = record_transaction(
    description="Invoice #123",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ]
)

# Check balance
balance = get_balance(receivable)  # Decimal('100.00')

# Reverse if needed
reversal = reverse_entry(tx.entries.first(), reason="Customer refund")
balance = get_balance(receivable)  # Decimal('0')

## Acceptance Criteria

- [ ] Account model with GenericFK owner
- [ ] Transaction model with posted_at for immutability
- [ ] Entry model with immutability enforcement
- [ ] record_transaction enforces balance
- [ ] get_balance calculates debits - credits
- [ ] reverse_entry creates opposite entry
- [ ] All 48 tests passing
- [ ] No float currency, only Decimal
```

---

## Hands-On: Generate Your Ledger

Copy the prompt above and paste it into your AI assistant. The AI will generate:

1. The complete package structure
2. Models with all constraints
3. Service functions with proper validation
4. Exception classes
5. Test cases covering all behaviors

After generation, run the tests:

```bash
cd packages/django-ledger
pip install -e .
pytest tests/ -v
```

All 48 tests should pass. If any fail, review the failing test to understand which constraint was violated, then ask the AI to fix it.

### Exercise: Add Currency Conversion

Extend the ledger with multicurrency support:

```
Extend django-ledger to support multicurrency transactions:

1. Add ExchangeRate model:
   - from_currency, to_currency (both CharField(3))
   - rate (DecimalField, max_digits=12, decimal_places=6)
   - effective_from, effective_to for temporal validity

2. Add convert_amount(amount, from_currency, to_currency, as_of) function:
   - Look up rate valid at as_of timestamp
   - Return amount * rate as Decimal
   - Raise CurrencyConversionError if no rate found

3. Modify record_transaction to validate all entries use same currency
   (multicurrency transactions require explicit conversion entries)

Write tests for:
- Exchange rate lookup by date
- Currency conversion calculation
- Rejecting mismatched currencies in single transaction
```

This exercise extends the ledger while maintaining its core invariants.

## What AI Gets Wrong

Without explicit constraints, AI-generated accounting code typically:

1. **Uses FloatField for amounts** — The 0.1 + 0.2 problem corrupts your books.

2. **Allows editing posted transactions** — Someone "fixes" an old entry instead of creating a reversal. The audit trail is broken.

3. **Skips balance validation** — Unbalanced transactions are silently accepted. Your books don't reconcile.

4. **Stores balance as a field** — Race conditions and sync failures corrupt the balance. You don't know the real number.

5. **Uses IntegerField for owner_id** — Breaks when parties have UUID primary keys.

6. **Lacks reversal pattern** — Deletions are allowed, destroying audit history.

The fix is always explicit constraints. The prompt above prevents all of these mistakes.

## Why This Matters Later

The ledger is the financial foundation:

- **Catalog**: When a basket is committed, ledger entries record the sale.

- **Agreements**: Payment schedules and invoicing derive from agreement terms and create ledger entries.

- **Audit**: Every ledger entry is permanent evidence of what happened.

- **Reporting**: Financial statements are computed from ledger entries, not stored summaries.

Get the ledger wrong, and your financial data is unreliable. Get it right, and you have books that auditors will trust.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-ledger | `docs/prompts/django-ledger.md` | 48 tests |

### Using the Prompt

```bash
cat docs/prompts/django-ledger.md | claude

# Request: "Implement Account model with GenericFK owner,
# then Transaction with posted_at for immutability,
# then Entry with debit/credit types."
```

### Key Constraints

- **DecimalField for all amounts**: Never use FloatField for money
- **Immutable posted entries**: Cannot modify after `posted_at` is set
- **Balance enforcement**: `record_transaction` must validate debits = credits
- **Reversal pattern**: Corrections create opposite entries, never delete

If Claude allows editing a posted entry or stores amounts as Float, that's a constraint violation.

---

## Sources and References

1. **Pacioli, Luca** (1494). *Summa de arithmetica, geometria, proportioni et proportionalita*. The first published description of double-entry bookkeeping.

2. **Government Accountability Office** (2019). "Financial Management: Federal Agencies Need to Address Long-Standing Deficiencies." GAO-19-572T. The $21 billion discrepancy finding.

3. **Floating-Point Arithmetic** — Goldberg, David. "What Every Computer Scientist Should Know About Floating-Point Arithmetic," *ACM Computing Surveys*, March 1991. The authoritative explanation of why 0.1 + 0.2 ≠ 0.3.

4. **ISO 4217** — International standard for currency codes. USD, EUR, GBP, etc.

5. **Django DecimalField** — Django documentation on using Decimal for precision monetary calculations.

---

*Status: Complete*
