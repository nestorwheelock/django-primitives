"""Tests for django-modules configuration."""

import pytest
from django.test import override_settings

from django_modules.conf import get_org_model, get_org_model_string
from django_modules.exceptions import ModulesConfigError


class TestModulesOrgModelConfig:
    """Tests for MODULES_ORG_MODEL configuration."""

    def test_get_org_model_returns_configured_model(self):
        """get_org_model returns the configured model string."""
        result = get_org_model()
        assert result == "testapp.Organization"

    def test_get_org_model_string_returns_configured_model(self):
        """get_org_model_string returns the configured model string."""
        result = get_org_model_string()
        assert result == "testapp.Organization"

    @override_settings(MODULES_ORG_MODEL=None)
    def test_missing_config_raises_error(self):
        """Missing MODULES_ORG_MODEL raises ModulesConfigError."""
        with pytest.raises(ModulesConfigError) as exc_info:
            get_org_model()

        assert "MODULES_ORG_MODEL" in str(exc_info.value)
        assert "required" in str(exc_info.value)

    @override_settings()
    def test_unset_config_raises_error(self):
        """Unset MODULES_ORG_MODEL raises ModulesConfigError."""
        # Remove the setting entirely
        from django.conf import settings
        if hasattr(settings, "MODULES_ORG_MODEL"):
            delattr(settings, "MODULES_ORG_MODEL")

        with pytest.raises(ModulesConfigError):
            get_org_model()
