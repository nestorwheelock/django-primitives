"""Tests for django-modules services."""

import pytest

from django_modules.exceptions import ModuleDisabled, ModuleNotFound
from django_modules.models import Module, OrgModuleState
from django_modules.services import (
    is_module_enabled,
    list_enabled_modules,
    require_module,
)
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
    """Create pharmacy module (active by default)."""
    return Module.objects.create(
        key="pharmacy",
        name="Pharmacy",
        active=True,
    )


@pytest.fixture
def billing_module():
    """Create billing module (inactive by default)."""
    return Module.objects.create(
        key="billing",
        name="Billing",
        active=False,
    )


@pytest.fixture
def lab_module():
    """Create lab module (active by default)."""
    return Module.objects.create(
        key="lab",
        name="Laboratory",
        active=True,
    )


@pytest.mark.django_db
class TestIsModuleEnabled:
    """Tests for is_module_enabled service."""

    def test_returns_true_for_active_module_no_override(self, org, pharmacy_module):
        """Returns True for active module with no org override."""
        result = is_module_enabled(org, "pharmacy")
        assert result is True

    def test_returns_false_for_inactive_module_no_override(self, org, billing_module):
        """Returns False for inactive module with no org override."""
        result = is_module_enabled(org, "billing")
        assert result is False

    def test_org_override_enables_inactive_module(self, org, billing_module):
        """Org override can enable a globally inactive module."""
        OrgModuleState.objects.create(org=org, module=billing_module, enabled=True)

        result = is_module_enabled(org, "billing")
        assert result is True

    def test_org_override_disables_active_module(self, org, pharmacy_module):
        """Org override can disable a globally active module."""
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)

        result = is_module_enabled(org, "pharmacy")
        assert result is False

    def test_override_only_affects_specific_org(self, org, org2, pharmacy_module):
        """Override for one org doesn't affect other orgs."""
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)

        assert is_module_enabled(org, "pharmacy") is False
        assert is_module_enabled(org2, "pharmacy") is True

    def test_raises_for_nonexistent_module(self, org):
        """Raises ModuleNotFound for nonexistent module key."""
        with pytest.raises(ModuleNotFound) as exc_info:
            is_module_enabled(org, "nonexistent")

        assert exc_info.value.module_key == "nonexistent"
        assert "nonexistent" in str(exc_info.value)

    def test_soft_deleted_module_not_found(self, org, pharmacy_module):
        """Soft deleted module raises ModuleNotFound."""
        pharmacy_module.delete()

        with pytest.raises(ModuleNotFound):
            is_module_enabled(org, "pharmacy")

    def test_soft_deleted_override_uses_global_default(self, org, pharmacy_module):
        """Soft deleted override falls back to global default."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=False
        )
        state.delete()

        result = is_module_enabled(org, "pharmacy")
        assert result is True  # Falls back to module.active=True


@pytest.mark.django_db
class TestRequireModule:
    """Tests for require_module service."""

    def test_does_not_raise_for_enabled_module(self, org, pharmacy_module):
        """Does not raise for enabled module."""
        require_module(org, "pharmacy")  # Should not raise

    def test_raises_for_disabled_module(self, org, billing_module):
        """Raises ModuleDisabled for disabled module."""
        with pytest.raises(ModuleDisabled) as exc_info:
            require_module(org, "billing")

        assert exc_info.value.module_key == "billing"
        assert exc_info.value.org == org

    def test_raises_with_descriptive_message(self, org, billing_module):
        """ModuleDisabled has descriptive message."""
        with pytest.raises(ModuleDisabled) as exc_info:
            require_module(org, "billing")

        message = str(exc_info.value)
        assert "billing" in message
        assert "disabled" in message

    def test_raises_for_overridden_disabled_module(self, org, pharmacy_module):
        """Raises when org override disables module."""
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)

        with pytest.raises(ModuleDisabled):
            require_module(org, "pharmacy")

    def test_does_not_raise_for_overridden_enabled_module(self, org, billing_module):
        """Does not raise when org override enables module."""
        OrgModuleState.objects.create(org=org, module=billing_module, enabled=True)

        require_module(org, "billing")  # Should not raise

    def test_raises_module_not_found_for_nonexistent(self, org):
        """Raises ModuleNotFound for nonexistent module."""
        with pytest.raises(ModuleNotFound):
            require_module(org, "nonexistent")


@pytest.mark.django_db
class TestListEnabledModules:
    """Tests for list_enabled_modules service."""

    def test_returns_empty_set_when_no_modules(self, org):
        """Returns empty set when no modules exist."""
        result = list_enabled_modules(org)
        assert result == set()

    def test_returns_active_modules(self, org, pharmacy_module, lab_module):
        """Returns globally active modules."""
        result = list_enabled_modules(org)
        assert result == {"pharmacy", "lab"}

    def test_excludes_inactive_modules(self, org, pharmacy_module, billing_module):
        """Excludes globally inactive modules."""
        result = list_enabled_modules(org)
        assert "pharmacy" in result
        assert "billing" not in result

    def test_includes_overridden_enabled_modules(self, org, billing_module):
        """Includes modules enabled via org override."""
        OrgModuleState.objects.create(org=org, module=billing_module, enabled=True)

        result = list_enabled_modules(org)
        assert "billing" in result

    def test_excludes_overridden_disabled_modules(self, org, pharmacy_module):
        """Excludes modules disabled via org override."""
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)

        result = list_enabled_modules(org)
        assert "pharmacy" not in result

    def test_different_orgs_get_different_results(
        self, org, org2, pharmacy_module, billing_module
    ):
        """Different orgs can have different enabled modules."""
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)
        OrgModuleState.objects.create(org=org, module=billing_module, enabled=True)

        org1_modules = list_enabled_modules(org)
        org2_modules = list_enabled_modules(org2)

        assert org1_modules == {"billing"}
        assert org2_modules == {"pharmacy"}

    def test_returns_deterministic_set(self, org, pharmacy_module, billing_module, lab_module):
        """Returns consistent results on repeated calls."""
        OrgModuleState.objects.create(org=org, module=billing_module, enabled=True)

        result1 = list_enabled_modules(org)
        result2 = list_enabled_modules(org)

        assert result1 == result2
        assert result1 == {"pharmacy", "lab", "billing"}

    def test_excludes_soft_deleted_modules(self, org, pharmacy_module, lab_module):
        """Excludes soft deleted modules."""
        pharmacy_module.delete()

        result = list_enabled_modules(org)
        assert "pharmacy" not in result
        assert "lab" in result

    def test_ignores_soft_deleted_overrides(self, org, pharmacy_module):
        """Ignores soft deleted overrides, uses global default."""
        state = OrgModuleState.objects.create(
            org=org, module=pharmacy_module, enabled=False
        )
        state.delete()

        result = list_enabled_modules(org)
        assert "pharmacy" in result  # Falls back to global active=True


@pytest.mark.django_db
class TestModuleResolutionOrder:
    """Tests for correct resolution order: Org override > Module.active."""

    def test_org_override_takes_precedence_enable(self, org, billing_module):
        """Org override=True takes precedence over Module.active=False."""
        assert billing_module.active is False
        OrgModuleState.objects.create(org=org, module=billing_module, enabled=True)

        assert is_module_enabled(org, "billing") is True

    def test_org_override_takes_precedence_disable(self, org, pharmacy_module):
        """Org override=False takes precedence over Module.active=True."""
        assert pharmacy_module.active is True
        OrgModuleState.objects.create(org=org, module=pharmacy_module, enabled=False)

        assert is_module_enabled(org, "pharmacy") is False

    def test_no_override_uses_global_default(self, org, pharmacy_module, billing_module):
        """No override falls back to Module.active."""
        assert is_module_enabled(org, "pharmacy") is True  # active=True
        assert is_module_enabled(org, "billing") is False  # active=False


@pytest.mark.django_db
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_many_modules_many_orgs(self):
        """Works with many modules and orgs."""
        orgs = [Organization.objects.create(name=f"Org {i}") for i in range(10)]
        modules = [
            Module.objects.create(key=f"mod{i}", name=f"Module {i}", active=(i % 2 == 0))
            for i in range(20)
        ]

        # Create some overrides
        for i, org in enumerate(orgs):
            for j, module in enumerate(modules[:5]):
                OrgModuleState.objects.create(
                    org=org, module=module, enabled=(i + j) % 2 == 0
                )

        # Verify each org gets correct result
        for org in orgs:
            result = list_enabled_modules(org)
            assert isinstance(result, set)

    def test_module_key_with_special_characters(self, org):
        """Module keys can contain underscores and hyphens."""
        Module.objects.create(key="my_module", name="My Module", active=True)
        Module.objects.create(key="other-module", name="Other Module", active=True)

        assert is_module_enabled(org, "my_module") is True
        assert is_module_enabled(org, "other-module") is True

    def test_empty_module_key(self, org):
        """Empty module key raises ModuleNotFound."""
        with pytest.raises(ModuleNotFound):
            is_module_enabled(org, "")
