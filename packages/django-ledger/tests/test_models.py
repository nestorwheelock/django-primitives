"""Tests for Ledger models."""
import pytest
from decimal import Decimal
from django.utils import timezone

from django_ledger.models import Account, Transaction, Entry
from django_ledger.exceptions import ImmutableEntryError
from tests.models import Organization, Customer


@pytest.mark.django_db
class TestAccountModel:
    """Test suite for Account model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Test Customer", org=org)

    def test_account_has_owner_generic_fk(self, org):
        """Account should have owner via GenericFK."""
        account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )
        assert account.owner == org

    def test_account_owner_id_is_charfield(self, org):
        """Account owner_id should be CharField for UUID support."""
        account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )
        assert isinstance(account.owner_id, str)

    def test_account_has_account_type(self, org):
        """Account should have account_type classification."""
        account = Account.objects.create(
            owner=org,
            account_type='receivable',
            currency='USD',
        )
        assert account.account_type == 'receivable'

    def test_account_has_currency(self, org):
        """Account should have currency field."""
        account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='EUR',
        )
        assert account.currency == 'EUR'

    def test_account_has_name_optional(self, org):
        """Account should have optional name field."""
        account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
            name='Main Revenue Account',
        )
        assert account.name == 'Main Revenue Account'

    def test_account_name_defaults_to_empty(self, org):
        """Account name should default to empty string."""
        account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )
        assert account.name == ''

    def test_account_has_timestamps(self, org):
        """Account should have created_at and updated_at."""
        account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )
        assert account.created_at is not None
        assert account.updated_at is not None


@pytest.mark.django_db
class TestTransactionModel:
    """Test suite for Transaction model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    def test_transaction_has_description(self, org):
        """Transaction should have description field."""
        tx = Transaction.objects.create(
            description="Invoice #123",
        )
        assert tx.description == "Invoice #123"

    def test_transaction_description_is_optional(self):
        """Transaction description should be optional."""
        tx = Transaction.objects.create()
        assert tx.description == ''

    def test_transaction_has_posted_at_nullable(self):
        """Transaction should have nullable posted_at."""
        tx = Transaction.objects.create()
        assert tx.posted_at is None

    def test_transaction_is_posted_property(self):
        """Transaction.is_posted should return boolean."""
        tx = Transaction.objects.create()
        assert tx.is_posted is False

        tx.posted_at = timezone.now()
        tx.save()
        assert tx.is_posted is True

    def test_transaction_has_effective_at(self):
        """Transaction should have effective_at for time semantics."""
        now = timezone.now()
        tx = Transaction.objects.create(effective_at=now)
        assert tx.effective_at == now

    def test_transaction_effective_at_defaults_to_now(self):
        """Transaction effective_at should default to now."""
        tx = Transaction.objects.create()
        assert tx.effective_at is not None

    def test_transaction_has_recorded_at(self):
        """Transaction should have recorded_at timestamp."""
        tx = Transaction.objects.create()
        assert tx.recorded_at is not None

    def test_transaction_has_metadata(self):
        """Transaction should have metadata JSONField."""
        tx = Transaction.objects.create(
            metadata={"source": "api", "request_id": "abc123"},
        )
        assert tx.metadata["source"] == "api"


