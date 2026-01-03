"""Services for check-in module.

Provides functions for:
- Price list snapshots for disclosure
- Creating pricing disclosure agreements
- Checking required consents
"""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_agreements.models import Agreement
from django_agreements.services import create_agreement
from django_catalog.models import CatalogItem

from primitives_testbed.pricing.models import Price


# Required consent types for check-in
REQUIRED_CONSENT_TYPES = [
    "general_consent",
    "hipaa_acknowledgment",
    "financial_responsibility",
    "pricing_disclosure",
]


def get_current_pricelist(organization, *, party=None, as_of=None):
    """Get current prices for all billable catalog items.

    Returns list of price snapshots suitable for agreement terms.

    Args:
        organization: The organization context (currently unused for filtering,
                     but included for future org-specific pricing)
        party: Optional party for party-specific pricing
        as_of: Optional timestamp (defaults to now)

    Returns:
        List of dicts with price information for each billable item
    """
    as_of = as_of or timezone.now()

    # Get all active, billable catalog items
    billable_items = CatalogItem.objects.filter(
        is_billable=True,
        active=True,
    )

    pricelist = []

    for item in billable_items:
        # Find the best current price for this item
        # Priority: party > organization > global
        price = _resolve_price(item, organization, party, as_of)

        if price is not None:
            pricelist.append({
                "catalog_item_id": str(item.pk),
                "catalog_item_name": item.display_name,
                "amount": str(price.amount),
                "currency": price.currency,
                "scope": price.scope_type,
            })

    return pricelist


def _resolve_price(catalog_item, organization, party, as_of):
    """Resolve the best price for a catalog item.

    Resolution priority (highest to lowest):
    1. Party-specific price
    2. Organization-specific price
    3. Global price
    """
    base_qs = Price.objects.filter(catalog_item=catalog_item).current(as_of=as_of)

    # Try party-specific price first
    if party:
        party_price = base_qs.for_party(party).order_by("-priority").first()
        if party_price:
            return party_price

    # Try organization-specific price
    if organization:
        org_price = base_qs.for_organization(organization).order_by("-priority").first()
        if org_price:
            return org_price

    # Fall back to global price
    global_price = base_qs.global_scope().order_by("-priority").first()
    return global_price


def snapshot_prices_for_disclosure(organization, *, party=None):
    """Create the terms dict for a pricing disclosure agreement.

    Args:
        organization: The organization providing services
        party: Optional party for party-specific pricing

    Returns:
        Dict suitable for Agreement.terms
    """
    now = timezone.now()
    prices = get_current_pricelist(organization, party=party, as_of=now)

    return {
        "consent_type": "pricing_disclosure",
        "consent_name": "Price List Acknowledgment",
        "form_version": now.strftime("%Y-%m"),
        "effective_date": now.date().isoformat(),
        "prices": prices,
        "total_items": len(prices),
        "snapshot_at": now.isoformat(),
    }


def create_pricing_disclosure(
    patient,
    organization,
    *,
    signed_by,
    encounter=None,
    valid_for_days=30,
):
    """Create a pricing disclosure agreement.

    Snapshots current prices and creates Agreement with:
    - scope_type="pricing_disclosure"
    - terms containing price snapshot
    - valid_from=now, valid_to=now+valid_for_days
    - Optional scope_ref to encounter

    Args:
        patient: The patient (Person) acknowledging prices
        organization: The organization providing services
        signed_by: User who recorded the consent
        encounter: Optional Encounter to link the disclosure to
        valid_for_days: How long the disclosure is valid (default 30)

    Returns:
        The created Agreement
    """
    now = timezone.now()
    terms = snapshot_prices_for_disclosure(organization, party=patient)

    agreement = create_agreement(
        party_a=patient,
        party_b=organization,
        scope_type="pricing_disclosure",
        terms=terms,
        agreed_by=signed_by,
        valid_from=now,
        valid_to=now + timedelta(days=valid_for_days),
        scope_ref=encounter,
    )

    return agreement


def get_missing_consents(patient, organization):
    """Return list of consent types patient needs to sign.

    Checks for current agreements for each required consent type.

    Args:
        patient: The patient to check
        organization: The organization to check against

    Returns:
        List of consent type strings that are missing
    """
    now = timezone.now()
    patient_ct = ContentType.objects.get_for_model(patient)
    org_ct = ContentType.objects.get_for_model(organization)

    missing = []

    for consent_type in REQUIRED_CONSENT_TYPES:
        # Check for pricing_disclosure specifically
        if consent_type == "pricing_disclosure":
            scope_type = "pricing_disclosure"
        else:
            scope_type = "consent"

        # Find current agreement of this type
        # Using the field names from Agreement model: party_a_id, party_b_id (CharField)
        exists = Agreement.objects.filter(
            party_a_content_type=patient_ct,
            party_a_id=str(patient.pk),
            party_b_content_type=org_ct,
            party_b_id=str(organization.pk),
            valid_from__lte=now,
        ).filter(
            # Check scope type matches
            scope_type=scope_type,
        ).exclude(
            valid_to__lte=now,  # Exclude expired
        )

        # For consent type, also check the terms
        if scope_type == "consent":
            exists = exists.filter(terms__consent_type=consent_type)

        if not exists.exists():
            missing.append(consent_type)

    return missing


def has_valid_pricing_disclosure(patient, organization):
    """Check if patient has a current pricing disclosure.

    Args:
        patient: The patient to check
        organization: The organization to check against

    Returns:
        True if patient has a valid (non-expired) pricing disclosure
    """
    now = timezone.now()
    patient_ct = ContentType.objects.get_for_model(patient)
    org_ct = ContentType.objects.get_for_model(organization)

    return Agreement.objects.filter(
        party_a_content_type=patient_ct,
        party_a_id=str(patient.pk),
        party_b_content_type=org_ct,
        party_b_id=str(organization.pk),
        scope_type="pricing_disclosure",
        valid_from__lte=now,
    ).exclude(
        valid_to__lte=now,  # Exclude expired
    ).exists()
