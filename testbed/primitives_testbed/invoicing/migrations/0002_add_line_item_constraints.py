"""Add data integrity constraints for InvoiceLineItem.

P0 fixes:
1. quantity must be > 0 (PositiveIntegerField allows 0)
2. line_total_amount must equal quantity * unit_price_amount

These constraints ensure:
- No zero-quantity line items (meaningless billing records)
- Calculated totals cannot drift from their source values
"""

from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0001_initial"),
    ]

    operations = [
        # Constraint 1: quantity must be positive (> 0, not >= 0)
        migrations.AddConstraint(
            model_name="invoicelineitem",
            constraint=models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="invoicelineitem_quantity_positive",
            ),
        ),
        # Constraint 2: line_total must equal quantity * unit_price
        # This ensures the calculated value cannot drift from its components
        migrations.AddConstraint(
            model_name="invoicelineitem",
            constraint=models.CheckConstraint(
                condition=Q(line_total_amount=F("quantity") * F("unit_price_amount")),
                name="invoicelineitem_total_equals_qty_times_price",
            ),
        ),
    ]
