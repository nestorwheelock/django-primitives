"""Pricing scenario: Price rules for catalog items."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_catalog.models import CatalogItem
from django_parties.models import Organization, Person

from primitives_testbed.pricing.models import Price

User = get_user_model()


def seed():
    """Create sample pricing data for catalog items."""
    count = 0

    user = User.objects.first()
    if not user:
        return count

    now = timezone.now()

    # Get catalog items
    aspirin = CatalogItem.objects.filter(display_name="Aspirin 100mg").first()
    bandage = CatalogItem.objects.filter(display_name="Bandage Roll").first()
    exam = CatalogItem.objects.filter(display_name="General Examination").first()

    # Get organizations for scoped pricing
    acme_corp = Organization.objects.filter(name="Acme Corporation").first()
    general_hospital = Organization.objects.filter(name="General Hospital").first()

    # Get a person for individual pricing
    patient = Person.objects.first()

    # Create global prices (base prices for all customers)
    if aspirin:
        price, created = Price.objects.get_or_create(
            catalog_item=aspirin,
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("12.50"),
                "currency": "USD",
                "priority": 50,
                "valid_from": now,
                "created_by": user,
                "reason": "Standard retail price for Aspirin",
            }
        )
        if created:
            count += 1

    if bandage:
        price, created = Price.objects.get_or_create(
            catalog_item=bandage,
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("5.00"),
                "currency": "USD",
                "priority": 50,
                "valid_from": now,
                "created_by": user,
                "reason": "Standard retail price for Bandage",
            }
        )
        if created:
            count += 1

    if exam:
        price, created = Price.objects.get_or_create(
            catalog_item=exam,
            organization__isnull=True,
            party__isnull=True,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("75.00"),
                "currency": "USD",
                "priority": 50,
                "valid_from": now,
                "created_by": user,
                "reason": "Standard consultation fee",
            }
        )
        if created:
            count += 1

    # Create organization-specific prices (corporate discounts)
    if aspirin and acme_corp:
        price, created = Price.objects.get_or_create(
            catalog_item=aspirin,
            organization=acme_corp,
            party__isnull=True,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("10.00"),
                "currency": "USD",
                "priority": 60,
                "valid_from": now,
                "created_by": user,
                "reason": "Acme Corporation employee discount",
            }
        )
        if created:
            count += 1

    if exam and acme_corp:
        price, created = Price.objects.get_or_create(
            catalog_item=exam,
            organization=acme_corp,
            party__isnull=True,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("55.00"),
                "currency": "USD",
                "priority": 60,
                "valid_from": now,
                "created_by": user,
                "reason": "Acme Corporation contracted rate for consultations",
            }
        )
        if created:
            count += 1

    if exam and general_hospital:
        price, created = Price.objects.get_or_create(
            catalog_item=exam,
            organization=general_hospital,
            party__isnull=True,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("60.00"),
                "currency": "USD",
                "priority": 60,
                "valid_from": now,
                "created_by": user,
                "reason": "General Hospital staff rate",
            }
        )
        if created:
            count += 1

    # Create individual-specific price (VIP patient)
    if exam and patient:
        price, created = Price.objects.get_or_create(
            catalog_item=exam,
            organization__isnull=True,
            party=patient,
            agreement__isnull=True,
            valid_to__isnull=True,
            defaults={
                "amount": Decimal("45.00"),
                "currency": "USD",
                "priority": 70,
                "valid_from": now,
                "created_by": user,
                "reason": "Loyal patient special rate",
            }
        )
        if created:
            count += 1

    return count


def verify():
    """Verify pricing constraints with negative writes."""
    results = []

    user = User.objects.first()
    catalog_item = CatalogItem.objects.first()

    if not user or not catalog_item:
        results.append(("pricing_tests", None, "Skipped - no test data"))
        return results

    now = timezone.now()

    # Test 1: Negative amount rejected
    try:
        with transaction.atomic():
            Price.objects.create(
                catalog_item=catalog_item,
                amount=Decimal("-10.00"),  # Should fail
                currency="USD",
                priority=50,
                valid_from=now,
                created_by=user,
            )
        results.append(("price_amount_positive", False, "Should have raised error"))
    except (IntegrityError, Exception):
        results.append(("price_amount_positive", True, "Correctly rejected negative amount"))

    # Test 2: Zero amount rejected
    try:
        with transaction.atomic():
            Price.objects.create(
                catalog_item=catalog_item,
                amount=Decimal("0.00"),  # Should fail
                currency="USD",
                priority=50,
                valid_from=now,
                created_by=user,
            )
        results.append(("price_amount_zero", False, "Should have raised error"))
    except (IntegrityError, Exception):
        results.append(("price_amount_zero", True, "Correctly rejected zero amount"))

    # Test 3: Invalid date range rejected (valid_to before valid_from)
    try:
        with transaction.atomic():
            Price.objects.create(
                catalog_item=catalog_item,
                amount=Decimal("10.00"),
                currency="USD",
                priority=50,
                valid_from=now,
                valid_to=now - timezone.timedelta(days=1),  # Should fail
                created_by=user,
            )
        results.append(("price_valid_date_range", False, "Should have raised error"))
    except (IntegrityError, Exception):
        results.append(("price_valid_date_range", True, "Correctly rejected invalid date range"))

    return results
