"""Tests for fulfillment pipeline."""

import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model

from django_catalog.models import CatalogItem

from primitives_testbed.diveops.entitlements.services import user_has_entitlement
from primitives_testbed.diveops.fulfillment.services import fulfill_order, get_order_entitlements
from primitives_testbed.store.models import StoreOrder, StoreOrderItem, CatalogItemEntitlement

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def catalog_item(db):
    """Create a test catalog item."""
    return CatalogItem.objects.create(
        display_name="Test Course",
        kind="service",
        is_billable=True,
        active=True,
    )


@pytest.fixture
def catalog_item_with_entitlements(catalog_item, db):
    """Create catalog item with entitlement mapping."""
    CatalogItemEntitlement.objects.create(
        catalog_item=catalog_item,
        entitlement_codes=["content:test-course", "feature:quizzes"],
    )
    return catalog_item


@pytest.fixture
def order(user, catalog_item_with_entitlements, db):
    """Create a test order with items."""
    order = StoreOrder.objects.create(
        order_number="ORD-TEST-001",
        user=user,
        status="paid",
        subtotal_amount=Decimal("99.00"),
        total_amount=Decimal("99.00"),
    )
    StoreOrderItem.objects.create(
        order=order,
        catalog_item=catalog_item_with_entitlements,
        description="Test Course",
        quantity=1,
        unit_price=Decimal("99.00"),
        line_total=Decimal("99.00"),
        entitlement_codes=["content:test-course", "feature:quizzes"],
    )
    return order


@pytest.mark.django_db
class TestGetOrderEntitlements:
    """Tests for get_order_entitlements."""

    def test_collects_entitlements_from_items(self, order):
        """Collects all entitlement codes from order items."""
        codes = get_order_entitlements(order)

        assert set(codes) == {"content:test-course", "feature:quizzes"}

    def test_empty_order_returns_empty(self, user, db):
        """Order with no items returns empty list."""
        order = StoreOrder.objects.create(
            order_number="ORD-EMPTY-001",
            user=user,
            status="paid",
            subtotal_amount=Decimal("0"),
            total_amount=Decimal("0"),
        )

        codes = get_order_entitlements(order)

        assert codes == []


@pytest.mark.django_db
class TestFulfillOrder:
    """Tests for fulfill_order service."""

    def test_grants_entitlements_to_user(self, order, user):
        """Fulfillment grants all item entitlements to user."""
        assert not user_has_entitlement(user, "content:test-course")

        fulfill_order(order)

        assert user_has_entitlement(user, "content:test-course")
        assert user_has_entitlement(user, "feature:quizzes")

    def test_updates_order_status(self, order):
        """Fulfillment sets order status to fulfilled."""
        assert order.status == "paid"

        fulfill_order(order)
        order.refresh_from_db()

        assert order.status == "fulfilled"
        assert order.fulfilled_at is not None

    def test_returns_granted_codes(self, order):
        """Fulfillment returns list of granted entitlement codes."""
        codes = fulfill_order(order)

        assert set(codes) == {"content:test-course", "feature:quizzes"}

    def test_cannot_fulfill_already_fulfilled(self, order, user):
        """Cannot fulfill an already fulfilled order."""
        fulfill_order(order)

        with pytest.raises(ValueError, match="Cannot fulfill"):
            fulfill_order(order)
