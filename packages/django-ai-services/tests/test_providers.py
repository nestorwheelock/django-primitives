"""Tests for django-ai-services providers."""

import pytest
from unittest.mock import Mock, patch


class TestAIResponse:
    """Tests for AIResponse dataclass."""

    def test_ai_response_creation(self):
        """AIResponse can be created with required fields."""
        from django_ai_services.providers import AIResponse

        response = AIResponse(
            content="Hello, world!",
            model="anthropic/claude-sonnet-4",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            raw_response={"id": "test-123"},
        )

        assert response.content == "Hello, world!"
        assert response.model == "anthropic/claude-sonnet-4"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.cost_usd == 0.001


class TestOpenRouterProvider:
    """Tests for OpenRouterProvider."""

    def test_provider_initialization(self):
        """Provider can be initialized with API key."""
        from django_ai_services.providers import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key="test-api-key",
            site_url="https://test.com",
            site_name="Test Site",
        )

        assert provider.api_key == "test-api-key"
        assert provider.site_url == "https://test.com"
        assert provider.site_name == "Test Site"

    def test_cost_estimation(self):
        """Provider can estimate cost for a request."""
        from django_ai_services.providers import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")

        # anthropic/claude-sonnet-4: $3/1M input, $15/1M output
        cost = provider.estimate_cost(
            model="anthropic/claude-sonnet-4",
            input_tokens=1000,
            max_output_tokens=500,
        )

        # 1000 input * 3/1M + 500 output * 15/1M = 0.003 + 0.0075 = 0.0105
        assert cost > 0
        assert cost < 1.0  # Sanity check

    def test_provider_has_default_pricing(self):
        """Provider has default pricing for common models."""
        from django_ai_services.providers import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")

        assert "anthropic/claude-sonnet-4" in provider.DEFAULT_PRICING
        assert "input" in provider.DEFAULT_PRICING["anthropic/claude-sonnet-4"]
        assert "output" in provider.DEFAULT_PRICING["anthropic/claude-sonnet-4"]

    @patch("httpx.Client.post")
    def test_chat_sends_request(self, mock_post):
        """Provider.chat() sends request to OpenRouter API."""
        from django_ai_services.providers import OpenRouterProvider

        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "anthropic/claude-sonnet-4",
            "choices": [{"message": {"content": "Test response", "tool_calls": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        provider = OpenRouterProvider(api_key="test-key")
        response = provider.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model="anthropic/claude-sonnet-4",
        )

        assert response.content == "Test response"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        mock_post.assert_called_once()

    @patch("httpx.Client.post")
    def test_chat_includes_auth_headers(self, mock_post):
        """Provider.chat() includes proper authorization headers."""
        from django_ai_services.providers import OpenRouterProvider

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test", "tool_calls": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        provider = OpenRouterProvider(api_key="test-api-key")
        provider.chat(messages=[{"role": "user", "content": "Hello"}])

        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert "Bearer test-api-key" in headers.get("Authorization", "")
