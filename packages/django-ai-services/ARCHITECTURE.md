# Architecture: django-ai-services

**Status:** Stable / v0.1.0

AI service integration for Django with audit trails, cost tracking, and reliability.

---

## What This Package Is For

Answering the question: **"How do I safely call AI APIs with full observability?"**

Use cases:
- Calling OpenRouter/Ollama APIs with automatic logging
- Cost estimation and budget enforcement
- Retry logic with exponential backoff
- Circuit breaker for provider health
- Structured output validation with Pydantic
- Idempotent analysis with caching
- Tool/function calling registration

---

## What This Package Is NOT For

- **Not an AI framework** - Use LangChain/LlamaIndex for complex chains
- **Not prompt engineering** - This is infrastructure, not prompts
- **Not model hosting** - Use Ollama or cloud APIs for that
- **Not fine-tuning** - Use provider tools for model training
- **Not RAG/embeddings** - Use dedicated vector DBs

---

## Design Principles

1. **Singleton configuration** - Global config via AIServiceConfig
2. **Immutable audit log** - Every API call is logged, cannot be modified/deleted
3. **Provider abstraction** - Swap OpenRouter/Ollama without code changes
4. **Cost-aware** - Pre-flight cost estimation, budget enforcement
5. **Resilient** - Retry, circuit breaker, fallback chain
6. **Structured output** - Pydantic validation with auto-repair

---

## Data Model

```
AIServiceConfig (Singleton)
├── default_provider, default_model
├── fallback_provider, fallback_model
├── cost limits (daily, per-request, monthly)
├── rate limiting hints
├── circuit_breaker_threshold
├── retry config (max_retries, backoff)
├── provider_configs (encrypted at rest)
├── model_pricing (for cost estimation)
├── logging controls (log_prompts, log_responses)
└── provider_health (circuit breaker state)

AIUsageLog (Immutable)
├── id (UUID, PK)
├── user (FK, nullable)
├── session_id
├── target (GenericFK, optional)
├── operation (chat, analyze, classify)
├── provider, model, model_version
├── input_tokens, output_tokens, total_tokens
├── estimated_cost_usd, actual_cost_usd
├── processing_time_ms, retry_count
├── success, error_message, error_code
├── used_fallback
├── prompt_hash (SHA-256)
├── prompt_preview, response_preview (optional)
├── metadata (JSON)
└── created_at

AIAnalysis (Idempotent Results)
├── id (UUID, PK)
├── target (GenericFK)
├── analysis_type
├── provider, model, model_version
├── input_data, input_hash
├── result (JSON)
├── confidence (0-1)
├── validation_passed, validation_errors
├── triggered_by (FK User)
├── usage_log (FK to AIUsageLog)
├── is_reviewed, reviewed_by, reviewed_at
└── timestamps
```

---

## Public API

### AIService Class

```python
from django_ai_services import AIService

# Initialize with user context
service = AIService(user=request.user, session_id="abc123")

# Simple chat
response = service.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    operation="greeting",
)

# With structured output (Pydantic)
from pydantic import BaseModel

class Classification(BaseModel):
    category: str
    confidence: float

response = service.chat(
    messages=[{"role": "user", "content": "Classify this text..."}],
    operation="classify",
    response_model=Classification,
)
print(response.parsed.category)  # Validated Pydantic object

# Async version
response = await service.achat(...)

# Object analysis with idempotency
response = service.analyze_object(
    obj=document,
    analysis_type="classification",
    prompt="Classify this document...",
    force=False,  # Returns cached result if same input_hash
)
```

### Tool Registry

```python
from django_ai_services.tools import ToolRegistry, tool

# Register via decorator
@tool(
    name="get_weather",
    description="Get current weather",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
    permission="authenticated",
)
def get_weather(city: str):
    return {"temp": 72, "city": city}

# Get tools for OpenAI function calling format
tools = ToolRegistry.get_openai_tools(user=request.user)

# Execute tool
result = ToolRegistry.execute_tool("get_weather", {"city": "NYC"}, user=request.user)
```

### AIResponse Dataclass

```python
@dataclass
class AIResponse:
    content: str              # Raw response text
    model: str                # Actual model used
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw_response: dict        # Full API response
    tool_calls: list | None   # Function calling results
    parsed: Any | None        # Validated Pydantic object
    validation_errors: list | None
```

---

## Providers

| Provider | Class | Use Case |
|----------|-------|----------|
| OpenRouter | `OpenRouterProvider` | Cloud access to Claude, GPT, etc. |
| Ollama | `OllamaProvider` | Local/private LLM hosting |

### Adding New Providers

Subclass `AIProvider` and implement:
- `chat()` - Sync chat completion
- `achat()` - Async chat completion
- `estimate_cost()` - Cost estimation

---

## Hard Rules

