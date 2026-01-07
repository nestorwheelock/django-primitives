"""Tests for circuit breaker functionality."""

import pytest
from unittest.mock import patch, Mock
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    def test_circuit_opens_after_threshold(self):
        """Circuit opens after configured number of failures."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import ProviderError

        config = AIServiceConfig.get_instance()
        config.circuit_breaker_threshold = 3
        config.max_retries = 0  # No retries, fail immediately
        config.save()

        service = AIService()

        # Simulate failures
        with patch.object(service, "_get_provider") as mock_provider:
            mock_provider.return_value.chat.side_effect = Exception("API Error")
            mock_provider.return_value.estimate_cost.return_value = 0.0

            for i in range(3):
                try:
                    service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)
                except ProviderError:
                    pass

        # Refresh config to get updated health
        config.refresh_from_db()
        health = config.provider_health.get("openrouter", {})
        assert health.get("circuit_open") is True
        assert health.get("failures") >= 3

    def test_circuit_blocks_requests_when_open(self):
        """Requests are blocked when circuit is open."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import CircuitOpen

        config = AIServiceConfig.get_instance()
        # Manually open the circuit
        config.provider_health = {
            "openrouter": {
                "failures": 5,
                "circuit_open": True,
                "last_failure": timezone.now().isoformat(),
            }
        }
        config.circuit_breaker_reset_minutes = 15
        config.save()

        service = AIService()

        with pytest.raises(CircuitOpen):
            service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)

    def test_circuit_resets_after_timeout(self):
        """Circuit resets (half-open) after reset timeout."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        # Set circuit open but with old last_failure (past reset time)
        old_failure = (timezone.now() - timedelta(minutes=20)).isoformat()
        config.provider_health = {
            "openrouter": {
                "failures": 5,
                "circuit_open": True,
                "last_failure": old_failure,
            }
        }
        config.circuit_breaker_reset_minutes = 15
        config.max_retries = 0
        config.save()

        service = AIService()

        # Should not raise CircuitOpen, circuit should reset
        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.chat.return_value = AIResponse(
                content="Success",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_provider.estimate_cost.return_value = 0.0
            mock_get.return_value = mock_provider

            response = service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)
            assert response.content == "Success"

        # Circuit should now be closed
        config.refresh_from_db()
        health = config.provider_health.get("openrouter", {})
        assert health.get("circuit_open") is False
        assert health.get("failures") == 0

    def test_successful_request_resets_failures(self):
        """Successful request resets failure count."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.provider_health = {
            "openrouter": {"failures": 2, "circuit_open": False}
        }
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.chat.return_value = AIResponse(
                content="Success",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )
            mock_provider.estimate_cost.return_value = 0.0
            mock_get.return_value = mock_provider

            service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)

        config.refresh_from_db()
        health = config.provider_health.get("openrouter", {})
        assert health.get("failures") == 0


@pytest.mark.django_db
class TestRetryLogic:
    """Tests for retry with exponential backoff."""

    def test_retry_on_transient_failure(self):
        """Service retries on transient failures."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.max_retries = 3
        config.retry_base_delay_seconds = 0.01  # Fast for testing
        config.retry_jitter = False
        config.save()

        service = AIService()
        call_count = 0

        def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return AIResponse(
                content="Success after retry",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.chat.side_effect = mock_chat
            mock_provider.estimate_cost.return_value = 0.0
            mock_get.return_value = mock_provider

            response = service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)
            assert response.content == "Success after retry"
            assert call_count == 3

    def test_retry_exhaustion_raises_error(self):
        """Error raised after all retries exhausted."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import ProviderError

        config = AIServiceConfig.get_instance()
        config.max_retries = 2
        config.retry_base_delay_seconds = 0.01
        config.fallback_provider = ""  # No fallback
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.chat.side_effect = Exception("Persistent error")
            mock_provider.estimate_cost.return_value = 0.0
            mock_get.return_value = mock_provider

            with pytest.raises(ProviderError, match="Persistent error"):
                service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)

    def test_retry_count_logged(self):
        """Retry count is logged in usage log."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.max_retries = 3
        config.retry_base_delay_seconds = 0.01
        config.save()

        service = AIService()
        call_count = 0

        def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return AIResponse(
                content="Success",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.chat.side_effect = mock_chat
            mock_provider.estimate_cost.return_value = 0.0
            mock_get.return_value = mock_provider

            service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)

        log = AIUsageLog.objects.latest("created_at")
        assert log.retry_count == 2  # Failed twice before success


@pytest.mark.django_db
class TestFallbackProvider:
    """Tests for fallback provider functionality."""

    def test_fallback_provider_used_on_failure(self):
        """Fallback provider used when primary fails."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.fallback_provider = "ollama"
        config.fallback_model = "mistral:latest"
        config.save()

        service = AIService()

        def get_provider(name):
            mock = Mock()
            mock.estimate_cost.return_value = 0.0
            if name == "openrouter":
                mock.chat.side_effect = Exception("Primary failed")
            else:  # ollama
                mock.chat.return_value = AIResponse(
                    content="Fallback response",
                    model="mistral:latest",
                    input_tokens=10,
                    output_tokens=5,
                    cost_usd=0.0,
                    raw_response={},
                )
            return mock

        with patch.object(service, "_get_provider", side_effect=get_provider):
            response = service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)
            assert response.content == "Fallback response"

        log = AIUsageLog.objects.latest("created_at")
        assert log.used_fallback is True
        assert "Fallback used" in log.error_message

    def test_no_fallback_when_not_configured(self):
        """No fallback attempted when not configured."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import ProviderError

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.fallback_provider = ""
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.chat.side_effect = Exception("Primary failed")
            mock_provider.estimate_cost.return_value = 0.0
            mock_get.return_value = mock_provider

            with pytest.raises(ProviderError):
                service.chat(messages=[{"role": "user", "content": "test"}], skip_budget_check=True)
