"""Django Catalog models.

Provides order catalog functionality:
- CatalogItem: Definition layer for orderable items
- Basket: Encounter-scoped container for items before commit
- BasketItem: Items in basket with snapshot on commit
- WorkItem: Spawned executable tasks with board routing
- DispenseLog: Clinical record of pharmacy dispensing
- CatalogSettings: Singleton configuration for catalog behavior
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_basemodels import BaseModel
from django_catalog.conf import ENCOUNTER_MODEL, INVENTORY_ITEM_MODEL, PRESCRIPTION_MODEL
from django_decisioning.querysets import EventAsOfQuerySet
from django_singleton.models import SingletonModel


# =============================================================================
# Base Model Alias (uses django-basemodels)
# =============================================================================

class CatalogBaseModel(BaseModel):
    """Base model for catalog - extends django_basemodels.BaseModel.

    Provides: UUID PK, created_at, updated_at, deleted_at, soft delete.
    """

    class Meta:
        abstract = True


# =============================================================================
# CatalogItem - Definition Layer
# =============================================================================

class CatalogItem(CatalogBaseModel):
    """Minimal unit of orderable definition.

    The Catalog is a definition layer only - it does NOT execute work,
    track encounters, decrement inventory, or perform accounting.
    Items become actionable only when added to a Basket and committed.
    """

    KIND_CHOICES = [
        ('stock_item', _('Stock Item')),
        ('service', _('Service')),
    ]

    SERVICE_CATEGORY_CHOICES = [
        ('lab', _('Lab')),
        ('imaging', _('Imaging')),
        ('procedure', _('Procedure')),
        ('consult', _('Consultation')),
        ('vaccine', _('Vaccine')),
        ('other', _('Other')),
    ]

    STOCK_ACTION_CHOICES = [
        ('dispense', _('Dispense')),
        ('administer', _('Administer')),
    ]

    kind = models.CharField(
        _('kind'),
        max_length=20,
        choices=KIND_CHOICES,
        db_index=True,
        help_text=_('stock_item for physical inventory, service for clinical services'),
    )
    service_category = models.CharField(
        _('service category'),
        max_length=20,
        choices=SERVICE_CATEGORY_CHOICES,
        blank=True,
        db_index=True,
        help_text=_('For services: determines routing to Lab, Imaging, or Treatment board'),
    )
    default_stock_action = models.CharField(
        _('default stock action'),
        max_length=20,
        choices=STOCK_ACTION_CHOICES,
        blank=True,
        help_text=_('For stock items: dispense goes to Pharmacy, administer goes to Treatment'),
    )
    display_name = models.CharField(
        _('display name'),
        max_length=200,
        help_text=_('Name shown to staff and on invoices'),
    )
    display_name_es = models.CharField(
        _('display name (Spanish)'),
        max_length=200,
        blank=True,
        help_text=_('Spanish translation of display name'),
    )
    is_billable = models.BooleanField(
        _('is billable'),
        default=True,
        help_text=_('Whether this item appears on invoices'),
    )
    active = models.BooleanField(
        _('active'),
        default=True,
        db_index=True,
        help_text=_('Inactive items cannot be added to baskets'),
    )

    class Meta:
        verbose_name = _('catalog item')
        verbose_name_plural = _('catalog items')
        ordering = ['display_name']
        indexes = [
            models.Index(fields=['kind', 'active']),
        ]

    def __str__(self):
        return f'{self.display_name} ({self.get_kind_display()})'

    def clean(self):
        """Enforce kind-based constraints."""
        super().clean()
        errors = {}

        # Check for duplicate active display names
        if self.active and self.display_name:
            qs = CatalogItem.objects.filter(
                display_name=self.display_name,
                active=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors['display_name'] = _(
                    'An active catalog item with this name already exists.'
                )

        if errors:
            raise ValidationError(errors)


# Add inventory_item FK only if INVENTORY_ITEM_MODEL is configured
if INVENTORY_ITEM_MODEL:
    CatalogItem.add_to_class(
        'inventory_item',
        models.ForeignKey(
            INVENTORY_ITEM_MODEL,
            on_delete=models.PROTECT,
            null=True,
            blank=True,
            related_name='catalog_items',
            verbose_name=_('inventory item'),
            help_text=_('Required for stock_item kind, must be null for service kind'),
        )
    )


# =============================================================================
# Basket - Encounter-Scoped Container
# =============================================================================

class Basket(CatalogBaseModel):
    """Encounter-scoped container for items before commit.

    - Basket is editable until committed
    - One active basket per encounter at a time
    - On commit, BasketItems are transformed into WorkItems

    Time semantics:
    - effective_at: When the basket was created in business terms (can be backdated)
    - recorded_at: When the system learned about the basket (immutable)
    """

    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('committed', _('Committed')),
        ('cancelled', _('Cancelled')),
    ]

    encounter = models.ForeignKey(
        ENCOUNTER_MODEL,
        on_delete=models.CASCADE,
        related_name='baskets',
        verbose_name=_('encounter'),
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='baskets_created',
        verbose_name=_('created by'),
    )
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='baskets_committed',
        verbose_name=_('committed by'),
    )
    committed_at = models.DateTimeField(
        _('committed at'),
        null=True,
        blank=True,
    )

    effective_at = models.DateTimeField(
        _('effective at'),
        default=timezone.now,
        db_index=True,
        help_text=_('When the basket was created in business terms'),
    )
    recorded_at = models.DateTimeField(
        _('recorded at'),
        auto_now_add=True,
        help_text=_('When the system learned about this basket'),
    )

    objects = EventAsOfQuerySet.as_manager()

    class Meta:
        verbose_name = _('basket')
        verbose_name_plural = _('baskets')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['encounter', 'status']),
            models.Index(fields=['effective_at']),
        ]

    def __str__(self):
        return f"Basket #{self.pk} - Encounter #{self.encounter_id} ({self.status})"

    @property
    def is_editable(self):
        """Basket is only editable in draft status."""
        return self.status == 'draft'


# =============================================================================
# BasketItem - Item in Basket (Pre-Commit)
# =============================================================================

class BasketItem(CatalogBaseModel):
    """Item in a basket, references CatalogItem.

    - BasketItems must reference a CatalogItem
    - CatalogItem identity is snapshotted on commit (display_name_snapshot)
    - No tasks, inventory, or accounting actions occur until commit
    """

    basket = models.ForeignKey(
        Basket,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('basket'),
    )
    catalog_item = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        related_name='basket_items',
        verbose_name=_('catalog item'),
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        default=1,
    )

    stock_action_override = models.CharField(
        _('stock action override'),
        max_length=20,
        choices=CatalogItem.STOCK_ACTION_CHOICES,
        blank=True,
        help_text=_('Override default stock action for this item'),
    )

    # Snapshotted on commit (immutable after)
    display_name_snapshot = models.CharField(
        _('display name (snapshot)'),
        max_length=200,
        blank=True,
        help_text=_('Snapshot of display_name at commit time'),
    )
    kind_snapshot = models.CharField(
        _('kind (snapshot)'),
        max_length=20,
        blank=True,
        help_text=_('Snapshot of kind at commit time'),
    )

    notes = models.TextField(
        _('notes'),
        blank=True,
        help_text=_('Instructions or notes for this item'),
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='basket_items_added',
        verbose_name=_('added by'),
    )

    class Meta:
        verbose_name = _('basket item')
        verbose_name_plural = _('basket items')
        ordering = ['created_at']

    def __str__(self):
        name = self.display_name_snapshot or self.catalog_item.display_name
        return f"{self.quantity}x {name}"

    def get_effective_stock_action(self):
        """Get stock action: override or catalog default."""
        if self.stock_action_override:
            return self.stock_action_override
        return self.catalog_item.default_stock_action


# =============================================================================
# WorkItem - Spawned Executable Task
# =============================================================================

class WorkItem(CatalogBaseModel):
    """Spawned executable task after basket commit.

    - WorkItems spawn only on basket commit
    - Spawning must be idempotent (enforced via unique constraint)
    - Routing is deterministic and stored on creation
    - Inventory decrements only on WorkItem completion

    Idempotency is enforced by the unique constraint on (basket_item, spawn_role).

    Time semantics:
    - effective_at: When the work "happened" in business terms (distinct from started_at)
    - recorded_at: When the system learned about this work item (immutable)
    """

    TARGET_BOARD_CHOICES = [
        ('treatment', _('Treatment')),
        ('lab', _('Lab')),
        ('pharmacy', _('Pharmacy')),
        ('imaging', _('Imaging')),
        ('admin', _('Administrative')),
        ('outsource', _('Outsource')),
        ('followup', _('Follow-up')),
    ]

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('blocked', _('Blocked')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]

    # Origin tracking
    basket_item = models.ForeignKey(
        BasketItem,
        on_delete=models.PROTECT,
        related_name='work_items',
        verbose_name=_('basket item'),
    )
    encounter = models.ForeignKey(
        ENCOUNTER_MODEL,
        on_delete=models.CASCADE,
        related_name='work_items',
        verbose_name=_('encounter'),
    )

    # Idempotency key
    spawn_role = models.CharField(
        _('spawn role'),
        max_length=50,
        default='primary',
        help_text=_('Role within basket item spawn (e.g., primary, label, followup)'),
    )

    # Deterministic routing (set at spawn time, immutable after)
    target_board = models.CharField(
        _('target board'),
        max_length=20,
        choices=TARGET_BOARD_CHOICES,
        db_index=True,
        help_text=_('Board this work item appears on'),
    )
    target_lane = models.CharField(
        _('target lane'),
        max_length=50,
        blank=True,
        db_index=True,
        help_text=_('Optional sub-lane within board (e.g., stat, routine)'),
    )

    # Snapshotted from BasketItem/CatalogItem at spawn time
    display_name = models.CharField(
        _('display name'),
        max_length=200,
        help_text=_('Snapshotted from catalog at spawn time'),
    )
    kind = models.CharField(
        _('kind'),
        max_length=20,
        help_text=_('Snapshotted from catalog at spawn time'),
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        default=1,
    )
    notes = models.TextField(
        _('notes'),
        blank=True,
    )

    # Execution state
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    status_detail = models.CharField(
        _('status detail'),
        max_length=50,
        blank=True,
        default='',
        db_index=True,
        help_text=_('Board-specific workflow phase'),
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_items_assigned',
        verbose_name=_('assigned to'),
    )
    priority = models.PositiveSmallIntegerField(
        _('priority'),
        default=50,
        help_text=_('Lower = higher priority (0-100)'),
    )

    # Workflow timestamps
    started_at = models.DateTimeField(
        _('started at'),
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True,
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_items_completed',
        verbose_name=_('completed by'),
    )

    # Time semantics
    effective_at = models.DateTimeField(
        _('effective at'),
        default=timezone.now,
        db_index=True,
        help_text=_('When the work item was created in business terms'),
    )
    recorded_at = models.DateTimeField(
        _('recorded at'),
        auto_now_add=True,
        help_text=_('When the system learned about this work item'),
    )

    objects = EventAsOfQuerySet.as_manager()

    class Meta:
        verbose_name = _('work item')
        verbose_name_plural = _('work items')
        ordering = ['priority', 'created_at']
        indexes = [
            models.Index(fields=['encounter', 'status']),
            models.Index(fields=['target_board', 'status']),
            models.Index(fields=['target_board', 'target_lane', 'status']),
            models.Index(fields=['effective_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['basket_item', 'spawn_role'],
                name='unique_workitem_per_basketitem_role',
            ),
        ]

    def __str__(self):
        return f"WorkItem #{self.pk}: {self.display_name} ({self.target_board}/{self.status})"


# =============================================================================
# DispenseLog - Clinical Record of Pharmacy Dispensing
# =============================================================================

class DispenseLog(CatalogBaseModel):
    """Clinical record of pharmacy dispensing action.

    - Created when WorkItem(target_board='pharmacy') transitions to 'dispensed'
    - Idempotent: one log per workitem (enforced via OneToOneField)
    - Captures: who dispensed, when, quantity, notes
    - Links to WorkItem for audit trail back to original order
    """

    workitem = models.OneToOneField(
        WorkItem,
        on_delete=models.PROTECT,
        related_name='dispense_log',
        verbose_name=_('work item'),
        help_text=_('Pharmacy WorkItem that was dispensed'),
    )

    display_name = models.CharField(
        _('display name'),
        max_length=200,
        help_text=_('Medication/item name at time of dispensing'),
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        help_text=_('Quantity dispensed'),
    )

    dispensed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='dispense_logs',
        verbose_name=_('dispensed by'),
    )
    dispensed_at = models.DateTimeField(
        _('dispensed at'),
        help_text=_('When the item was dispensed'),
    )

    notes = models.TextField(
        _('notes'),
        blank=True,
        help_text=_('Notes from dispensing (e.g., patient instructions)'),
    )

    class Meta:
        verbose_name = _('dispense log')
        verbose_name_plural = _('dispense logs')
        ordering = ['-dispensed_at']

    def __str__(self):
        return f"Dispensed: {self.display_name} x{self.quantity} ({self.dispensed_at.date()})"


# Add prescription FK only if PRESCRIPTION_MODEL is configured
if PRESCRIPTION_MODEL:
    DispenseLog.add_to_class(
        'prescription',
        models.ForeignKey(
            PRESCRIPTION_MODEL,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name='dispense_logs',
            verbose_name=_('prescription'),
            help_text=_('Optional link to Prescription record'),
        )
    )


# =============================================================================
# CatalogSettings - Singleton Configuration
# =============================================================================

# PRIMITIVES: allow-plain-model
class CatalogSettings(SingletonModel):
    """Singleton configuration for catalog behavior.

    Access via get_catalog_settings() service function.
    """

    default_currency = models.CharField(
        _('default currency'),
        max_length=3,
        default='USD',
        help_text=_('ISO 4217 currency code for pricing'),
    )
    allow_inactive_items = models.BooleanField(
        _('allow inactive items'),
        default=False,
        help_text=_('If True, inactive catalog items can be added to baskets'),
    )
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Optional JSON metadata for custom configuration'),
    )

    class Meta:
        verbose_name = _('catalog settings')
        verbose_name_plural = _('catalog settings')
