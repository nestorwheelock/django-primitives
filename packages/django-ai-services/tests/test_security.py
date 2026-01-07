"""Tests for security features: encryption, version pinning, logging controls."""

import pytest
from unittest.mock import patch, Mock
import os


@pytest.mark.django_db
class TestEncryptedApiKeyStorage:
    """Tests for encrypted API key storage."""

    def test_set_encryption_key_class_method(self):
        """AIServiceConfig.set_encryption_key() stores key."""
        from django_ai_services.models import AIServiceConfig

        # Reset encryption key
        AIServiceConfig._encryption_key = None

        AIServiceConfig.set_encryption_key("test-key-32-bytes-long-exactly!!")
        assert AIServiceConfig._encryption_key is not None

        # Clean up
        AIServiceConfig._encryption_key = None

    def test_provider_configs_encrypted_when_key_set(self):
        """Provider configs are encrypted when encryption key is set."""
        from django_ai_services.models import AIServiceConfig
        from cryptography.fernet import Fernet

        # Generate a valid Fernet key
        key = Fernet.generate_key().decode()
        AIServiceConfig.set_encryption_key(key)

        config = AIServiceConfig.get_instance()
        config.provider_configs = {"openrouter": {"api_key": "secret-key-123"}}
        config.save()

        # Refresh and check raw storage is encrypted (not plain JSON)
        config.refresh_from_db()
        raw_value = config._provider_configs

        # Should not contain plain text
        assert "secret-key-123" not in raw_value
        assert "openrouter" not in raw_value  # Entire JSON is encrypted

        # But property should decrypt correctly
        decrypted = config.provider_configs
        assert decrypted["openrouter"]["api_key"] == "secret-key-123"

        # Clean up
        AIServiceConfig._encryption_key = None

    def test_provider_configs_readable_without_encryption(self):
        """Provider configs work without encryption (plain JSON)."""
        from django_ai_services.models import AIServiceConfig

        # Ensure no encryption key
        AIServiceConfig._encryption_key = None

        config = AIServiceConfig.get_instance()
        config.provider_configs = {"test_provider": {"api_key": "test-key"}}
        config.save()

        config.refresh_from_db()
        assert config.provider_configs["test_provider"]["api_key"] == "test-key"

    def test_encrypted_configs_persist_across_instances(self):
        """Encrypted configs can be read after restart (with same key)."""
        from django_ai_services.models import AIServiceConfig
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        AIServiceConfig.set_encryption_key(key)

        config = AIServiceConfig.get_instance()
        config.provider_configs = {"provider": {"secret": "value"}}
        config.save()

        # Simulate app restart - clear singleton cache
        AIServiceConfig._encryption_key = None
        AIServiceConfig._instance = None

        # Re-set key (would happen in app startup)
        AIServiceConfig.set_encryption_key(key)

        # Get fresh instance
        new_config = AIServiceConfig.get_instance()
        assert new_config.provider_configs["provider"]["secret"] == "value"

        # Clean up
        AIServiceConfig._encryption_key = None


@pytest.mark.django_db
class TestModelVersionPinning:
    """Tests for model version pinning."""

    def test_model_version_pinning_disabled_by_default(self):
        """Model version pinning is off by default."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        assert config.pin_model_version is False

    def test_get_model_without_pinning_returns_unchanged(self):
        """get_model_with_version returns unchanged model when pinning disabled."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        config.pin_model_version = False
        config.save()

        result = config.get_model_with_version("anthropic/claude-sonnet-4")
        assert result == "anthropic/claude-sonnet-4"

    def test_get_model_with_pinning_appends_version(self):
        """get_model_with_version appends version when pinning enabled."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        config.pin_model_version = True
        config.pinned_model_versions = {
            "anthropic/claude-sonnet-4": "20240620",
            "openai/gpt-4o": "2024-05-13",
        }
        config.save()

        result = config.get_model_with_version("anthropic/claude-sonnet-4")
        assert result == "anthropic/claude-sonnet-4-20240620"

    def test_get_model_with_pinning_no_version_returns_unchanged(self):
        """get_model_with_version returns unchanged if no version mapping exists."""
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        config.pin_model_version = True
        config.pinned_model_versions = {"other/model": "v1"}
        config.save()

        result = config.get_model_with_version("anthropic/claude-sonnet-4")
        assert result == "anthropic/claude-sonnet-4"  # No mapping, unchanged

    def test_chat_uses_pinned_version(self):
        """AIService.chat() uses pinned model version."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.pin_model_version = True
        config.pinned_model_versions = {"anthropic/claude-sonnet-4": "20240620"}
        config.max_retries = 0
        config.save()

        service = AIService()
        captured_model = None

        def capture_chat(messages, model, **kwargs):
            nonlocal captured_model
            captured_model = model
            return AIResponse(
                content="test",
                model=model,
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = capture_chat
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )

        assert captured_model == "anthropic/claude-sonnet-4-20240620"


@pytest.mark.django_db
class TestPromptLoggingControls:
    """Tests for prompt/response logging privacy controls."""

    def test_prompt_hash_logged_by_default(self):
        """Prompt hash is logged by default (safe for deduplication)."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.log_prompt_hash = True  # Default
        config.log_prompts = False
        config.log_responses = False
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "test message"}],
                skip_budget_check=True,
            )

        log = AIUsageLog.objects.latest("created_at")
        assert log.prompt_hash != ""  # Hash is logged
        assert len(log.prompt_hash) == 64  # SHA-256
        assert log.prompt_preview == ""  # Prompt not logged
        assert log.response_preview == ""  # Response not logged

    def test_prompt_preview_logged_when_enabled(self):
        """Prompt preview is logged when log_prompts=True."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.log_prompts = True
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "secret prompt"}],
                skip_budget_check=True,
            )

        log = AIUsageLog.objects.latest("created_at")
        assert "secret prompt" in log.prompt_preview

    def test_response_preview_logged_when_enabled(self):
        """Response preview is logged when log_responses=True."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.log_responses = True
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="secret response content",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )

        log = AIUsageLog.objects.latest("created_at")
        assert "secret response content" in log.response_preview

    def test_prompt_hash_disabled(self):
        """Prompt hash can be disabled."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.log_prompt_hash = False
        config.log_prompts = False
        config.log_responses = False
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )

        log = AIUsageLog.objects.latest("created_at")
        assert log.prompt_hash == ""
        assert log.prompt_preview == ""
        assert log.response_preview == ""

    def test_long_prompts_truncated(self):
        """Long prompts are truncated to max length."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.log_prompts = True
        config.max_retries = 0
        config.save()

        service = AIService()
        long_prompt = "x" * 1000  # Longer than 500 char limit

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content="response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": long_prompt}],
                skip_budget_check=True,
            )

        log = AIUsageLog.objects.latest("created_at")
        assert len(log.prompt_preview) <= 500
