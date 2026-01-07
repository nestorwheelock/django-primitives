"""Tests for structured output validation and repair."""

import pytest
from unittest.mock import patch, Mock
from decimal import Decimal


@pytest.mark.django_db
class TestStructuredOutputValidation:
    """Tests for structured output with Pydantic validation."""

    def test_valid_structured_output_parsed(self):
        """Valid JSON response is parsed into Pydantic model."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        class AnalysisResult(BaseModel):
            category: str
            confidence: float

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.return_value = AIResponse(
                content='{"category": "electronics", "confidence": 0.95}',
                model="test",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                raw_response={},
                parsed=AnalysisResult(category="electronics", confidence=0.95),
                validation_errors=None,
            )
            mock_get.return_value = mock_provider

            response = service.chat(
                messages=[{"role": "user", "content": "Analyze this item"}],
                response_model=AnalysisResult,
                skip_budget_check=True,
            )

            assert response.parsed is not None
            assert response.parsed.category == "electronics"
            assert response.parsed.confidence == 0.95

    def test_invalid_json_triggers_validation_error(self):
        """Invalid JSON response sets validation_errors."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        class AnalysisResult(BaseModel):
            category: str
            confidence: float

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            # First call returns invalid JSON, triggers repair
            mock_provider.chat.return_value = AIResponse(
                content='not valid json',
                model="test",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                raw_response={},
                parsed=None,
                validation_errors=["JSON decode error"],
            )
            mock_get.return_value = mock_provider

            # With max_repair_attempts=0, should return the failed response
            response = service.chat(
                messages=[{"role": "user", "content": "Analyze this item"}],
                response_model=AnalysisResult,
                skip_budget_check=True,
                max_repair_attempts=0,  # Disable repair loop
            )

            assert response.parsed is None
            assert response.validation_errors is not None

    def test_schema_mismatch_triggers_validation_error(self):
        """Response that doesn't match schema sets validation_errors."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        class AnalysisResult(BaseModel):
            category: str
            confidence: float

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            # Valid JSON but missing required field
            mock_provider.chat.return_value = AIResponse(
                content='{"category": "electronics"}',
                model="test",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                raw_response={},
                parsed=None,
                validation_errors=["Field 'confidence' is required"],
            )
            mock_get.return_value = mock_provider

            response = service.chat(
                messages=[{"role": "user", "content": "Analyze this item"}],
                response_model=AnalysisResult,
                skip_budget_check=True,
                max_repair_attempts=0,
            )

            assert response.parsed is None
            assert response.validation_errors is not None


@pytest.mark.django_db
class TestStructuredOutputRepair:
    """Tests for structured output repair loop."""

    def test_repair_loop_fixes_invalid_output(self):
        """Repair loop retries with schema feedback until valid."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        class AnalysisResult(BaseModel):
            category: str
            confidence: float

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()
        call_count = 0

        def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: invalid response
                return AIResponse(
                    content='{"category": "electronics"}',  # missing confidence
                    model="test",
                    input_tokens=10,
                    output_tokens=20,
                    cost_usd=0.001,
                    raw_response={},
                    parsed=None,
                    validation_errors=["Field 'confidence' is required"],
                )
            else:
                # Repair call: valid response
                return AIResponse(
                    content='{"category": "electronics", "confidence": 0.95}',
                    model="test",
                    input_tokens=30,
                    output_tokens=25,
                    cost_usd=0.002,
                    raw_response={},
                    parsed=AnalysisResult(category="electronics", confidence=0.95),
                    validation_errors=None,
                )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = mock_chat
            mock_get.return_value = mock_provider

            response = service.chat(
                messages=[{"role": "user", "content": "Analyze this item"}],
                response_model=AnalysisResult,
                skip_budget_check=True,
                max_repair_attempts=2,
            )

            assert response.parsed is not None
            assert response.parsed.category == "electronics"
            assert response.parsed.confidence == 0.95
            assert call_count == 2  # Initial + 1 repair

    def test_repair_loop_raises_after_max_attempts(self):
        """Repair loop raises ValidationFailed after max attempts."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse
        from django_ai_services.exceptions import ValidationFailed

        class AnalysisResult(BaseModel):
            category: str
            confidence: float

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()

        def mock_chat(*args, **kwargs):
            # Always return invalid response
            return AIResponse(
                content='{"category": "electronics"}',
                model="test",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                raw_response={},
                parsed=None,
                validation_errors=["Field 'confidence' is required"],
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = mock_chat
            mock_get.return_value = mock_provider

            with pytest.raises(ValidationFailed, match="repair attempts"):
                service.chat(
                    messages=[{"role": "user", "content": "Analyze this item"}],
                    response_model=AnalysisResult,
                    skip_budget_check=True,
                    max_repair_attempts=2,
                )

    def test_repair_loop_includes_error_feedback(self):
        """Repair loop includes validation errors in retry message."""
        pytest.importorskip("pydantic")
        from pydantic import BaseModel
        from django_ai_services.services import AIService
        from django_ai_services.models import AIServiceConfig
        from django_ai_services.providers import AIResponse

        class AnalysisResult(BaseModel):
            category: str
            confidence: float

        config = AIServiceConfig.get_instance()
        config.max_retries = 0
        config.save()

        service = AIService()
        repair_messages = None

        def mock_chat(messages, *args, **kwargs):
            nonlocal repair_messages
            if len(messages) > 1:  # Repair call has more messages
                repair_messages = messages
                return AIResponse(
                    content='{"category": "electronics", "confidence": 0.95}',
                    model="test",
                    input_tokens=30,
                    output_tokens=25,
                    cost_usd=0.002,
                    raw_response={},
                    parsed=AnalysisResult(category="electronics", confidence=0.95),
                    validation_errors=None,
                )
            return AIResponse(
                content='invalid',
                model="test",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.001,
                raw_response={},
                parsed=None,
                validation_errors=["Invalid JSON"],
            )

        with patch.object(service, "_get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.estimate_cost.return_value = 0.0
            mock_provider.chat.side_effect = mock_chat
            mock_get.return_value = mock_provider

            service.chat(
                messages=[{"role": "user", "content": "Analyze this"}],
                response_model=AnalysisResult,
                skip_budget_check=True,
                max_repair_attempts=2,
            )

            # Check repair message includes error feedback
            assert repair_messages is not None
            assert len(repair_messages) == 3  # original + assistant + repair request
            repair_content = repair_messages[-1]["content"]
            assert "schema" in repair_content.lower() or "error" in repair_content.lower()
