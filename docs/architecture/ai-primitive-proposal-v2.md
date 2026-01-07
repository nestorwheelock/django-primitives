# AI Primitive Proposal v2: django-ai-services

## Change Summary

**What Changed from v1 → v2** (based on analysis report findings):

| Change | Reason |
|--------|--------|
| Added encrypted API key storage option | Gap: All three projects store keys in plain text |
| Added circuit breaker with provider health tracking | Gap: No proactive failure handling in any project |
| Added retry with exponential backoff + jitter | Gap: Only nestorwheelock has basic retries |
| Added sync + async interface (`chat()` / `achat()`) | Gap: No project fully leverages async |
| Added structured output validation with repair loop | Gap: All projects use try/except JSON parsing |
| Added pre-request cost estimation + budget guard | Gap: All calculate cost AFTER the call |
| Added model version pinning support | Gap: Provider model updates break behavior |
| Added django-audit-log integration (dual logging) | Gap: No unified audit trail integration |
| Combined AIUsageLog fields from all three projects | Union: user, model, tokens, cost, timing, errors, session, target |
| Revised phases to ship MVP earlier | Phase 1 now shippable in days, not weeks |
| Added detailed Migration Strategy section | Concrete steps for each project |
| Moved ToolRegistry to Phase 2 | Needed earlier since it affects core API |

**What Stays the Same**:
- Scope boundaries (primitive = pipes/meters, not water)
- Layer placement (Infrastructure)
- GenericFK patterns
- Singleton config
- Provider abstraction

---

## The Single Question This Primitive Answers

> **"How do I integrate AI services into my Django application with proper audit trails, cost tracking, reliability, and configuration management?"**

---

## Scope Boundaries (HARD RULES)

### INCLUDED in Primitive (Infrastructure)

| Component | Purpose |
|-----------|---------|
| `AIServiceConfig` | Singleton config: API keys, models, limits, circuit breaker state |
| `AIUsageLog` | Immutable audit trail of ALL AI API calls |
| `AIAnalysis` | GenericFK-based analysis result storage |
| `AIProvider` | Abstract provider interface with fallback chain |
| `ToolRegistry` | Permission-gated function calling infrastructure |
| Cost estimation | Pre-request budget checks |
| Circuit breaker | Provider health monitoring |
| Retry logic | Exponential backoff with jitter |
| Idempotency | Via django-decisioning integration |
| Audit integration | Via django-audit-log integration |

### EXCLUDED from Primitive (App Responsibility)

| Component | Why Excluded |
|-----------|--------------|
| Conversation/Chat models | UI-coupled, varies by app (nestorwheelock: ChatSession, vetfriendly: Conversation) |
| Content indexing/embeddings | Requires vector DB, domain-specific (nestorwheelock: ContentIndex) |
| Image analysis schemas | Too specific (nestorwheelock: 50+ MediaAnalysis fields) |
| OSINT processing | Specialized use case (nestorwheelock only) |
| Module/template systems | Domain-specific pipelines (inventory-ai only) |
| Natural language command parsing | Domain-specific grammar |
| Multi-language support | Not universally needed (vetfriendly only) |
| Tool implementations | Domain-specific by definition |
| Context builders | Each app builds own context |
| Domain prompts | App-specific prompt engineering |

---

## Layer Placement

```
INFRASTRUCTURE LAYER (like django-decisioning, django-audit-log)
└─ django-ai-services
   ├─ Depends on: django-basemodels, django-singleton, django-decisioning, django-audit-log
   ├─ Used by: Any application layer package
   └─ Provides: Services and infrastructure, not domain models
```

---

## Data Model

### 1. AIServiceConfig (Singleton)

