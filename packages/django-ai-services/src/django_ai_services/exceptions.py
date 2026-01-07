"""Exceptions for django-ai-services."""


class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass


class AIServiceDisabled(AIServiceError):
    """AI services are currently disabled."""
    pass


class BudgetExceeded(AIServiceError):
    """Request exceeds budget limits."""
    pass


class CircuitOpen(AIServiceError):
    """Circuit breaker is open for provider."""
    pass


class ProviderError(AIServiceError):
    """Provider-level error (API failure, network, etc.)."""
    pass


class ValidationFailed(AIServiceError):
    """Structured output validation failed."""
    pass
