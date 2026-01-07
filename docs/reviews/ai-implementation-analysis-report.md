# AI Implementation Analysis Report

## Cross-Project Analysis: nestorwheelock.com, inventory-ai, vetfriendly

**Date**: January 2026
**Purpose**: Analyze existing AI implementations to inform django-ai-services primitive design

---

## Executive Summary

Three production Django projects were analyzed for AI integration patterns. Each project independently evolved similar solutions for common problems (API key management, usage tracking, provider abstraction), while developing domain-specific features unique to their use cases.

**Key Finding**: ~60% of AI-related code is infrastructure that could be shared via a primitive. ~40% is domain-specific and should remain in application code.

---

## Project Profiles

### 1. nestorwheelock.com (Personal Knowledge Management)

**AI Scope**: Most comprehensive - full agentic system with 30+ admin tools

| Capability | Implementation | Maturity |
|------------|---------------|----------|
| Token Storage | Database (SiteConfig JSONField) + env fallback | Production |
| Usage Tracking | AIUsageLog with service type, user, cost | Production |
| Provider | OpenRouter only (Claude + GPT models) | Production |
| Tool Calling | 30+ admin tools with confirmation workflow | Production |
| Content Indexing | ContentIndex model for semantic search | Production |
| Image Analysis | MediaAnalysis with 50+ metadata fields | Production |
| OSINT Processing | Profile extraction, timeline triangulation | Production |
| Chatbot | Dual-tier (public read-only, admin agentic) | Production |

**Unique Strengths**:
- Tool confirmation workflow (preview before destructive actions)
- Content indexing for chatbot context injection
- Comprehensive image analysis schema (faces, objects, scenes, mood, colors)
- OSINT-specific age derivation and confidence bands

### 2. inventory-ai (Photo-Based Inventory System)

**AI Scope**: Focused on photo-to-structured-data pipeline

| Capability | Implementation | Maturity |
|------------|---------------|----------|
| Token Storage | SQLite settings table (plain text) | Production |
| Usage Tracking | ai_processing_logs with timing and errors | Production |
| Provider | OpenRouter + Ollama + Custom API | Production |
| Classification | Category detection + multi-pass enhancement | Production |
| Module System | Atomic/composite AI instruction modules | Production |
| OCR | Via Claude vision (ISBN, serial numbers) | Production |
| Value Estimation | Currency conversion + melt value calculation | Production |
| Natural Language | Command parsing for inventory operations | Beta |

**Unique Strengths**:
- Multi-provider with local fallback (Ollama for offline/privacy)
- Module-based prompt composition (stackable AI instructions)
- Domain-specific post-processing (currency conversion, book enrichment)
- Detailed timing and error tracking per request

### 3. vetfriendly (Veterinary Clinic Management)

**AI Scope**: Customer-facing assistant with staff tools

| Capability | Implementation | Maturity |
|------------|---------------|----------|
| Token Storage | Environment variables only | Production |
| Usage Tracking | AIUsage model with session_id | Production |
| Provider | OpenRouter only | Production |
| Tool Calling | Registry with permission levels | Production |
| Context Injection | 17 domain-specific ai_context.py files | Production |
| Knowledge Base | Bilingual articles + FAQs with relevance scoring | Production |
| Rate Limiting | Per-user, per-IP, daily limits | Production |
| Multi-language | Full Spanish/English support | Production |

**Unique Strengths**:
- Permission-gated tool registry (public → customer → staff → admin)
- Domain-specific context modules with explicit field allowlisting
- Privacy-first design (never expose internal fields to AI)
- Comprehensive rate limiting and cost controls

---

## Pattern Analysis

### What All Three Projects Have in Common

These patterns appeared independently in all projects and should be **included in the primitive**:

#### 1. API Key/Token Management

