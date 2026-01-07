# AI Primitive Proposal: django-ai-services

## Executive Summary

After analyzing AI implementations across three production projects (nestorwheelock.com, inventory-ai, vetfriendly), we propose creating a reusable AI primitive that captures the best patterns while remaining domain-agnostic and composable with other django-primitives packages.

---

## The Single Question This Primitive Answers

> **"How do I integrate AI services into my Django application with proper audit trails, cost tracking, and configuration management?"**

---

## What This Primitive Provides

| Component | Purpose |
|-----------|---------|
| `AIServiceConfig` | Singleton configuration for API keys, models, limits |
| `AIUsageLog` | Immutable audit trail of all AI API calls |
| `AIAnalysis` | GenericFK-based record of AI analysis on any entity |
| `AIProvider` | Abstract provider interface (OpenRouter, Ollama, custom) |
| `ToolRegistry` | Optional function calling registry with permissions |

## What This Primitive Does NOT Do

- **NOT a chatbot** - No conversation UI or session management
- **NOT domain-specific** - No assumptions about healthcare, inventory, etc.
- **NOT content indexing** - No embeddings, vector search, or semantic indexing
- **NOT rate limiting enforcement** - Provides hooks, doesn't enforce (use django-ratelimit)
- **NOT model serving** - Doesn't run models, only calls external APIs

---

## Layer Placement

```
INFRASTRUCTURE LAYER (like django-decisioning, django-audit-log)
└─ django-ai-services
   ├─ Depends on: django-basemodels, django-singleton, django-audit-log
   ├─ Used by: Any application layer package
   └─ Provides: Services, not domain models
```

**Rationale**: AI services are infrastructure (like audit logging) that any domain can use. They don't belong in Foundation (they have dependencies) or Domain (they're not business logic).

---

## Data Model

### 1. AIServiceConfig (Singleton)

```python
from django_singleton import SingletonModel
from django.db import models
import json

class AIServiceConfig(SingletonModel):
    """
    Global AI service configuration.
    API keys encrypted at rest, never logged.
    """

    # Provider Configuration (encrypted JSONField in production)
    provider_configs = models.JSONField(
        default=dict,
        help_text="Provider-specific configs: {provider_name: {api_key, base_url, ...}}"
    )

    # Default Model Settings
    default_provider = models.CharField(max_length=50, default="openrouter")
    default_model = models.CharField(max_length=100, default="anthropic/claude-sonnet-4")
    default_max_tokens = models.PositiveIntegerField(default=4096)
    default_temperature = models.DecimalField(max_digits=3, decimal_places=2, default=0.7)

    # Token Budget Presets (per operation type)
    token_budgets = models.JSONField(
        default=dict,
        help_text="Operation-specific budgets: {operation: max_tokens}"
    )

    # Cost Controls
    daily_cost_limit_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    per_request_cost_limit_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0.50)
    pause_on_budget_exceeded = models.BooleanField(default=False)

    # Rate Limiting (hints for application layer)
    requests_per_minute_anonymous = models.PositiveIntegerField(default=10)
    requests_per_minute_authenticated = models.PositiveIntegerField(default=60)
    requests_per_day_per_user = models.PositiveIntegerField(default=1000)

    # Feature Flags
    is_enabled = models.BooleanField(default=True)
    debug_mode = models.BooleanField(default=False)
    log_prompts = models.BooleanField(default=False, help_text="Log full prompts (privacy concern)")
    log_responses = models.BooleanField(default=False, help_text="Log full responses (cost concern)")

    # Fallback Configuration
    fallback_provider = models.CharField(max_length=50, blank=True)
    fallback_model = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "AI Service Configuration"

    def get_provider_config(self, provider_name: str) -> dict:
        """Get config for specific provider, with env fallback."""
        config = self.provider_configs.get(provider_name, {})
        # Env fallback pattern
        if not config.get('api_key'):
            import os
            env_key = f"{provider_name.upper()}_API_KEY"
            config['api_key'] = os.environ.get(env_key, '')
        return config
```

### 2. AIUsageLog (Immutable Audit Trail)

