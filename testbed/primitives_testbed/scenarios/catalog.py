"""Catalog scenario: CatalogItem, Basket, BasketItem, WorkItem, DispenseLog."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_catalog.models import (
    CatalogItem,
    Basket,
    BasketItem,
    WorkItem,
    DispenseLog,
)
from django_encounters.models import Encounter

User = get_user_model()


def seed():
    """Create sample catalog data."""
    count = 0

    # Create catalog items (products/services)
    aspirin, created = CatalogItem.objects.get_or_create(
        display_name="Aspirin 100mg",
        kind="stock_item",
        defaults={
            "default_stock_action": "dispense",
            "is_billable": True,
            "active": True,
        }
    )
    if created:
        count += 1

    bandage, created = CatalogItem.objects.get_or_create(
        display_name="Bandage Roll",
        kind="stock_item",
        defaults={
            "default_stock_action": "dispense",
            "is_billable": True,
            "active": True,
        }
    )
    if created:
        count += 1

    exam, created = CatalogItem.objects.get_or_create(
        display_name="General Examination",
        kind="service",
        defaults={
            "service_category": "consult",
            "is_billable": True,
            "active": True,
        }
    )
    if created:
        count += 1

    # Create a basket for an encounter
    encounter = Encounter.objects.first()
    user = User.objects.first()

    if encounter and user:
        basket, created = Basket.objects.get_or_create(
            encounter=encounter,
            status="draft",
            defaults={
                "created_by": user,
            }
        )
        if created:
            count += 1

            # Add items to basket
            BasketItem.objects.get_or_create(
                basket=basket,
                catalog_item=aspirin,
                defaults={"quantity": 2, "added_by": user}
            )
            BasketItem.objects.get_or_create(
                basket=basket,
                catalog_item=bandage,
                defaults={"quantity": 5, "added_by": user}
            )
            BasketItem.objects.get_or_create(
                basket=basket,
                catalog_item=exam,
                defaults={"quantity": 1, "added_by": user}
            )
            count += 3

            # Create work items for the basket items
            exam_item = BasketItem.objects.filter(basket=basket, catalog_item=exam).first()
            if exam_item:
                WorkItem.objects.get_or_create(
                    basket_item=exam_item,
                    encounter=encounter,
                    spawn_role="primary",
                    defaults={
                        "display_name": exam.display_name,
                        "kind": exam.kind,
                        "target_board": "treatment",
                        "status": "pending",
                        "priority": 50,
                    }
                )
                count += 1

            # Create a dispense log for medication
            aspirin_item = BasketItem.objects.filter(basket=basket, catalog_item=aspirin).first()
            if aspirin_item:
                # First create a work item for the aspirin
                aspirin_work_item, work_created = WorkItem.objects.get_or_create(
                    basket_item=aspirin_item,
                    encounter=encounter,
                    spawn_role="primary",
                    defaults={
                        "display_name": aspirin.display_name,
                        "kind": aspirin.kind,
                        "target_board": "pharmacy",
                        "status": "completed",
                        "priority": 30,
                    }
                )
                if work_created:
                    count += 1

                # Then create dispense log for the work item
                DispenseLog.objects.get_or_create(
                    workitem=aspirin_work_item,
                    defaults={
                        "display_name": aspirin.display_name,
                        "quantity": 2,
                        "dispensed_by": user,
                        "dispensed_at": timezone.now(),
                        "notes": "Dispensed to patient",
                    }
                )
                count += 1

    return count


def verify():
    """Verify catalog constraints with negative writes."""
    results = []

    user = User.objects.first()
    if not user:
        results.append(("catalog_tests", None, "Skipped - no test user"))
        return results

    # Test 1: BasketItem quantity must be positive (> 0)
    basket = Basket.objects.first()
    catalog_item = CatalogItem.objects.first()

    if basket and catalog_item:
        # Test quantity = 0
        try:
            with transaction.atomic():
                BasketItem.objects.create(
                    basket=basket,
                    catalog_item=catalog_item,
                    quantity=0,  # Should fail
                    added_by=user,
                )
            results.append(("basketitem_quantity_positive (zero)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("basketitem_quantity_positive (zero)", True, "Correctly rejected"))
    else:
        results.append(("basketitem_quantity_positive", None, "Skipped - no test data"))

    # Test 2: WorkItem priority must be in range 0-100
    basket_item = BasketItem.objects.first()
    encounter = Encounter.objects.first()
    if basket_item and encounter:
        # Test priority > 100
        try:
            with transaction.atomic():
                WorkItem.objects.create(
                    basket_item=basket_item,
                    encounter=encounter,
                    spawn_role="test-role-high",
                    target_board="treatment",
                    display_name="Test Item",
                    kind="stock_item",
                    status="pending",
                    priority=150,  # Should fail
                )
            results.append(("workitem_priority_range (above 100)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("workitem_priority_range (above 100)", True, "Correctly rejected"))
    else:
        results.append(("workitem_priority_range", None, "Skipped - no test data"))

    # Test 3: DispenseLog quantity must be positive (> 0)
    work_item = WorkItem.objects.filter(dispense_log__isnull=True).first()
    if work_item:
        try:
            with transaction.atomic():
                DispenseLog.objects.create(
                    workitem=work_item,
                    display_name="Test Item",
                    quantity=0,  # Should fail
                    dispensed_by=user,
                    dispensed_at=timezone.now(),
                )
            results.append(("dispenselog_quantity_positive", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("dispenselog_quantity_positive", True, "Correctly rejected"))
    else:
        results.append(("dispenselog_quantity_positive", None, "Skipped - no work item without dispense log"))

    # Test 4: Unique active basket per encounter
    encounter = Encounter.objects.first()
    if encounter:
        # Try to create a second draft basket for the same encounter
        existing_draft = Basket.objects.filter(
            encounter=encounter,
            status="draft",
        ).first()

        if existing_draft:
            try:
                with transaction.atomic():
                    Basket.objects.create(
                        encounter=encounter,
                        status="draft",  # Another draft - should fail
                        created_by=user,
                    )
                results.append(("unique_active_basket_per_encounter", False, "Should have raised IntegrityError"))
            except IntegrityError:
                results.append(("unique_active_basket_per_encounter", True, "Correctly rejected"))
        else:
            results.append(("unique_active_basket_per_encounter", None, "Skipped - no existing draft"))
    else:
        results.append(("unique_active_basket_per_encounter", None, "Skipped - no test data"))

    return results
