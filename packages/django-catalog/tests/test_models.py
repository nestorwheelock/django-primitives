"""Tests for django-catalog models."""

import pytest

from django_catalog.models import CatalogItem, Basket, BasketItem


@pytest.mark.django_db
class TestCatalogItem:
    """Tests for CatalogItem model."""

    def test_create_service(self):
        """Test creating a service catalog item."""
        item = CatalogItem.objects.create(
            kind='service',
            service_category='lab',
            display_name='Blood Test',
        )

        assert item.pk is not None
        assert item.kind == 'service'
        assert item.service_category == 'lab'
        assert item.active is True
        assert 'Blood Test' in str(item)

    def test_create_stock_item(self):
        """Test creating a stock item."""
        item = CatalogItem.objects.create(
            kind='stock_item',
            default_stock_action='dispense',
            display_name='Medication',
        )

        assert item.pk is not None
        assert item.kind == 'stock_item'
        assert item.default_stock_action == 'dispense'


@pytest.mark.django_db
class TestBasket:
    """Tests for Basket model."""

    def test_create_basket(self, django_user_model):
        """Test creating a basket."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='testuser',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Test Patient')

        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
        )

        assert basket.pk is not None
        assert basket.status == 'draft'
        assert basket.is_editable is True

    def test_basket_not_editable_when_committed(self, django_user_model):
        """Test that committed baskets are not editable."""
        from tests.testapp.models import Encounter

        user = django_user_model.objects.create_user(
            username='testuser2',
            password='testpass'
        )
        encounter = Encounter.objects.create(patient_name='Test Patient')

        basket = Basket.objects.create(
            encounter=encounter,
            created_by=user,
            status='committed',
        )

        assert basket.is_editable is False
