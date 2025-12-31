"""Tests for SingletonModel."""

import pytest
from django.db import connection

from django_singleton.exceptions import SingletonDeletionError, SingletonViolationError
from django_singleton.models import SingletonModel
from tests.testapp.models import SiteSettings, TaxSettings


@pytest.mark.django_db
class TestSingletonCreation:
    """Tests for singleton creation and basic behavior."""

    def test_singleton_can_be_created(self):
        """Concrete singleton model can be created."""
        settings = SiteSettings.objects.create()
        assert settings.pk is not None

    def test_pk_is_always_1(self):
        """pk is always 1 regardless of what's passed."""
        settings = SiteSettings(pk=999)
        settings.save()

        assert settings.pk == 1

    def test_get_instance_creates_if_not_exists(self):
        """get_instance() creates if not exists."""
        assert SiteSettings.objects.count() == 0

        settings = SiteSettings.get_instance()

        assert settings.pk == 1
        assert SiteSettings.objects.count() == 1

    def test_get_instance_returns_existing(self):
        """get_instance() returns existing if exists."""
        SiteSettings.objects.create(site_name="Original")

        settings = SiteSettings.get_instance()

        assert settings.site_name == "Original"

    def test_get_instance_always_returns_pk_1(self):
        """get_instance() always returns same pk."""
        settings1 = SiteSettings.get_instance()
        settings2 = SiteSettings.get_instance()

        assert settings1.pk == 1
        assert settings2.pk == 1

    def test_second_save_still_uses_pk_1(self):
        """Second save still uses pk=1."""
        settings = SiteSettings.get_instance()
        settings.site_name = "Updated"
        settings.save()

        assert settings.pk == 1
        assert SiteSettings.objects.count() == 1

    def test_multiple_get_instance_calls_return_same_instance(self):
        """Multiple get_instance() calls return same instance."""
        settings1 = SiteSettings.get_instance()
        settings1.site_name = "Changed"
        settings1.save()

        settings2 = SiteSettings.get_instance()

        assert settings2.site_name == "Changed"


@pytest.mark.django_db
class TestSingletonFields:
    """Tests for singleton with custom fields."""

    def test_fields_work_correctly(self):
        """Fields defined on subclass work correctly."""
        settings = SiteSettings.get_instance()
        settings.site_name = "My Website"
        settings.maintenance_mode = True
        settings.save()

        reloaded = SiteSettings.get_instance()
        assert reloaded.site_name == "My Website"
        assert reloaded.maintenance_mode is True

    def test_singleton_persists_data(self):
        """Singleton with custom fields persists data."""
        SiteSettings.objects.create(site_name="Test Site")

        settings = SiteSettings.objects.get(pk=1)
        assert settings.site_name == "Test Site"


@pytest.mark.django_db
class TestMultipleSingletons:
    """Tests for multiple singleton subclasses."""

    def test_multiple_singletons_are_independent(self):
        """Multiple singleton subclasses are independent."""
        site = SiteSettings.get_instance()
        site.site_name = "My Site"
        site.save()

        tax = TaxSettings.get_instance()
        tax.tax_rate = 7.5
        tax.save()

        assert SiteSettings.objects.count() == 1
        assert TaxSettings.objects.count() == 1
        assert SiteSettings.get_instance().site_name == "My Site"
        assert TaxSettings.get_instance().tax_rate == 7.5


@pytest.mark.django_db
class TestSingletonDeletion:
    """Tests for singleton deletion protection."""

    def test_delete_raises_error(self):
        """delete() raises SingletonDeletionError."""
        settings = SiteSettings.get_instance()

        with pytest.raises(SingletonDeletionError) as exc_info:
            settings.delete()

        assert "Cannot delete singleton" in str(exc_info.value)

    def test_delete_does_not_remove_row(self):
        """delete() does not remove the row."""
        settings = SiteSettings.get_instance()

        with pytest.raises(SingletonDeletionError):
            settings.delete()

        assert SiteSettings.objects.count() == 1
        assert SiteSettings.objects.filter(pk=1).exists()

    def test_subclass_inherits_deletion_protection(self):
        """Subclass inherits deletion protection."""
        tax = TaxSettings.get_instance()

        with pytest.raises(SingletonDeletionError):
            tax.delete()


@pytest.mark.django_db
class TestSingletonViolation:
    """Tests for singleton invariant violation detection."""

    def test_save_with_rogue_rows_raises_error(self):
        """Creating row with pk!=1 then saving raises SingletonViolationError."""
        # First create proper singleton
        SiteSettings.get_instance()

        # Manually insert rogue row (bypassing save())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO testapp_sitesettings (id, site_name, maintenance_mode) "
                "VALUES (2, 'Rogue', 0)"
            )

        # Now try to save - should detect corruption
        settings = SiteSettings(site_name="New")
        with pytest.raises(SingletonViolationError) as exc_info:
            settings.save()

        assert "Multiple rows exist" in str(exc_info.value)

    def test_subclass_inherits_violation_protection(self):
        """Subclass inherits violation protection."""
        TaxSettings.get_instance()

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO testapp_taxsettings (id, tax_rate) VALUES (2, 5.00)"
            )

        tax = TaxSettings(tax_rate=10.0)
        with pytest.raises(SingletonViolationError):
            tax.save()
