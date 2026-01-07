"""Mixins for django-singleton models."""

import os
from typing import Any, Dict


class EnvFallbackMixin:
    """Mixin for SingletonModel that provides environment variable fallback.

    Define ENV_FALLBACKS as a class attribute mapping field names to env var names:

        class MySettings(EnvFallbackMixin, SingletonModel):
            api_key = models.CharField(max_length=255, blank=True)

            ENV_FALLBACKS = {
                'api_key': 'MY_API_KEY',
            }

    Then use get_with_fallback() to get DB value or env fallback:

        settings = MySettings.get_instance()
        key = settings.get_with_fallback('api_key')

    The precedence is:
        1. Database value (if not blank)
        2. Environment variable (if configured in ENV_FALLBACKS)
        3. Default value (passed to get_with_fallback())
    """

    ENV_FALLBACKS: Dict[str, str] = {}

    def get_with_fallback(self, field_name: str, default: Any = "") -> Any:
        """Get field value, falling back to environment variable if blank.

        Args:
            field_name: Name of the model field
            default: Default value if both DB and env are empty

        Returns:
            DB value if not blank, else env value, else default
        """
        # Get DB value
        db_value = getattr(self, field_name, None)

        # If DB has a non-blank value, use it
        if db_value not in (None, ""):
            return db_value

        # Check for env fallback
        env_var = self.ENV_FALLBACKS.get(field_name)
        if env_var:
            env_value = os.environ.get(env_var, "")
            if env_value:
                return env_value

        return default

    def get_value_source(self, field_name: str) -> str:
        """Return where the value comes from: 'database', 'environment', or 'default'.

        Useful for debugging and admin display.

        Args:
            field_name: Name of the model field

        Returns:
            'database' if DB has value, 'environment' if env has value, else 'default'
        """
        db_value = getattr(self, field_name, None)
        if db_value not in (None, ""):
            return "database"

        env_var = self.ENV_FALLBACKS.get(field_name)
        if env_var and os.environ.get(env_var):
            return "environment"

        return "default"

    def get_resolved(self) -> Dict[str, Any]:
        """Get all ENV_FALLBACKS fields with fallbacks applied.

        Returns:
            Dict of field_name -> resolved_value for all fields in ENV_FALLBACKS
        """
        return {field: self.get_with_fallback(field) for field in self.ENV_FALLBACKS.keys()}

    def has_value(self, field_name: str) -> bool:
        """Check if field has a value from either DB or environment.

        Args:
            field_name: Name of the model field

        Returns:
            True if field has a non-empty value from DB or env
        """
        return bool(self.get_with_fallback(field_name))
