"""Tests for soft delete behavior inherited from django-basemodels.

These tests only inspect model metadata, not database operations,
so no database setup is required.
"""
import pytest


class TestSoftDeleteInheritance:
    """Verify models correctly inherit soft delete from BaseModel."""

    def test_person_has_deleted_at_field(self):
        """Person model should have deleted_at field from BaseModel."""
        from django_parties.models import Person
        field_names = [f.name for f in Person._meta.get_fields()]
        assert 'deleted_at' in field_names, "Person must inherit deleted_at from BaseModel"

    def test_person_has_timestamps(self):
        """Person model should have timestamp fields from BaseModel."""
        from django_parties.models import Person
        field_names = [f.name for f in Person._meta.get_fields()]
        assert 'created_at' in field_names, "Person must inherit created_at"
        assert 'updated_at' in field_names, "Person must inherit updated_at"

    def test_person_has_uuid_pk(self):
        """Person model should have UUID primary key."""
        from django_parties.models import Person
        pk_field = Person._meta.pk
        assert pk_field.name == 'id'
        assert 'UUID' in str(type(pk_field))

    def test_organization_has_deleted_at_field(self):
        """Organization model should have deleted_at field."""
        from django_parties.models import Organization
        field_names = [f.name for f in Organization._meta.get_fields()]
        assert 'deleted_at' in field_names

    def test_group_has_deleted_at_field(self):
        """Group model should have deleted_at field."""
        from django_parties.models import Group
        field_names = [f.name for f in Group._meta.get_fields()]
        assert 'deleted_at' in field_names

    def test_address_has_deleted_at_field(self):
        """Address model should have deleted_at field."""
        from django_parties.models import Address
        field_names = [f.name for f in Address._meta.get_fields()]
        assert 'deleted_at' in field_names

    def test_default_manager_is_soft_delete_manager(self):
        """Default objects manager should exclude soft-deleted rows."""
        from django_parties.models import Person
        from django_basemodels import SoftDeleteManager
        assert isinstance(Person.objects, SoftDeleteManager), \
            "Person.objects must be SoftDeleteManager"

    def test_all_objects_manager_exists(self):
        """all_objects manager should exist for querying deleted rows."""
        from django_parties.models import Person
        assert hasattr(Person, 'all_objects'), \
            "Person must have all_objects manager for deleted rows"
