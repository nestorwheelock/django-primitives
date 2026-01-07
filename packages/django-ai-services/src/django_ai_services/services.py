"""AI Services for django-ai-services."""

import hashlib
import random
import time
from datetime import timedelta
from decimal import Decimal
from typing import Type

from django.db import models
from django.utils import timezone

from .exceptions import (
    AIServiceDisabled,
    BudgetExceeded,
    CircuitOpen,
    ProviderError,
    ValidationFailed,
)
from .models import AIAnalysis, AIServiceConfig, AIUsageLog
from .providers import AIProvider, AIResponse, OllamaProvider, OpenRouterProvider

try:
    from pydantic import BaseModel as PydanticModel
except ImportError:
    PydanticModel = None


class AIService:
    """
    High-level AI service with:
    - Automatic logging
    - Cost estimation & budget guards
    - Circuit breaker
    - Retry with exponential backoff
    - Sync + async interface
    """

    def __init__(self, user=None, session_id: str = ""):
        self.user = user
        self.session_id = session_id
        self.config = AIServiceConfig.get_instance()
        self._providers: dict[str, AIProvider] = {}

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

    def _check_circuit(self, provider_name: str):
        """Check if circuit is open for provider."""
        health = self.config.provider_health.get(provider_name, {})
        if health.get("circuit_open"):
            last_failure = health.get("last_failure")
            if last_failure:
                reset_after = timezone.now() - timedelta(
                    minutes=self.config.circuit_breaker_reset_minutes
                )
                try:
                    last_failure_dt = timezone.datetime.fromisoformat(last_failure)
                    if last_failure_dt > reset_after:
                        raise CircuitOpen(f"Circuit open for {provider_name}")
                except (ValueError, TypeError):
                    pass
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
            today_start = timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_cost = AIUsageLog.objects.filter(created_at__gte=today_start).aggregate(
                total=models.Sum("actual_cost_usd")
            )["total"] or Decimal("0")

            if float(today_cost) + estimated_cost > float(
                self.config.daily_cost_limit_usd
            ):
                if self.config.pause_on_budget_exceeded:
                    raise BudgetExceeded(
                        f"Daily budget ${self.config.daily_cost_limit_usd} would be exceeded"
                    )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        base = float(self.config.retry_base_delay_seconds)
        max_delay = float(self.config.retry_max_delay_seconds)
        delay = min(base * (2**attempt), max_delay)
        if self.config.retry_jitter:
            delay = delay * (0.5 + random.random())
        return delay

    def chat(
        self,
        messages: list[dict],
        operation: str = "chat",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        response_model: Type | None = None,
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
        max_tokens = (
            max_tokens
            or self.config.token_budgets.get(operation)
            or self.config.default_max_tokens
        )

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
                        temperature=float(
                            temperature or self.config.default_temperature
                        ),
                        tools=tools,
                        response_model=response_model,
                    )

                    # Structured output validation with repair loop
                    if (
                        response_model
                        and response.validation_errors
                        and max_repair_attempts > 0
                    ):
                        response = self._repair_structured_output(
                            messages,
                            response,
                            response_model,
                            model,
                            max_tokens,
                            temperature,
                            tools,
                            max_repair_attempts,
                        )

                    self._update_circuit(provider_name, success=True)
                    break

                except ValidationFailed:
                    # Validation failures should not trigger retry logic
                    raise
                except Exception as e:
                    retry_count += 1  # Count failures (retries needed)
                    if attempt < self.config.max_retries:
                        delay = self._calculate_delay(attempt)
                        time.sleep(delay)
                    else:
                        # Try fallback
                        if self.config.fallback_provider:
                            try:
                                fallback = self._get_provider(
                                    self.config.fallback_provider
                                )
                                response = fallback.chat(
                                    messages=messages,
                                    model=self.config.fallback_model,
                                    max_tokens=max_tokens,
                                    temperature=float(
                                        temperature or self.config.default_temperature
                                    ),
                                    response_model=response_model,
                                )
                                used_fallback = True
                                error_message = f"Fallback used after: {e}"
                                break
                            except Exception as fallback_error:
                                error_message = (
                                    f"Primary: {e}; Fallback: {fallback_error}"
                                )
                        else:
                            error_message = str(e)
                        self._update_circuit(provider_name, success=False)
                        raise ProviderError(error_message)

        except (ProviderError, ValidationFailed):
            success = False
            raise
        except Exception as e:
            success = False
            error_message = str(e)
            raise ProviderError(error_message)
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
        response_model: Type | None = None,
        target_obj=None,
        metadata: dict | None = None,
        skip_budget_check: bool = False,
        max_repair_attempts: int = 2,
    ) -> AIResponse:
        """Async version of chat()."""
        import asyncio

        if not self.config.is_enabled:
            raise AIServiceDisabled("AI services are currently disabled")

        model = self.config.get_model_with_version(model or self.config.default_model)
        max_tokens = (
            max_tokens
            or self.config.token_budgets.get(operation)
            or self.config.default_max_tokens
        )

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
                        temperature=float(
                            temperature or self.config.default_temperature
                        ),
                        tools=tools,
                        response_model=response_model,
                    )
                    self._update_circuit(provider_name, success=True)
                    break
                except ValidationFailed:
                    # Validation failures should not trigger retry logic
                    raise
                except Exception as e:
                    retry_count += 1  # Count failures (retries needed)
                    if attempt < self.config.max_retries:
                        delay = self._calculate_delay(attempt)
                        await asyncio.sleep(delay)
                    else:
                        if self.config.fallback_provider:
                            try:
                                fallback = self._get_provider(
                                    self.config.fallback_provider
                                )
                                response = await fallback.achat(
                                    messages=messages,
                                    model=self.config.fallback_model,
                                    max_tokens=max_tokens,
                                    temperature=float(
                                        temperature or self.config.default_temperature
                                    ),
                                    response_model=response_model,
                                )
                                used_fallback = True
                                error_message = f"Fallback used after: {e}"
                                break
                            except Exception as fallback_error:
                                error_message = (
                                    f"Primary: {e}; Fallback: {fallback_error}"
                                )
                        else:
                            error_message = str(e)
                        self._update_circuit(provider_name, success=False)
                        raise ProviderError(error_message)
        except (ProviderError, ValidationFailed):
            success = False
            raise
        except Exception as e:
            success = False
            error_message = str(e)
            raise ProviderError(error_message)
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

    def _repair_structured_output(
        self,
        original_messages: list[dict],
        failed_response: AIResponse,
        response_model: Type,
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
                {
                    "role": "user",
                    "content": (
                        f"Your response didn't match the required schema. "
                        f"Errors: {failed_response.validation_errors}. "
                        f"Please provide a valid JSON response matching this schema: "
                        f"{response_model.model_json_schema()}"
                    ),
                },
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
            "estimated_cost_usd": Decimal(str(estimated_cost)),
            "retry_count": retry_count,
            "used_fallback": used_fallback,
        }

        if response:
            log_kwargs.update(
                {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "actual_cost_usd": Decimal(str(response.cost_usd)),
                }
            )

        if target_obj:
            from django.contrib.contenttypes.models import ContentType

            log_kwargs.update(
                {
                    "target_content_type": ContentType.objects.get_for_model(target_obj),
                    "target_object_id": str(target_obj.pk),
                }
            )

        if messages and self.config.log_prompt_hash:
            prompt_str = str(messages)
            log_kwargs["prompt_hash"] = hashlib.sha256(prompt_str.encode()).hexdigest()

        if messages and self.config.log_prompts:
            log_kwargs["prompt_preview"] = str(messages)[:500]

        if response and self.config.log_responses:
            log_kwargs["response_preview"] = response.content[:500]

        AIUsageLog.objects.create(**log_kwargs)

    def analyze_object(
        self,
        obj,
        analysis_type: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_model: Type | None = None,
        metadata: dict | None = None,
        force: bool = False,
    ) -> AIResponse:
        """
        Analyze an object with idempotency support.

        Returns cached AIAnalysis result if same input_hash exists,
        otherwise makes a new AI call and stores the result.

        Args:
            obj: The object to analyze (any Django model instance)
            analysis_type: Type of analysis (e.g., "classification", "summary")
            prompt: The analysis prompt
            model: Model override
            max_tokens: Max tokens override
            temperature: Temperature override
            response_model: Pydantic model for structured output
            metadata: Additional metadata
            force: If True, bypass cache and force new analysis

        Returns:
            AIResponse with the analysis result
        """
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(obj)
        object_id = str(obj.pk)

        # Compute input hash for idempotency
        input_data = {
            "prompt": prompt,
            "analysis_type": analysis_type,
            "object_id": object_id,
            "content_type": f"{content_type.app_label}.{content_type.model}",
        }
        input_hash = hashlib.sha256(str(input_data).encode()).hexdigest()

        # Check for existing analysis (idempotency)
        if not force:
            existing = AIAnalysis.objects.filter(
                target_content_type=content_type,
                target_object_id=object_id,
                analysis_type=analysis_type,
                input_hash=input_hash,
            ).first()

            if existing:
                # Return cached result as AIResponse
                return AIResponse(
                    content=str(existing.result),
                    model=existing.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    raw_response=existing.result,
                )

        # Make new analysis call
        messages = [{"role": "user", "content": prompt}]

        response = self.chat(
            messages=messages,
            operation=f"analyze_{analysis_type}",
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_model=response_model,
            target_obj=obj,
            metadata=metadata,
        )

        # Parse result as JSON if possible
        try:
            import json
            result = json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            result = {"raw_response": response.content}

        # Get confidence from parsed result if available
        confidence = None
        if response.parsed and hasattr(response.parsed, "confidence"):
            confidence = Decimal(str(response.parsed.confidence))

        # Create AIAnalysis record
        usage_log = AIUsageLog.objects.filter(
            target_content_type=content_type,
            target_object_id=object_id,
        ).order_by("-created_at").first()

        AIAnalysis.objects.create(
            target_content_type=content_type,
            target_object_id=object_id,
            analysis_type=analysis_type,
            provider=self.config.default_provider,
            model=response.model,
            input_data=input_data,
            input_hash=input_hash,
            result=result,
            confidence=confidence,
            validation_passed=response.validation_errors is None,
            validation_errors=response.validation_errors or [],
            triggered_by=self.user,
            usage_log=usage_log,
        )

        return response