@pytest.mark.django_db
class TestEntryModel:
    """Test suite for Entry model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def account(self, org):
        """Create a test account."""
        return Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )

    @pytest.fixture
    def transaction(self):
        """Create a test transaction."""
        return Transaction.objects.create(description="Test transaction")

    def test_entry_has_transaction_fk(self, account, transaction):
        """Entry should have transaction FK."""
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )
        assert entry.transaction == transaction

    def test_entry_has_account_fk(self, account, transaction):
        """Entry should have account FK."""
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )
        assert entry.account == account

    def test_entry_has_amount_decimal(self, account, transaction):
        """Entry should have amount as Decimal."""
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('123.4567'),
            entry_type='debit',
        )
        assert entry.amount == Decimal('123.4567')

    def test_entry_has_entry_type(self, account, transaction):
        """Entry should have entry_type (debit/credit)."""
        debit = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )
        credit = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='credit',
        )
        assert debit.entry_type == 'debit'
        assert credit.entry_type == 'credit'

    def test_entry_has_description(self, account, transaction):
        """Entry should have optional description."""
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
            description='Line item description',
        )
        assert entry.description == 'Line item description'

    def test_entry_has_effective_at(self, account, transaction):
        """Entry should have effective_at for time semantics."""
        now = timezone.now()
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
            effective_at=now,
        )
        assert entry.effective_at == now

    def test_entry_has_recorded_at(self, account, transaction):
        """Entry should have recorded_at auto-set."""
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )
        assert entry.recorded_at is not None

    def test_entry_has_reverses_fk(self, account, transaction):
        """Entry should have optional reverses FK to another entry."""
        original = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )

        tx2 = Transaction.objects.create(description="Reversal")
        reversal = Entry.objects.create(
            transaction=tx2,
            account=account,
            amount=Decimal('100.00'),
            entry_type='credit',
            reverses=original,
        )
        assert reversal.reverses == original

    def test_entry_reversal_entries_related_name(self, account, transaction):
        """Entry should have reversal_entries related name."""
        original = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )

        tx2 = Transaction.objects.create(description="Reversal")
        reversal = Entry.objects.create(
            transaction=tx2,
            account=account,
            amount=Decimal('100.00'),
            entry_type='credit',
            reverses=original,
        )

        assert reversal in original.reversal_entries.all()

    def test_entry_has_metadata(self, account, transaction):
        """Entry should have metadata JSONField."""
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
            metadata={"line_item": 1, "product_id": "ABC"},
        )
        assert entry.metadata["line_item"] == 1


@pytest.mark.django_db
class TestEntryImmutability:
    """Test suite for entry immutability after posting."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def account(self, org):
        """Create a test account."""
        return Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )

    def test_entry_can_be_modified_before_posting(self, account):
        """Entry should allow modification before transaction is posted."""
        transaction = Transaction.objects.create(description="Test")
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )

        # Should be modifiable
        entry.amount = Decimal('200.00')
        entry.save()  # Should not raise

        entry.refresh_from_db()
        assert entry.amount == Decimal('200.00')

    def test_entry_immutable_after_posting(self, account):
        """Entry should be immutable after transaction is posted."""
        transaction = Transaction.objects.create(description="Test")
        entry = Entry.objects.create(
            transaction=transaction,
            account=account,
            amount=Decimal('100.00'),
            entry_type='debit',
        )

        # Post the transaction
        transaction.posted_at = timezone.now()
        transaction.save()

        # Attempt to modify should raise
        entry.amount = Decimal('200.00')
        with pytest.raises(ImmutableEntryError):
            entry.save()


@pytest.mark.django_db
class TestAccountQuerySet:
    """Test suite for Account queryset methods."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def customer(self, org):
        """Create a test customer."""
        return Customer.objects.create(name="Test Customer", org=org)

    def test_for_owner_returns_accounts(self, org, customer):
        """for_owner() should return accounts for specific owner."""
        org_account = Account.objects.create(
            owner=org,
            account_type='revenue',
            currency='USD',
        )
        customer_account = Account.objects.create(
            owner=customer,
            account_type='receivable',
            currency='USD',
        )

        org_accounts = Account.objects.for_owner(org)
        assert org_accounts.count() == 1
        assert org_account in org_accounts
        assert customer_account not in org_accounts

    def test_by_type_filters_accounts(self, org):
        """by_type() should filter by account_type."""
        Account.objects.create(owner=org, account_type='revenue', currency='USD')
        Account.objects.create(owner=org, account_type='expense', currency='USD')
        Account.objects.create(owner=org, account_type='receivable', currency='USD')

        revenue = Account.objects.by_type('revenue')
        assert revenue.count() == 1

    def test_by_currency_filters_accounts(self, org):
        """by_currency() should filter by currency."""
        Account.objects.create(owner=org, account_type='revenue', currency='USD')
        Account.objects.create(owner=org, account_type='revenue', currency='EUR')
        Account.objects.create(owner=org, account_type='revenue', currency='USD')

        usd_accounts = Account.objects.by_currency('USD')
        assert usd_accounts.count() == 2
