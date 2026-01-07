"""Account, Transaction, and Entry models for double-entry ledger."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel
from django_ledger.exceptions import ImmutableEntryError, InactiveAccountError


class AccountQuerySet(models.QuerySet):
    """Custom queryset for Account model."""

    def active(self):
        """Return only active accounts."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive accounts."""
        return self.filter(is_active=False)

    def for_owner(self, owner):
        """Return accounts for the given owner."""
        content_type = ContentType.objects.get_for_model(owner)
        return self.filter(
            owner_content_type=content_type,
            owner_id=str(owner.pk),
        )

    def by_type(self, account_type):
        """Return accounts of the specified type."""
        return self.filter(account_type=account_type)

    def by_currency(self, currency):
        """Return accounts with the specified currency."""
        return self.filter(currency=currency)


class Account(BaseModel):
    """
    Ledger account model.

    Tracks balances for owners with currency isolation.

    Usage:
        account = Account.objects.create(
            owner=customer,
            account_type='receivable',
            currency='USD',
        )
    """

    # Owner via GenericFK - CharField for UUID support
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        help_text="Content type of the account owner",
    )
    owner_id = models.CharField(
        max_length=255,
        help_text="ID of the account owner (CharField for UUID support)",
    )
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    account_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        db_index=True,
        help_text="Account number for accounting standards (e.g., 1000, 2000)",
    )
    account_type = models.CharField(
        max_length=50,
        help_text="Account type (receivable, payable, revenue, expense, etc.)",
    )
    currency = models.CharField(
        max_length=3,
        help_text="ISO currency code (USD, EUR, etc.)",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Optional account name",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this account is active. Inactive accounts cannot receive new entries.",
    )

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    objects = AccountQuerySet.as_manager()

    class Meta:
        app_label = 'django_ledger'
        indexes = [
            models.Index(fields=['owner_content_type', 'owner_id']),
            models.Index(fields=['account_type']),
            models.Index(fields=['currency']),
        ]

    def save(self, *args, **kwargs):
        """Ensure owner_id is always stored as string."""
        if self.owner_id is not None:
            self.owner_id = str(self.owner_id)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.account_number:
            return f"{self.account_number} - {self.name or self.account_type} ({self.currency})"
        return f"{self.name or self.account_type} ({self.currency})"


# PRIMITIVES: allow-plain-model
class Transaction(models.Model):
    """
    Transaction model that groups balanced entries.

    A transaction is created first, then entries are attached to it.
    The transaction is posted when all entries balance.

    Usage:
        tx = Transaction.objects.create(description="Invoice #123")
        # Add entries...
        tx.post()  # Validates balance and marks posted
    """

    description = models.TextField(
        blank=True,
        default='',
        help_text="Transaction description",
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the transaction was posted (null = draft)",
    )

    # Time semantics
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the transaction is effective (business time)",
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the transaction was recorded (system time)",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata",
    )

    class Meta:
        app_label = 'django_ledger'
        ordering = ['-effective_at', '-recorded_at']

    def __str__(self):
        status = "posted" if self.is_posted else "draft"
        return f"Transaction ({status}): {self.description[:50]}"

    @property
    def is_posted(self) -> bool:
        """Check if the transaction has been posted."""
        return self.posted_at is not None


# PRIMITIVES: allow-plain-model
class Entry(models.Model):
    """
    Immutable ledger entry.

    Entries are attached to a transaction and become immutable once
    the transaction is posted.

    Usage:
        entry = Entry.objects.create(
            transaction=tx,
            account=revenue_account,
            amount=Decimal('100.00'),
            entry_type='credit',
        )
    """

    class EntryType(models.TextChoices):
        DEBIT = 'debit', 'Debit'
        CREDIT = 'credit', 'Credit'

    # Transaction FK (not M2M)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name='entries',
        help_text="The transaction this entry belongs to",
    )

    # Account FK
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='entries',
        help_text="The account affected by this entry",
    )

    # Amount with internal precision
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        help_text="Entry amount (internal precision)",
    )

    # Entry type
    entry_type = models.CharField(
        max_length=10,
        choices=EntryType.choices,
        help_text="Debit or credit",
    )

    # Optional description
    description = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Line item description",
    )

    # Time semantics
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the entry is effective (business time)",
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the entry was recorded (system time)",
    )

    # Reversal tracking - ONE direction only
    reverses = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='reversal_entries',
        help_text="The entry this reverses (if this is a reversal)",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata",
    )

    class Meta:
        app_label = 'django_ledger'
        ordering = ['-effective_at', '-recorded_at']
        constraints = [
            # Amount must be positive - use entry_type for direction
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="entry_amount_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        """Enforce immutability after transaction is posted and check account is active."""
        if self.pk and self.transaction.is_posted:
            raise ImmutableEntryError(
                f"Cannot modify entry {self.pk} - transaction is posted. "
                "Create a reversal instead."
            )
        # Prevent new entries on inactive accounts
        if not self.pk and self.account and not self.account.is_active:
            raise InactiveAccountError(
                f"Cannot create entry on inactive account '{self.account}'. "
                "Reactivate the account first."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry_type} {self.amount} to {self.account}"
