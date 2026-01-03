"""Views for pricing module - HTML templates and REST API."""

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from django_catalog.models import CatalogItem
from django_parties.models import Organization, Person

from .exceptions import NoPriceFoundError
from .models import Price, PricedBasketItem
from .selectors import explain_price_resolution, list_applicable_prices, resolve_price

User = get_user_model()


# =============================================================================
# HTML Views
# =============================================================================


@require_GET
def price_list(request):
    """List all prices with filtering."""
    prices = Price.objects.select_related(
        "catalog_item", "organization", "party", "agreement", "created_by"
    ).order_by("-created_at")

    # Filter by scope
    scope = request.GET.get("scope")
    if scope == "global":
        prices = prices.filter(
            organization__isnull=True, party__isnull=True, agreement__isnull=True
        )
    elif scope == "organization":
        prices = prices.filter(organization__isnull=False)
    elif scope == "party":
        prices = prices.filter(party__isnull=False)
    elif scope == "agreement":
        prices = prices.filter(agreement__isnull=False)

    # Filter by active/expired
    status = request.GET.get("status")
    now = timezone.now()
    if status == "active":
        prices = prices.filter(valid_from__lte=now).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=now)
        )
    elif status == "expired":
        prices = prices.filter(valid_to__lt=now)
    elif status == "future":
        prices = prices.filter(valid_from__gt=now)

    context = {
        "prices": prices[:100],
        "total_count": prices.count(),
        "catalog_items": CatalogItem.objects.filter(active=True).order_by("display_name"),
        "organizations": Organization.objects.all().order_by("name"),
    }
    return render(request, "pricing/price_list.html", context)


@require_GET
def price_resolver(request):
    """Interactive price resolution tool."""
    catalog_items = CatalogItem.objects.filter(active=True).order_by("display_name")
    organizations = Organization.objects.all().order_by("name")
    persons = Person.objects.all().order_by("last_name", "first_name")

    context = {
        "catalog_items": catalog_items,
        "organizations": organizations,
        "persons": persons,
    }
    return render(request, "pricing/resolver.html", context)


# =============================================================================
# REST API Views
# =============================================================================


@require_GET
def api_prices(request):
    """API: List all prices."""
    prices = Price.objects.select_related(
        "catalog_item", "organization", "party", "created_by"
    ).order_by("-created_at")[:100]

    data = [
        {
            "id": str(p.pk),
            "catalog_item": p.catalog_item.display_name,
            "catalog_item_id": str(p.catalog_item.pk),
            "amount": str(p.amount),
            "currency": p.currency,
            "scope_type": p.scope_type,
            "organization": p.organization.name if p.organization else None,
            "party": f"{p.party.first_name} {p.party.last_name}" if p.party else None,
            "priority": p.priority,
            "valid_from": p.valid_from.isoformat(),
            "valid_to": p.valid_to.isoformat() if p.valid_to else None,
            "created_by": p.created_by.username if p.created_by else None,
        }
        for p in prices
    ]
    return JsonResponse({"prices": data})


@csrf_exempt
@require_POST
def api_price_create(request):
    """API: Create a new price."""
    try:
        body = json.loads(request.body)

        catalog_item_id = body.get("catalog_item_id")
        catalog_item = get_object_or_404(CatalogItem, pk=catalog_item_id)

        amount = Decimal(body.get("amount", "0"))
        currency = body.get("currency", "USD")
        priority = int(body.get("priority", 50))

        # Optional scope
        organization = None
        if body.get("organization_id"):
            organization = get_object_or_404(Organization, pk=body["organization_id"])

        party = None
        if body.get("party_id"):
            party = get_object_or_404(Person, pk=body["party_id"])

        # Dates
        valid_from = body.get("valid_from")
        if valid_from:
            from django.utils.dateparse import parse_datetime
            valid_from = parse_datetime(valid_from) or timezone.now()
        else:
            valid_from = timezone.now()

        valid_to = None
        if body.get("valid_to"):
            from django.utils.dateparse import parse_datetime
            valid_to = parse_datetime(body["valid_to"])

        # Get creator (use first staff user for demo)
        creator = User.objects.filter(is_staff=True).first()
        if not creator:
            creator = User.objects.first()

        price = Price.objects.create(
            catalog_item=catalog_item,
            amount=amount,
            currency=currency,
            organization=organization,
            party=party,
            priority=priority,
            valid_from=valid_from,
            valid_to=valid_to,
            created_by=creator,
            reason=body.get("reason", ""),
        )

        return JsonResponse(
            {
                "id": str(price.pk),
                "created": True,
                "scope_type": price.scope_type,
            },
            status=201,
        )
    except InvalidOperation:
        return JsonResponse({"error": "Invalid amount"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_GET
def api_resolve_price(request):
    """API: Resolve price for a catalog item."""
    catalog_item_id = request.GET.get("catalog_item_id")
    if not catalog_item_id:
        return JsonResponse({"error": "catalog_item_id required"}, status=400)

    catalog_item = get_object_or_404(CatalogItem, pk=catalog_item_id)

    # Optional scope filters
    organization = None
    if request.GET.get("organization_id"):
        organization = get_object_or_404(Organization, pk=request.GET["organization_id"])

    party = None
    if request.GET.get("party_id"):
        party = get_object_or_404(Person, pk=request.GET["party_id"])

    try:
        resolved = resolve_price(
            catalog_item,
            organization=organization,
            party=party,
        )

        return JsonResponse({
            "resolved": True,
            "unit_price": {
                "amount": str(resolved.unit_price.amount),
                "currency": resolved.unit_price.currency,
            },
            "price_id": str(resolved.price_id),
            "scope_type": resolved.scope_type,
            "priority": resolved.priority,
            "explanation": resolved.explain(),
        })
    except NoPriceFoundError as e:
        return JsonResponse({
            "resolved": False,
            "error": str(e),
        }, status=404)


@require_GET
def api_explain_price(request):
    """API: Explain price resolution for debugging."""
    catalog_item_id = request.GET.get("catalog_item_id")
    if not catalog_item_id:
        return JsonResponse({"error": "catalog_item_id required"}, status=400)

    catalog_item = get_object_or_404(CatalogItem, pk=catalog_item_id)

    # Optional scope filters
    organization = None
    if request.GET.get("organization_id"):
        organization = get_object_or_404(Organization, pk=request.GET["organization_id"])

    party = None
    if request.GET.get("party_id"):
        party = get_object_or_404(Person, pk=request.GET["party_id"])

    explanation = explain_price_resolution(
        catalog_item,
        organization=organization,
        party=party,
    )

    return JsonResponse(explanation)