| Project | Storage | Retrieval Pattern |
|---------|---------|-------------------|
| nestorwheelock | DB (SiteConfig) | `SiteConfig.get('key', {}).get('key')` + env fallback |
| inventory-ai | DB (settings table) | `DatabaseService.get_setting('key')` with cache |
| vetfriendly | Environment only | `os.getenv('OPENROUTER_API_KEY')` |

**Consensus Pattern**:
```python
# All projects need: primary storage + fallback
def get_api_key(provider):
    # 1. Check database/config store
    # 2. Fall back to environment variable
    # 3. Return None if not configured
```

**Recommendation**: Include in primitive with DB-first + env-fallback pattern.

#### 2. Usage/Cost Tracking

All three track the same core metrics:

| Field | nestorwheelock | inventory-ai | vetfriendly |
|-------|---------------|--------------|-------------|
| user | ✅ | ✅ | ✅ |
| model | ✅ | ✅ | ✅ |
| input_tokens | ✅ | ✅ | ✅ |
| output_tokens | ✅ | ✅ | ✅ |
| cost_usd | ✅ | ✅ | ✅ |
| timestamp | ✅ | ✅ | ✅ |
| operation_type | ✅ (service) | ✅ (operation_type) | ❌ |
| processing_time | ❌ | ✅ | ❌ |
| error_message | ❌ | ✅ | ❌ |
| session_id | ❌ | ❌ | ✅ |
| target_object | ❌ | ✅ (item_id) | ❌ |

**Recommendation**: Include comprehensive logging with ALL fields from all projects.

#### 3. Provider Abstraction

| Project | Providers Supported | Fallback |
|---------|--------------------| ---------|
| nestorwheelock | OpenRouter (Claude, GPT) | ❌ |
| inventory-ai | OpenRouter, Ollama, Custom | ✅ Ollama local |
| vetfriendly | OpenRouter | ❌ |

**Recommendation**: Include multi-provider abstraction with fallback chain.

#### 4. Configuration Singleton

All use a single configuration source:

| Project | Implementation | Fields |
|---------|---------------|--------|
| nestorwheelock | ChatbotConfig (84 fields) | Models, tokens, rate limits, behaviors |
| inventory-ai | settings table | Model, prompts, debug mode |
| vetfriendly | Django settings | Model, max_tokens, rate limits, cost limits |

**Recommendation**: Include singleton config model with sensible defaults.

#### 5. Rate Limiting Hints

| Project | Implementation |
|---------|---------------|
| nestorwheelock | `public_requests_per_minute`, `per_day`, cooldown |
| inventory-ai | Per-request cost limits |
| vetfriendly | `requests_per_minute_anonymous`, `per_day_per_user` |

**Recommendation**: Include rate limit configuration (hints for app layer to enforce).

---

### What Differs Between Projects

These patterns vary by domain and should be **left out of the primitive**:

#### 1. Tool/Function Definitions

Each project has domain-specific tools:

**nestorwheelock** (content management):
- `get_post`, `create_post`, `edit_post`, `delete_post`
- `get_person`, `create_person`, `link_contacts`
- `add_observation`, `tag_category`
- `analyze_media`, `detect_people_in_image`

**inventory-ai** (inventory operations):
- Search items, move to category, move to location
- Delete items, bulk operations
- Natural language command parsing

**vetfriendly** (clinic operations):
- `get_clinic_hours`, `get_available_services`
- Appointment management
- Pet information access
- Customer data retrieval

**Recommendation**: Primitive provides ToolRegistry infrastructure; apps register their own tools.

#### 2. Context Injection Strategies

| Project | Strategy | Implementation |
|---------|----------|----------------|
| nestorwheelock | Semantic search | ContentIndex model, AI-generated summaries |
| inventory-ai | Module prompts | Category-specific prompt templates |
| vetfriendly | Domain context files | 17 ai_context.py files with allowlists |

**Recommendation**: Leave out - too domain-specific. Each app builds its own context.

#### 3. Response Processing

| Project | Post-Processing |
|---------|-----------------|
| nestorwheelock | Content enhancement, auto-tagging, indexing |
| inventory-ai | Currency conversion, melt value, book enrichment |
| vetfriendly | Bilingual formatting, quick actions |

