"""AI Provider implementations for django-ai-services."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Type

import httpx

try:
    from pydantic import BaseModel as PydanticModel, ValidationError
except ImportError:
    PydanticModel = None
    ValidationError = Exception


@dataclass
class AIResponse:
    """Standardized AI response across all providers."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw_response: dict
    tool_calls: list[dict] | None = None
    parsed: Any | None = None
    validation_errors: list[str] | None = None


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        response_model: Type | None = None,
        **kwargs,
    ) -> AIResponse:
        """Send chat completion request (sync)."""
        pass

    @abstractmethod
    async def achat(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        response_model: Type | None = None,
        **kwargs,
    ) -> AIResponse:
        """Send chat completion request (async)."""
        pass

    @abstractmethod
    def estimate_cost(
        self, model: str, input_tokens: int, max_output_tokens: int
    ) -> float:
        """Estimate cost before making request."""
        pass


class OpenRouterProvider(AIProvider):
    """OpenRouter API provider (supports Claude, GPT, etc.)."""

    BASE_URL = "https://openrouter.ai/api/v1"

    # Default pricing (USD per 1M tokens)
    DEFAULT_PRICING = {
        "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
        "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
        "openai/gpt-4o": {"input": 5.0, "output": 15.0},
        "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    }

    def __init__(
        self,
        api_key: str,
        site_url: str = "",
        site_name: str = "",
        pricing: dict | None = None,
    ):
        self.api_key = api_key
        self.site_url = site_url
        self.site_name = site_name
        self.pricing = pricing or self.DEFAULT_PRICING
        self.client = httpx.Client(timeout=60.0)
        self.async_client = httpx.AsyncClient(timeout=60.0)

    def estimate_cost(
        self, model: str, input_tokens: int, max_output_tokens: int
    ) -> float:
        pricing = self.pricing.get(model, {"input": 10.0, "output": 30.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _build_request(self, messages, model, max_tokens, temperature, tools):
        return {
            "model": model or "anthropic/claude-sonnet-4",
            "messages": messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature or 0.7,
            **({"tools": tools} if tools else {}),
        }

    def _parse_response(
        self,
        data: dict,
        model: str,
        response_model: Type | None = None,
    ) -> AIResponse:
        usage = data.get("usage", {})
        content = data["choices"][0]["message"]["content"] or ""

        # Calculate actual cost
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = self.estimate_cost(model, input_tokens, output_tokens)

        # Structured output validation
        parsed = None
        validation_errors = None
        if response_model and content and PydanticModel:
            try:
                import json

                parsed = response_model.model_validate_json(content)
            except (ValidationError, json.JSONDecodeError) as e:
                validation_errors = [str(e)]

        return AIResponse(
            content=content,
            model=data.get("model", model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            raw_response=data,
            tool_calls=data["choices"][0]["message"].get("tool_calls"),
            parsed=parsed,
            validation_errors=validation_errors,
        )

    def chat(
        self,
        messages,
        model=None,
        max_tokens=None,
        temperature=None,
        tools=None,
        response_model=None,
        **kwargs,
    ):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }
        payload = self._build_request(messages, model, max_tokens, temperature, tools)
        response = self.client.post(
            f"{self.BASE_URL}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        return self._parse_response(
            response.json(), model or payload["model"], response_model
        )

    async def achat(
        self,
        messages,
        model=None,
        max_tokens=None,
        temperature=None,
        tools=None,
        response_model=None,
        **kwargs,
    ):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }
        payload = self._build_request(messages, model, max_tokens, temperature, tools)
        response = await self.async_client.post(
            f"{self.BASE_URL}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        return self._parse_response(
            response.json(), model or payload["model"], response_model
        )


class OllamaProvider(AIProvider):
    """Local Ollama provider for offline/private use."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.client = httpx.Client(timeout=120.0)
        self.async_client = httpx.AsyncClient(timeout=120.0)

    def estimate_cost(
        self, model: str, input_tokens: int, max_output_tokens: int
    ) -> float:
        return 0.0  # Local = free

    def chat(
        self,
        messages,
        model=None,
        max_tokens=None,
        temperature=None,
        tools=None,
        response_model=None,
        **kwargs,
    ):
        payload = {
            "model": model or "mistral:latest",
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens or 4096,
                "temperature": temperature or 0.7,
            },
        }
        response = self.client.post(f"{self.host}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["message"]["content"]
        parsed = None
        validation_errors = None
        if response_model and content and PydanticModel:
            try:
                import json

                parsed = response_model.model_validate_json(content)
            except Exception as e:
                validation_errors = [str(e)]

        return AIResponse(
            content=content,
            model=model or "mistral:latest",
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,
            raw_response=data,
            parsed=parsed,
            validation_errors=validation_errors,
        )

    async def achat(
        self,
        messages,
        model=None,
        max_tokens=None,
        temperature=None,
        tools=None,
        response_model=None,
        **kwargs,
    ):
        payload = {
            "model": model or "mistral:latest",
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens or 4096,
                "temperature": temperature or 0.7,
            },
        }
        response = await self.async_client.post(f"{self.host}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["message"]["content"]
        parsed = None
        validation_errors = None
        if response_model and content and PydanticModel:
            try:
                import json

                parsed = response_model.model_validate_json(content)
            except Exception as e:
                validation_errors = [str(e)]

        return AIResponse(
            content=content,
            model=model or "mistral:latest",
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,
            raw_response=data,
            parsed=parsed,
            validation_errors=validation_errors,
        )
