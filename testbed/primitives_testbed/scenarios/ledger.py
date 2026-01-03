"""Ledger scenario: Account, Transaction, Entry with double-entry enforcement."""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction

from django_ledger.models import Account, Transaction, Entry
from django_parties.models import Organization


def seed():
    """Create sample ledger data."""
    count = 0

    org = Organization.objects.first()
    if org:
        org_ct = ContentType.objects.get_for_model(Organization)

        # Create accounts (chart of accounts)
        cash, created = Account.objects.get_or_create(
            owner_content_type=org_ct,
            owner_id=str(org.pk),
            account_type="asset",
            currency="USD",
            name="Cash",
        )
        if created:
            count += 1

        revenue, created = Account.objects.get_or_create(
            owner_content_type=org_ct,
            owner_id=str(org.pk),
            account_type="revenue",
            currency="USD",
            name="Service Revenue",
        )
        if created:
            count += 1

        expenses, created = Account.objects.get_or_create(
            owner_content_type=org_ct,
            owner_id=str(org.pk),
            account_type="expense",
            currency="USD",
            name="Operating Expenses",
        )
        if created:
            count += 1

        ar, created = Account.objects.get_or_create(
            owner_content_type=org_ct,
            owner_id=str(org.pk),
            account_type="receivable",
            currency="USD",
            name="Accounts Receivable",
        )
        if created:
            count += 1

        # Create a balanced transaction
        existing_txn = Transaction.objects.filter(
            description__startswith="Service revenue",
        ).exists()

        if not existing_txn:
            txn = Transaction.objects.create(
                description="Service revenue received - Invoice #001",
            )
            count += 1

            # Debit cash, credit revenue (balanced)
            Entry.objects.create(
                transaction=txn,
                account=cash,
                entry_type="debit",
                amount=Decimal("100.00"),
            )
            Entry.objects.create(
                transaction=txn,
                account=revenue,
                entry_type="credit",
                amount=Decimal("100.00"),
            )
            count += 2

    return count


def verify():
    """Verify ledger constraints with negative writes."""
    results = []

    # Test 1: Entry amount must be positive
    account = Account.objects.first()
    txn = Transaction.objects.first()

    if account and txn:
        try:
            with transaction.atomic():
                Entry.objects.create(
                    transaction=txn,
                    account=account,
                    entry_type="debit",
                    amount=Decimal("0.00"),  # Zero - should fail
                )
            results.append(("entry_amount_positive (zero)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("entry_amount_positive (zero)", True, "Correctly rejected"))

        try:
            with transaction.atomic():
                Entry.objects.create(
                    transaction=txn,
                    account=account,
                    entry_type="credit",
                    amount=Decimal("-50.00"),  # Negative - should fail
                )
            results.append(("entry_amount_positive (negative)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("entry_amount_positive (negative)", True, "Correctly rejected"))
    else:
        results.append(("entry_amount_positive", None, "Skipped - no test data"))

    # Test 2: Verify transaction has entries
    if txn:
        entry_count = txn.entries.count()
        if entry_count >= 2:
            results.append(("transaction_has_entries", True, f"Transaction has {entry_count} entries"))
        else:
            results.append(("transaction_has_entries", False, f"Expected at least 2 entries, got {entry_count}"))
    else:
        results.append(("transaction_has_entries", None, "Skipped - no transaction"))

    return results
