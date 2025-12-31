"""Comprehensive tests for django-basemodels package."""
import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from tests.models import (
    TimestampedTestModel,
    UUIDTestModel,
    SoftDeleteTestModel,
    BaseTestModel,
    UUIDBaseTestModel,
)


class TestTimeStampedModel(TestCase):
    """Tests for TimeStampedModel."""

    def test_created_at_auto_populated(self):
        """created_at should be set automatically on creation."""
        before = timezone.now()
        obj = TimestampedTestModel.objects.create(name='Test')
        after = timezone.now()

        assert obj.created_at is not None
        assert before <= obj.created_at <= after

    def test_updated_at_auto_populated(self):
        """updated_at should be set automatically on creation."""
        before = timezone.now()
        obj = TimestampedTestModel.objects.create(name='Test')
        after = timezone.now()

        assert obj.updated_at is not None
        assert before <= obj.updated_at <= after

    def test_updated_at_changes_on_save(self):
        """updated_at should change when object is modified."""
        obj = TimestampedTestModel.objects.create(name='Test')
        original_updated = obj.updated_at

        obj.name = 'Modified'
        obj.save()

        obj.refresh_from_db()
        assert obj.updated_at > original_updated

    def test_created_at_unchanged_on_save(self):
        """created_at should NOT change when object is modified."""
        obj = TimestampedTestModel.objects.create(name='Test')
        original_created = obj.created_at

        obj.name = 'Modified'
        obj.save()

        obj.refresh_from_db()
        assert obj.created_at == original_created


class TestUUIDModel(TestCase):
    """Tests for UUIDModel."""

    def test_uuid_primary_key(self):
        """Primary key should be a UUID."""
        obj = UUIDTestModel.objects.create(name='Test')
        assert isinstance(obj.id, uuid.UUID)
        assert obj.pk == obj.id

    def test_uuid_auto_generated(self):
        """UUID should be automatically generated."""
        obj = UUIDTestModel(name='Test')
        assert obj.id is not None
        assert isinstance(obj.id, uuid.UUID)

    def test_uuid_unique_per_instance(self):
        """Each instance should get a unique UUID."""
        obj1 = UUIDTestModel.objects.create(name='Test1')
        obj2 = UUIDTestModel.objects.create(name='Test2')
        assert obj1.id != obj2.id

    def test_uuid_not_editable(self):
        """UUID should not be editable after creation."""
        pk_field = UUIDTestModel._meta.pk
        assert pk_field.editable is False


class TestSoftDeleteManager(TestCase):
    """Tests for SoftDeleteManager."""

    def test_default_excludes_deleted(self):
        """Default queryset should exclude soft-deleted objects."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj.delete()

        assert SoftDeleteTestModel.objects.filter(pk=obj.pk).exists() is False

    def test_with_deleted_includes_all(self):
        """with_deleted() should include soft-deleted objects."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj.delete()

        assert SoftDeleteTestModel.objects.with_deleted().filter(pk=obj.pk).exists() is True

    def test_deleted_only_returns_deleted(self):
        """deleted_only() should return only soft-deleted objects."""
        active = SoftDeleteTestModel.objects.create(name='Active')
        deleted = SoftDeleteTestModel.objects.create(name='Deleted')
        deleted.delete()

        deleted_qs = SoftDeleteTestModel.objects.deleted_only()
        assert deleted_qs.filter(pk=deleted.pk).exists() is True
        assert deleted_qs.filter(pk=active.pk).exists() is False

    def test_count_excludes_deleted(self):
        """count() should only count active records."""
        SoftDeleteTestModel.objects.create(name='Active1')
        SoftDeleteTestModel.objects.create(name='Active2')
        deleted = SoftDeleteTestModel.objects.create(name='Deleted')
        deleted.delete()

        assert SoftDeleteTestModel.objects.count() == 2

    def test_all_objects_includes_everything(self):
        """all_objects manager should include deleted records."""
        SoftDeleteTestModel.objects.create(name='Active')
        deleted = SoftDeleteTestModel.objects.create(name='Deleted')
        deleted.delete()

        assert SoftDeleteTestModel.all_objects.count() == 2