**Recommendation**: Leave out - domain-specific post-processing stays in apps.

#### 4. Image/Media Analysis Schema

nestorwheelock has 50+ MediaAnalysis fields:
- `detected_objects`, `brand_logos`, `faces`
- `scene_type`, `time_of_day`, `weather`
- `colors`, `color_palette`, `mood`
- `content_rating`, `quality_score`

**Recommendation**: Leave out - too specific to personal photo management use case.

---

## Gap Analysis: What's Missing

Patterns that would improve all projects but don't exist yet:

### 1. Encrypted API Key Storage

**Current State**:
- nestorwheelock: Plain JSON in database
- inventory-ai: Plain text in SQLite
- vetfriendly: Environment variables (better but not always available)

**Gap**: No project encrypts API keys at rest in the database.

**Recommendation**: Primitive should support encrypted storage option.

```python
class AIServiceConfig(SingletonModel):
    # Option A: Use django-encrypted-model-fields
    api_keys = EncryptedJSONField()

    # Option B: Provide encryption/decryption methods
    def set_api_key(self, provider, key):
        encrypted = self._encrypt(key)
        self.provider_configs[provider] = {'key': encrypted}
```

### 2. Provider Health Monitoring

**Current State**: All projects call APIs and handle errors reactively.

**Gap**: No proactive health checks or circuit breaker patterns.

**Recommendation**: Add to primitive:

```python
class AIServiceConfig(SingletonModel):
    # Circuit breaker state
    provider_failures = models.JSONField(default=dict)
    # {provider: {'consecutive_failures': 5, 'last_failure': timestamp, 'circuit_open': True}}

    circuit_breaker_threshold = models.PositiveIntegerField(default=5)
    circuit_breaker_reset_minutes = models.PositiveIntegerField(default=15)
```

### 3. Request Idempotency

**Current State**:
- nestorwheelock: No idempotency
- inventory-ai: No idempotency
- vetfriendly: No idempotency

**Gap**: Duplicate API calls if user double-clicks or network retries.

**Recommendation**: Include in primitive via django-decisioning integration:

```python
@idempotent(scope='ai_chat', key_from=lambda messages, **kw: hash_messages(messages))
def chat(messages, ...):
    # Same input within TTL returns cached response
```

### 4. Async Support

**Current State**:
- nestorwheelock: Sync only
- inventory-ai: Sync only
- vetfriendly: Has async methods but rarely used

**Gap**: No project fully leverages async for concurrent AI calls.

**Recommendation**: Primitive should support both:

```python
class AIService:
    def chat(self, messages, ...):  # Sync
        return self._chat_sync(messages, ...)

    async def achat(self, messages, ...):  # Async
        return await self._chat_async(messages, ...)
```

### 5. Structured Output Validation

**Current State**: All projects parse AI JSON responses with try/except.

**Gap**: No schema validation of AI outputs.

**Recommendation**: Add optional Pydantic/JSON Schema validation:

```python
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    category: str
    confidence: float
    tags: list[str]

response = service.chat(
    messages=[...],
    response_model=ClassificationResult,  # Validates output
)
```

### 6. Retry with Exponential Backoff

**Current State**:
- nestorwheelock: 2 retry attempts, simple
- inventory-ai: No retries
- vetfriendly: No retries

**Gap**: No exponential backoff, no jitter.

**Recommendation**: Include proper retry logic:

```python
class AIServiceConfig(SingletonModel):
    max_retries = models.PositiveIntegerField(default=3)
    retry_base_delay_seconds = models.DecimalField(default=1.0)
    retry_max_delay_seconds = models.DecimalField(default=30.0)
```

### 7. Request/Response Logging Toggle

**Current State**:
- nestorwheelock: `debug_mode` logs full responses
- inventory-ai: `debug_mode` stores raw API response
- vetfriendly: No prompt/response logging

