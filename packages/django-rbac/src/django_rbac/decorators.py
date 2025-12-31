"""
RBAC Decorators for function-based views.

Provides decorators to protect views with permission and hierarchy checks.

Usage:
    @require_permission('practice', 'manage')
    def staff_create(request):
        ...

    @requires_hierarchy_level(60)  # Manager or higher
    def approve_leave(request):
        ...
"""

from functools import wraps

from django.core.exceptions import PermissionDenied


def require_permission(module: str, action: str = 'view'):
    """Decorator to require module permission for function-based views.

    Checks if the current user has the specified module.action permission.
    Raises PermissionDenied if the user lacks the required permission.

    The user must have a `has_module_permission` method, which is provided
    by the RBACUserMixin.

    Args:
        module: The module name (e.g., 'practice', 'accounting')
        action: The action name (e.g., 'view', 'create', 'manage')

    Raises:
        PermissionDenied: If user lacks the required permission.

    Examples:
        @require_permission('practice', 'manage')
        def staff_create(request):
            # Only users with practice.manage permission can access
            ...

        @require_permission('accounting', 'view')
        def view_invoices(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied('Authentication required')

            if not hasattr(request.user, 'has_module_permission'):
                raise PermissionDenied('User model must include RBACUserMixin')

            if not request.user.has_module_permission(module, action):
                raise PermissionDenied(f'Permission denied: {module}.{action}')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def requires_hierarchy_level(min_level: int):
    """Decorator to require minimum hierarchy level for function-based views.

    Checks if the current user's hierarchy level meets or exceeds the minimum.
    Raises PermissionDenied if the user's level is too low.

    The user must have a `hierarchy_level` property, which is provided
    by the RBACUserMixin.

    Args:
        min_level: The minimum hierarchy level required (10-100).

    Raises:
        PermissionDenied: If user's hierarchy level is below min_level.

    Examples:
        @requires_hierarchy_level(60)  # Manager or higher
        def approve_leave_request(request, user_id):
            ...

        @requires_hierarchy_level(80)  # Administrator or higher
        def system_settings(request):
            ...

    Hierarchy levels reference:
        100 = Superuser
        80 = Administrator
        60 = Manager
        40 = Professional
        30 = Technician
        20 = Staff
        10 = Customer
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied('Authentication required')

            if not hasattr(request.user, 'hierarchy_level'):
                raise PermissionDenied('User model must include RBACUserMixin')

            if request.user.hierarchy_level < min_level:
                raise PermissionDenied(
                    f'Requires hierarchy level {min_level} or higher. '
                    f'Your level: {request.user.hierarchy_level}'
                )

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