```python
from django_singleton import SingletonModel
from django.db import models
from django.conf import settings
import os
import json
from cryptography.fernet import Fernet

class AIServiceConfig(SingletonModel):
    """
    Global AI service configuration.
    Supports encrypted API key storage with environment fallback.
    """

    # ═══════════════════════════════════════════════════════════════════
    # PROVIDER CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════

    # Provider configs stored as JSON (optionally encrypted)
    # Structure: {provider_name: {api_key, base_url, site_url, site_name, ...}}
    _provider_configs = models.TextField(
        db_column="provider_configs",
        default="{}",
        help_text="Provider-specific configs (encrypted if encryption_key set)"
    )

    # Encryption key for API keys (stored in env, not DB)
    # If set, provider_configs are encrypted at rest
    # Usage: AIServiceConfig.set_encryption_key(os.environ['AI_ENCRYPTION_KEY'])
    _encryption_key: str | None = None

    # Default Provider & Model
    default_provider = models.CharField(max_length=50, default="openrouter")
    default_model = models.CharField(max_length=100, default="anthropic/claude-sonnet-4")
    default_max_tokens = models.PositiveIntegerField(default=4096)
    default_temperature = models.DecimalField(max_digits=3, decimal_places=2, default=0.7)

    # Model Version Pinning
    pin_model_version = models.BooleanField(
        default=False,
        help_text="If True, append version date to model name for reproducibility"
    )
    pinned_model_versions = models.JSONField(
        default=dict,
        help_text="Model → version mapping: {'anthropic/claude-sonnet-4': '20240620'}"
    )

    # Fallback Chain
    fallback_provider = models.CharField(max_length=50, blank=True)
    fallback_model = models.CharField(max_length=100, blank=True)

    # ═══════════════════════════════════════════════════════════════════
    # COST CONTROLS
    # ═══════════════════════════════════════════════════════════════════

    # Budget Limits
    daily_cost_limit_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Max spend per day (null = unlimited)"
    )
    per_request_cost_limit_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=0.50,
        help_text="Pre-flight cost check rejects requests above this"
    )
    monthly_cost_limit_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    pause_on_budget_exceeded = models.BooleanField(default=False)

    # Token Budgets (per operation type)
    token_budgets = models.JSONField(
        default=dict,
        help_text="Operation-specific max_tokens: {operation: max_tokens}"
    )

    # Model Pricing (for cost estimation)
    model_pricing = models.JSONField(
        default=dict,
        help_text="Pricing per model: {model: {input_per_1m: X, output_per_1m: Y}}"
    )

    # ═══════════════════════════════════════════════════════════════════
    # RATE LIMITING (hints for app layer)
    # ═══════════════════════════════════════════════════════════════════

    requests_per_minute_anonymous = models.PositiveIntegerField(default=10)
    requests_per_minute_authenticated = models.PositiveIntegerField(default=60)
    requests_per_day_per_user = models.PositiveIntegerField(default=1000)
    request_cooldown_seconds = models.PositiveIntegerField(default=2)

    # ═══════════════════════════════════════════════════════════════════
    # RELIABILITY: CIRCUIT BREAKER
    # ═══════════════════════════════════════════════════════════════════

    # Circuit breaker state (updated by service layer)
    provider_health = models.JSONField(
        default=dict,
        help_text="Health state: {provider: {failures: N, last_failure: ts, circuit_open: bool}}"
    )
    circuit_breaker_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Consecutive failures before opening circuit"
    )
    circuit_breaker_reset_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Minutes before attempting to close circuit"
    )

    # ═══════════════════════════════════════════════════════════════════
    # RELIABILITY: RETRY
    # ═══════════════════════════════════════════════════════════════════

    max_retries = models.PositiveIntegerField(default=3)
    retry_base_delay_seconds = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.0
    )
    retry_max_delay_seconds = models.DecimalField(
        max_digits=5, decimal_places=2, default=30.0
    )
    retry_jitter = models.BooleanField(
        default=True,
        help_text="Add randomness to retry delays to prevent thundering herd"
    )

    # ═══════════════════════════════════════════════════════════════════
    # LOGGING & DEBUG
    # ═══════════════════════════════════════════════════════════════════

    is_enabled = models.BooleanField(default=True)
    debug_mode = models.BooleanField(default=False)

    # Prompt/Response logging (privacy/storage tradeoffs)
    log_prompt_hash = models.BooleanField(
        default=True,
        help_text="Always safe: SHA-256 for deduplication"
    )
    log_prompts = models.BooleanField(
        default=False,
        help_text="Privacy concern: stores prompt preview"
    )
    log_responses = models.BooleanField(
        default=False,
        help_text="Storage concern: stores response preview"
    )

    class Meta:
        verbose_name = "AI Service Configuration"

    # ═══════════════════════════════════════════════════════════════════
    # ENCRYPTION METHODS
    # ═══════════════════════════════════════════════════════════════════

    @classmethod
    def set_encryption_key(cls, key: str):
        """Set encryption key from environment (call at app startup)."""
        cls._encryption_key = key

    def _get_fernet(self) -> Fernet | None:
        if self._encryption_key:
            return Fernet(self._encryption_key.encode())
        return None

    @property
    def provider_configs(self) -> dict:
        """Decrypt and return provider configs."""
        fernet = self._get_fernet()
        if fernet and self._provider_configs:
            try:
                decrypted = fernet.decrypt(self._provider_configs.encode())
                return json.loads(decrypted)
            except Exception:
                pass
        try:
            return json.loads(self._provider_configs)
        except json.JSONDecodeError:
            return {}

    @provider_configs.setter
    def provider_configs(self, value: dict):
        """Encrypt and store provider configs."""
        json_str = json.dumps(value)
        fernet = self._get_fernet()
        if fernet:
            self._provider_configs = fernet.encrypt(json_str.encode()).decode()
        else:
            self._provider_configs = json_str

    def get_provider_config(self, provider_name: str) -> dict:
        """Get config for specific provider, with env fallback."""
        config = self.provider_configs.get(provider_name, {}).copy()

        # Environment variable fallback for API key
        if not config.get('api_key'):
            env_key = f"{provider_name.upper()}_API_KEY"
            config['api_key'] = os.environ.get(env_key, '')

        return config

    def get_model_with_version(self, model: str) -> str:
        """Apply version pinning if enabled."""
        if not self.pin_model_version:
            return model
        version = self.pinned_model_versions.get(model)
        if version:
            return f"{model}-{version}"
        return model
```

### 2. AIUsageLog (Immutable Audit Trail)

Combined fields from all three projects:

