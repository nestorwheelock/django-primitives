"""Sequence model for human-readable IDs."""

from datetime import date
from django.conf import settings
from django.db import models

from django_basemodels import BaseModel


class Sequence(BaseModel):
    """
    Human-readable sequence generator.

    Generates IDs like "INV-2026-000123" for invoices, orders, tickets, etc.
    Each sequence is scoped to an organization for multi-tenant isolation.

    Usage:
        from django_sequence.services import next_sequence

        # Get next invoice number for an org
        invoice_number = next_sequence('invoice', org=my_org)
        # Returns: "INV-2026-000001"
    """

    scope = models.CharField(
        max_length=50,
        help_text="Sequence scope, e.g., 'invoice', 'order', 'ticket'"
    )

    # Organization FK - uses GenericForeignKey pattern for flexibility
    # Can be null for global sequences
    org_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Content type of the organization model"
    )
    org_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of the organization (CharField for UUID support)"
    )

    prefix = models.CharField(
        max_length=20,
        help_text="Prefix for formatted value, e.g., 'INV-', 'ORD-'"
    )

    current_value = models.PositiveBigIntegerField(
        default=0,
        help_text="Current sequence value"
    )

    pad_width = models.PositiveSmallIntegerField(
        default=6,
        help_text="Zero-padding width for the number portion"
    )

    include_year = models.BooleanField(
        default=True,
        help_text="Whether to include the year in the formatted value"
    )

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    class Meta:
        app_label = 'django_sequence'
        unique_together = ['scope', 'org_content_type', 'org_id']
        indexes = [
            models.Index(fields=['scope', 'org_content_type', 'org_id']),
        ]

    def __str__(self):
        org_str = f" (org:{self.org_id})" if self.org_id else " (global)"
        return f"{self.scope}{org_str}: {self.current_value}"

    @property
    def formatted_value(self) -> str:
        """
        Return the current value formatted with prefix, year, and padding.

        Examples:
            - With year: "INV-2026-000123"
            - Without year: "TKT-000042"
        """
        number_str = str(self.current_value).zfill(self.pad_width)

        if self.include_year:
            year = date.today().year
            return f"{self.prefix}{year}-{number_str}"
        else:
            return f"{self.prefix}{number_str}"

    @property
    def org(self):
        """Return the organization object if set."""
        if self.org_content_type and self.org_id:
            model = self.org_content_type.model_class()
            try:
                return model.objects.get(pk=self.org_id)
            except model.DoesNotExist:
                return None
        return None

    @org.setter
    def org(self, value):
        """Set the organization from a model instance."""
        if value is None:
            self.org_content_type = None
            self.org_id = ''
        else:
            from django.contrib.contenttypes.models import ContentType
            self.org_content_type = ContentType.objects.get_for_model(value)
            self.org_id = str(value.pk)
