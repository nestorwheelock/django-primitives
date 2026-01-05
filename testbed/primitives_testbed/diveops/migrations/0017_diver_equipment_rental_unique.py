"""Add unique constraint for DiverEquipmentRental.

Prevents duplicate equipment rentals for the same diver/item on a booking.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diveops", "0016_diver_equipment_rental"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="diverequipmentrental",
            constraint=models.UniqueConstraint(
                fields=["booking", "diver", "catalog_item"],
                condition=models.Q(deleted_at__isnull=True),
                name="diveops_rental_unique_per_booking",
            ),
        ),
    ]
