"""Models for the pricing module.

Provides Price and PricedBasketItem models for flexible, auditable pricing.

## Production Safety Features

This module implements several database-level safeguards to ensure data integrity:

### 1. Overlap Prevention (PostgreSQL Exclusion Constraint)

**Problem**: Without database enforcement, two concurrent transactions can create
prices with overlapping date ranges for the same (catalog_item + scope), leading
to ambiguous price resolution and data corruption.

**Solution**: PostgreSQL exclusion constraint (migration 0002) that atomically
rejects overlapping prices at the database level.

```sql
ALTER TABLE pricing_price
ADD CONSTRAINT price_no_overlapping_date_ranges
EXCLUDE USING GIST (
    catalog_item_id WITH =,
    COALESCE(organization_id, '00000000-...'::uuid) WITH =,
    COALESCE(party_id, '00000000-...'::uuid) WITH =,
    COALESCE(agreement_id, '00000000-...'::uuid) WITH =,
    tstzrange(valid_from, valid_to, '[)') WITH &&
);
```

**Key design decisions**:
- Uses `btree_gist` extension for combining equality and range operators
- Uses `COALESCE` to normalize NULL scopes to a sentinel UUID (because NULL != NULL
  in PostgreSQL would defeat the constraint)
- Uses `tstzrange` with `'[)'` bounds (inclusive start, exclusive end) for
  standard temporal semantics
- NULL `valid_to` is treated as infinity (open-ended range)

**Why DB enforcement is required**:
Python-level validation in `Price.clean()` is susceptible to race conditions.
Two transactions can both pass validation simultaneously, then both insert,
creating overlapping prices. Only a database constraint guarantees atomicity.

### 2. PROTECT on Scope Foreign Keys

**Problem**: CASCADE delete on organization/party/agreement FKs would silently
delete price records when their scope entity is deleted, causing data loss in
audit-sensitive pricing data.

**Solution**: Changed `on_delete` from CASCADE to PROTECT (migration 0003).
Attempting to delete an organization/party/agreement that has associated prices
now raises `ProtectedError`.

**Note**: Since Organization, Person, and Agreement use soft delete by default,
PROTECT only triggers when calling `hard_delete()`. Soft delete (setting
`deleted_at`) works normally and does not trigger PROTECT.

### 3. Price Resolution Hierarchy

Prices are resolved in this order (first match wins):
1. Agreement-specific (agreement field is set)
2. Party-specific (party field is set, agreement is NULL)
3. Organization-specific (organization field is set, party/agreement NULL)
4. Global (all scope fields NULL)

Within each scope level, higher `priority` wins, then more recent `valid_from`.

The canonical resolution function is `pricing.selectors.resolve_price()`.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from django_money import Money


class PriceQuerySet(models.QuerySet):
    """Custom queryset for Price model."""

    def current(self, as_of=None):
        """Filter to prices that are currently valid."""
        check_time = as_of or timezone.now()
        return self.filter(
            valid_from__lte=check_time,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gt=check_time))

    def for_catalog_item(self, catalog_item):
        """Filter to prices for a specific catalog item."""
        return self.filter(catalog_item=catalog_item)

    def global_scope(self):
        """Filter to prices with no scope (global prices)."""
        return self.filter(
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
        )

    def for_organization(self, organization):
        """Filter to prices scoped to an organization."""
        return self.filter(organization=organization)

    def for_party(self, party):
        """Filter to prices scoped to a party."""
        return self.filter(party=party)

    def for_agreement(self, agreement):
        """Filter to prices scoped to an agreement."""
        return self.filter(agreement=agreement)


class Price(models.Model):
    """A price for a catalog item, optionally scoped and time-bounded.

    Resolution priority (higher scope = higher priority):
    1. Agreement-specific (agreement is not null)
    2. Party-specific (party is not null, agreement is null)
    3. Organization-specific (organization is not null, party/agreement is null)
    4. Global (all scope fields null)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # What is being priced
    catalog_item = models.ForeignKey(
        "django_catalog.CatalogItem",
        on_delete=models.PROTECT,
        related_name="prices",
    )

    # The price itself
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")

    # Optional scoping (more specific = higher priority)
    # NOTE: PROTECT prevents accidental data loss when deleting scoped entities.
    # Delete or reassign prices before deleting their organization/party/agreement.
    organization = models.ForeignKey(
        "django_parties.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prices",
        help_text="Payer organization for this price",
    )
    party = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prices",
        help_text="Individual person for this price",
    )
    agreement = models.ForeignKey(
        "django_agreements.Agreement",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prices",
        help_text="Contract/agreement for this price",
    )

    # Effective dating
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="NULL means indefinite (no end date)",
    )

    # Priority for tie-breaking (higher = preferred)
    priority = models.PositiveIntegerField(
        default=50,
        help_text="Higher priority wins when multiple prices match",
    )

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(
        blank=True,
        help_text="Why this price exists (e.g., 'Preferred payer rate', 'VIP discount')",
    )

    objects = PriceQuerySet.as_manager()

    class Meta:
        ordering = ["-priority", "-valid_from"]
        constraints = [
            # Amount must be positive
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="price_amount_positive",
            ),
            # valid_to must be after valid_from (if set)
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=models.F("valid_from")),
                name="price_valid_to_after_valid_from",
            ),
        ]

    def __str__(self):
        scope = self._get_scope_description()
        return f"{self.catalog_item}: {self.money} ({scope})"

    @property
    def money(self) -> Money:
        """Return the price as a Money value object."""
        return Money(self.amount, self.currency)

    @property
    def scope_type(self) -> str:
        """Return the scope type for this price."""
        if self.agreement_id:
            return "agreement"
        if self.party_id:
            return "party"
        if self.organization_id:
            return "organization"
        return "global"

    @property
    def scope_id(self):
        """Return the scope object's ID."""
        if self.agreement_id:
            return self.agreement_id
        if self.party_id:
            return self.party_id
        if self.organization_id:
            return self.organization_id
        return None

    def _get_scope_description(self) -> str:
        """Human-readable scope description."""
        if self.agreement_id:
            return f"agreement:{self.agreement_id}"
        if self.party_id:
            return f"party:{self.party_id}"
        if self.organization_id:
            return f"org:{self.organization_id}"
        return "global"

    def clean(self):
        """Validate the price before saving."""
        from django.core.exceptions import ValidationError

        # Check for overlapping prices in the same scope
        overlapping = self._find_overlapping_prices()
        if overlapping.exists():
            raise ValidationError(
                f"Price overlaps with existing price(s) in the same scope: "
                f"{list(overlapping.values_list('id', flat=True))}"
            )

    def save(self, *args, **kwargs):
        """Save with overlap validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    def _find_overlapping_prices(self):
        """Find prices that would overlap with this one in the same scope."""
        qs = Price.objects.filter(catalog_item=self.catalog_item)

        # Match the exact scope
        if self.agreement_id:
            qs = qs.filter(agreement_id=self.agreement_id)
        else:
            qs = qs.filter(agreement__isnull=True)

        if self.party_id:
            qs = qs.filter(party_id=self.party_id)
        else:
            qs = qs.filter(party__isnull=True)

        if self.organization_id:
            qs = qs.filter(organization_id=self.organization_id)
        else:
            qs = qs.filter(organization__isnull=True)

        # Exclude self if updating
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        # Check date range overlap
        # Two ranges [A, B) and [C, D) overlap if A < D and C < B
        # For open-ended ranges (NULL valid_to), treat as infinity
        if self.valid_to:
            # This price has an end date
            qs = qs.filter(valid_from__lt=self.valid_to)
        # else: this price goes to infinity, so any price starting before infinity overlaps

        # Other price must start before this one ends (or have no end)
        qs = qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gt=self.valid_from))

        return qs


class PricedBasketItem(models.Model):
    """Stores the resolved price for a basket item.

    This model extends BasketItem (from django-catalog primitive) without
    modifying it, following the principle of not touching primitives.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to the basket item (OneToOne - each basket item has at most one price)
    basket_item = models.OneToOneField(
        "django_catalog.BasketItem",
        on_delete=models.CASCADE,
        related_name="priced",
    )

    # Snapshot of the resolved price at the time of adding to basket
    unit_price_amount = models.DecimalField(max_digits=10, decimal_places=4)
    unit_price_currency = models.CharField(max_length=3, default="USD")

    # Reference to the price rule that was applied
    price_rule = models.ForeignKey(
        Price,
        on_delete=models.PROTECT,
        related_name="priced_items",
        help_text="The Price record that determined this unit price",
    )

    # When the price was resolved
    resolved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Priced Basket Item"
        verbose_name_plural = "Priced Basket Items"

    def __str__(self):
        return f"{self.basket_item}: {self.unit_price}"

    @property
    def unit_price(self) -> Money:
        """Return the unit price as a Money value object."""
        return Money(self.unit_price_amount, self.unit_price_currency)

    @property
    def line_total(self) -> Money:
        """Calculate line total (unit_price * quantity)."""
        total_amount = self.unit_price_amount * self.basket_item.quantity
        return Money(total_amount, self.unit_price_currency)
