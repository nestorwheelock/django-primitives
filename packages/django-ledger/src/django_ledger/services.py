"""Ledger services for double-entry bookkeeping."""

from decimal import Decimal
from typing import List, Dict, Optional, Any
from django.db import transaction, models
from django.utils import timezone

from django_ledger.models import Account, Transaction, Entry
from django_ledger.exceptions import UnbalancedTransactionError


@transaction.atomic
def record_transaction(
    description: str,
    entries: List[Dict[str, Any]],
    effective_at: Optional[Any] = None,
    metadata: Optional[Dict] = None,
) -> Transaction:
    """
    Record a balanced double-entry transaction.

    Creates a transaction with entries and validates that debits equal credits
    before posting.

    Args:
        description: Transaction description.
        entries: List of entry dicts with keys: account, amount, entry_type, description (optional).
        effective_at: When the transaction is effective (defaults to now).
        metadata: Additional metadata dictionary.

    Returns:
        The posted Transaction.

    Raises:
        UnbalancedTransactionError: If debits don't equal credits.

    Usage:
        tx = record_transaction(
            description="Invoice #123",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
    """
    # Calculate totals
    total_debits = sum(
        e['amount'] for e in entries if e['entry_type'] == 'debit'
    )
    total_credits = sum(
        e['amount'] for e in entries if e['entry_type'] == 'credit'
    )

    if total_debits != total_credits:
        raise UnbalancedTransactionError(
            f"Transaction unbalanced: debits={total_debits}, credits={total_credits}"
        )

    # Create transaction
    tx = Transaction.objects.create(
        description=description,
        effective_at=effective_at or timezone.now(),
        metadata=metadata or {},
    )

    # Create entries
    for entry_data in entries:
        Entry.objects.create(
            transaction=tx,
            account=entry_data['account'],
            amount=entry_data['amount'],
            entry_type=entry_data['entry_type'],
            description=entry_data.get('description', ''),
            effective_at=effective_at or timezone.now(),
        )

    # Post the transaction
    tx.posted_at = timezone.now()
    tx.save()

    return tx


def get_balance(
    account: Account,
    as_of: Optional[Any] = None,
) -> Decimal:
    """
    Get the balance of an account.

    Calculates balance as sum(debits) - sum(credits) for all posted entries.

    Args:
        account: The account to get balance for.
        as_of: Optional timestamp to get historical balance (defaults to now).

    Returns:
        The account balance as a Decimal.

    Usage:
        balance = get_balance(receivable)  # Current balance
        past_balance = get_balance(receivable, as_of=some_date)  # Historical
    """
    entries = Entry.objects.filter(
        account=account,
        transaction__posted_at__isnull=False,  # Only posted transactions
    )

    if as_of:
        entries = entries.filter(effective_at__lte=as_of)

    # Calculate debits and credits
    totals = entries.values('entry_type').annotate(
        total=models.Sum('amount')
    )

    debits = Decimal('0')
    credits = Decimal('0')

    for item in totals:
        if item['entry_type'] == 'debit':
            debits = item['total'] or Decimal('0')
        elif item['entry_type'] == 'credit':
            credits = item['total'] or Decimal('0')

    return debits - credits


@transaction.atomic
def reverse_entry(
    entry: Entry,
    reason: str,
    effective_at: Optional[Any] = None,
) -> Transaction:
    """
    Create a reversal transaction for an entry.

    Creates a new transaction with an entry of the opposite type that
    references the original entry via the reverses FK.

    Args:
        entry: The entry to reverse.
        reason: Reason for the reversal.
        effective_at: When the reversal is effective (defaults to now).

    Returns:
        The reversal Transaction.

    Usage:
        reversal_tx = reverse_entry(
            entry=original_entry,
            reason="Customer refund",
        )
    """
    # Determine opposite entry type
    opposite_type = 'credit' if entry.entry_type == 'debit' else 'debit'

    # Create reversal transaction
    reversal_tx = Transaction.objects.create(
        description=f"Reversal: {reason}",
        effective_at=effective_at or timezone.now(),
        metadata={"reverses_entry_id": entry.pk, "reason": reason},
    )

    # Create reversal entry
    Entry.objects.create(
        transaction=reversal_tx,
        account=entry.account,
        amount=entry.amount,
        entry_type=opposite_type,
        description=f"Reversal of entry {entry.pk}: {reason}",
        effective_at=effective_at or timezone.now(),
        reverses=entry,
    )

    # Post the reversal
    reversal_tx.posted_at = timezone.now()
    reversal_tx.save()

    return reversal_tx
