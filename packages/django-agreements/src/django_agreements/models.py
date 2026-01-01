"""Agreement and AgreementVersion models."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AgreementQuerySet(models.QuerySet):
    """Custom queryset for Agreement model."""

    def for_party(self, party):
        """Return agreements where the given object is either party."""
        content_type = ContentType.objects.get_for_model(party)
        party_id = str(party.pk)
        return self.filter(
            models.Q(party_a_content_type=content_type, party_a_id=party_id) |
            models.Q(party_b_content_type=content_type, party_b_id=party_id)
        )

    def current(self):
        """Return currently valid agreements."""
        return self.as_of(timezone.now())

    def as_of(self, timestamp):
        """Return agreements valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )


class Agreement(models.Model):
    """
    Agreement between two parties.

    Tracks agreements, contracts, or consents between parties with
    effective dating and version history.

    Usage:
        agreement = Agreement.objects.create(
            party_a=vendor,
            party_b=customer,
            scope_type='service_contract',
            terms={'duration': '12 months', 'value': 10000},
            agreed_at=timezone.now(),
            agreed_by=request.user,
        )
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

    # Terms
    terms = models.JSONField(
        help_text="Agreement terms and conditions",
    )

    # Effective dating
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

    # Optimistic locking
    version = models.PositiveIntegerField(
        default=1,
        help_text="Version for optimistic locking",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AgreementQuerySet.as_manager()

    class Meta:
        app_label = 'django_agreements'
        indexes = [
            models.Index(fields=['party_a_content_type', 'party_a_id']),
            models.Index(fields=['party_b_content_type', 'party_b_id']),
            models.Index(fields=['scope_type']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Ensure IDs are strings and set valid_from default."""
        if self.party_a_id is not None:
            self.party_a_id = str(self.party_a_id)
        if self.party_b_id is not None:
            self.party_b_id = str(self.party_b_id)
        if self.scope_ref_id:
            self.scope_ref_id = str(self.scope_ref_id)
        if not self.valid_from:
            self.valid_from = self.agreed_at or timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Agreement ({self.scope_type}) - v{self.version}"

    @property
    def is_active(self) -> bool:
        """Check if the agreement is currently active."""
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now >= self.valid_to:
            return False
        return True


class AgreementVersion(models.Model):
    """
    Append-only version history for agreement amendments.

    Each amendment creates a new version with the updated terms.
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
        help_text="Terms snapshot for this version",
    )
    created_at = models.DateTimeField(auto_now_add=True)
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
        unique_together = ['agreement', 'version']
        ordering = ['-version']

    def __str__(self):
        return f"Agreement {self.agreement.pk} - v{self.version}"
