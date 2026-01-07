"""Models for django-ai-services."""

import json
import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_singleton.models import SingletonModel


class AIServiceConfig(SingletonModel):
    """
    Global AI service configuration.
    Supports API key storage with environment variable fallback.
    Optional encryption for provider configs at rest.
    """

    # Class-level encryption key (set at app startup, not stored in DB)
    _encryption_key: str | None = None

    # Provider Configuration
    _provider_configs = models.TextField(
        db_column="provider_configs",
        default="{}",
        help_text="Provider-specific configs as JSON",
    )

    # Default Provider & Model
    default_provider = models.CharField(max_length=50, default="openrouter")
    default_model = models.CharField(
        max_length=100, default="anthropic/claude-sonnet-4"
    )
    default_max_tokens = models.PositiveIntegerField(default=4096)
    default_temperature = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.7")
    )

    # Model Version Pinning
    pin_model_version = models.BooleanField(
        default=False,
        help_text="If True, append version date to model name for reproducibility",
    )
    pinned_model_versions = models.JSONField(
        default=dict,
        help_text="Model → version mapping",
    )

    # Fallback Chain
    fallback_provider = models.CharField(max_length=50, blank=True)
    fallback_model = models.CharField(max_length=100, blank=True)

    # Cost Controls
    daily_cost_limit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Max spend per day (null = unlimited)",
    )
    per_request_cost_limit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.50"),
        help_text="Pre-flight cost check rejects requests above this",
    )
    monthly_cost_limit_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    pause_on_budget_exceeded = models.BooleanField(default=False)

    # Token Budgets (per operation type)
    token_budgets = models.JSONField(
        default=dict,
        help_text="Operation-specific max_tokens: {operation: max_tokens}",
    )

    # Model Pricing (for cost estimation)
    model_pricing = models.JSONField(
        default=dict,
        help_text="Pricing per model: {model: {input_per_1m: X, output_per_1m: Y}}",
    )

    # Rate Limiting (hints for app layer)
    requests_per_minute_anonymous = models.PositiveIntegerField(default=10)
    requests_per_minute_authenticated = models.PositiveIntegerField(default=60)
    requests_per_day_per_user = models.PositiveIntegerField(default=1000)
    request_cooldown_seconds = models.PositiveIntegerField(default=2)

    # Circuit Breaker
    provider_health = models.JSONField(
        default=dict,
        help_text="Health state: {provider: {failures: N, last_failure: ts, circuit_open: bool}}",
    )
    circuit_breaker_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Consecutive failures before opening circuit",
    )
    circuit_breaker_reset_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Minutes before attempting to close circuit",
    )

    # Retry Configuration
    max_retries = models.PositiveIntegerField(default=3)
    retry_base_delay_seconds = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("1.0")
    )
    retry_max_delay_seconds = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("30.0")
    )
    retry_jitter = models.BooleanField(
        default=True,
        help_text="Add randomness to retry delays to prevent thundering herd",
    )

    # Logging & Debug
    is_enabled = models.BooleanField(default=True)
    debug_mode = models.BooleanField(default=False)

    # Prompt/Response logging controls
    log_prompt_hash = models.BooleanField(
        default=True,
        help_text="Always safe: SHA-256 for deduplication",
    )
    log_prompts = models.BooleanField(
        default=False,
        help_text="Privacy concern: stores prompt preview",
    )
    log_responses = models.BooleanField(
        default=False,
        help_text="Storage concern: stores response preview",
    )

    class Meta:
        verbose_name = "AI Service Configuration"

    # ═══════════════════════════════════════════════════════════════════
    # ENCRYPTION METHODS
    # ═══════════════════════════════════════════════════════════════════

    @classmethod
    def set_encryption_key(cls, key: str):
        """
        Set encryption key from environment (call at app startup).

        Args:
            key: A Fernet-compatible key (use Fernet.generate_key())
        """
        cls._encryption_key = key

    def _get_fernet(self):
        """Get Fernet instance if encryption key is set."""
        if self._encryption_key:
            try:
                from cryptography.fernet import Fernet
                return Fernet(self._encryption_key.encode())
            except Exception:
                return None
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
                # Fall back to plain JSON if decryption fails
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
        if not config.get("api_key"):
            env_key = f"{provider_name.upper()}_API_KEY"
            config["api_key"] = os.environ.get(env_key, "")

        return config

    def get_model_with_version(self, model: str) -> str:
        """Apply version pinning if enabled."""
        if not self.pin_model_version:
            return model
        version = self.pinned_model_versions.get(model)
        if version:
            return f"{model}-{version}"
        return model


class AIUsageLog(models.Model):
    """
    Immutable record of every AI API call.
    """

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who triggered this?
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_logs",
    )

    # Session tracking
    session_id = models.CharField(max_length=255, blank=True, db_index=True)

    # What was the target?
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    target_object_id = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Operation
    operation = models.CharField(
        max_length=100,
        db_index=True,
        help_text="e.g., chat, analyze, classify, tagging",
    )

    # Provider & Model
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50, blank=True)

    # Token Usage
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    # Cost Tracking
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Pre-request estimate",
    )
    actual_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal("0"),
        help_text="Post-request actual",
    )

    # Performance
    processing_time_ms = models.PositiveIntegerField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    used_fallback = models.BooleanField(default=False)

    # Debug (privacy-controlled)
    prompt_hash = models.CharField(max_length=64, blank=True, db_index=True)
    prompt_preview = models.CharField(max_length=500, blank=True)
    response_preview = models.CharField(max_length=500, blank=True)

    # Timestamps
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


class AIAnalysis(models.Model):
    """
    Record of AI analysis performed on any entity.
    Uses GenericFK to attach to any model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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
        null=True,
        blank=True,
        related_name="ai_analyses",
    )

    # Link to usage log
    usage_log = models.ForeignKey(
        AIUsageLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analyses",
    )

    # Review status
    is_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["analysis_type", "created_at"]),
            models.Index(fields=["input_hash"]),
            models.Index(fields=["triggered_by", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(confidence__isnull=True)
                | (models.Q(confidence__gte=0) & models.Q(confidence__lte=1)),
                name="ai_analysis_confidence_range",
            ),
        ]