class TestSoftDeleteModel(TestCase):
    """Tests for SoftDeleteModel delete/restore operations."""

    def test_delete_sets_timestamp(self):
        """delete() should set deleted_at timestamp."""
        before = timezone.now()
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj.delete()
        after = timezone.now()

        obj.refresh_from_db()
        assert obj.deleted_at is not None
        assert before <= obj.deleted_at <= after

    def test_delete_does_not_remove_row(self):
        """delete() should NOT remove the row from database."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        pk = obj.pk
        obj.delete()

        assert SoftDeleteTestModel.all_objects.filter(pk=pk).exists() is True

    def test_hard_delete_removes_row(self):
        """hard_delete() should permanently remove the row."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        pk = obj.pk
        obj.hard_delete()

        assert SoftDeleteTestModel.all_objects.filter(pk=pk).exists() is False

    def test_restore_clears_deleted_at(self):
        """restore() should set deleted_at to None."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj.delete()
        obj.restore()

        obj.refresh_from_db()
        assert obj.deleted_at is None

    def test_restore_makes_visible_in_default_queryset(self):
        """restore() should make object visible in default queryset."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj.delete()

        assert SoftDeleteTestModel.objects.filter(pk=obj.pk).exists() is False

        obj.restore()

        assert SoftDeleteTestModel.objects.filter(pk=obj.pk).exists() is True

    def test_is_deleted_property(self):
        """is_deleted should return True when deleted, False otherwise."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        assert obj.is_deleted is False

        obj.delete()
        assert obj.is_deleted is True

        obj.restore()
        assert obj.is_deleted is False


class TestBaseModel(TestCase):
    """Tests for BaseModel (combined functionality)."""

    def test_has_timestamps(self):
        """BaseModel should have created_at and updated_at."""
        obj = BaseTestModel.objects.create(name='Test')
        assert obj.created_at is not None
        assert obj.updated_at is not None

    def test_has_soft_delete(self):
        """BaseModel should have soft delete functionality."""
        obj = BaseTestModel.objects.create(name='Test')
        obj.delete()

        assert obj.is_deleted is True
        assert BaseTestModel.objects.filter(pk=obj.pk).exists() is False
        assert BaseTestModel.all_objects.filter(pk=obj.pk).exists() is True

    def test_has_restore(self):
        """BaseModel should support restore."""
        obj = BaseTestModel.objects.create(name='Test')
        obj.delete()
        obj.restore()

        assert obj.is_deleted is False
        assert BaseTestModel.objects.filter(pk=obj.pk).exists() is True

    def test_manager_order(self):
        """Default manager should be SoftDeleteManager, not Manager."""
        default_manager = BaseTestModel._meta.default_manager
        assert default_manager.name == 'objects'
        assert hasattr(default_manager, 'with_deleted')
        assert hasattr(default_manager, 'deleted_only')


class TestUUIDBaseModel(TestCase):
    """Tests for recommended pattern: UUIDModel + BaseModel."""

    def test_combined_uuid_and_basemodel(self):
        """UUIDModel + BaseModel should provide all features."""
        obj = UUIDBaseTestModel.objects.create(name='Test', email='test@example.com')

        # UUID PK
        assert isinstance(obj.id, uuid.UUID)

        # Timestamps
        assert obj.created_at is not None
        assert obj.updated_at is not None

        # Soft delete
        obj.delete()
        assert obj.is_deleted is True
        assert UUIDBaseTestModel.objects.filter(pk=obj.pk).exists() is False

    def test_conditional_unique_constraint(self):
        """Unique constraint should only apply to active records."""
        obj1 = UUIDBaseTestModel.objects.create(name='User1', email='same@example.com')
        obj1.delete()  # Soft delete

        # Should be able to create another with same email (first is deleted)
        obj2 = UUIDBaseTestModel.objects.create(name='User2', email='same@example.com')
        assert obj2.pk is not None

        # But cannot create another active one with same email
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            UUIDBaseTestModel.objects.create(name='User3', email='same@example.com')


class TestBulkDeleteGotcha(TestCase):
    """Tests documenting the bulk delete gotcha."""

    def test_queryset_delete_is_hard_delete(self):
        """GOTCHA: QuerySet.delete() does NOT soft delete."""
        SoftDeleteTestModel.objects.create(name='Test1')
        SoftDeleteTestModel.objects.create(name='Test2')

        # This is HARD DELETE, not soft delete!
        SoftDeleteTestModel.objects.all().delete()

        # Records are GONE from database
        assert SoftDeleteTestModel.all_objects.count() == 0

    def test_bulk_soft_delete_with_update(self):
        """Correct way to bulk soft delete is using update()."""
        SoftDeleteTestModel.objects.create(name='Test1')
        SoftDeleteTestModel.objects.create(name='Test2')

        # Correct bulk soft delete:
        SoftDeleteTestModel.objects.all().update(deleted_at=timezone.now())

        # Records still exist but are soft deleted
        assert SoftDeleteTestModel.all_objects.count() == 2
        assert SoftDeleteTestModel.objects.count() == 0


class TestMetaInheritance(TestCase):
    """Tests for proper Meta class inheritance."""

    def test_base_classes_are_abstract(self):
        """Base model classes should be abstract."""
        from django_basemodels import TimeStampedModel, UUIDModel, SoftDeleteModel, BaseModel
        assert TimeStampedModel._meta.abstract is True
        assert UUIDModel._meta.abstract is True
        assert SoftDeleteModel._meta.abstract is True
        assert BaseModel._meta.abstract is True

    def test_concrete_model_has_table(self):
        """Concrete test models should have database tables."""
        assert SoftDeleteTestModel._meta.db_table is not None
        assert BaseTestModel._meta.db_table is not None

    def test_field_names(self):
        """BaseModel should have expected field names."""
        field_names = [f.name for f in BaseTestModel._meta.get_fields()]
        assert 'created_at' in field_names
        assert 'updated_at' in field_names
        assert 'deleted_at' in field_names
