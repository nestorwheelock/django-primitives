"""Validators for check-in module.

Provides validation functions for invoices against pricing disclosures.
"""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from django_agreements.models import Agreement


def validate_invoice_against_disclosure(invoice):
    """Check if invoice prices match disclosed prices.

    Finds the pricing disclosure for the encounter and compares
    each line item's unit price against the disclosed price.

    Args:
        invoice: The Invoice to validate

    Returns:
        List of discrepancy descriptions (empty = all prices match)
    """
    # Find the pricing disclosure for this encounter
    disclosure = _find_disclosure_for_invoice(invoice)

    if disclosure is None:
        # No disclosure to validate against
        return []

    # Build a lookup of disclosed prices by catalog item ID
    disclosed_prices = {}
    for price_entry in disclosure.terms.get("prices", []):
        item_id = price_entry.get("catalog_item_id")
        if item_id:
            disclosed_prices[item_id] = {
                "amount": Decimal(price_entry.get("amount", "0")),
                "currency": price_entry.get("currency", "USD"),
            }

    discrepancies = []

    # Check each line item
    for line_item in invoice.line_items.all():
        # Get catalog item ID from the priced basket item
        catalog_item_id = str(
            line_item.priced_basket_item.basket_item.catalog_item_id
        )

        if catalog_item_id in disclosed_prices:
            disclosed = disclosed_prices[catalog_item_id]
            disclosed_amount = disclosed["amount"]

            # Compare prices
            if line_item.unit_price_amount > disclosed_amount:
                item_name = line_item.description
                discrepancies.append(
                    f"{item_name}: invoiced {line_item.unit_price_amount} "
                    f"exceeds disclosed {disclosed_amount}"
                )

    return discrepancies


def _find_disclosure_for_invoice(invoice):
    """Find the pricing disclosure for an invoice.

    Looks for a pricing_disclosure agreement linked to the same encounter.

    Args:
        invoice: The Invoice to find disclosure for

    Returns:
        Agreement or None
    """
    encounter = invoice.encounter
    encounter_ct = ContentType.objects.get_for_model(encounter)

    # Find disclosure linked to this encounter
    # Using the field name from Agreement model: scope_ref_id (CharField)
    disclosure = Agreement.objects.filter(
        scope_type="pricing_disclosure",
        scope_ref_content_type=encounter_ct,
        scope_ref_id=str(encounter.pk),
    ).first()

    return disclosure
