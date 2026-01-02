"""
RBAC User Mixin - Add role-based access control to User model.

This mixin should be added to your custom User model to enable RBAC features:

    from django.contrib.auth.models import AbstractUser
    from django_rbac.mixins import RBACUserMixin

    class User(RBACUserMixin, AbstractUser):
        pass

The mixin provides:
- hierarchy_level property (from highest assigned role)
- can_manage_user(other_user) method (hierarchy check)
- get_manageable_roles() method (roles user can assign)
- has_module_permission(module, action) method (permission check)

Key Rule (CONTRACT Rule 2):
Users can only manage users with LOWER hierarchy levels.
"""

from django.db.models import QuerySet


class RBACUserMixin:
    """Mixin that adds RBAC methods to a User model.

    Add this mixin to your User model:

        class User(RBACUserMixin, AbstractUser):
            pass

    This enables:
    - user.hierarchy_level -> int (0-100)
    - user.can_manage_user(other) -> bool
    - user.get_manageable_roles() -> QuerySet[Role]
    - user.has_module_permission(module, action) -> bool
    """

    @property
    def hierarchy_level(self) -> int:
        """Get user's highest hierarchy level from currently valid roles.

        Only considers roles where:
        - valid_from <= now
        - valid_to is null OR valid_to > now

        Returns:
            int: The highest hierarchy level from all current roles.
                 100 for superusers (is_superuser=True).
                 0 for users with no current roles.

        Examples:
            >>> user.hierarchy_level
            60  # Manager level

            >>> superuser.hierarchy_level
            100  # Always highest
        """
        if self.is_superuser:
            return 100

        levels = self.user_roles.current().values_list('role__hierarchy_level', flat=True)
        return max(levels) if levels else 0

    def can_manage_user(self, other_user) -> bool:
        """Check if this user can manage another user (hierarchy check).

        A user can only manage users with a LOWER hierarchy level.
        Users at the same level cannot manage each other.

        This enforces CONTRACT Rule 2:
        "Users can only manage users with LOWER hierarchy levels."

        Args:
            other_user: The user to check management permission for.

        Returns:
            bool: True if this user can manage the other user.

        Examples:
            >>> manager.can_manage_user(staff)
            True  # Manager (60) > Staff (20)

            >>> staff.can_manage_user(manager)
            False  # Staff (20) < Manager (60)

            >>> manager1.can_manage_user(manager2)
            False  # Same level (60) cannot manage each other
        """
        return self.hierarchy_level > other_user.hierarchy_level

    def get_manageable_roles(self) -> QuerySet:
        """Get roles this user can assign to others.

        Users can only assign roles that are BELOW their own hierarchy level.
        This prevents privilege escalation.

        Returns:
            QuerySet[Role]: Active roles with hierarchy_level below this user's level.

        Examples:
            >>> manager.get_manageable_roles()
            [Staff (20), Customer (10)]  # Below Manager (60)
        """
        from django_rbac.models import Role

        return Role.objects.filter(
            hierarchy_level__lt=self.hierarchy_level,
            is_active=True,
        )

    def has_module_permission(self, module: str, action: str = 'view') -> bool:
        """Check if user has permission for module+action.

        Superusers always have all permissions.
        Regular users must have the permission assigned via their role's group.

        Permission codenames are formatted as: "{module}.{action}"
        e.g., "practice.view", "accounting.manage", "inventory.edit"

        Args:
            module: The module name (e.g., 'practice', 'accounting')
            action: The action name (e.g., 'view', 'create', 'edit', 'delete', 'manage')

        Returns:
            bool: True if user has the permission.

        Examples:
            >>> receptionist.has_module_permission('practice', 'view')
            True

            >>> receptionist.has_module_permission('accounting', 'view')
            False

            >>> superuser.has_module_permission('anything', 'any')
            True
        """
        if self.is_superuser:
            return True

        # Build the permission codename
        codename = f'{module}.{action}'

        # Check permissions via Role's groups (only current roles)
        from django.contrib.auth.models import Permission

        role_group_ids = self.user_roles.current().values_list('role__group_id', flat=True)
        return Permission.objects.filter(
            group__id__in=role_group_ids,
            codename=codename,
        ).exists()
