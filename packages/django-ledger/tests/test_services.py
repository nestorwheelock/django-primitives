"""Tests for ledger services."""
import pytest
from decimal import Decimal
from django.utils import timezone

from django_ledger.models import Account, Transaction, Entry
from django_ledger.services import record_transaction, get_balance, reverse_entry
from django_ledger.exceptions import UnbalancedTransactionError, CurrencyMismatchError
from tests.models import Organization, Customer


@pytest.mark.django_db
class TestRecordTransaction:
    """Test suite for record_transaction service."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Test Customer", org=org)

    @pytest.fixture
    def receivable(self, customer):
        """Create a receivable account."""
        return Account.objects.create(
            owner=customer,
            account_type='receivable',
            currency='USD',
        )

    @pytest.fixture
    def revenue(self, org):
        """Create a revenue account."""
        return Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )

    def test_record_transaction_creates_transaction(self, receivable, revenue):
        """record_transaction should create a Transaction."""
        tx = record_transaction(
            description="Invoice #123",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        assert tx is not None
        assert tx.pk is not None

    def test_record_transaction_creates_entries(self, receivable, revenue):
        """record_transaction should create Entry records."""
        tx = record_transaction(
            description="Invoice #123",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        assert tx.entries.count() == 2

    def test_record_transaction_posts_transaction(self, receivable, revenue):
        """record_transaction should post the transaction."""
        tx = record_transaction(
            description="Invoice #123",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        assert tx.is_posted is True
        assert tx.posted_at is not None

    def test_record_transaction_enforces_balance(self, receivable, revenue):
        """record_transaction should raise if debits != credits."""
        with pytest.raises(UnbalancedTransactionError):
            record_transaction(
                description="Unbalanced",
                entries=[
                    {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                    {'account': revenue, 'amount': Decimal('50.00'), 'entry_type': 'credit'},
                ],
            )

    def test_record_transaction_multiple_entries(self, receivable, revenue, org):
        """record_transaction should handle multiple entries."""
        expense = Account.objects.create(owner=org, account_type='expense', currency='USD')

        tx = record_transaction(
            description="Complex transaction",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('80.00'), 'entry_type': 'credit'},
                {'account': expense, 'amount': Decimal('20.00'), 'entry_type': 'credit'},
            ],
        )
        assert tx.entries.count() == 3

    def test_record_transaction_with_metadata(self, receivable, revenue):
        """record_transaction should support metadata."""
        tx = record_transaction(
            description="Invoice #123",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
            metadata={"invoice_id": "123", "source": "api"},
        )
        assert tx.metadata["invoice_id"] == "123"

    def test_record_transaction_with_effective_at(self, receivable, revenue):
        """record_transaction should support custom effective_at."""
        past = timezone.now() - timezone.timedelta(days=7)
        tx = record_transaction(
            description="Backdated entry",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
            effective_at=past,
        )
        assert tx.effective_at == past


@pytest.mark.django_db
class TestGetBalance:
    """Test suite for get_balance service."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Test Customer", org=org)

    @pytest.fixture
    def receivable(self, customer):
        """Create a receivable account."""
        return Account.objects.create(
            owner=customer,
            account_type='receivable',
            currency='USD',
        )

    @pytest.fixture
    def revenue(self, org):
        """Create a revenue account."""
        return Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )

    def test_get_balance_returns_zero_for_empty_account(self, receivable):
        """get_balance should return 0 for account with no entries."""
        balance = get_balance(receivable)
        assert balance == Decimal('0')

    def test_get_balance_calculates_debit_minus_credit(self, receivable, revenue):
        """get_balance should return debits - credits."""
        record_transaction(
            description="Test",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )

        balance = get_balance(receivable)
        assert balance == Decimal('100.00')  # Debit account

    def test_get_balance_credit_account(self, receivable, revenue):
        """get_balance should return correct balance for credit accounts."""
        record_transaction(
            description="Test",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )

        balance = get_balance(revenue)
        assert balance == Decimal('-100.00')  # Credit account (debits - credits = negative)

    def test_get_balance_multiple_transactions(self, receivable, revenue):
        """get_balance should sum across multiple transactions."""
        for _ in range(3):
            record_transaction(
                description="Test",
                entries=[
                    {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                    {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
                ],
            )

        balance = get_balance(receivable)
        assert balance == Decimal('300.00')

    def test_get_balance_as_of_timestamp(self, receivable, revenue):
        """get_balance should support as_of parameter."""
        past = timezone.now() - timezone.timedelta(days=7)
        now = timezone.now()

        # Old transaction
        record_transaction(
            description="Old",
            entries=[
                {'account': receivable, 'amount': Decimal('50.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('50.00'), 'entry_type': 'credit'},
            ],
            effective_at=past,
        )

        # New transaction
        record_transaction(
            description="New",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
            effective_at=now,
        )

        # Balance as of past should only include old transaction
        past_balance = get_balance(receivable, as_of=past + timezone.timedelta(minutes=1))
        assert past_balance == Decimal('50.00')

        # Current balance includes both
        current_balance = get_balance(receivable)
        assert current_balance == Decimal('150.00')


@pytest.mark.django_db
class TestReverseEntry:
    """Test suite for reverse_entry service."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Test Customer", org=org)

    @pytest.fixture
    def receivable(self, customer):
        """Create a receivable account."""
        return Account.objects.create(
            owner=customer,
            account_type='receivable',
            currency='USD',
        )

    @pytest.fixture
    def revenue(self, org):
        """Create a revenue account."""
        return Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )

    def test_reverse_entry_creates_new_transaction(self, receivable, revenue):
        """reverse_entry should create a new reversal transaction."""
        tx = record_transaction(
            description="Original",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        original_entry = tx.entries.filter(account=receivable).first()

        reversal_tx = reverse_entry(
            entry=original_entry,
            reason="Customer refund",
        )

        assert reversal_tx is not None
        assert reversal_tx.pk != tx.pk

    def test_reverse_entry_creates_opposite_entry(self, receivable, revenue):
        """reverse_entry should create entry with opposite type."""
        tx = record_transaction(
            description="Original",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        original_entry = tx.entries.filter(account=receivable).first()

        reversal_tx = reverse_entry(
            entry=original_entry,
            reason="Refund",
        )

        reversal_entry = reversal_tx.entries.filter(account=receivable).first()
        assert reversal_entry.entry_type == 'credit'  # Opposite of debit
        assert reversal_entry.amount == Decimal('100.00')

    def test_reverse_entry_links_to_original(self, receivable, revenue):
        """reverse_entry should link reversal to original via reverses FK."""
        tx = record_transaction(
            description="Original",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        original_entry = tx.entries.filter(account=receivable).first()

        reversal_tx = reverse_entry(
            entry=original_entry,
            reason="Refund",
        )

        reversal_entry = reversal_tx.entries.filter(account=receivable).first()
        assert reversal_entry.reverses == original_entry

    def test_reverse_entry_nets_to_zero(self, receivable, revenue):
        """Reversing an entry should result in zero net balance change."""
        tx = record_transaction(
            description="Original",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        original_entry = tx.entries.filter(account=receivable).first()

        # Balance before reversal
        balance_before = get_balance(receivable)
        assert balance_before == Decimal('100.00')

        # Reverse
        reverse_entry(entry=original_entry, reason="Refund")

        # Balance after reversal
        balance_after = get_balance(receivable)
        assert balance_after == Decimal('0')

    def test_reverse_entry_includes_reason(self, receivable, revenue):
        """reverse_entry should include reason in transaction description."""
        tx = record_transaction(
            description="Original",
            entries=[
                {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )
        original_entry = tx.entries.filter(account=receivable).first()

        reversal_tx = reverse_entry(
            entry=original_entry,
            reason="Customer returned merchandise",
        )

        assert "Customer returned merchandise" in reversal_tx.description


@pytest.mark.django_db
class TestDoubleEntryIntegration:
    """Integration tests for double-entry bookkeeping."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Test Customer", org=org)

    def test_complete_sales_cycle(self, org, customer):
        """Test a complete sales cycle: sale, payment, refund."""
        # Create accounts
        receivable = Account.objects.create(
            owner=customer, account_type='receivable', currency='USD'
        )
        revenue = Account.objects.create(
            owner=org, account_type='revenue', currency='USD'
        )
        cash = Account.objects.create(
            owner=org, account_type='asset', currency='USD'
        )

        # 1. Record sale: Debit receivable, Credit revenue
        sale_tx = record_transaction(
            description="Sale - Invoice #100",
            entries=[
                {'account': receivable, 'amount': Decimal('500.00'), 'entry_type': 'debit'},
                {'account': revenue, 'amount': Decimal('500.00'), 'entry_type': 'credit'},
            ],
        )

        assert get_balance(receivable) == Decimal('500.00')
        assert get_balance(revenue) == Decimal('-500.00')

        # 2. Record payment: Debit cash, Credit receivable
        payment_tx = record_transaction(
            description="Payment received",
            entries=[
                {'account': cash, 'amount': Decimal('500.00'), 'entry_type': 'debit'},
                {'account': receivable, 'amount': Decimal('500.00'), 'entry_type': 'credit'},
            ],
        )

        assert get_balance(receivable) == Decimal('0')
        assert get_balance(cash) == Decimal('500.00')

        # 3. Partial refund
        refund_tx = record_transaction(
            description="Partial refund",
            entries=[
                {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
                {'account': cash, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
            ],
        )

        assert get_balance(revenue) == Decimal('-400.00')  # Net revenue
        assert get_balance(cash) == Decimal('400.00')  # Net cash
