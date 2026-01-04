"""Primitive integrations for diveops.

This module provides a single location for all primitive package imports,
following the adapter pattern recommended in DEPENDENCIES.md.

Application layers should import primitives through this module,
making dependencies explicit and easier to maintain.

Billing Adapter Functions:
- create_trip_basket(): Create a basket for a booking
- resolve_trip_price(): Resolve price for a trip item
- price_basket_item(): Create PricedBasketItem with resolved price
- create_booking_invoice(): Create invoice from priced basket
"""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

# Identity primitives
from django_parties.models import Organization, Person

# Location primitives
from django_geo.models import Place

# Workflow primitives
from django_encounters.models import Encounter, EncounterDefinition

# Commerce primitives
from django_catalog.models import Basket, BasketItem, CatalogItem

# Legal primitives
from django_agreements.models import Agreement

# Sequence generation
from django_sequence.services import next_sequence

# Invoicing (testbed module built on primitives)
from primitives_testbed.invoicing.models import Invoice, InvoiceLineItem

# Pricing (testbed module)
from primitives_testbed.pricing.models import Price, PricedBasketItem
from primitives_testbed.pricing.selectors import resolve_price
from primitives_testbed.pricing.value_objects import ResolvedPrice

__all__ = [
    # Identity
    "Person",
    "Organization",
    # Location
    "Place",
    # Workflow
    "Encounter",
    "EncounterDefinition",
    # Commerce
    "Basket",
    "BasketItem",
    "CatalogItem",
    # Legal
    "Agreement",
    # Sequence
    "next_sequence",
    # Invoicing
    "Invoice",
    "InvoiceLineItem",
    # Pricing
    "Price",
    "PricedBasketItem",
    "ResolvedPrice",
    # Billing adapter functions
    "create_trip_basket",
    "resolve_trip_price",
    "price_basket_item",
    "create_booking_invoice",
]


# =============================================================================
# Billing Adapter Functions
# =============================================================================


def create_trip_basket(trip, diver, catalog_item, created_by) -> Basket:
    """Create a basket for a dive trip booking.

    Creates a basket with:
    - An encounter for the booking workflow
    - One basket item for the trip

    Args:
        trip: The DiveTrip being booked
        diver: The DiverProfile making the booking
        catalog_item: The CatalogItem representing the trip service
        created_by: User creating the basket

    Returns:
        Created Basket in 'draft' status
    """
    # Get or create dive booking encounter definition
    definition, _ = EncounterDefinition.objects.get_or_create(
        key="dive_booking",
        defaults={
            "name": "Dive Booking",
            "states": ["draft", "confirmed", "completed", "cancelled"],
            "transitions": {
                "draft": ["confirmed", "cancelled"],
                "confirmed": ["completed", "cancelled"],
                "completed": [],
                "cancelled": [],
            },
            "initial_state": "draft",
            "terminal_states": ["completed", "cancelled"],
        },
    )

    # Create encounter for the booking (subject is the diver)
    diver_ct = ContentType.objects.get_for_model(diver)
    encounter = Encounter.objects.create(
        definition=definition,
        subject_type=diver_ct,
        subject_id=str(diver.pk),
        state="draft",
    )

    # Create basket
    basket = Basket.objects.create(
        encounter=encounter,
        status="draft",
        created_by=created_by,
    )

    # Add trip as basket item
    BasketItem.objects.create(
        basket=basket,
        catalog_item=catalog_item,
        quantity=1,
        added_by=created_by,
    )

    return basket


def resolve_trip_price(catalog_item, trip, diver) -> ResolvedPrice:
    """Resolve the price for a dive trip.

    Uses the pricing module's resolution hierarchy:
    1. Agreement-specific (if diver has agreement)
    2. Party-specific (diver's person)
    3. Organization-specific (dive shop)
    4. Global price

    Args:
        catalog_item: The CatalogItem to price
        trip: The DiveTrip (provides organization context)
        diver: The DiverProfile (provides party context)

    Returns:
        ResolvedPrice with unit_price and metadata

    Raises:
        NoPriceFoundError: If no applicable price exists
    """
    return resolve_price(
        catalog_item,
        organization=trip.dive_shop,
        party=diver.person,
        agreement=None,  # Could be extended to check for diver's agreements
    )


def price_basket_item(basket_item, trip, diver) -> PricedBasketItem:
    """Create a PricedBasketItem for a basket item.

    Resolves the price using the pricing module and creates an
    immutable snapshot of the price at resolution time.

    Args:
        basket_item: The BasketItem to price
        trip: The DiveTrip (for price context)
        diver: The DiverProfile (for price context)

    Returns:
        Created PricedBasketItem with resolved price snapshot
    """
    resolved = resolve_trip_price(
        catalog_item=basket_item.catalog_item,
        trip=trip,
        diver=diver,
    )

    return PricedBasketItem.objects.create(
        basket_item=basket_item,
        unit_price_amount=resolved.unit_price.amount,
        unit_price_currency=resolved.unit_price.currency,
        price_rule_id=resolved.price_id,
    )


def create_booking_invoice(basket, trip, diver, created_by) -> Invoice:
    """Create an invoice from a priced basket.

    Commits the basket and creates an invoice with line items
    from the priced basket items.

    Args:
        basket: The Basket with priced items
        trip: The DiveTrip being booked
        diver: The DiverProfile (billed_to party)
        created_by: User creating the invoice

    Returns:
        Created Invoice with line items
    """
    # Commit the basket
    basket.status = "committed"
    basket.committed_by = created_by
    basket.committed_at = timezone.now()
    basket.save()

    # Calculate totals from priced items
    subtotal = Decimal("0")
    currency = "USD"

    for item in basket.items.all():
        if hasattr(item, "priced"):
            subtotal += item.priced.line_total.amount
            currency = item.priced.unit_price_currency

    # Generate invoice number
    invoice_number = next_sequence(
        scope="invoice",
        org=trip.dive_shop,
        prefix="INV-",
        pad_width=4,
        include_year=True,
    )

    # Create invoice
    invoice = Invoice.objects.create(
        basket=basket,
        encounter=basket.encounter,
        billed_to=diver.person,
        issued_by=trip.dive_shop,
        invoice_number=invoice_number,
        status="issued",
        currency=currency,
        subtotal_amount=subtotal,
        tax_amount=Decimal("0"),
        total_amount=subtotal,
        created_by=created_by,
        issued_at=timezone.now(),
    )

    # Create line items from priced basket items
    for item in basket.items.all():
        if hasattr(item, "priced"):
            priced = item.priced
            InvoiceLineItem.objects.create(
                invoice=invoice,
                priced_basket_item=priced,
                description=item.catalog_item.display_name,
                quantity=item.quantity,
                unit_price_amount=priced.unit_price_amount,
                line_total_amount=priced.line_total.amount,
                price_scope_type=priced.price_rule.scope_type,
                price_rule_id=priced.price_rule.pk,
            )

    return invoice
