"""Tests for DispenseLog creation rules.

DispenseLog tracks clinical dispensing of pharmacy items.
"""

import pytest
from django.utils import timezone

from django_catalog.models import (
    Basket, BasketItem, CatalogItem, WorkItem, DispenseLog
)
from django_catalog.services import (
    get_or_create_draft_basket,
    add_item_to_basket,
    commit_basket,
    update_work_item_status,
)


@pytest.fixture
def user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username='dispenseuser', password='test')


@pytest.fixture
def encounter():
    """Create a test encounter."""
    from tests.testapp.models import Encounter
    return Encounter.objects.create(patient_name='Dispense Test Patient')


@pytest.fixture
def pharmacy_item():
    """Create a pharmacy-routed catalog item."""
    return CatalogItem.objects.create(
        kind='stock_item',
        default_stock_action='dispense',
        display_name='Test Medication 500mg',
        active=True,
    )


@pytest.fixture
def lab_item():
    """Create a lab-routed catalog item."""
    return CatalogItem.objects.create(
        kind='service',
        service_category='lab',
        display_name='Blood Test',
        active=True,
    )


@pytest.mark.django_db
class TestDispenseLogCreation:
    """DispenseLog creation rules."""

    def test_dispense_log_links_to_workitem(self, user, encounter, pharmacy_item):
        """DispenseLog correctly links to pharmacy WorkItem."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user, quantity=30)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        # Create dispense log
        dispense_log = DispenseLog.objects.create(
            workitem=work_item,
            display_name='Test Medication 500mg',
            quantity=30,
            dispensed_by=user,
            dispensed_at=timezone.now(),
        )

        assert dispense_log.workitem == work_item
        assert dispense_log.quantity == 30
        assert dispense_log.dispensed_by == user

    def test_dispense_log_is_one_to_one(self, user, encounter, pharmacy_item):
        """Only one DispenseLog per WorkItem (OneToOne relationship)."""
        from django.db import IntegrityError

        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        # Create first dispense log
        DispenseLog.objects.create(
            workitem=work_item,
            display_name='Test Medication',
            quantity=10,
            dispensed_by=user,
            dispensed_at=timezone.now(),
        )

        # Attempt second dispense log should fail
        with pytest.raises(IntegrityError):
            DispenseLog.objects.create(
                workitem=work_item,
                display_name='Test Medication',
                quantity=5,
                dispensed_by=user,
                dispensed_at=timezone.now(),
            )

    def test_dispense_log_captures_snapshot(self, user, encounter, pharmacy_item):
        """DispenseLog captures medication name at dispensing time."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user, quantity=30)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        dispense_log = DispenseLog.objects.create(
            workitem=work_item,
            display_name='Test Medication 500mg',
            quantity=30,
            dispensed_by=user,
            dispensed_at=timezone.now(),
        )

        # Change catalog item name
        pharmacy_item.display_name = 'CHANGED Medication Name'
        pharmacy_item.save()

        # Dispense log retains original name
        dispense_log.refresh_from_db()
        assert dispense_log.display_name == 'Test Medication 500mg'

    def test_dispense_log_requires_dispensed_by(self, user, encounter, pharmacy_item):
        """DispenseLog requires dispensed_by user."""
        from django.db import IntegrityError

        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        with pytest.raises(IntegrityError):
            DispenseLog.objects.create(
                workitem=work_item,
                display_name='Test Medication',
                quantity=10,
                dispensed_by=None,  # Should fail
                dispensed_at=timezone.now(),
            )


@pytest.mark.django_db
class TestDispenseLogWorkitemRelation:
    """DispenseLog relationship with WorkItem."""

    def test_workitem_has_dispense_log_accessor(self, user, encounter, pharmacy_item):
        """WorkItem has reverse relation to DispenseLog."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        dispense_log = DispenseLog.objects.create(
            workitem=work_item,
            display_name='Medication',
            quantity=10,
            dispensed_by=user,
            dispensed_at=timezone.now(),
        )

        # Access via reverse relation
        assert work_item.dispense_log == dispense_log

    def test_workitem_without_dispense_log_raises(self, user, encounter, pharmacy_item):
        """Accessing dispense_log on WorkItem without one raises DoesNotExist."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        with pytest.raises(DispenseLog.DoesNotExist):
            _ = work_item.dispense_log


@pytest.mark.django_db
class TestDispenseLogTimestamps:
    """DispenseLog timestamp behavior."""

    def test_dispense_log_has_created_at(self, user, encounter, pharmacy_item):
        """DispenseLog has auto-populated created_at."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        dispense_log = DispenseLog.objects.create(
            workitem=work_item,
            display_name='Medication',
            quantity=10,
            dispensed_by=user,
            dispensed_at=timezone.now(),
        )

        assert dispense_log.created_at is not None

    def test_dispense_log_dispensed_at_is_explicit(self, user, encounter, pharmacy_item):
        """DispenseLog dispensed_at is explicitly set, not auto-populated."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, pharmacy_item, user)
        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        explicit_time = timezone.now()
        dispense_log = DispenseLog.objects.create(
            workitem=work_item,
            display_name='Medication',
            quantity=10,
            dispensed_by=user,
            dispensed_at=explicit_time,
        )

        # dispensed_at should match what we set
        assert dispense_log.dispensed_at == explicit_time
