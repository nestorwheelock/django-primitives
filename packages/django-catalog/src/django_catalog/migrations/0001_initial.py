# Generated manually for standalone django-catalog package

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from django_catalog.conf import ENCOUNTER_MODEL


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        migrations.swappable_dependency(ENCOUNTER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CatalogItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="deleted at"
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("stock_item", "Stock Item"), ("service", "Service")],
                        db_index=True,
                        help_text="stock_item for physical inventory, service for clinical services",
                        max_length=20,
                        verbose_name="kind",
                    ),
                ),
                (
                    "service_category",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("lab", "Lab"),
                            ("imaging", "Imaging"),
                            ("procedure", "Procedure"),
                            ("consult", "Consultation"),
                            ("vaccine", "Vaccine"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        help_text="For services: determines routing to Lab, Imaging, or Treatment board",
                        max_length=20,
                        verbose_name="service category",
                    ),
                ),
                (
                    "default_stock_action",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("dispense", "Dispense"),
                            ("administer", "Administer"),
                        ],
                        help_text="For stock items: dispense goes to Pharmacy, administer goes to Treatment",
                        max_length=20,
                        verbose_name="default stock action",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        help_text="Name shown to staff and on invoices",
                        max_length=200,
                        verbose_name="display name",
                    ),
                ),
                (
                    "display_name_es",
                    models.CharField(
                        blank=True,
                        help_text="Spanish translation of display name",
                        max_length=200,
                        verbose_name="display name (Spanish)",
                    ),
                ),
                (
                    "is_billable",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this item appears on invoices",
                        verbose_name="is billable",
                    ),
                ),
                (
                    "active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Inactive items cannot be added to baskets",
                        verbose_name="active",
                    ),
                ),
            ],
            options={
                "verbose_name": "catalog item",
                "verbose_name_plural": "catalog items",
                "ordering": ["display_name"],
            },
        ),
        migrations.CreateModel(
            name="Basket",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="deleted at"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("committed", "Committed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                        verbose_name="status",
                    ),
                ),
                (
                    "committed_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="committed at"
                    ),
                ),
                (
                    "committed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="baskets_committed",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="committed by",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="baskets_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="created by",
                    ),
                ),
                (
                    "encounter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="baskets",
                        to=ENCOUNTER_MODEL,
                        verbose_name="encounter",
                    ),
                ),
            ],
            options={
                "verbose_name": "basket",
                "verbose_name_plural": "baskets",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BasketItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="deleted at"
                    ),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(default=1, verbose_name="quantity"),
                ),
                (
                    "stock_action_override",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("dispense", "Dispense"),
                            ("administer", "Administer"),
                        ],
                        help_text="Override default stock action for this item",
                        max_length=20,
                        verbose_name="stock action override",
                    ),
                ),
                (
                    "display_name_snapshot",
                    models.CharField(
                        blank=True,
                        help_text="Snapshot of display_name at commit time",
                        max_length=200,
                        verbose_name="display name (snapshot)",
                    ),
                ),
                (
                    "kind_snapshot",
                    models.CharField(
                        blank=True,
                        help_text="Snapshot of kind at commit time",
                        max_length=20,
                        verbose_name="kind (snapshot)",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Instructions or notes for this item",
                        verbose_name="notes",
                    ),
                ),
                (
                    "added_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="basket_items_added",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="added by",
                    ),
                ),
                (
                    "basket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="django_catalog.basket",
                        verbose_name="basket",
                    ),
                ),
                (
                    "catalog_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="basket_items",
                        to="django_catalog.catalogitem",
                        verbose_name="catalog item",
                    ),
                ),
            ],
            options={
                "verbose_name": "basket item",
                "verbose_name_plural": "basket items",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="WorkItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="deleted at"
                    ),
                ),
                (
                    "spawn_role",
                    models.CharField(
                        default="primary",
                        help_text="Role within basket item spawn (e.g., primary, label, followup)",
                        max_length=50,
                        verbose_name="spawn role",
                    ),
                ),
                (
                    "target_board",
                    models.CharField(
                        choices=[
                            ("treatment", "Treatment"),
                            ("lab", "Lab"),
                            ("pharmacy", "Pharmacy"),
                            ("imaging", "Imaging"),
                            ("admin", "Administrative"),
                            ("outsource", "Outsource"),
                            ("followup", "Follow-up"),
                        ],
                        db_index=True,
                        help_text="Board this work item appears on",
                        max_length=20,
                        verbose_name="target board",
                    ),
                ),
                (
                    "target_lane",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Optional sub-lane within board (e.g., stat, routine)",
                        max_length=50,
                        verbose_name="target lane",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        help_text="Snapshotted from catalog at spawn time",
                        max_length=200,
                        verbose_name="display name",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        help_text="Snapshotted from catalog at spawn time",
                        max_length=20,
                        verbose_name="kind",
                    ),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(default=1, verbose_name="quantity"),
                ),
                ("notes", models.TextField(blank=True, verbose_name="notes")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In Progress"),
                            ("blocked", "Blocked"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="status",
                    ),
                ),
                (
                    "status_detail",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        help_text="Board-specific workflow phase",
                        max_length=50,
                        verbose_name="status detail",
                    ),
                ),
                (
                    "priority",
                    models.PositiveSmallIntegerField(
                        default=50,
                        help_text="Lower = higher priority (0-100)",
                        verbose_name="priority",
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="started at"
                    ),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="completed at"
                    ),
                ),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="work_items_assigned",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="assigned to",
                    ),
                ),
                (
                    "basket_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="work_items",
                        to="django_catalog.basketitem",
                        verbose_name="basket item",
                    ),
                ),
                (
                    "completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="work_items_completed",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="completed by",
                    ),
                ),
                (
                    "encounter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_items",
                        to=ENCOUNTER_MODEL,
                        verbose_name="encounter",
                    ),
                ),
            ],
            options={
                "verbose_name": "work item",
                "verbose_name_plural": "work items",
                "ordering": ["priority", "created_at"],
            },
        ),
        migrations.CreateModel(
            name="DispenseLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="deleted at"
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        help_text="Medication/item name at time of dispensing",
                        max_length=200,
                        verbose_name="display name",
                    ),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(
                        help_text="Quantity dispensed", verbose_name="quantity"
                    ),
                ),
                (
                    "dispensed_at",
                    models.DateTimeField(
                        help_text="When the item was dispensed",
                        verbose_name="dispensed at",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Notes from dispensing (e.g., patient instructions)",
                        verbose_name="notes",
                    ),
                ),
                (
                    "dispensed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dispense_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="dispensed by",
                    ),
                ),
                (
                    "workitem",
                    models.OneToOneField(
                        help_text="Pharmacy WorkItem that was dispensed",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dispense_log",
                        to="django_catalog.workitem",
                        verbose_name="work item",
                    ),
                ),
            ],
            options={
                "verbose_name": "dispense log",
                "verbose_name_plural": "dispense logs",
                "ordering": ["-dispensed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="basket",
            index=models.Index(
                fields=["encounter", "status"], name="django_cata_encount_4fe2e4_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="catalogitem",
            index=models.Index(
                fields=["kind", "active"], name="django_cata_kind_501917_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="workitem",
            index=models.Index(
                fields=["encounter", "status"], name="django_cata_encount_87461a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="workitem",
            index=models.Index(
                fields=["target_board", "status"], name="django_cata_target__faf80e_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="workitem",
            index=models.Index(
                fields=["target_board", "target_lane", "status"],
                name="django_cata_target__321e91_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="workitem",
            constraint=models.UniqueConstraint(
                fields=("basket_item", "spawn_role"),
                name="unique_workitem_per_basketitem_role",
            ),
        ),
    ]