```python
from django_basemodels import BaseModel
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AIUsageLog(models.Model):
    """
    Immutable record of every AI API call.
    Similar to django-audit-log but specialized for AI cost tracking.
    """

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who triggered this?
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ai_usage_logs"
    )
    session_id = models.CharField(max_length=255, blank=True, db_index=True)

    # What was analyzed? (optional GenericFK)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+"
    )
    target_object_id = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Operation Classification
    operation = models.CharField(max_length=100, db_index=True)  # e.g., "chat", "analyze", "classify"

    # Provider & Model
    provider = models.CharField(max_length=50)  # openrouter, ollama, custom
    model = models.CharField(max_length=100)

    # Token Usage
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    # Cost Tracking
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    # Performance
    processing_time_ms = models.PositiveIntegerField(null=True, blank=True)

    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)

    # Debug (only populated if config.debug_mode or config.log_prompts)
    prompt_hash = models.CharField(max_length=64, blank=True)  # SHA-256 for deduplication
    prompt_preview = models.CharField(max_length=500, blank=True)  # First 500 chars
    response_preview = models.CharField(max_length=500, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Request metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["operation", "created_at"]),
            models.Index(fields=["provider", "model", "created_at"]),
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["success", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and AIUsageLog.objects.filter(pk=self.pk).exists():
            raise ValueError("AIUsageLog records are immutable")
        self.total_tokens = self.input_tokens + self.output_tokens
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AIUsageLog records cannot be deleted")
```

### 3. AIAnalysis (Domain Analysis Record)

```python
from django_basemodels import BaseModel
from django_decisioning import TimeSemanticsMixin

class AIAnalysis(TimeSemanticsMixin, BaseModel):
    """
    Record of AI analysis performed on any entity.
    Uses GenericFK to attach to any model.
    Supports time semantics (effective_at vs recorded_at).
    """

    # What was analyzed?
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    target_object_id = models.CharField(max_length=255)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Analysis Type
    analysis_type = models.CharField(max_length=100, db_index=True)
    # Examples: "classification", "description", "extraction", "summary", "tagging"

    # Model Used
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50, blank=True)

    # Input (what was sent to AI)
    input_data = models.JSONField(default=dict)
    input_hash = models.CharField(max_length=64, db_index=True)  # For idempotency

    # Output (what AI returned)
    result = models.JSONField(default=dict)
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="0.0000 to 1.0000"
    )

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

    # Status
    is_reviewed = models.BooleanField(default=False)  # Human reviewed?
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Time semantics inherited from mixin:
    # effective_at: when analysis applies (can be backdated)
    # recorded_at: when system recorded (immutable)

    class Meta:
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["analysis_type", "created_at"]),
            models.Index(fields=["input_hash"]),  # For idempotency lookup
            models.Index(fields=["triggered_by", "created_at"]),
            models.Index(fields=["is_reviewed"]),
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

### Provider Abstraction

```python
# providers.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
import httpx

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
        **kwargs
    ) -> AIResponse:
        """Send chat completion request."""
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """List available models for this provider."""
        pass

class OpenRouterProvider(AIProvider):
    """OpenRouter API provider (supports Claude, GPT, etc.)."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, site_url: str = "", site_name: str = ""):
        self.api_key = api_key
        self.site_url = site_url
        self.site_name = site_name
        self.client = httpx.Client(timeout=60.0)

    def chat(self, messages, model=None, max_tokens=None, temperature=None, tools=None, **kwargs):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }

        payload = {
            "model": model or "anthropic/claude-sonnet-4",
            "messages": messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature or 0.7,
        }
        if tools:
            payload["tools"] = tools

        response = self.client.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        return AIResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cost_usd=self._estimate_cost(model, usage),
            raw_response=data,
            tool_calls=data["choices"][0]["message"].get("tool_calls"),
        )

class OllamaProvider(AIProvider):
    """Local Ollama provider for offline/private use."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.client = httpx.Client(timeout=120.0)

    def chat(self, messages, model=None, max_tokens=None, temperature=None, **kwargs):
        # Ollama uses different API format
        payload = {
            "model": model or "mistral:latest",
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens or 4096,
                "temperature": temperature or 0.7,
            }
        }

        response = self.client.post(f"{self.host}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        return AIResponse(
            content=data["message"]["content"],
            model=model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,  # Local = free
            raw_response=data,
        )
```

### Core Service

```python
# services.py
from django.db import transaction
from django_decisioning import idempotent
import hashlib
import time