```python
import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AIUsageLog(models.Model):
    """
    Immutable record of every AI API call.
    Combined schema from: nestorwheelock (service type, user, cost),
    inventory-ai (timing, errors), vetfriendly (session_id).
    """

    # ═══════════════════════════════════════════════════════════════════
    # IDENTITY
    # ═══════════════════════════════════════════════════════════════════

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who triggered this?
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ai_usage_logs"
    )

    # Session tracking (from vetfriendly)
    session_id = models.CharField(max_length=255, blank=True, db_index=True)

    # What was the target? (from inventory-ai: item_id)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+"
    )
    target_object_id = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # ═══════════════════════════════════════════════════════════════════
    # OPERATION (from nestorwheelock: service type)
    # ═══════════════════════════════════════════════════════════════════

    operation = models.CharField(
        max_length=100, db_index=True,
        help_text="e.g., chat, analyze, classify, tagging, enhancement"
    )

    # ═══════════════════════════════════════════════════════════════════
    # PROVIDER & MODEL
    # ═══════════════════════════════════════════════════════════════════

    provider = models.CharField(max_length=50)  # openrouter, ollama, custom
    model = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50, blank=True)

    # ═══════════════════════════════════════════════════════════════════
    # TOKEN USAGE (from all three)
    # ═══════════════════════════════════════════════════════════════════

    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    # ═══════════════════════════════════════════════════════════════════
    # COST TRACKING (from all three)
    # ═══════════════════════════════════════════════════════════════════

    estimated_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True,
        help_text="Pre-request estimate"
    )
    actual_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, default=0,
        help_text="Post-request actual"
    )

    # ═══════════════════════════════════════════════════════════════════
    # PERFORMANCE (from inventory-ai)
    # ═══════════════════════════════════════════════════════════════════

    processing_time_ms = models.PositiveIntegerField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    # ═══════════════════════════════════════════════════════════════════
    # STATUS (from inventory-ai)
    # ═══════════════════════════════════════════════════════════════════

    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    used_fallback = models.BooleanField(default=False)

    # ═══════════════════════════════════════════════════════════════════
    # DEBUG (privacy-controlled)
    # ═══════════════════════════════════════════════════════════════════

    prompt_hash = models.CharField(max_length=64, blank=True, db_index=True)
    prompt_preview = models.CharField(max_length=500, blank=True)
    response_preview = models.CharField(max_length=500, blank=True)

    # ═══════════════════════════════════════════════════════════════════
    # TIMESTAMPS
    # ═══════════════════════════════════════════════════════════════════

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Flexible metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["operation", "created_at"]),
            models.Index(fields=["provider", "model", "created_at"]),
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["success", "created_at"]),
            models.Index(fields=["session_id", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Immutability check
        if self.pk and AIUsageLog.objects.filter(pk=self.pk).exists():
            raise ValueError("AIUsageLog records are immutable")
        self.total_tokens = self.input_tokens + self.output_tokens
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AIUsageLog records cannot be deleted")
```

### 3. AIAnalysis (GenericFK Analysis Record)

```python
from django_basemodels import BaseModel
from django_decisioning import TimeSemanticsMixin

class AIAnalysis(TimeSemanticsMixin, BaseModel):
    """
    Record of AI analysis performed on any entity.
    Uses GenericFK to attach to any model.
    Supports idempotency via input_hash.
    """

    # What was analyzed?
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    target_object_id = models.CharField(max_length=255)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Analysis Type
    analysis_type = models.CharField(max_length=100, db_index=True)

    # Model Used
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50, blank=True)

    # Input (for idempotency)
    input_data = models.JSONField(default=dict)
    input_hash = models.CharField(max_length=64, db_index=True)

    # Output
    result = models.JSONField(default=dict)
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )

    # Validation status (for structured output)
    validation_passed = models.BooleanField(default=True)
    validation_errors = models.JSONField(default=list, blank=True)
    repair_attempts = models.PositiveIntegerField(default=0)

    # Who triggered this?
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ai_analyses"
    )

    # Link to usage log
    usage_log = models.ForeignKey(
        AIUsageLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="analyses"
    )

    # Review status
    is_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["analysis_type", "created_at"]),
            models.Index(fields=["input_hash"]),
            models.Index(fields=["triggered_by", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(confidence__isnull=True) |
                      (models.Q(confidence__gte=0) & models.Q(confidence__lte=1)),
                name="ai_analysis_confidence_range"
            ),
        ]
```

---

## Service Layer

### Provider Abstraction with Retry & Circuit Breaker

