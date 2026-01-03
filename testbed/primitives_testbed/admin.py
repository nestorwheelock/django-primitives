"""Admin configuration for primitives testbed.

Most primitive packages already register their own admin classes.
This module only registers the custom User model and any models
that aren't already registered.
"""

from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


# ============================================================================
# Custom User Admin (testbed-specific)
# ============================================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "hierarchy_level_display")

    def hierarchy_level_display(self, obj):
        return obj.hierarchy_level
    hierarchy_level_display.short_description = "RBAC Level"


# ============================================================================
# Helper to safely register models
# ============================================================================

def safe_register(model, admin_class=None):
    """Register a model only if not already registered."""
    try:
        if admin_class:
            admin.site.register(model, admin_class)
        else:
            admin.site.register(model)
    except AlreadyRegistered:
        pass  # Already registered by the package


# ============================================================================
# Register any unregistered primitive models
# ============================================================================

# Note: Most primitive packages register their own admin classes.
# The imports below will trigger those registrations.
# We only need to import them to ensure they're registered.

# Trigger admin registrations from primitive packages
try:
    import django_parties.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_rbac.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_catalog.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_geo.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_encounters.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_documents.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_notes.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_sequence.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_ledger.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_worklog.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_agreements.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_audit_log.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_decisioning.admin  # noqa: F401
except ImportError:
    pass

try:
    import django_modules.admin  # noqa: F401
except ImportError:
    pass