class AIService:
    """
    High-level AI service with automatic logging, cost tracking, and fallback.
    """

    def __init__(self, user=None):
        self.user = user
        self.config = AIServiceConfig.get_solo()
        self._provider = None

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = self._get_provider(self.config.default_provider)
        return self._provider

    def _get_provider(self, provider_name: str) -> AIProvider:
        """Get provider instance by name."""
        config = self.config.get_provider_config(provider_name)

        if provider_name == "openrouter":
            return OpenRouterProvider(
                api_key=config.get("api_key", ""),
                site_url=config.get("site_url", ""),
                site_name=config.get("site_name", ""),
            )
        elif provider_name == "ollama":
            return OllamaProvider(host=config.get("host", "http://localhost:11434"))
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    @transaction.atomic
    def chat(
        self,
        messages: list[dict],
        operation: str = "chat",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        target_obj=None,
        metadata: dict | None = None,
    ) -> AIResponse:
        """
        Send chat request with automatic logging.
        """
        if not self.config.is_enabled:
            raise AIServiceDisabled("AI services are currently disabled")

        # Check budget
        self._check_budget()

        start_time = time.time()
        error_message = ""
        success = True
        response = None

        try:
            response = self.provider.chat(
                messages=messages,
                model=model or self.config.default_model,
                max_tokens=max_tokens or self.config.default_max_tokens,
                temperature=float(temperature or self.config.default_temperature),
                tools=tools,
            )
        except Exception as e:
            success = False
            error_message = str(e)
            # Try fallback
            if self.config.fallback_provider:
                try:
                    fallback = self._get_provider(self.config.fallback_provider)
                    response = fallback.chat(
                        messages=messages,
                        model=self.config.fallback_model,
                        max_tokens=max_tokens or self.config.default_max_tokens,
                        temperature=float(temperature or self.config.default_temperature),
                    )
                    success = True
                    error_message = f"Fallback used: {error_message}"
                except Exception as fallback_error:
                    error_message = f"Primary: {error_message}; Fallback: {fallback_error}"
                    raise
            else:
                raise
        finally:
            processing_time = int((time.time() - start_time) * 1000)

            # Log usage
            self._log_usage(
                operation=operation,
                model=model or self.config.default_model,
                response=response,
                success=success,
                error_message=error_message,
                processing_time_ms=processing_time,
                target_obj=target_obj,
                messages=messages,
                metadata=metadata,
            )

        return response

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
    ):
        """Create immutable usage log entry."""
        from django.contrib.contenttypes.models import ContentType

        log_kwargs = {
            "user": self.user,
            "operation": operation,
            "provider": self.config.default_provider,
            "model": model,
            "success": success,
            "error_message": error_message,
            "processing_time_ms": processing_time_ms,
            "metadata": metadata or {},
        }

        if response:
            log_kwargs.update({
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            })

        if target_obj:
            log_kwargs.update({
                "target_content_type": ContentType.objects.get_for_model(target_obj),
                "target_object_id": str(target_obj.pk),
            })

        # Optionally log prompt preview
        if self.config.log_prompts and messages:
            prompt_str = str(messages)
            log_kwargs["prompt_hash"] = hashlib.sha256(prompt_str.encode()).hexdigest()
            log_kwargs["prompt_preview"] = prompt_str[:500]

        if self.config.log_responses and response:
            log_kwargs["response_preview"] = response.content[:500]

        AIUsageLog.objects.create(**log_kwargs)


@idempotent(
    scope="ai_analysis",
    key_from=lambda target_obj, analysis_type, input_data, **kw:
        f"{target_obj.pk}:{analysis_type}:{hashlib.sha256(str(input_data).encode()).hexdigest()[:16]}"
)
def analyze_object(
    target_obj,
    analysis_type: str,
    input_data: dict,
    prompt_template: str,
    user=None,
    model: str | None = None,
) -> AIAnalysis:
    """
    Perform AI analysis on any object.
    Idempotent: same input returns cached result.
    """
    from django.contrib.contenttypes.models import ContentType

    service = AIService(user=user)

    # Build messages from template
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": prompt_template.format(**input_data)},
    ]

    input_hash = hashlib.sha256(str(input_data).encode()).hexdigest()

    # Check for existing analysis with same input
    existing = AIAnalysis.objects.filter(
        target_content_type=ContentType.objects.get_for_model(target_obj),
        target_object_id=str(target_obj.pk),
        analysis_type=analysis_type,
        input_hash=input_hash,
    ).first()

    if existing:
        return existing

    # Perform analysis
    response = service.chat(
        messages=messages,
        operation=f"analyze_{analysis_type}",
        model=model,
        target_obj=target_obj,
    )

    # Parse result (assume JSON response)
    import json
    try:
        result = json.loads(response.content)
        confidence = result.pop("confidence", None)
    except json.JSONDecodeError:
        result = {"raw_response": response.content}
        confidence = None

    # Create analysis record
    analysis = AIAnalysis.objects.create(
        target_content_type=ContentType.objects.get_for_model(target_obj),
        target_object_id=str(target_obj.pk),
        analysis_type=analysis_type,
        provider=service.config.default_provider,
        model=response.model,
        input_data=input_data,
        input_hash=input_hash,
        result=result,
        confidence=confidence,
        triggered_by=user,
    )

    # Audit log
    from django_audit_log import log
    log(
        action=f"ai_analysis_{analysis_type}",
        obj=target_obj,
        actor=user,
        metadata={"analysis_id": str(analysis.pk), "model": response.model},
    )

    return analysis
```

---

## Tool Registry (Optional Module)

```python
# tools.py
from dataclasses import dataclass
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

