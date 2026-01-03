"""Agreement and AgreementVersion models.

Agreements are temporal facts about legal relationships between parties.
This is a ledger, not a workflow engine.

Write through services only:
- create_agreement()
- amend_agreement()
- terminate_agreement()
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

from django_basemodels import BaseModel, SoftDeleteManager

from .exceptions import ImmutableVersionError


class AgreementQuerySet(models.QuerySet):
    """Custom queryset for Agreement model."""

    def for_party(self, party):
        """Return agreements where the given object is either party."""
        content_type = ContentType.objects.get_for_model(party)
        party_id = str(party.pk)
        return self.filter(
            Q(party_a_content_type=content_type, party_a_id=party_id) |
            Q(party_b_content_type=content_type, party_b_id=party_id)
        )

    def current(self):
        """Return currently valid agreements."""
        return self.as_of(timezone.now())

    def as_of(self, timestamp):
        """Return agreements valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=timestamp)
        )


class AgreementManager(SoftDeleteManager):
    """Manager combining soft-delete filtering with custom queryset."""

    def get_queryset(self):
        return AgreementQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)

    def for_party(self, party):
        return self.get_queryset().for_party(party)

    def current(self):
        return self.get_queryset().current()

    def as_of(self, timestamp):
        return self.get_queryset().as_of(timestamp)


class Agreement(BaseModel):
    """
    Agreement between two parties.

    This is a temporal fact store, not a workflow engine.
    Agreements are append-only: amendments create versions, they don't overwrite.

    Fields:
    - party_a, party_b: The parties to the agreement (GenericFK)
    - scope_type: What kind of agreement (order, subscription, consent, etc.)
    - scope_ref: Optional reference to what the agreement is about (GenericFK)
    - terms: Current terms (JSON) - updated on amend, projection of latest version
    - valid_from: When the agreement becomes effective (REQUIRED)
    - valid_to: When the agreement expires (null = indefinite)
    - agreed_at: When the agreement was made
    - agreed_by: Who made the agreement
    - current_version: Denormalized version counter (synced by services)

    Write through services only:
        from django_agreements.services import create_agreement, amend_agreement

    Query examples:
        Agreement.objects.for_party(customer).current()
        Agreement.objects.as_of(some_date)
    """

    # Party A - GenericFK with CharField for UUID support
    party_a_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Content type of party A",
    )
    party_a_id = models.CharField(
        max_length=255,
        help_text="ID of party A (CharField for UUID support)",
    )
    party_a = GenericForeignKey('party_a_content_type', 'party_a_id')

    # Party B - GenericFK with CharField for UUID support
    party_b_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='+',
        help_text="Content type of party B",
    )
    party_b_id = models.CharField(
        max_length=255,
        help_text="ID of party B (CharField for UUID support)",
    )
    party_b = GenericForeignKey('party_b_content_type', 'party_b_id')

    # Scope
    scope_type = models.CharField(
        max_length=50,
        help_text="Agreement type (order, subscription, consent, etc.)",
    )
    scope_ref_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        help_text="Content type of the scope reference",
    )
    scope_ref_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="ID of the scope reference",
    )
    scope_ref = GenericForeignKey('scope_ref_content_type', 'scope_ref_id')

    # Terms - current projection (updated on amend)
    terms = models.JSONField(
        help_text="Current agreement terms (projection of latest version)",
    )

    # Effective dating - valid_from is REQUIRED, no defaults
    valid_from = models.DateTimeField(
        help_text="When the agreement becomes effective",
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the agreement expires (null = indefinite)",
    )

    # Decision surface fields
    agreed_at = models.DateTimeField(
        help_text="When the agreement was made",
    )
    agreed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='agreements_made',
        help_text="User who made the agreement",
    )

    # Version counter - denormalized, synced by services
    current_version = models.PositiveIntegerField(
        default=1,
        help_text="Current version (synced with max AgreementVersion.version)",
    )

    # Managers
    objects = AgreementManager()
    all_objects = models.Manager()

    class Meta:
        app_label = 'django_agreements'
        indexes = [
            models.Index(fields=['party_a_content_type', 'party_a_id']),
            models.Index(fields=['party_b_content_type', 'party_b_id']),
            models.Index(fields=['scope_type']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')),
                name='agreements_valid_to_after_valid_from'
            ),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Ensure GenericFK IDs are strings."""
        # String coercion for GenericFK IDs (valid, prevents type errors)
        if self.party_a_id is not None:
            self.party_a_id = str(self.party_a_id)
        if self.party_b_id is not None:
            self.party_b_id = str(self.party_b_id)
        if self.scope_ref_id:
            self.scope_ref_id = str(self.scope_ref_id)
        # NO defaults for valid_from - that's service layer responsibility
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Agreement ({self.scope_type}) - v{self.current_version}"

    @property
    def is_active(self) -> bool:
        """Check if the agreement is currently active."""
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now >= self.valid_to:
            return False
        return True


class AgreementVersion(BaseModel):
    """
    Immutable version history for agreement amendments.

    This is the ledger. Never modified after creation.
    Each amendment creates a new version with the updated terms.

    Invariant: Agreement.current_version == max(AgreementVersion.version)
    """

    agreement = models.ForeignKey(
        Agreement,
        on_delete=models.CASCADE,
        related_name='versions',
        help_text="The agreement this version belongs to",
    )
    version = models.PositiveIntegerField(
        help_text="Version number",
    )
    terms = models.JSONField(
        help_text="Terms snapshot for this version (immutable)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        help_text="User who created this version",
    )
    reason = models.TextField(
        help_text="Reason for this version/amendment",
    )

    class Meta:
        app_label = 'django_agreements'
        constraints = [
            models.UniqueConstraint(
                fields=['agreement', 'version'],
                name='unique_agreement_version'
            ),
        ]
        ordering = ['-version']

    def save(self, *args, **kwargs):
        """Enforce immutability - versions are ledger records."""
        if not self._state.adding:
            raise ImmutableVersionError(self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Agreement {self.agreement_id} - v{self.version}"