```python
# providers.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, Type
from pydantic import BaseModel as PydanticModel, ValidationError
import httpx
import asyncio
import random
import time

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
    # Structured output (if response_model was provided)
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
        response_model: Type[PydanticModel] | None = None,
        **kwargs
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
        response_model: Type[PydanticModel] | None = None,
        **kwargs
    ) -> AIResponse:
        """Send chat completion request (async)."""
        pass

    @abstractmethod
    def estimate_cost(self, model: str, input_tokens: int, max_output_tokens: int) -> float:
        """Estimate cost before making request."""
        pass

class OpenRouterProvider(AIProvider):
    """OpenRouter API provider (supports Claude, GPT, etc.)."""

    BASE_URL = "https://openrouter.ai/api/v1"

    # Default pricing (USD per 1M tokens) - override via config
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

    def estimate_cost(self, model: str, input_tokens: int, max_output_tokens: int) -> float:
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
        response_model: Type[PydanticModel] | None = None,
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
        if response_model and content:
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

    def chat(self, messages, model=None, max_tokens=None, temperature=None, tools=None, response_model=None, **kwargs):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }
        payload = self._build_request(messages, model, max_tokens, temperature, tools)
        response = self.client.post(f"{self.BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return self._parse_response(response.json(), model or payload["model"], response_model)

    async def achat(self, messages, model=None, max_tokens=None, temperature=None, tools=None, response_model=None, **kwargs):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }
        payload = self._build_request(messages, model, max_tokens, temperature, tools)
        response = await self.async_client.post(f"{self.BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return self._parse_response(response.json(), model or payload["model"], response_model)


class OllamaProvider(AIProvider):
    """Local Ollama provider for offline/private use."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.client = httpx.Client(timeout=120.0)
        self.async_client = httpx.AsyncClient(timeout=120.0)

    def estimate_cost(self, model: str, input_tokens: int, max_output_tokens: int) -> float:
        return 0.0  # Local = free

    def chat(self, messages, model=None, max_tokens=None, temperature=None, tools=None, response_model=None, **kwargs):
        payload = {
            "model": model or "mistral:latest",
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens or 4096, "temperature": temperature or 0.7},
        }
        response = self.client.post(f"{self.host}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["message"]["content"]
        parsed = None
        validation_errors = None
        if response_model and content:
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

    async def achat(self, messages, model=None, max_tokens=None, temperature=None, tools=None, response_model=None, **kwargs):
        payload = {
            "model": model or "mistral:latest",
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens or 4096, "temperature": temperature or 0.7},
        }
        response = await self.async_client.post(f"{self.host}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["message"]["content"]
        parsed = None
        validation_errors = None
        if response_model and content:
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
```

### Core Service with Reliability Features