class ToolRegistry:
    """
    Central registry for AI-callable tools.
    Domain apps register tools here.
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
    def get_tools_for_user(cls, user=None) -> list[AITool]:
        """Get tools available for user's permission level."""
        if user is None:
            user_level = 0
        elif user.is_superuser:
            user_level = 3
        elif user.is_staff:
            user_level = 2
        elif user.is_authenticated:
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
        tools = cls.get_tools_for_user(user)
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in tools
        ]

    @classmethod
    def execute_tool(cls, name: str, arguments: dict, user=None) -> Any:
        """Execute a tool by name."""
        tool = cls._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Permission check
        available = cls.get_tools_for_user(user)
        if tool not in available:
            raise PermissionError(f"User not authorized for tool: {name}")

        return tool.handler(**arguments)


def tool(
    name: str,
    description: str,
    parameters: dict,
    permission: str = "public",
    requires_confirmation: bool = False,
    module: str = "core",
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
        ))
        return func
    return decorator
```

---

## Hard Rules

1. **AIUsageLog is immutable** - Cannot update or delete after creation
2. **Cost tracking is mandatory** - Every API call logged with cost estimate
3. **Provider abstraction required** - Never call provider APIs directly
4. **Time semantics on AIAnalysis** - Both effective_at and recorded_at tracked
5. **GenericFK for targets** - Analysis can attach to any model
6. **Idempotent analysis** - Same input returns cached result
7. **Permission-gated tools** - Tools checked against user level before execution
8. **Config via singleton** - No hardcoded API keys or settings

---

## Invariants

- `AIUsageLog.cost_usd >= 0`
- `AIAnalysis.confidence` is null or in range [0.0, 1.0]
- `AIUsageLog.total_tokens == input_tokens + output_tokens`
- `AIServiceConfig` singleton always exists (get_or_create pattern)
- Provider API keys never logged in prompts or responses

---

## Integration Examples

### Basic Chat

```python
from django_ai_services import AIService

service = AIService(user=request.user)
response = service.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    operation="customer_support",
)
print(response.content)
```

### Analyze Any Object

```python
from django_ai_services import analyze_object

# Analyze a product
analysis = analyze_object(
    target_obj=product,
    analysis_type="description",
    input_data={"title": product.name, "category": product.category.name},
    prompt_template="Generate a product description for: {title} in category {category}",
    user=request.user,
)
print(analysis.result)
```

### Register Domain Tools

```python
from django_ai_services.tools import tool

@tool(
    name="get_inventory_count",
    description="Get the current inventory count for a product",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "Product UUID"},
        },
        "required": ["product_id"],
    },
    permission="staff",
    module="inventory",
)
def get_inventory_count(product_id: str) -> dict:
    product = Product.objects.get(pk=product_id)
    return {"product": product.name, "count": product.stock_count}
```

---

## File Structure

```
packages/django-ai-services/
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
├── src/django_ai_services/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py         # AIServiceConfig, AIUsageLog, AIAnalysis
│   ├── providers.py      # AIProvider, OpenRouterProvider, OllamaProvider
│   ├── services.py       # AIService, analyze_object
│   ├── tools.py          # ToolRegistry, @tool decorator
│   ├── exceptions.py     # AIServiceDisabled, BudgetExceeded, etc.
│   └── migrations/
│       └── __init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    ├── test_providers.py
    ├── test_services.py
    └── test_tools.py
```

---

## Dependencies

```toml
[project]
dependencies = [
    "Django>=4.2",
    "django-basemodels",      # For BaseModel
    "django-singleton",       # For AIServiceConfig
    "django-decisioning",     # For @idempotent, TimeSemanticsMixin
    "django-audit-log",       # For audit trail integration
    "httpx>=0.25.0",          # For async HTTP client
]
```

---

## What's NOT Included (Future Primitives)

1. **django-ai-context** (Content layer)
   - Knowledge base indexing
   - Embedding generation
   - Vector search
   - Context extraction patterns

2. **django-ai-chat** (Application layer)
   - Conversation session management
   - Message history
   - UI components

These could be separate primitives that depend on django-ai-services.

---

## Migration Path for Existing Projects

### nestorwheelock.com
- Replace `SiteConfig` AI keys with `AIServiceConfig`
- Replace `AIUsageLog` model with primitive version
- Keep domain-specific `ContentIndex` and `MediaAnalysis`

### inventory-ai
- Replace settings table API keys with `AIServiceConfig`
- Replace `ai_processing_logs` with `AIUsageLog`
- Keep module system (domain-specific)

### vetfriendly
- Keep environment variable config (primitive supports env fallback)
- Replace custom `AIUsage` with primitive version
- Keep domain-specific tool implementations