**Gap**: Inconsistent approach to privacy vs debugging.

**Recommendation**: Explicit separate toggles:

```python
class AIServiceConfig(SingletonModel):
    log_prompts = models.BooleanField(default=False)  # Privacy concern
    log_responses = models.BooleanField(default=False)  # Cost concern (storage)
    log_prompt_hash = models.BooleanField(default=True)  # Safe deduplication
```

### 8. Cost Estimation Before Request

**Current State**: All projects calculate cost AFTER the API call.

**Gap**: No pre-flight cost estimation to prevent budget overruns.

**Recommendation**: Add estimation method:

```python
class AIService:
    def estimate_cost(self, messages, max_tokens) -> Decimal:
        """Estimate cost before making request."""
        input_tokens = self._count_tokens(messages)
        model_pricing = self._get_model_pricing()
        estimated = (input_tokens * model_pricing.input_per_1k / 1000) + \
                   (max_tokens * model_pricing.output_per_1k / 1000)
        return estimated

    def chat(self, messages, ...):
        estimated = self.estimate_cost(messages, max_tokens)
        if estimated > self.config.per_request_cost_limit_usd:
            raise CostLimitExceeded(f"Estimated ${estimated} exceeds limit")
        # Proceed with request
```

### 9. Audit Log Integration

**Current State**:
- nestorwheelock: Separate AIUsageLog, no link to audit-log primitive
- inventory-ai: ai_processing_logs standalone
- vetfriendly: AIUsage standalone

**Gap**: No integration with django-audit-log for unified audit trail.

**Recommendation**: Dual logging - AIUsageLog for AI-specific metrics + django-audit-log for business events:

```python
def analyze_object(target_obj, ...):
    # AI-specific log
    usage_log = AIUsageLog.objects.create(...)

    # Business audit log (via django-audit-log)
    from django_audit_log import log
    log(
        action='ai_analysis',
        obj=target_obj,
        actor=user,
        metadata={'usage_log_id': str(usage_log.pk)}
    )
```

### 10. Model Versioning/Pinning

**Current State**: All projects use model names like `anthropic/claude-3.5-sonnet`.

**Gap**: When providers update models, behavior may change unexpectedly.

**Recommendation**: Support version pinning:

```python
class AIServiceConfig(SingletonModel):
    default_model = models.CharField(default="anthropic/claude-sonnet-4")
    pin_model_version = models.BooleanField(default=False)
    # If True, include version in requests
    # anthropic/claude-sonnet-4 → anthropic/claude-sonnet-4-20240620
```

---

## What to Leave Out of the Primitive

These features are too domain-specific or application-level:

### 1. Chatbot/Conversation Management

**Why Leave Out**:
- Conversation models (Session, Message) are tightly coupled to UI
- Different apps need different conversation semantics
- Some need multi-turn, some need single-shot
- UI concerns (streaming, typing indicators) don't belong in primitive

**What Apps Should Build**:
- ChatSession model
- ChatMessage model
- WebSocket/SSE handling
- Conversation history management

### 2. Content Indexing / Embeddings

**Why Leave Out**:
- Requires vector database (pgvector, Pinecone, etc.)
- Embedding models vary (OpenAI, local, etc.)
- Search semantics are domain-specific
- Token budget allocation is application-specific

**What Apps Should Build**:
- ContentIndex model
- Embedding generation pipeline
- Semantic search queries
- Context window management

### 3. Image/Media Analysis Schema

**Why Leave Out**:
- nestorwheelock's 50+ field schema is specific to photo management
- Other apps need different fields (medical imaging, inventory photos)
- Analysis depth varies by use case

**What Apps Should Build**:
- Domain-specific analysis models
- Custom field schemas
- Analysis pipeline orchestration

### 4. OSINT / Intelligence Processing

**Why Leave Out**:
- Highly specialized (age derivation, timeline triangulation)
- Ethical/legal concerns need app-level handling
- Not applicable to most projects

