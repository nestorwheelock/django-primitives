"""Tests for catalog service functions.

These tests cover the basket and workitem service layer.
"""

import pytest
from django.utils import timezone

from django_catalog.models import Basket, BasketItem, CatalogItem, WorkItem
from django_catalog.services import (
    get_or_create_draft_basket,
    add_item_to_basket,
    commit_basket,
    cancel_basket,
    update_work_item_status,
)


@pytest.fixture
def user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username='svcuser', password='test')


@pytest.fixture
def encounter():
    """Create a test encounter."""
    from tests.testapp.models import Encounter
    return Encounter.objects.create(patient_name='Service Test')


@pytest.fixture
def catalog_item():
    """Create a test catalog item."""
    return CatalogItem.objects.create(
        kind='service',
        service_category='lab',
        display_name='Service Test Item',
        active=True,
    )


@pytest.mark.django_db
class TestGetOrCreateDraftBasket:
    """Tests for get_or_create_draft_basket."""

    def test_creates_basket_when_none_exists(self, user, encounter):
        """Creates new draft basket when none exists."""
        basket = get_or_create_draft_basket(encounter, user)

        assert basket.pk is not None
        assert basket.status == 'draft'
        assert basket.encounter == encounter
        assert basket.created_by == user

    def test_returns_existing_draft_basket(self, user, encounter):
        """Returns existing draft basket instead of creating new."""
        basket1 = get_or_create_draft_basket(encounter, user)
        basket2 = get_or_create_draft_basket(encounter, user)

        assert basket1.pk == basket2.pk

    def test_creates_new_basket_after_commit(self, user, encounter, catalog_item):
        """Creates new draft basket after previous one is committed."""
        basket1 = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket1, catalog_item, user)
        commit_basket(basket1, user)

        basket2 = get_or_create_draft_basket(encounter, user)

        assert basket1.pk != basket2.pk
        assert basket2.status == 'draft'

    def test_creates_new_basket_after_cancel(self, user, encounter):
        """Creates new draft basket after previous one is cancelled."""
        basket1 = get_or_create_draft_basket(encounter, user)
        cancel_basket(basket1)

        basket2 = get_or_create_draft_basket(encounter, user)

        assert basket1.pk != basket2.pk
        assert basket2.status == 'draft'


