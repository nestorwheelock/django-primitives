"""Configuration for django-modules."""

from django.conf import settings

from django_modules.exceptions import ModulesConfigError


def get_org_model():
    """Get the configured organization model.

    Reads MODULES_ORG_MODEL from Django settings.
    Format: 'app_label.ModelName'

    Raises:
        ModulesConfigError: If MODULES_ORG_MODEL is not configured
    """
    org_model = getattr(settings, "MODULES_ORG_MODEL", None)
    if not org_model:
        raise ModulesConfigError(
            "MODULES_ORG_MODEL setting is required. "
            "Set it to your organization model path, e.g. 'myapp.Organization'"
        )
    return org_model


# Lazy evaluation - only resolve when models are loaded
ORG_MODEL = None


def get_org_model_string():
    """Get org model as string for ForeignKey."""
    return get_org_model()
