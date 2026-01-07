"""Tests for EnvFallbackMixin."""

import os
import pytest

from tests.testapp.models import APISettings


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up test environment variables before and after each test."""
    # Store original values
    original_api = os.environ.get("TEST_API_KEY")
    original_secret = os.environ.get("TEST_SECRET_KEY")

    # Clear before test
    os.environ.pop("TEST_API_KEY", None)
    os.environ.pop("TEST_SECRET_KEY", None)

    yield

    # Restore after test
    os.environ.pop("TEST_API_KEY", None)
    os.environ.pop("TEST_SECRET_KEY", None)
    if original_api is not None:
        os.environ["TEST_API_KEY"] = original_api
    if original_secret is not None:
        os.environ["TEST_SECRET_KEY"] = original_secret


@pytest.mark.django_db
class TestEnvFallbackMixin:
    """Tests for EnvFallbackMixin."""

    def test_db_value_takes_precedence_over_env(self):
        """Database value should be returned even if env var is set."""
        os.environ["TEST_API_KEY"] = "env-api-key"

        settings = APISettings.get_instance()
        settings.api_key = "db-api-key"
        settings.save()

        assert settings.get_with_fallback("api_key") == "db-api-key"

    def test_env_fallback_when_db_is_blank(self):
        """Environment variable should be used when DB value is blank."""
        os.environ["TEST_API_KEY"] = "env-api-key"

        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.get_with_fallback("api_key") == "env-api-key"

    def test_env_fallback_when_db_is_empty_string(self):
        """Environment variable should be used when DB value is empty string."""
        os.environ["TEST_API_KEY"] = "env-api-key"

        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.get_with_fallback("api_key") == "env-api-key"

    def test_default_when_both_db_and_env_empty(self):
        """Default value should be used when both DB and env are empty."""
        # No env var set, DB is blank
        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.get_with_fallback("api_key") == ""
        assert settings.get_with_fallback("api_key", "my-default") == "my-default"

    def test_field_without_env_fallback_uses_db_only(self):
        """Fields not in ENV_FALLBACKS should only use DB value."""
        settings = APISettings.get_instance()
        settings.base_url = "https://api.example.com"
        settings.save()

        assert settings.get_with_fallback("base_url") == "https://api.example.com"

    def test_field_without_env_fallback_returns_default_when_blank(self):
        """Fields not in ENV_FALLBACKS should return default when blank."""
        settings = APISettings.get_instance()
        settings.base_url = ""
        settings.save()

        assert settings.get_with_fallback("base_url") == ""
        assert settings.get_with_fallback("base_url", "default-url") == "default-url"


@pytest.mark.django_db
class TestGetValueSource:
    """Tests for get_value_source() method."""

    def test_source_is_database_when_db_has_value(self):
        """Should return 'database' when DB has a non-blank value."""
        os.environ["TEST_API_KEY"] = "env-value"

        settings = APISettings.get_instance()
        settings.api_key = "db-value"
        settings.save()

        assert settings.get_value_source("api_key") == "database"

    def test_source_is_environment_when_db_blank_and_env_set(self):
        """Should return 'environment' when DB is blank but env is set."""
        os.environ["TEST_API_KEY"] = "env-value"

        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.get_value_source("api_key") == "environment"

    def test_source_is_default_when_both_empty(self):
        """Should return 'default' when both DB and env are empty."""
        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.get_value_source("api_key") == "default"

    def test_source_is_default_for_field_without_fallback(self):
        """Should return 'default' for fields not in ENV_FALLBACKS when blank."""
        settings = APISettings.get_instance()
        settings.base_url = ""
        settings.save()

        assert settings.get_value_source("base_url") == "default"


@pytest.mark.django_db
class TestGetResolved:
    """Tests for get_resolved() method."""

    def test_get_resolved_returns_all_fallback_fields(self):
        """Should return dict with all ENV_FALLBACKS fields resolved."""
        os.environ["TEST_API_KEY"] = "env-api"
        os.environ["TEST_SECRET_KEY"] = "env-secret"

        settings = APISettings.get_instance()
        settings.api_key = "db-api"  # Has DB value
        settings.secret_key = ""  # Will use env
        settings.save()

        resolved = settings.get_resolved()

        assert resolved == {
            "api_key": "db-api",  # From DB
            "secret_key": "env-secret",  # From env
        }

    def test_get_resolved_excludes_non_fallback_fields(self):
        """Should not include fields not in ENV_FALLBACKS."""
        settings = APISettings.get_instance()
        settings.base_url = "https://example.com"
        settings.save()

        resolved = settings.get_resolved()

        assert "base_url" not in resolved


@pytest.mark.django_db
class TestHasValue:
    """Tests for has_value() method."""

    def test_has_value_true_when_db_has_value(self):
        """Should return True when DB has a value."""
        settings = APISettings.get_instance()
        settings.api_key = "db-value"
        settings.save()

        assert settings.has_value("api_key") is True

    def test_has_value_true_when_env_has_value(self):
        """Should return True when env has a value (DB is blank)."""
        os.environ["TEST_API_KEY"] = "env-value"

        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.has_value("api_key") is True

    def test_has_value_false_when_both_empty(self):
        """Should return False when both DB and env are empty."""
        settings = APISettings.get_instance()
        settings.api_key = ""
        settings.save()

        assert settings.has_value("api_key") is False

    def test_has_value_false_for_non_fallback_field_when_blank(self):
        """Should return False for blank non-fallback field."""
        settings = APISettings.get_instance()
        settings.base_url = ""
        settings.save()

        assert settings.has_value("base_url") is False

    def test_has_value_true_for_non_fallback_field_with_value(self):
        """Should return True for non-fallback field with value."""
        settings = APISettings.get_instance()
        settings.base_url = "https://example.com"
        settings.save()

        assert settings.has_value("base_url") is True