```python
# services.py
from django.db import transaction
from django.utils import timezone
from django_decisioning import idempotent
from pydantic import BaseModel as PydanticModel
import hashlib
import time
import random
from typing import Type
from datetime import timedelta

from .models import AIServiceConfig, AIUsageLog, AIAnalysis
from .providers import AIProvider, AIResponse, OpenRouterProvider, OllamaProvider
from .exceptions import (
    AIServiceDisabled, BudgetExceeded, CircuitOpen,
    ProviderError, ValidationFailed
)

class AIService:
    """
    High-level AI service with:
    - Automatic logging
    - Cost estimation & budget guards
    - Circuit breaker
    - Retry with exponential backoff
    - Sync + async interface
    - Structured output validation with repair loop
    """

    def __init__(self, user=None, session_id: str = ""):
        self.user = user
        self.session_id = session_id
        self.config = AIServiceConfig.get_solo()
        self._providers: dict[str, AIProvider] = {}

    # ═══════════════════════════════════════════════════════════════════
    # PROVIDER MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════

    def _get_provider(self, provider_name: str) -> AIProvider:
        """Get or create provider instance."""
        if provider_name not in self._providers:
            config = self.config.get_provider_config(provider_name)

            if provider_name == "openrouter":
                self._providers[provider_name] = OpenRouterProvider(
                    api_key=config.get("api_key", ""),
                    site_url=config.get("site_url", ""),
                    site_name=config.get("site_name", ""),
                    pricing=self.config.model_pricing or None,
                )
            elif provider_name == "ollama":
                self._providers[provider_name] = OllamaProvider(
                    host=config.get("host", "http://localhost:11434")
                )
            else:
                raise ValueError(f"Unknown provider: {provider_name}")

        return self._providers[provider_name]

    # ═══════════════════════════════════════════════════════════════════
    # CIRCUIT BREAKER
    # ═══════════════════════════════════════════════════════════════════

    def _check_circuit(self, provider_name: str):
        """Check if circuit is open for provider."""
        health = self.config.provider_health.get(provider_name, {})
        if health.get("circuit_open"):
            last_failure = health.get("last_failure")
            if last_failure:
                reset_after = timezone.now() - timedelta(
                    minutes=self.config.circuit_breaker_reset_minutes
                )
                if timezone.datetime.fromisoformat(last_failure) > reset_after:
                    raise CircuitOpen(f"Circuit open for {provider_name}")
                # Reset circuit (half-open state)
                self._update_circuit(provider_name, success=True)

    def _update_circuit(self, provider_name: str, success: bool):
        """Update circuit breaker state."""
        health = self.config.provider_health.copy()
        provider_health = health.get(provider_name, {"failures": 0})

        if success:
            provider_health = {"failures": 0, "circuit_open": False}
        else:
            provider_health["failures"] = provider_health.get("failures", 0) + 1
            provider_health["last_failure"] = timezone.now().isoformat()
            if provider_health["failures"] >= self.config.circuit_breaker_threshold:
                provider_health["circuit_open"] = True

        health[provider_name] = provider_health
        self.config.provider_health = health
        self.config.save(update_fields=["provider_health"])

    # ═══════════════════════════════════════════════════════════════════
    # COST ESTIMATION
    # ═══════════════════════════════════════════════════════════════════

    def estimate_cost(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> float:
        """Estimate cost before making request."""
        provider = self._get_provider(self.config.default_provider)
        model = model or self.config.default_model
        max_tokens = max_tokens or self.config.default_max_tokens

        # Rough token count (4 chars per token approximation)
        input_text = str(messages)
        input_tokens = len(input_text) // 4

        return provider.estimate_cost(model, input_tokens, max_tokens)

    def _check_budget(self, estimated_cost: float):
        """Check if request is within budget."""
        # Per-request limit
        if estimated_cost > float(self.config.per_request_cost_limit_usd):
            raise BudgetExceeded(
                f"Estimated cost ${estimated_cost:.4f} exceeds per-request limit "
                f"${self.config.per_request_cost_limit_usd}"
            )

        # Daily limit
        if self.config.daily_cost_limit_usd:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_cost = AIUsageLog.objects.filter(
                created_at__gte=today_start
            ).aggregate(total=models.Sum("actual_cost_usd"))["total"] or 0

            if today_cost + estimated_cost > float(self.config.daily_cost_limit_usd):
                if self.config.pause_on_budget_exceeded:
                    raise BudgetExceeded(
                        f"Daily budget ${self.config.daily_cost_limit_usd} would be exceeded"
                    )

    # ═══════════════════════════════════════════════════════════════════
    # RETRY LOGIC
    # ═══════════════════════════════════════════════════════════════════

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        base = float(self.config.retry_base_delay_seconds)
        max_delay = float(self.config.retry_max_delay_seconds)
        delay = min(base * (2 ** attempt), max_delay)
        if self.config.retry_jitter:
            delay = delay * (0.5 + random.random())
        return delay

    # ═══════════════════════════════════════════════════════════════════
    # MAIN CHAT METHODS (SYNC + ASYNC)
    # ═══════════════════════════════════════════════════════════════════

    def chat(
        self,
        messages: list[dict],
        operation: str = "chat",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        response_model: Type[PydanticModel] | None = None,
        target_obj=None,
        metadata: dict | None = None,
        skip_budget_check: bool = False,
        max_repair_attempts: int = 2,
    ) -> AIResponse:
        """
        Send chat request with full reliability features.

        Args:
            messages: Chat messages
            operation: Operation type for logging
            model: Model override
            max_tokens: Max tokens override
            temperature: Temperature override
            tools: Function calling tools
            response_model: Pydantic model for structured output validation
            target_obj: Object being analyzed (for GenericFK logging)
            metadata: Additional metadata for logging
            skip_budget_check: Skip pre-flight cost check
            max_repair_attempts: Retries for validation failures
        """
        if not self.config.is_enabled:
            raise AIServiceDisabled("AI services are currently disabled")

        model = self.config.get_model_with_version(model or self.config.default_model)
        max_tokens = max_tokens or self.config.token_budgets.get(operation) or self.config.default_max_tokens

        # Pre-flight cost check
        estimated_cost = self.estimate_cost(messages, model, max_tokens)
        if not skip_budget_check:
            self._check_budget(estimated_cost)

        # Circuit breaker check
        provider_name = self.config.default_provider
        self._check_circuit(provider_name)

        start_time = time.time()
        response = None
        error_message = ""
        success = True
        retry_count = 0
        used_fallback = False

        try:
            # Retry loop
            for attempt in range(self.config.max_retries + 1):
                try:
                    provider = self._get_provider(provider_name)
                    response = provider.chat(
                        messages=messages,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=float(temperature or self.config.default_temperature),
                        tools=tools,
                        response_model=response_model,
                    )

                    # Structured output validation with repair loop
                    if response_model and response.validation_errors and max_repair_attempts > 0:
                        response = self._repair_structured_output(
                            messages, response, response_model,
                            model, max_tokens, temperature, tools,
                            max_repair_attempts
                        )

                    self._update_circuit(provider_name, success=True)
                    break

                except Exception as e:
                    retry_count = attempt
                    if attempt < self.config.max_retries:
                        delay = self._calculate_delay(attempt)
                        time.sleep(delay)
                    else:
                        # Try fallback
                        if self.config.fallback_provider:
                            try:
                                fallback = self._get_provider(self.config.fallback_provider)
                                response = fallback.chat(
                                    messages=messages,
                                    model=self.config.fallback_model,
                                    max_tokens=max_tokens,
                                    temperature=float(temperature or self.config.default_temperature),
                                    response_model=response_model,
                                )
                                used_fallback = True
                                error_message = f"Fallback used after: {e}"
                                break
                            except Exception as fallback_error:
                                error_message = f"Primary: {e}; Fallback: {fallback_error}"
                        else:
                            error_message = str(e)
                        self._update_circuit(provider_name, success=False)
                        raise ProviderError(error_message)

        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            processing_time = int((time.time() - start_time) * 1000)
            self._log_usage(
                operation=operation,
                model=model,
                response=response,
                success=success,
                error_message=error_message,
                processing_time_ms=processing_time,
                target_obj=target_obj,
                messages=messages,
                metadata=metadata,
                estimated_cost=estimated_cost,
                retry_count=retry_count,
                used_fallback=used_fallback,
            )

        return response

    async def achat(
        self,
        messages: list[dict],
        operation: str = "chat",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        response_model: Type[PydanticModel] | None = None,
        target_obj=None,
        metadata: dict | None = None,
        skip_budget_check: bool = False,
        max_repair_attempts: int = 2,
    ) -> AIResponse:
        """Async version of chat()."""
        if not self.config.is_enabled:
            raise AIServiceDisabled("AI services are currently disabled")

        model = self.config.get_model_with_version(model or self.config.default_model)
        max_tokens = max_tokens or self.config.token_budgets.get(operation) or self.config.default_max_tokens

        estimated_cost = self.estimate_cost(messages, model, max_tokens)
        if not skip_budget_check:
            self._check_budget(estimated_cost)

        provider_name = self.config.default_provider
        self._check_circuit(provider_name)

        start_time = time.time()
        response = None
        error_message = ""
        success = True
        retry_count = 0
        used_fallback = False

        try:
            for attempt in range(self.config.max_retries + 1):
                try:
                    provider = self._get_provider(provider_name)
                    response = await provider.achat(
                        messages=messages,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=float(temperature or self.config.default_temperature),
                        tools=tools,
                        response_model=response_model,
                    )
                    self._update_circuit(provider_name, success=True)
                    break
                except Exception as e:
                    retry_count = attempt
                    if attempt < self.config.max_retries:
                        delay = self._calculate_delay(attempt)
                        await asyncio.sleep(delay)
                    else:
                        if self.config.fallback_provider:
                            try:
                                fallback = self._get_provider(self.config.fallback_provider)
                                response = await fallback.achat(
                                    messages=messages,
                                    model=self.config.fallback_model,
                                    max_tokens=max_tokens,
                                    temperature=float(temperature or self.config.default_temperature),
                                    response_model=response_model,
                                )
                                used_fallback = True
                                error_message = f"Fallback used after: {e}"
                                break
                            except Exception as fallback_error:
                                error_message = f"Primary: {e}; Fallback: {fallback_error}"
                        else:
                            error_message = str(e)
                        self._update_circuit(provider_name, success=False)
                        raise ProviderError(error_message)
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            processing_time = int((time.time() - start_time) * 1000)
            self._log_usage(
                operation=operation,
                model=model,
                response=response,
                success=success,
                error_message=error_message,
                processing_time_ms=processing_time,
                target_obj=target_obj,
                messages=messages,
                metadata=metadata,
                estimated_cost=estimated_cost,
                retry_count=retry_count,
                used_fallback=used_fallback,
            )

        return response

    # ═══════════════════════════════════════════════════════════════════
    # STRUCTURED OUTPUT REPAIR
    # ═══════════════════════════════════════════════════════════════════

    def _repair_structured_output(
        self,
        original_messages: list[dict],
        failed_response: AIResponse,
        response_model: Type[PydanticModel],
        model: str,
        max_tokens: int,
        temperature: float | None,
        tools: list[dict] | None,
        max_attempts: int,
    ) -> AIResponse:
        """Attempt to repair invalid structured output."""
        for attempt in range(max_attempts):
            repair_messages = original_messages + [
                {"role": "assistant", "content": failed_response.content},
                {"role": "user", "content": (
                    f"Your response didn't match the required schema. "
                    f"Errors: {failed_response.validation_errors}. "
                    f"Please provide a valid JSON response matching this schema: "
                    f"{response_model.model_json_schema()}"
                )},
            ]
            provider = self._get_provider(self.config.default_provider)
            response = provider.chat(
                messages=repair_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                response_model=response_model,
            )
            if response.parsed is not None:
                return response
            failed_response = response

        raise ValidationFailed(
            f"Failed to get valid structured output after {max_attempts} repair attempts"
        )

    # ═══════════════════════════════════════════════════════════════════
    # LOGGING
    # ═══════════════════════════════════════════════════════════════════

    def _log_usage(
        self,
        operation: str,
        model: str,
        response: AIResponse | None,
        success: bool,
        error_message: str,
        processing_time_ms: int,
        target_obj=None,
        messages: list[dict] | None = None,
        metadata: dict | None = None,
        estimated_cost: float = 0,
        retry_count: int = 0,
        used_fallback: bool = False,
    ):
        """Create immutable usage log entry."""
        log_kwargs = {
            "user": self.user,
            "session_id": self.session_id,
            "operation": operation,
            "provider": self.config.default_provider,
            "model": model,
            "success": success,
            "error_message": error_message,
            "processing_time_ms": processing_time_ms,
            "metadata": metadata or {},
            "estimated_cost_usd": estimated_cost,
            "retry_count": retry_count,
            "used_fallback": used_fallback,
        }

        if response:
            log_kwargs.update({
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "actual_cost_usd": response.cost_usd,
            })

        if target_obj:
            from django.contrib.contenttypes.models import ContentType
            log_kwargs.update({
                "target_content_type": ContentType.objects.get_for_model(target_obj),
                "target_object_id": str(target_obj.pk),
            })

        if messages and self.config.log_prompt_hash:
            prompt_str = str(messages)
            log_kwargs["prompt_hash"] = hashlib.sha256(prompt_str.encode()).hexdigest()

        if messages and self.config.log_prompts:
            log_kwargs["prompt_preview"] = str(messages)[:500]

        if response and self.config.log_responses:
            log_kwargs["response_preview"] = response.content[:500]

        AIUsageLog.objects.create(**log_kwargs)

        # Also log to django-audit-log if target_obj provided
        if target_obj and success:
            from django_audit_log import log
            log(
                action=f"ai_{operation}",
                obj=target_obj,
                actor=self.user,
                metadata={"model": model, "cost_usd": str(response.cost_usd if response else 0)},
            )
```

