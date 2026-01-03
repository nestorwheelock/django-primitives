"""Change on_delete from CASCADE to PROTECT for scope foreign keys.

This prevents accidental data loss when deleting organizations, parties,
or agreements that have associated price records.

Before: Deleting an organization would silently delete all its prices.
After: Deleting an organization with prices raises ProtectedError.

This is the safe default for audit-sensitive data. If you need to delete
a scoped entity, you must first either:
1. Delete or reassign its associated prices, or
2. Soft-delete the entity (if supported by the model)
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0002_add_overlap_exclusion_constraint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="price",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                help_text="Payer organization for this price",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="prices",
                to="django_parties.organization",
            ),
        ),
        migrations.AlterField(
            model_name="price",
            name="party",
            field=models.ForeignKey(
                blank=True,
                help_text="Individual person for this price",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="prices",
                to="django_parties.person",
            ),
        ),
        migrations.AlterField(
            model_name="price",
            name="agreement",
            field=models.ForeignKey(
                blank=True,
                help_text="Contract/agreement for this price",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="prices",
                to="django_agreements.agreement",
            ),
        ),
    ]