@pytest.mark.django_db
class TestCancelBasket:
    """Tests for cancel_basket."""

    def test_cancel_draft_basket(self, user, encounter):
        """Can cancel a draft basket."""
        basket = get_or_create_draft_basket(encounter, user)

        cancel_basket(basket)

        basket.refresh_from_db()
        assert basket.status == 'cancelled'

    def test_cannot_cancel_committed_basket(self, user, encounter, catalog_item):
        """Cannot cancel already-committed basket."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)
        commit_basket(basket, user)

        with pytest.raises(ValueError, match="Only draft baskets can be cancelled"):
            cancel_basket(basket)

    def test_cannot_cancel_already_cancelled_basket(self, user, encounter):
        """Cannot cancel already-cancelled basket."""
        basket = get_or_create_draft_basket(encounter, user)
        cancel_basket(basket)

        with pytest.raises(ValueError, match="Only draft baskets can be cancelled"):
            cancel_basket(basket)


@pytest.mark.django_db
class TestAddItemToBasket:
    """Tests for add_item_to_basket."""

    def test_add_item_with_defaults(self, user, encounter, catalog_item):
        """Add item with default quantity and no notes."""
        basket = get_or_create_draft_basket(encounter, user)

        basket_item = add_item_to_basket(basket, catalog_item, user)

        assert basket_item.basket == basket
        assert basket_item.catalog_item == catalog_item
        assert basket_item.quantity == 1
        assert basket_item.notes == ''
        assert basket_item.added_by == user

    def test_add_item_with_quantity(self, user, encounter, catalog_item):
        """Add item with custom quantity."""
        basket = get_or_create_draft_basket(encounter, user)

        basket_item = add_item_to_basket(basket, catalog_item, user, quantity=5)

        assert basket_item.quantity == 5

    def test_add_item_with_notes(self, user, encounter, catalog_item):
        """Add item with notes."""
        basket = get_or_create_draft_basket(encounter, user)

        basket_item = add_item_to_basket(
            basket, catalog_item, user,
            notes='Special instructions here'
        )

        assert basket_item.notes == 'Special instructions here'

    def test_add_item_with_stock_action_override(self, user, encounter):
        """Add stock item with action override."""
        stock_item = CatalogItem.objects.create(
            kind='stock_item',
            default_stock_action='dispense',
            display_name='Injectable',
            active=True,
        )
        basket = get_or_create_draft_basket(encounter, user)

        basket_item = add_item_to_basket(
            basket, stock_item, user,
            stock_action_override='administer'
        )

        assert basket_item.stock_action_override == 'administer'

    def test_add_multiple_items(self, user, encounter, catalog_item):
        """Can add multiple items to basket."""
        item2 = CatalogItem.objects.create(
            kind='service', service_category='imaging',
            display_name='X-Ray', active=True,
        )
        basket = get_or_create_draft_basket(encounter, user)

        add_item_to_basket(basket, catalog_item, user)
        add_item_to_basket(basket, item2, user)

        assert basket.items.count() == 2


@pytest.mark.django_db
class TestUpdateWorkItemStatus:
    """Tests for update_work_item_status."""

    @pytest.fixture
    def work_item(self, user, encounter, catalog_item):
        """Create a work item for testing."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)
        work_items = commit_basket(basket, user)
        return work_items[0]

    def test_update_to_in_progress(self, work_item, user):
        """Update status to in_progress sets started_at."""
        assert work_item.status == 'pending'
        assert work_item.started_at is None

        update_work_item_status(work_item, 'in_progress', user)

        work_item.refresh_from_db()
        assert work_item.status == 'in_progress'
        assert work_item.started_at is not None

    def test_update_to_completed(self, work_item, user):
        """Update status to completed sets completed_at and completed_by."""
        update_work_item_status(work_item, 'in_progress', user)
        update_work_item_status(work_item, 'completed', user)

        work_item.refresh_from_db()
        assert work_item.status == 'completed'
        assert work_item.completed_at is not None
        assert work_item.completed_by == user

    def test_update_with_status_detail(self, work_item, user):
        """Update status with board-specific detail."""
        update_work_item_status(
            work_item, 'in_progress', user,
            status_detail='collecting_sample'
        )

        work_item.refresh_from_db()
        assert work_item.status_detail == 'collecting_sample'

    def test_update_to_blocked(self, work_item, user):
        """Update status to blocked."""
        update_work_item_status(work_item, 'blocked', user)

        work_item.refresh_from_db()
        assert work_item.status == 'blocked'

    def test_update_to_cancelled(self, work_item, user):
        """Update status to cancelled."""
        update_work_item_status(work_item, 'cancelled', user)

        work_item.refresh_from_db()
        assert work_item.status == 'cancelled'


@pytest.mark.django_db
class TestCommitBasketMultipleItems:
    """Tests for committing baskets with multiple items."""

    def test_commit_multiple_items_creates_workitems_for_each(self, user, encounter):
        """Each basket item gets its own work item."""
        items = [
            CatalogItem.objects.create(
                kind='service', service_category='lab',
                display_name=f'Test {i}', active=True,
            )
            for i in range(3)
        ]

        basket = get_or_create_draft_basket(encounter, user)
        for item in items:
            add_item_to_basket(basket, item, user)

        work_items = commit_basket(basket, user)

        assert len(work_items) == 3
        assert WorkItem.objects.filter(encounter=encounter).count() == 3

    def test_empty_basket_commit(self, user, encounter):
        """Committing empty basket creates no work items."""
        basket = get_or_create_draft_basket(encounter, user)

        work_items = commit_basket(basket, user)

        assert len(work_items) == 0
        assert basket.status == 'committed'

    def test_commit_preserves_item_quantities(self, user, encounter, catalog_item):
        """Work item preserves basket item quantity."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user, quantity=10)

        work_items = commit_basket(basket, user)

        assert work_items[0].quantity == 10
