"""Tests for CATALOG_ENCOUNTER_MODEL and configuration validation.

These tests verify the settings seam works correctly.
"""

import pytest
from django.conf import settings


@pytest.mark.django_db
class TestEncounterModelConfiguration:
    """CATALOG_ENCOUNTER_MODEL setting validation."""

    def test_encounter_model_setting_is_used(self):
        """Configured encounter model is used for baskets."""
        from django_catalog.conf import ENCOUNTER_MODEL

        # In test settings, this should be 'testapp.Encounter'
        assert ENCOUNTER_MODEL == 'testapp.Encounter'

    def test_basket_links_to_configured_encounter(self, django_user_model):
        """Basket FK points to configured encounter model."""
        from tests.testapp.models import Encounter
        from django_catalog.models import Basket

        user = django_user_model.objects.create_user(username='configtest', password='test')
        encounter = Encounter.objects.create(patient_name='Config Test')

        basket = Basket.objects.create(encounter=encounter, created_by=user)

        assert basket.encounter == encounter
        assert basket.encounter.patient_name == 'Config Test'

    def test_workitem_links_to_configured_encounter(self, django_user_model):
        """WorkItem FK points to configured encounter model."""
        from tests.testapp.models import Encounter
        from django_catalog.models import Basket, BasketItem, CatalogItem, WorkItem

        user = django_user_model.objects.create_user(username='configtest2', password='test')
        encounter = Encounter.objects.create(patient_name='Config Test 2')

        item = CatalogItem.objects.create(
            kind='service', service_category='lab',
            display_name='Test', active=True,
        )
        basket = Basket.objects.create(encounter=encounter, created_by=user)
        basket_item = BasketItem.objects.create(
            basket=basket, catalog_item=item, added_by=user,
        )

        work_item = WorkItem.objects.create(
            basket_item=basket_item,
            encounter=encounter,
            spawn_role='primary',
            target_board='lab',
            display_name='Test',
            kind='service',
        )

        assert work_item.encounter == encounter


@pytest.mark.django_db
class TestOptionalConfigurations:
    """Optional configuration settings."""

    def test_inventory_model_not_configured(self):
        """INVENTORY_ITEM_MODEL is None when not configured."""
        from django_catalog.conf import INVENTORY_ITEM_MODEL, is_inventory_enabled

        # In test settings, this is not configured
        assert INVENTORY_ITEM_MODEL is None
        assert is_inventory_enabled() is False

    def test_prescription_model_not_configured(self):
        """PRESCRIPTION_MODEL is None when not configured."""
        from django_catalog.conf import PRESCRIPTION_MODEL, is_prescription_enabled

        # In test settings, this is not configured
        assert PRESCRIPTION_MODEL is None
        assert is_prescription_enabled() is False


@pytest.mark.django_db
class TestConfHelperFunctions:
    """Configuration helper functions."""

    def test_get_setting_with_prefix(self):
        """get_setting() adds CATALOG_ prefix."""
        from django_catalog.conf import get_setting

        # This should look for CATALOG_ENCOUNTER_MODEL
        result = get_setting('ENCOUNTER_MODEL')
        assert result == 'testapp.Encounter'

    def test_get_setting_with_default(self):
        """get_setting() returns default for missing settings."""
        from django_catalog.conf import get_setting

        result = get_setting('NONEXISTENT_SETTING', default='fallback')
        assert result == 'fallback'
