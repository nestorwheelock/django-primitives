"""Tests for django-ai-services services."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal


@pytest.mark.django_db
class TestAIService:
    """Tests for AIService class."""

    def test_service_initialization(self):
        """AIService can be initialized."""
        from django_ai_services.services import AIService

        service = AIService()
        assert service.config is not None

    def test_service_initialization_with_user(self):
        """AIService can be initialized with user context."""
        from django_ai_services.services import AIService

        mock_user = Mock()
        mock_user.pk = 1
        service = AIService(user=mock_user)
        assert service.user == mock_user

    def test_service_initialization_with_session(self):
        """AIService can be initialized with session_id."""
        from django_ai_services.services import AIService

        service = AIService(session_id="test-session-123")
        assert service.session_id == "test-session-123"

    @patch("django_ai_services.providers.OpenRouterProvider.chat")
    def test_chat_logs_usage(self, mock_chat):
        """AIService.chat() logs usage to AIUsageLog."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIUsageLog
        from django_ai_services.providers import AIResponse

        mock_chat.return_value = AIResponse(
            content="Test response",
            model="anthropic/claude-sonnet-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            raw_response={},
        )

        service = AIService()
        initial_count = AIUsageLog.objects.count()

        service.chat(
            messages=[{"role": "user", "content": "Hello"}],
            operation="test_chat",
        )

        assert AIUsageLog.objects.count() == initial_count + 1
        log = AIUsageLog.objects.latest("created_at")
        assert log.operation == "test_chat"
        assert log.input_tokens == 100
        assert log.output_tokens == 50

    @patch("django_ai_services.providers.OpenRouterProvider.chat")
    def test_chat_returns_response(self, mock_chat):
        """AIService.chat() returns AIResponse."""
        from django_ai_services.services import AIService
        from django_ai_services.providers import AIResponse

        mock_chat.return_value = AIResponse(
            content="Test response",
            model="anthropic/claude-sonnet-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            raw_response={},
        )

        service = AIService()
        response = service.chat(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response.content == "Test response"
        assert response.input_tokens == 100

    def test_chat_raises_when_disabled(self):
        """AIService.chat() raises AIServiceDisabled when config.is_enabled=False."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import AIServiceDisabled

        config = AIServiceConfig.get_instance()
        config.is_enabled = False
        config.save()

        service = AIService()

        with pytest.raises(AIServiceDisabled):
            service.chat(messages=[{"role": "user", "content": "Hello"}])

        # Clean up
        config.is_enabled = True
        config.save()

    @patch("django_ai_services.providers.OpenRouterProvider.chat")
    def test_chat_logs_errors(self, mock_chat):
        """AIService.chat() logs errors when provider fails."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIUsageLog
        from django_ai_services.exceptions import ProviderError

        mock_chat.side_effect = Exception("API Error")

        service = AIService()
        initial_count = AIUsageLog.objects.count()

        with pytest.raises(ProviderError):
            service.chat(messages=[{"role": "user", "content": "Hello"}])

        # Should still log the failed attempt
        assert AIUsageLog.objects.count() == initial_count + 1
        log = AIUsageLog.objects.latest("created_at")
        assert log.success is False
        assert "API Error" in log.error_message


@pytest.mark.django_db
class TestCostEstimation:
    """Tests for cost estimation functionality."""

    def test_estimate_cost(self):
        """AIService can estimate cost before request."""
        from django_ai_services.services import AIService

        service = AIService()
        estimated = service.estimate_cost(
            messages=[{"role": "user", "content": "Hello, how are you?"}],
        )

        assert estimated >= 0
        assert estimated < 1.0  # Sanity check for simple message

    def test_budget_check_passes(self):
        """Budget check passes for normal requests."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig

        config = AIServiceConfig.get_instance()
        config.per_request_cost_limit_usd = Decimal("1.00")
        config.save()

        service = AIService()
        # Should not raise
        service._check_budget(0.01)

    def test_budget_check_raises_on_expensive_request(self):
        """Budget check raises BudgetExceeded for expensive requests."""
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.exceptions import BudgetExceeded

        config = AIServiceConfig.get_instance()
        config.per_request_cost_limit_usd = Decimal("0.10")
        config.save()

        service = AIService()

        with pytest.raises(BudgetExceeded):
            service._check_budget(0.50)  # $0.50 exceeds $0.10 limit
