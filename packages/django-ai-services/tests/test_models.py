"""Tests for django-ai-services models."""

import os
import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestAIServiceConfig:
    """Tests for AIServiceConfig singleton model."""

    def test_config_singleton_created(self):
        """AIServiceConfig singleton can be created and retrieved."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        assert config is not None
        assert config.pk is not None

    def test_config_has_default_provider(self):
        """Config has default provider set."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        assert config.default_provider == "openrouter"

    def test_config_has_default_model(self):
        """Config has default model set."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        assert "claude" in config.default_model.lower() or "gpt" in config.default_model.lower()

    def test_api_key_env_fallback(self):
        """API key falls back to environment variable if not in DB."""
        from django_ai_services.models import AIServiceConfig

        # Set environment variable
        os.environ["OPENROUTER_API_KEY"] = "test-key-from-env"

        config = AIServiceConfig.get_instance()
        provider_config = config.get_provider_config("openrouter")

        assert provider_config.get("api_key") == "test-key-from-env"

        # Clean up
        del os.environ["OPENROUTER_API_KEY"]

    def test_api_key_db_overrides_env(self):
        """API key from DB overrides environment variable."""
        from django_ai_services.models import AIServiceConfig

        # Set environment variable
        os.environ["OPENROUTER_API_KEY"] = "test-key-from-env"

        config = AIServiceConfig.get_instance()
        # Store key in DB
        config.provider_configs = {"openrouter": {"api_key": "test-key-from-db"}}
        config.save()

        provider_config = config.get_provider_config("openrouter")
        assert provider_config.get("api_key") == "test-key-from-db"

        # Clean up
        del os.environ["OPENROUTER_API_KEY"]

    def test_config_is_enabled_by_default(self):
        """Config has is_enabled=True by default."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        assert config.is_enabled is True

    def test_config_has_cost_limits(self):
        """Config has per_request_cost_limit_usd field."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        assert config.per_request_cost_limit_usd is not None
        assert config.per_request_cost_limit_usd > 0


@pytest.mark.django_db
class TestAIUsageLog:
    """Tests for AIUsageLog immutable model."""

    def test_usage_log_creation(self):
        """Usage log can be created with required fields."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            input_tokens=100,
            output_tokens=50,
        )
        assert log.pk is not None
        assert log.total_tokens == 150

    def test_usage_log_total_tokens_calculated(self):
        """Total tokens is calculated from input + output."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            input_tokens=200,
            output_tokens=100,
        )
        assert log.total_tokens == 300

    def test_usage_log_immutable(self):
        """Usage log cannot be updated after creation."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            input_tokens=100,
            output_tokens=50,
        )

        log.input_tokens = 999
        with pytest.raises(ValueError, match="immutable"):
            log.save()

    def test_usage_log_cannot_be_deleted(self):
        """Usage log cannot be deleted."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            input_tokens=100,
            output_tokens=50,
        )

        with pytest.raises(ValueError, match="cannot be deleted"):
            log.delete()

    def test_usage_log_has_timestamps(self):
        """Usage log has created_at timestamp."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
        )
        assert log.created_at is not None

    def test_usage_log_has_cost_fields(self):
        """Usage log has cost tracking fields."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            estimated_cost_usd=Decimal("0.001"),
            actual_cost_usd=Decimal("0.0008"),
        )
        assert log.estimated_cost_usd == Decimal("0.001")
        assert log.actual_cost_usd == Decimal("0.0008")

    def test_usage_log_supports_session_id(self):
        """Usage log supports session_id for tracking."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            session_id="test-session-123",
        )
        assert log.session_id == "test-session-123"

    def test_usage_log_supports_metadata(self):
        """Usage log supports arbitrary metadata."""
        from django_ai_services.models import AIUsageLog

        log = AIUsageLog.objects.create(
            operation="chat",
            provider="openrouter",
            model="anthropic/claude-sonnet-4",
            metadata={"custom_field": "custom_value"},
        )
        assert log.metadata["custom_field"] == "custom_value"
