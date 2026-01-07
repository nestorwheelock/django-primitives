"""Tests for async AI service functionality."""

import os
import pytest
from unittest.mock import patch, Mock, AsyncMock
from decimal import Decimal

# Allow sync ORM calls in async tests for simplicity
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


@pytest.mark.django_db
@pytest.mark.asyncio
class TestAsyncChat:
    """Tests for async chat method."""

    async def test_async_chat_returns_response(self):
        """achat() returns AIResponse."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.achat = AsyncMock(return_value=AIResponse(
                content="Async response",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                raw_response={},
            ))
            mock_get.return_value = mock_provider

            response = await service.achat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )

            assert response.content == "Async response"
            mock_provider.achat.assert_called_once()

    async def test_async_chat_logs_usage(self):
        """achat() creates usage log entry."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig, AIUsageLog
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        initial_count = AIUsageLog.objects.count()
        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.achat = AsyncMock(return_value=AIResponse(
                content="Success",
                model="test",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.002,
                raw_response={},
            ))
            mock_get.return_value = mock_provider

            await service.achat(
                messages=[{"role": "user", "content": "test"}],
                operation="async_test",
                skip_budget_check=True,
            )

        assert AIUsageLog.objects.count() == initial_count + 1
        log = AIUsageLog.objects.latest("created_at")
        assert log.operation == "async_test"
        assert log.input_tokens == 100
        assert log.output_tokens == 50

    async def test_async_chat_retry_on_failure(self):
        """achat() retries on transient failures."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        config = AIServiceConfig.get_instance()
        config.max_retries = 3
        config.retry_base_delay_seconds = Decimal("0.01")
        config.retry_jitter = False
        config.save()

        service = AIService()
        call_count = 0

        async def mock_achat(*args, **kwargs):
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
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.achat = mock_achat
            mock_get.return_value = mock_provider

            response = await service.achat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )

            assert response.content == "Success after retry"
            assert call_count == 3

    async def test_async_chat_fallback_on_failure(self):
        """achat() uses fallback provider when primary fails."""
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
                mock.achat = AsyncMock(side_effect=Exception("Primary failed"))
            else:  # ollama
                mock.achat = AsyncMock(return_value=AIResponse(
                    content="Fallback response",
                    model="mistral:latest",
                    input_tokens=10,
                    output_tokens=5,
                    cost_usd=0.0,
                    raw_response={},
                ))
            return mock

        with patch.object(service, "_get_provider", side_effect=get_provider):
            response = await service.achat(
                messages=[{"role": "user", "content": "test"}],
                skip_budget_check=True,
            )
            assert response.content == "Fallback response"

        log = AIUsageLog.objects.latest("created_at")
        assert log.used_fallback is True
