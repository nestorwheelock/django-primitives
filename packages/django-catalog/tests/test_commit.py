"""Tests for basket commit invariants.

These tests verify the critical transactional and idempotency guarantees
of the basket commit workflow.
"""

import pytest
from django.db import IntegrityError, transaction

from django_catalog.models import Basket, BasketItem, CatalogItem, WorkItem
from django_catalog.services import (
    commit_basket,
    add_item_to_basket,
    get_or_create_draft_basket,
)


@pytest.fixture
def user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username='testuser', password='test')


@pytest.fixture
def encounter():
    """Create a test encounter."""
    from tests.testapp.models import Encounter
    return Encounter.objects.create(patient_name='Test Patient')


@pytest.fixture
def catalog_item():
    """Create a test catalog item."""
    return CatalogItem.objects.create(
        kind='service',
        service_category='lab',
        display_name='Blood Test',
        active=True,
    )


@pytest.mark.django_db
class TestCommitSpawnsWorkItemsOnce:
    """Commit spawns WorkItems exactly once (idempotent behavior)."""

    def test_commit_creates_workitems(self, user, encounter, catalog_item):
        """First commit creates WorkItems for all basket items."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)

        work_items = commit_basket(basket, user)

        assert len(work_items) == 1
        assert WorkItem.objects.count() == 1
        assert basket.status == 'committed'

    def test_double_commit_is_idempotent(self, user, encounter, catalog_item):
        """Second commit on already-committed basket returns same WorkItems."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)

        # First commit
        work_items_1 = commit_basket(basket, user)
        first_count = WorkItem.objects.count()

        # Second commit should not create new WorkItems
        basket.refresh_from_db()
        work_items_2 = commit_basket(basket, user)

        assert WorkItem.objects.count() == first_count
        assert len(work_items_2) == len(work_items_1)
        # Same WorkItem objects returned
        assert work_items_1[0].pk == work_items_2[0].pk

    def test_workitem_unique_constraint_per_basket_item_role(self, user, encounter, catalog_item):
        """Database enforces uniqueness on (basket_item, spawn_role)."""
        basket = get_or_create_draft_basket(encounter, user)
        basket_item = add_item_to_basket(basket, catalog_item, user)

        # Create first WorkItem
        WorkItem.objects.create(
            basket_item=basket_item,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='Blood Test',
            kind='service',
        )

        # Attempt to create duplicate should fail
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                WorkItem.objects.create(
                    basket_item=basket_item,
                    encounter=encounter,
                    spawn_role='primary',  # Same role = duplicate
                    target_board='lab',
                    display_name='Blood Test',
                    kind='service',
                )


@pytest.mark.django_db
class TestBasketItemSnapshotImmutability:
    """BasketItem snapshot fields are immutable after commit."""

    def test_snapshot_captures_catalog_values_at_commit(self, user, encounter, catalog_item):
        """Snapshot captures CatalogItem values at commit time."""
        basket = get_or_create_draft_basket(encounter, user)
        basket_item = add_item_to_basket(basket, catalog_item, user)

        # Pre-commit: snapshot fields are empty
        assert basket_item.display_name_snapshot == ''
        assert basket_item.kind_snapshot == ''

        # Commit
        commit_basket(basket, user)
        basket_item.refresh_from_db()

        # Post-commit: snapshot fields populated
        assert basket_item.display_name_snapshot == 'Blood Test'
        assert basket_item.kind_snapshot == 'service'

    def test_catalog_change_after_commit_does_not_affect_snapshot(self, user, encounter, catalog_item):
        """Changing CatalogItem after commit doesn't alter committed snapshot."""
        basket = get_or_create_draft_basket(encounter, user)
        basket_item = add_item_to_basket(basket, catalog_item, user)

        # Commit
        commit_basket(basket, user)
        basket_item.refresh_from_db()

        original_snapshot = basket_item.display_name_snapshot

        # Change catalog item
        catalog_item.display_name = 'CHANGED Blood Test'
        catalog_item.save()

        # Refresh basket item - snapshot should be unchanged
        basket_item.refresh_from_db()
        assert basket_item.display_name_snapshot == original_snapshot
        assert basket_item.display_name_snapshot == 'Blood Test'
        assert basket_item.display_name_snapshot != 'CHANGED Blood Test'

    def test_workitem_uses_snapshot_not_current_catalog(self, user, encounter, catalog_item):
        """WorkItem display_name comes from snapshot, not current catalog."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)

        work_items = commit_basket(basket, user)
        work_item = work_items[0]

        # Change catalog item after commit
        catalog_item.display_name = 'CHANGED Blood Test'
        catalog_item.save()

        # WorkItem should still have original name
        work_item.refresh_from_db()
        assert work_item.display_name == 'Blood Test'


@pytest.mark.django_db
class TestAtomicCommit:
    """Basket commit is atomic - partial commits should roll back."""

    def test_commit_is_wrapped_in_transaction(self, user, encounter, catalog_item):
        """Commit uses @transaction.atomic decorator."""
        from django_catalog.services import commit_basket
        import inspect

        # Check that commit_basket is wrapped with transaction.atomic
        # by looking for the wrapper
        source = inspect.getsource(commit_basket)
        assert '@transaction.atomic' in source or 'transaction.atomic' in source

    def test_failed_workitem_creation_rolls_back_basket_status(self, user, encounter, catalog_item, mocker):
        """If WorkItem creation fails, basket status remains draft."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)

        # Mock spawn_work_item to raise an exception
        mocker.patch(
            'django_catalog.services.spawn_work_item',
            side_effect=Exception("Simulated failure")
        )

        # Commit should fail and roll back
        with pytest.raises(Exception, match="Simulated failure"):
            commit_basket(basket, user)

        # Basket should still be draft
        basket.refresh_from_db()
        assert basket.status == 'draft'
        assert WorkItem.objects.count() == 0


@pytest.mark.django_db
class TestSoftDeleteBehavior:
    """Soft-deleted/inactive items behave correctly."""

    def test_inactive_catalog_item_cannot_be_added_to_basket(self, user, encounter):
        """Inactive CatalogItem cannot be added to basket."""
        inactive_item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='Inactive Test',
            active=False,
        )

        basket = get_or_create_draft_basket(encounter, user)

        with pytest.raises(ValueError, match="Cannot add inactive catalog items"):
            add_item_to_basket(basket, inactive_item, user)

    def test_item_deactivated_after_add_can_still_commit(self, user, encounter, catalog_item):
        """Item added while active can still commit if deactivated later."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)

        # Deactivate item after adding to basket
        catalog_item.active = False
        catalog_item.save()

        # Commit should still work (item was valid when added)
        work_items = commit_basket(basket, user)
        assert len(work_items) == 1

    def test_cannot_add_to_committed_basket(self, user, encounter, catalog_item):
        """Cannot add items to already-committed basket."""
        basket = get_or_create_draft_basket(encounter, user)
        add_item_to_basket(basket, catalog_item, user)
        commit_basket(basket, user)

        new_item = CatalogItem.objects.create(
            kind='service',
            service_category='imaging',
            display_name='X-Ray',
            active=True,
        )

        with pytest.raises(ValueError, match="Cannot add items to a committed"):
            add_item_to_basket(basket, new_item, user)

    def test_cannot_add_to_cancelled_basket(self, user, encounter, catalog_item):
        """Cannot add items to cancelled basket."""
        from django_catalog.services import cancel_basket

        basket = get_or_create_draft_basket(encounter, user)
        cancel_basket(basket)

        with pytest.raises(ValueError, match="Cannot add items to a committed or cancelled"):
            add_item_to_basket(basket, catalog_item, user)
