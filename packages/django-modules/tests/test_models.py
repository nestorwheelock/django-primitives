"""Tests for django-modules models."""

import pytest
from django.db import IntegrityError

from django_modules.models import Module, OrgModuleState
from tests.testapp.models import Organization


@pytest.fixture
def org():
    """Create a test organization."""
    return Organization.objects.create(name="Test Org")


@pytest.fixture
def org2():
    """Create a second test organization."""
    return Organization.objects.create(name="Second Org")


@pytest.fixture
def pharmacy_module():
    """Create a pharmacy module."""
    return Module.objects.create(
        key="pharmacy",
        name="Pharmacy",
        description="Pharmacy management module",
        active=True,
    )


@pytest.fixture
def billing_module():
    """Create a billing module (inactive by default)."""
    return Module.objects.create(
        key="billing",
        name="Billing",
        description="Billing and invoicing module",
        active=False,
    )


@pytest.mark.django_db
class TestModuleCreation:
    """Tests for Module model creation and basic behavior."""

    def test_module_can_be_created(self):
        """Module can be created with required fields."""
        module = Module.objects.create(
            key="inventory",
            name="Inventory",
            active=True,
        )
        assert module.pk is not None
        assert module.key == "inventory"

    def test_module_has_pk(self):
        """Module has primary key."""
        module = Module.objects.create(key="test", name="Test")
        assert module.pk is not None

    def test_module_has_timestamps(self):
        """Module has created_at and updated_at from BaseModel."""
        module = Module.objects.create(key="test", name="Test")
        assert module.created_at is not None
        assert module.updated_at is not None

    def test_module_key_is_unique(self):
        """Module key must be unique."""
        Module.objects.create(key="unique", name="First")

        with pytest.raises(IntegrityError):
            Module.objects.create(key="unique", name="Second")

    def test_module_default_active_true(self):
        """Module.active defaults to True."""
        module = Module.objects.create(key="test", name="Test")
        assert module.active is True

    def test_module_description_optional(self):
        """Module description is optional."""
        module = Module.objects.create(key="test", name="Test")
        assert module.description == ""

    def test_module_str(self, pharmacy_module):
        """Module __str__ includes name, key, and status."""
        assert "Pharmacy" in str(pharmacy_module)
        assert "pharmacy" in str(pharmacy_module)
        assert "active" in str(pharmacy_module)

    def test_inactive_module_str(self, billing_module):
        """Inactive module __str__ shows inactive."""
        assert "inactive" in str(billing_module)

    def test_module_ordering_by_key(self):
        """Modules are ordered by key."""
        Module.objects.create(key="zebra", name="Z")
        Module.objects.create(key="alpha", name="A")
        Module.objects.create(key="middle", name="M")

        keys = list(Module.objects.values_list("key", flat=True))
        assert keys == ["alpha", "middle", "zebra"]


@pytest.mark.django_db
class TestModuleSoftDelete:
    """Tests for Module soft delete behavior."""

    def test_module_can_be_soft_deleted(self, pharmacy_module):
        """Module can be soft deleted."""
        pharmacy_module.delete()
        assert pharmacy_module.deleted_at is not None

    def test_soft_deleted_module_not_in_default_queryset(self, pharmacy_module):
        """Soft deleted modules are excluded from default queryset."""
        pk = pharmacy_module.pk
        pharmacy_module.delete()

        assert not Module.objects.filter(pk=pk).exists()

    def test_soft_deleted_module_in_all_objects(self, pharmacy_module):
        """Soft deleted modules accessible via all_objects."""
        pk = pharmacy_module.pk
        pharmacy_module.delete()

        assert Module.all_objects.filter(pk=pk).exists()

    def test_module_can_be_restored(self, pharmacy_module):
        """Soft deleted module can be restored."""
        pharmacy_module.delete()
        pharmacy_module.restore()

        assert pharmacy_module.deleted_at is None
        assert Module.objects.filter(pk=pharmacy_module.pk).exists()


@pytest.mark.django_db
class TestOrgModuleStateCreation:
    """Tests for OrgModuleState model creation."""

    def test_org_module_state_can_be_created(self, org, pharmacy_module):
        """OrgModuleState can be created."""
        state = OrgModuleState.objects.create(
            org=org,
            module=pharmacy_module,
            enabled=True,
        )
        assert state.pk is not None

    def test_org_module_state_has_pk(self, org, pharmacy_module):
        """OrgModuleState has primary key."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        assert state.pk is not None

    def test_org_module_state_unique_constraint(self, org, pharmacy_module):
        """Only one OrgModuleState per (org, module) pair."""
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=True)

        with pytest.raises(IntegrityError):
            OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)

    def test_different_orgs_can_have_same_module_state(self, org, org2, pharmacy_module):
        """Different orgs can have states for the same module."""
        state1 = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        state2 = OrgModuleState.objects.create(
            org=org2, module=pharmacy_module, enabled=False
        )

        assert state1.pk != state2.pk
        assert state1.enabled is True
        assert state2.enabled is False

    def test_same_org_can_have_different_module_states(self, org, pharmacy_module, billing_module):
        """Same org can have states for different modules."""
        state1 = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        state2 = OrgModuleState.objects.create(
            org=org, module=billing_module, enabled=False
        )

        assert state1.pk != state2.pk

    def test_org_module_state_str(self, org, pharmacy_module):
        """OrgModuleState __str__ is descriptive."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        result = str(state)
        assert "pharmacy" in result
        assert "enabled" in result

    def test_disabled_state_str(self, org, pharmacy_module):
        """Disabled OrgModuleState __str__ shows disabled."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=False
        )
        assert "disabled" in str(state)


@pytest.mark.django_db
class TestOrgModuleStateSoftDelete:
    """Tests for OrgModuleState soft delete behavior."""

    def test_org_module_state_can_be_soft_deleted(self, org, pharmacy_module):
        """OrgModuleState can be soft deleted."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        state.delete()

        assert state.deleted_at is not None

    def test_soft_deleted_state_not_in_default_queryset(self, org, pharmacy_module):
        """Soft deleted states are excluded from default queryset."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        pk = state.pk
        state.delete()

        assert not OrgModuleState.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestOrgModuleStateCascade:
    """Tests for OrgModuleState cascade behavior."""

    def test_deleting_module_deletes_states(self, org, pharmacy_module):
        """Hard deleting module cascades to OrgModuleState."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        state_pk = state.pk

        pharmacy_module.hard_delete()

        assert not OrgModuleState.all_objects.filter(pk=state_pk).exists()

    def test_deleting_org_deletes_states(self, org, pharmacy_module):
        """Deleting org cascades to OrgModuleState."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=True
        )
        state_pk = state.pk

        org.hard_delete()

        assert not OrgModuleState.all_objects.filter(pk=state_pk).exists()