---

## Tool Registry Infrastructure

```python
# tools.py
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class AITool:
    """Definition of a callable AI tool."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable[..., Any]
    permission_level: str = "public"  # public, authenticated, staff, admin
    requires_confirmation: bool = False
    module: str = "core"
    tags: list[str] = field(default_factory=list)

class ToolRegistry:
    """
    Central registry for AI-callable tools.
    Provides infrastructure only - apps register their own tools.
    """
    _tools: dict[str, AITool] = {}

    PERMISSION_LEVELS = {
        "public": 0,
        "authenticated": 1,
        "staff": 2,
        "admin": 3,
    }

    @classmethod
    def register(cls, tool: AITool):
        """Register a tool."""
        cls._tools[tool.name] = tool

    @classmethod
    def unregister(cls, name: str):
        """Unregister a tool."""
        cls._tools.pop(name, None)

    @classmethod
    def get(cls, name: str) -> AITool | None:
        """Get a tool by name."""
        return cls._tools.get(name)

    @classmethod
    def get_tools_for_user(cls, user=None) -> list[AITool]:
        """Get tools available for user's permission level."""
        if user is None:
            user_level = 0
        elif getattr(user, "is_superuser", False):
            user_level = 3
        elif getattr(user, "is_staff", False):
            user_level = 2
        elif getattr(user, "is_authenticated", True):
            user_level = 1
        else:
            user_level = 0

        return [
            tool for tool in cls._tools.values()
            if cls.PERMISSION_LEVELS.get(tool.permission_level, 0) <= user_level
        ]

    @classmethod
    def get_openai_tools(cls, user=None) -> list[dict]:
        """Get tools in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in cls.get_tools_for_user(user)
        ]

    @classmethod
    def execute_tool(
        cls,
        name: str,
        arguments: dict,
        user=None,
        require_confirmation_callback: Callable[[], bool] | None = None,
    ) -> Any:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments
            user: User for permission check
            require_confirmation_callback: Called if tool.requires_confirmation is True.
                                           Must return True to proceed.
        """
        tool = cls._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Permission check
        available = cls.get_tools_for_user(user)
        if tool not in available:
            raise PermissionError(f"User not authorized for tool: {name}")

        # Confirmation check
        if tool.requires_confirmation and require_confirmation_callback:
            if not require_confirmation_callback():
                raise PermissionError(f"Tool execution not confirmed: {name}")

        return tool.handler(**arguments)


def tool(
    name: str,
    description: str,
    parameters: dict,
    permission: str = "public",
    requires_confirmation: bool = False,
    module: str = "core",
    tags: list[str] | None = None,
):
    """Decorator to register a function as an AI tool."""
    def decorator(func):
        ToolRegistry.register(AITool(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            permission_level=permission,
            requires_confirmation=requires_confirmation,
            module=module,
            tags=tags or [],
        ))
        return func
    return decorator
```