1. **AIUsageLog is immutable** - Cannot update or delete records
2. **Cost estimation before request** - Pre-flight budget check
3. **Circuit breaker on failures** - Opens after N consecutive failures
4. **Provider configs can be encrypted** - Set encryption key at startup
5. **API keys from env fallback** - `{PROVIDER}_API_KEY` environment variable

---

## Invariants

- `AIUsageLog.total_tokens == input_tokens + output_tokens`
- `AIUsageLog` records cannot be modified after creation
- `AIUsageLog` records cannot be deleted
- `AIAnalysis.input_hash` is SHA-256 of input_data
- `AIAnalysis.confidence` is null or in range [0, 1] (database constraint)
- If `AIServiceConfig.is_enabled` is False, all requests are rejected

---

## Circuit Breaker

```
State Machine:
  CLOSED (normal) → N failures → OPEN (reject all)
  OPEN → timeout → HALF-OPEN (try one request)
  HALF-OPEN → success → CLOSED
  HALF-OPEN → failure → OPEN

Configuration (AIServiceConfig):
  circuit_breaker_threshold: 5 (consecutive failures)
  circuit_breaker_reset_minutes: 15 (before half-open)
```

---

## Retry Logic

```
Exponential backoff with jitter:
  delay = min(base * 2^attempt, max_delay)
  if jitter: delay *= (0.5 + random())

Configuration (AIServiceConfig):
  max_retries: 3
  retry_base_delay_seconds: 1.0
  retry_max_delay_seconds: 30.0
  retry_jitter: True
```

---

## Cost Controls

```python
# AIServiceConfig fields
daily_cost_limit_usd = Decimal("100.00")       # Max per day
per_request_cost_limit_usd = Decimal("0.50")   # Pre-flight reject
monthly_cost_limit_usd = Decimal("500.00")     # Monthly cap
pause_on_budget_exceeded = True                 # Hard stop vs soft limit

# Model pricing (for estimation)
model_pricing = {
    "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "openai/gpt-4o": {"input": 5.0, "output": 15.0},
}
```

---

## Known Gotchas

### 1. Pydantic Required for Structured Output

**Problem:** Using `response_model` without pydantic installed.

```python
# WRONG - pydantic not installed
response = service.chat(..., response_model=MyModel)

# Pydantic is optional dependency
pip install pydantic
```

### 2. Encryption Key Not Set

**Problem:** Provider configs stored in plain text.

```python
# Set at app startup (e.g., AppConfig.ready())
from django_ai_services.models import AIServiceConfig
from cryptography.fernet import Fernet

key = os.environ.get("AI_SERVICES_ENCRYPTION_KEY")
AIServiceConfig.set_encryption_key(key)
```

### 3. Budget Exceeded Silent Failures

**Problem:** Not catching BudgetExceeded exception.

```python
from django_ai_services.exceptions import BudgetExceeded

try:
    response = service.chat(...)
except BudgetExceeded as e:
    # Handle gracefully
    pass
```

### 4. Circuit Breaker Blocks All Requests

**Problem:** Circuit stays open too long.

```python
# Reduce reset time if needed
config = AIServiceConfig.get_instance()
config.circuit_breaker_reset_minutes = 5
config.save()
```

---

## Recommended Usage

### 1. Initialize Once Per Request

```python
# In view
def my_view(request):
    service = AIService(user=request.user, session_id=request.session.session_key)
    ...
```

### 2. Use analyze_object for Idempotency

```python
# Same input_hash returns cached result
response = service.analyze_object(
    obj=document,
    analysis_type="summary",
    prompt="Summarize this document",
    force=False,  # Use cache
)
```

### 3. Configure Budget Limits

```python
# In admin or migration
config = AIServiceConfig.get_instance()
config.daily_cost_limit_usd = Decimal("50.00")
config.per_request_cost_limit_usd = Decimal("0.25")
config.pause_on_budget_exceeded = True
config.save()
```

### 4. Set Up Fallback Chain

```python
config.default_provider = "openrouter"
config.default_model = "anthropic/claude-sonnet-4"
config.fallback_provider = "ollama"
config.fallback_model = "mistral:latest"
config.save()
```

---

## Dependencies

- Django >= 4.2
- django-singleton (for AIServiceConfig)
- httpx (HTTP client)
- pydantic (optional, for structured output)
- cryptography (optional, for encrypted configs)

---

## Changelog

### v0.1.0 (2025-01-06)
- Initial release
- AIServiceConfig singleton with encrypted provider configs
- AIUsageLog immutable audit trail
- AIAnalysis with idempotency support
- OpenRouter and Ollama providers
- Circuit breaker with configurable threshold
- Retry with exponential backoff and jitter
- Cost estimation and budget controls
- Tool registry for function calling
- Structured output validation with auto-repair
- Sync and async interfaces
