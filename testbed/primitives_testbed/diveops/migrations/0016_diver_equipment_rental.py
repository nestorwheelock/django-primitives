"""Migration for DiverEquipmentRental model.

Glue model connecting Booking, DiverProfile, and CatalogItem for equipment rental tracking.
"""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diveops", "0015_add_dive_site_to_template"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("django_catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiverEquipmentRental",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "quantity",
                    models.PositiveSmallIntegerField(
                        default=1, help_text="Number of items rented"
                    ),
                ),
                (
                    "unit_cost_amount",
                    models.DecimalField(
                        decimal_places=4,
                        help_text="Shop cost per unit at rental time",
                        max_digits=10,
                    ),
                ),
                (
                    "unit_cost_currency",
                    models.CharField(
                        default="MXN", help_text="Currency for shop cost", max_length=3
                    ),
                ),
                (
                    "unit_charge_amount",
                    models.DecimalField(
                        decimal_places=4,
                        help_text="Customer charge per unit at rental time",
                        max_digits=10,
                    ),
                ),
                (
                    "unit_charge_currency",
                    models.CharField(
                        default="MXN",
                        help_text="Currency for customer charge",
                        max_length=3,
                    ),
                ),
                (
                    "price_rule_id",
                    models.UUIDField(
                        blank=True,
                        help_text="ID of Price rule used for customer charge",
                        null=True,
                    ),
                ),
                (
                    "vendor_agreement_id",
                    models.UUIDField(
                        blank=True,
                        help_text="ID of vendor Agreement used for shop cost",
                        null=True,
                    ),
                ),
                (
                    "item_name_snapshot",
                    models.CharField(
                        help_text="Equipment name at rental time", max_length=200
                    ),
                ),
                (
                    "rented_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="When the rental was created",
                    ),
                ),
                (
                    "booking",
                    models.ForeignKey(
                        help_text="The booking this rental belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipment_rentals",
                        to="diveops.booking",
                    ),
                ),
                (
                    "catalog_item",
                    models.ForeignKey(
                        help_text="The equipment catalog item",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="diveops_rentals",
                        to="django_catalog.catalogitem",
                    ),
                ),
                (
                    "diver",
                    models.ForeignKey(
                        help_text="The diver renting the equipment",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="equipment_rentals",
                        to="diveops.diverprofile",
                    ),
                ),
                (
                    "rented_by",
                    models.ForeignKey(
                        help_text="User who created the rental",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="equipment_rentals_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Diver Equipment Rental",
                "verbose_name_plural": "Diver Equipment Rentals",
            },
        ),
        migrations.AddConstraint(
            model_name="diverequipmentrental",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gt", 0)),
                name="diveops_rental_quantity_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="diverequipmentrental",
            constraint=models.CheckConstraint(
                condition=models.Q(("unit_cost_amount__gte", 0)),
                name="diveops_rental_cost_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="diverequipmentrental",
            constraint=models.CheckConstraint(
                condition=models.Q(("unit_charge_amount__gte", 0)),
                name="diveops_rental_charge_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="diverequipmentrental",
            index=models.Index(
                fields=["booking", "diver"], name="diveops_div_booking_4af8e7_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="diverequipmentrental",
            index=models.Index(
                fields=["rented_at"], name="diveops_div_rented__09a009_idx"
            ),
        ),
    ]