---

## Implementation Phases

### Phase 1: MVP (Shippable Core)

**Goal**: Basic working AI service with logging. Ship in 1-2 days.

| Component | Acceptance Criteria |
|-----------|---------------------|
| `AIServiceConfig` | Singleton with default_provider, default_model, api key retrieval with env fallback |
| `OpenRouterProvider` | Sync chat(), handles Claude/GPT models |
| `AIUsageLog` | Immutable, tracks user/operation/model/tokens/cost/timestamp |
| `AIService.chat()` | Sends request, logs usage, basic error handling |

**Tests**:
- `test_config_singleton_created`
- `test_api_key_env_fallback`
- `test_chat_logs_usage`
- `test_usage_log_immutable`

### Phase 2: Reliability + Tools

**Goal**: Production-ready reliability. Ship in 2-3 days.

| Component | Acceptance Criteria |
|-----------|---------------------|
| Retry with backoff | Configurable retries, exponential backoff, jitter |
| Circuit breaker | Tracks failures, opens circuit, auto-reset after timeout |
| Cost estimation | Pre-request estimate, per-request limit check |
| Budget guards | Daily/monthly limits with optional pause |
| `ToolRegistry` | Permission levels, OpenAI format export, execution with confirmation |
| Fallback chain | Configurable fallback provider + model |

**Tests**:
- `test_retry_on_transient_failure`
- `test_circuit_opens_after_threshold`
- `test_circuit_resets_after_timeout`
- `test_cost_estimation_blocks_expensive_request`
- `test_tool_permission_levels`
- `test_tool_requires_confirmation`
- `test_fallback_provider_used`

### Phase 3: Extensibility

**Goal**: Full feature set for diverse use cases. Ship in 2-3 days.

| Component | Acceptance Criteria |
|-----------|---------------------|
| `OllamaProvider` | Local provider with same interface |
| Async support | `achat()` method with same features as sync |
| `AIAnalysis` | GenericFK-based analysis storage with idempotency |
| Structured output | `response_model` parameter, Pydantic validation, repair loop |
| Idempotency | `@idempotent` decorator on `analyze_object()` |

**Tests**:
- `test_ollama_provider_chat`
- `test_async_chat_works`
- `test_analysis_idempotent`
- `test_structured_output_validation`
- `test_structured_output_repair_loop`

### Phase 4: Security + Audit

**Goal**: Enterprise-ready security. Ship in 1-2 days.

| Component | Acceptance Criteria |
|-----------|---------------------|
| Encrypted key storage | Optional Fernet encryption for provider_configs |
| Model version pinning | `pin_model_version` flag, versioned model names |
| Prompt/response logging controls | Separate toggles, hash always safe |
| django-audit-log integration | Dual logging on analysis operations |

**Tests**:
- `test_encrypted_api_key_storage`
- `test_model_version_pinning`
- `test_prompt_logging_respects_config`
- `test_audit_log_created_on_analysis`

