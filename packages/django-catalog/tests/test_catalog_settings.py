"""Tests for CatalogSettings singleton and allow_inactive_items behavior."""

import pytest

from django_catalog.models import CatalogItem, CatalogSettings
from django_catalog.services import (
    add_item_to_basket,
    get_catalog_settings,
    get_or_create_draft_basket,
)
from django_singleton.exceptions import SingletonDeletionError


@pytest.fixture
def user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username='settingsuser', password='test')


@pytest.fixture
def encounter():
    """Create a test encounter."""
    from tests.testapp.models import Encounter
    return Encounter.objects.create(patient_name='Settings Test')


@pytest.fixture
def active_item():
    """Create an active catalog item."""
    return CatalogItem.objects.create(
        kind='service',
        service_category='lab',
        display_name='Active Item',
        active=True,
    )


@pytest.fixture
def inactive_item():
    """Create an inactive catalog item."""
    return CatalogItem.objects.create(
        kind='service',
        service_category='lab',
        display_name='Inactive Item',
        active=False,
    )


@pytest.mark.django_db
class TestCatalogSettingsSingleton:
    """Tests for CatalogSettings singleton behavior."""

    def test_get_catalog_settings_returns_singleton(self):
        """get_catalog_settings() returns a CatalogSettings instance."""
        settings = get_catalog_settings()

        assert isinstance(settings, CatalogSettings)
        assert settings.pk == 1

    def test_get_catalog_settings_creates_if_not_exists(self):
        """get_catalog_settings() creates instance if not exists."""
        assert CatalogSettings.objects.count() == 0

        settings = get_catalog_settings()

        assert CatalogSettings.objects.count() == 1
        assert settings.pk == 1

    def test_get_catalog_settings_returns_existing(self):
        """get_catalog_settings() returns existing instance."""
        CatalogSettings.objects.create(default_currency='EUR')

        settings = get_catalog_settings()

        assert settings.default_currency == 'EUR'

    def test_multiple_calls_return_same_pk(self):
        """Multiple get_catalog_settings() calls return same pk."""
        settings1 = get_catalog_settings()
        settings2 = get_catalog_settings()

        assert settings1.pk == settings2.pk == 1

    def test_singleton_pk_always_1(self):
        """CatalogSettings pk is always 1 regardless of what's passed."""
        settings = CatalogSettings(pk=999)
        settings.save()

        assert settings.pk == 1

    def test_singleton_cannot_be_deleted(self):
        """CatalogSettings cannot be deleted."""
        settings = get_catalog_settings()

        with pytest.raises(SingletonDeletionError):
            settings.delete()

    def test_settings_persisted(self):
        """CatalogSettings changes are persisted."""
        settings = get_catalog_settings()
        settings.default_currency = 'GBP'
        settings.allow_inactive_items = True
        settings.save()

        reloaded = get_catalog_settings()
        assert reloaded.default_currency == 'GBP'
        assert reloaded.allow_inactive_items is True


@pytest.mark.django_db
class TestCatalogSettingsDefaults:
    """Tests for CatalogSettings default values."""

    def test_default_currency_is_usd(self):
        """Default currency is USD."""
        settings = get_catalog_settings()
        assert settings.default_currency == 'USD'

    def test_allow_inactive_items_default_false(self):
        """allow_inactive_items defaults to False."""
        settings = get_catalog_settings()
        assert settings.allow_inactive_items is False

    def test_metadata_default_empty_dict(self):
        """metadata defaults to empty dict."""
        settings = get_catalog_settings()
        assert settings.metadata == {}


@pytest.mark.django_db
class TestAllowInactiveItemsBehavior:
    """Tests for allow_inactive_items wiring in add_item_to_basket."""

    def test_inactive_item_blocked_by_default(self, user, encounter, inactive_item):
        """Inactive items cannot be added when allow_inactive_items=False (default)."""
        basket = get_or_create_draft_basket(encounter, user)

        with pytest.raises(ValueError, match="Cannot add inactive catalog items"):
            add_item_to_basket(basket, inactive_item, user)

    def test_inactive_item_allowed_when_enabled(self, user, encounter, inactive_item):
        """Inactive items can be added when allow_inactive_items=True."""
        settings = get_catalog_settings()
        settings.allow_inactive_items = True
        settings.save()

        basket = get_or_create_draft_basket(encounter, user)
        basket_item = add_item_to_basket(basket, inactive_item, user)

        assert basket_item.catalog_item == inactive_item

    def test_active_item_always_allowed(self, user, encounter, active_item):
        """Active items can always be added regardless of setting."""
        basket = get_or_create_draft_basket(encounter, user)

        basket_item = add_item_to_basket(basket, active_item, user)

        assert basket_item.catalog_item == active_item

    def test_active_item_allowed_even_with_setting_true(self, user, encounter, active_item):
        """Active items still work when allow_inactive_items=True."""
        settings = get_catalog_settings()
        settings.allow_inactive_items = True
        settings.save()

        basket = get_or_create_draft_basket(encounter, user)
        basket_item = add_item_to_basket(basket, active_item, user)

        assert basket_item.catalog_item == active_item


@pytest.mark.django_db
class TestCatalogSettingsMetadata:
    """Tests for CatalogSettings metadata field."""

    def test_metadata_can_store_json(self):
        """metadata field can store JSON data."""
        settings = get_catalog_settings()
        settings.metadata = {'feature_flags': {'new_ui': True}, 'version': 2}
        settings.save()

        reloaded = get_catalog_settings()
        assert reloaded.metadata['feature_flags']['new_ui'] is True
        assert reloaded.metadata['version'] == 2

    def test_metadata_can_be_updated(self):
        """metadata can be updated without losing data."""
        settings = get_catalog_settings()
        settings.metadata = {'key1': 'value1'}
        settings.save()

        settings = get_catalog_settings()
        settings.metadata['key2'] = 'value2'
        settings.save()

        reloaded = get_catalog_settings()
        assert reloaded.metadata == {'key1': 'value1', 'key2': 'value2'}
