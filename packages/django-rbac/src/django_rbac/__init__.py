"""Django RBAC - Role-based access control with hierarchy enforcement."""

__version__ = '0.1.0'

# Lazy imports to avoid AppRegistryNotReady errors
def __getattr__(name):
    if name == 'Role':
        from django_rbac.models import Role
        return Role
    if name == 'UserRole':
        from django_rbac.models import UserRole
        return UserRole
    if name == 'RBACUserMixin':
        from django_rbac.mixins import RBACUserMixin
        return RBACUserMixin
    if name == 'require_permission':
        from django_rbac.decorators import require_permission
        return require_permission
    if name == 'requires_hierarchy_level':
        from django_rbac.decorators import requires_hierarchy_level
        return requires_hierarchy_level
    if name == 'ModulePermissionMixin':
        from django_rbac.views import ModulePermissionMixin
        return ModulePermissionMixin
    if name == 'HierarchyPermissionMixin':
        from django_rbac.views import HierarchyPermissionMixin
        return HierarchyPermissionMixin
    if name == 'CombinedPermissionMixin':
        from django_rbac.views import CombinedPermissionMixin
        return CombinedPermissionMixin
    if name == 'HierarchyLevelMixin':
        from django_rbac.views import HierarchyLevelMixin
        return HierarchyLevelMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'Role',
    'UserRole',
    'RBACUserMixin',
    'require_permission',
    'requires_hierarchy_level',
    'ModulePermissionMixin',
    'HierarchyPermissionMixin',
    'CombinedPermissionMixin',
    'HierarchyLevelMixin',
]