---

## Migration Strategy

### nestorwheelock.com

**What Moves to Primitive**:
| Current | Primitive Replacement |
|---------|----------------------|
| `SiteConfig.get('openrouter_api_key')` | `AIServiceConfig.get_provider_config('openrouter')` |
| `AIUsageLog` model | `django_ai_services.AIUsageLog` (schema compatible) |
| `ChatbotConfig` (84 fields) | Split: AI fields → `AIServiceConfig`, chatbot fields → app config |

**What Stays in App**:
- `ContentIndex` (semantic search)
- `MediaAnalysis` (50+ image fields)
- 30+ admin tools (register with `ToolRegistry`)
- Agentic chatbot logic
- OSINT processing

**Migration Steps**:
1. Install `django-ai-services`
2. Create data migration to copy API keys to `AIServiceConfig`
3. Update imports: `from ai_services.models import AIUsageLog` → `from django_ai_services import AIUsageLog`
4. Register existing tools with `ToolRegistry`
5. Replace direct OpenRouter calls with `AIService.chat()`
6. Keep `ChatbotConfig` for chatbot-specific settings (behavior mode, context limits)

### inventory-ai

**What Moves to Primitive**:
| Current | Primitive Replacement |
|---------|----------------------|
| `settings` table API keys | `AIServiceConfig.provider_configs` |
| `ai_processing_logs` | `AIUsageLog` (gains retry_count, used_fallback) |
| `LocalAIService` (Ollama) | `OllamaProvider` |
| `_api_key_cache` pattern | `AIServiceConfig` singleton |

**What Stays in App**:
- Module system (atomic/composite modules)
- Category-specific prompts
- Post-processing (currency, melt value, book enrichment)
- Natural language command parsing

**Migration Steps**:
1. Install `django-ai-services`
2. Migrate settings table keys to `AIServiceConfig.provider_configs`
3. Replace `AIService` with primitive's `AIService`
4. Keep module system, call primitive's `chat()` from modules
5. Migrate `ai_processing_logs` → `AIUsageLog`

### vetfriendly

**What Moves to Primitive**:
| Current | Primitive Replacement |
|---------|----------------------|
| `settings.OPENROUTER_API_KEY` | `AIServiceConfig` (env fallback still works) |
| `AIUsage` model | `AIUsageLog` (gains more fields) |
| `ToolRegistry` pattern | `django_ai_services.ToolRegistry` (nearly identical) |
| `OpenRouterClient` | `OpenRouterProvider` |

**What Stays in App**:
- 17 `ai_context.py` files (domain-specific)
- Tool implementations (clinic-specific)
- Knowledge base models
- Bilingual support
- Rate limiting enforcement (uses config hints)

**Migration Steps**:
1. Install `django-ai-services`
2. Keep env var config (primitive supports fallback)
3. Replace `OpenRouterClient` with `AIService`
4. Migrate `AIUsage` → `AIUsageLog`
5. Register tools with primitive's `ToolRegistry`
6. Update tool permission levels to match existing pattern

---

## File Structure

```
packages/django-ai-services/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── src/django_ai_services/
│   ├── __init__.py           # Public API exports
│   ├── apps.py
│   ├── models.py             # AIServiceConfig, AIUsageLog, AIAnalysis
│   ├── providers.py          # AIProvider, OpenRouterProvider, OllamaProvider
│   ├── services.py           # AIService, analyze_object
│   ├── tools.py              # ToolRegistry, @tool decorator
│   ├── exceptions.py         # AIServiceDisabled, BudgetExceeded, CircuitOpen, etc.
│   ├── admin.py              # Admin interface for config
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    ├── test_providers.py
    ├── test_services.py
    ├── test_tools.py
    ├── test_circuit_breaker.py
    └── test_cost_estimation.py
```

---

## Dependencies

```toml
[project]
name = "django-ai-services"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "Django>=4.2",
    "django-basemodels",      # For BaseModel on AIAnalysis
    "django-singleton",       # For AIServiceConfig
    "django-decisioning",     # For @idempotent, TimeSemanticsMixin
    "django-audit-log",       # For audit trail integration
    "httpx>=0.25.0",          # HTTP client (sync + async)
    "pydantic>=2.0",          # Structured output validation
    "cryptography>=41.0",     # API key encryption (optional feature)
]

[project.optional-dependencies]
dev = ["pytest", "pytest-django", "pytest-asyncio", "pytest-cov"]
```

---

## Hard Rules

1. **AIUsageLog is immutable** - Cannot update or delete after creation
2. **Cost tracking is mandatory** - Every API call logged with cost
3. **Provider abstraction required** - Never call provider APIs directly from apps
4. **Config via singleton** - No hardcoded API keys or settings
5. **Tools are domain-agnostic** - Registry provides infrastructure, apps register tools
6. **No conversation models** - Primitive doesn't store chat history
7. **No content indexing** - Primitive doesn't do embeddings or vector search
8. **No domain-specific schemas** - Apps define their own analysis result structures

---

## Invariants

- `AIUsageLog.actual_cost_usd >= 0`
- `AIUsageLog.total_tokens == input_tokens + output_tokens`
- `AIAnalysis.confidence` is null or in range [0.0, 1.0]
- `AIServiceConfig` singleton always exists
- Provider API keys never appear in logs (only hashes)
- Circuit breaker state persists across requests