**What Apps Should Build**:
- Profile extraction logic
- Confidence scoring
- Source triangulation

### 5. Module/Template System

**Why Leave Out**:
- inventory-ai's module system is specific to photo analysis pipelines
- Prompt composition strategies vary by domain
- Module stacking is application architecture

**What Apps Should Build**:
- Domain-specific prompt templates
- Module composition logic
- Category/type-specific processing

### 6. Natural Language Command Parsing

**Why Leave Out**:
- Command patterns are domain-specific
- "Move item to category" vs "Book appointment" are different grammars
- Intent detection is application logic

**What Apps Should Build**:
- Command regex patterns
- Intent classification
- Entity extraction for their domain

### 7. Bilingual/Multi-language Support

**Why Leave Out**:
- Not all apps need multiple languages
- Translation is a separate concern
- Language detection adds complexity

**What Apps Should Build**:
- Language field on models
- Bilingual prompt templates
- Translation service integration

---

## Recommended Primitive Scope

### INCLUDE in django-ai-services

| Component | Justification |
|-----------|--------------|
| **AIServiceConfig** | All projects need centralized config |
| **AIUsageLog** | All projects track usage/cost identically |
| **AIAnalysis** | Generic analysis record with GenericFK |
| **Provider Abstraction** | OpenRouter, Ollama, custom - all needed |
| **ToolRegistry** | Infrastructure for function calling |
| **Cost Estimation** | Budget protection needed everywhere |
| **Circuit Breaker** | Reliability pattern missing in all |
| **Retry Logic** | Missing in most projects |
| **Idempotency** | Via django-decisioning integration |
| **Audit Integration** | Via django-audit-log integration |

### EXCLUDE from primitive (app responsibility)

| Component | Justification |
|-----------|--------------|
| Conversation/Chat models | UI-coupled, varies by app |
| Content indexing | Requires vector DB, domain-specific |
| Image analysis schema | Too specific to nestorwheelock |
| OSINT processing | Specialized use case |
| Module/template system | inventory-ai specific |
| Command parsing | Domain-specific grammar |
| Multi-language | Not universally needed |
| Tool implementations | Domain-specific by definition |
| Context builders | Each app builds own context |

---

## Implementation Priority

### Phase 1: Core Infrastructure (MVP)
1. AIServiceConfig singleton
2. AIUsageLog immutable audit
3. OpenRouterProvider
4. Basic AIService with logging

### Phase 2: Reliability
5. Circuit breaker
6. Retry with backoff
7. Cost estimation/limits
8. Idempotency integration

### Phase 3: Extensibility
9. OllamaProvider (local)
10. Custom provider support
11. ToolRegistry infrastructure
12. AIAnalysis with GenericFK

### Phase 4: Security
13. Encrypted key storage option
14. Prompt/response logging controls
15. Audit log integration

---

## Migration Recommendations

### For nestorwheelock.com
- Replace ChatbotConfig with AIServiceConfig
- Keep: ContentIndex, MediaAnalysis, agentic tools
- Migrate: AIUsageLog schema to match primitive

### For inventory-ai
- Replace settings table with AIServiceConfig
- Keep: Module system, category processing, command parsing
- Migrate: ai_processing_logs to AIUsageLog
- Gain: Ollama provider already familiar

### For vetfriendly
- AIServiceConfig replaces settings.py AI configs
- Keep: Tool implementations, ai_context.py files, bilingual support
- Migrate: AIUsage to AIUsageLog
- Keep: ToolRegistry pattern (similar to proposed)

---

## Conclusion

A well-designed `django-ai-services` primitive can eliminate ~60% of duplicated AI infrastructure code across projects while remaining flexible enough for diverse domains. The key is drawing a clear line between:

- **Infrastructure** (primitive): Config, logging, providers, reliability
- **Application** (each project): Tools, context, domain logic, UI

This analysis should guide the primitive's API design to ensure it serves all three existing projects while being generic enough for future applications.
