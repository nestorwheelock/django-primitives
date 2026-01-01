# Prompt: Rebuild django-rbac

## Instruction

Create a Django package called `django-rbac` that provides role-based access control with hierarchy enforcement.

## Package Purpose

Provide role-based access control primitives:
- `Role` - Named roles with hierarchy support
- `UserRole` - Assignment of roles to users with effective dating
- `RBACUserMixin` - User model mixin for role checking
- EffectiveDatedQuerySet for temporal queries

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.auth

## File Structure

```
packages/django-rbac/
├── pyproject.toml
├── README.md
├── src/django_rbac/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── mixins.py
│   ├── querysets.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    ├── test_mixins.py
    └── test_querysets.py
```

## QuerySets Specification

### querysets.py

```python
from django.db import models
from django.utils import timezone

class EffectiveDatedQuerySet(models.QuerySet):
    """QuerySet for models with valid_from/valid_to fields."""

    def current(self):
        """Get currently valid records."""
        return self.as_of(timezone.now())

    def as_of(self, timestamp):
        """Get records valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )

    def expired(self):
        """Get records that have expired."""
        now = timezone.now()
        return self.filter(valid_to__lte=now)

    def future(self):
        """Get records not yet valid."""
        now = timezone.now()
        return self.filter(valid_from__gt=now)
```

## Models Specification

### Role Model

```python
from django.db import models
from django_basemodels.models import UUIDModel, BaseModel

class Role(UUIDModel, BaseModel):
    """Named role with optional hierarchy."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')

    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )

    # Priority for conflict resolution
    priority = models.IntegerField(default=0)

    class Meta:
        app_label = 'django_rbac'
        verbose_name = 'role'
        verbose_name_plural = 'roles'
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name

    def get_ancestors(self):
        """Get all ancestor roles (parent, grandparent, etc)."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """Get all descendant roles (children, grandchildren, etc)."""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def inherits_from(self, role) -> bool:
        """Check if this role inherits from another role."""
        return role in self.get_ancestors()
```

### UserRole Model

```python
from django.conf import settings
from django.utils import timezone
from .querysets import EffectiveDatedQuerySet

class UserRole(UUIDModel, BaseModel):
    """Assignment of a role to a user with effective dating."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_assignments'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_assignments'
    )

    # Effective dating
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)

    # Assignment metadata
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_assigned'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, default='')

    objects = EffectiveDatedQuerySet.as_manager()

    class Meta:
        app_label = 'django_rbac'
        verbose_name = 'user role'
        verbose_name_plural = 'user roles'
        constraints = [
            # Only one active assignment per user+role at a time
            models.UniqueConstraint(
                fields=['user', 'role'],
                condition=models.Q(valid_to__isnull=True),
                name='unique_active_user_role'
            )
        ]

    @property
    def is_active(self) -> bool:
        """Check if this assignment is currently active."""
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now >= self.valid_to:
            return False
        return True

    def __str__(self):
        status = 'active' if self.is_active else 'inactive'
        return f"{self.user} → {self.role} ({status})"
```

## Mixins Specification

### mixins.py

```python
from django.utils import timezone

class RBACUserMixin:
    """Mixin for User model to add role-checking methods."""

    def get_roles(self, include_inherited=True):
        """
        Get all roles for this user.

        Args:
            include_inherited: If True, include roles inherited via hierarchy

        Returns:
            Set of Role instances
        """
        from .models import UserRole, Role

        # Get directly assigned active roles
        assignments = UserRole.objects.filter(user=self).current()
        direct_roles = set(a.role for a in assignments)

        if not include_inherited:
            return direct_roles

        # Add inherited roles (ancestors)
        all_roles = set(direct_roles)
        for role in direct_roles:
            all_roles.update(role.get_ancestors())

        return all_roles

    def has_role(self, role_or_slug, include_inherited=True) -> bool:
        """
        Check if user has a specific role.

        Args:
            role_or_slug: Role instance or slug string
            include_inherited: If True, check inherited roles too

        Returns:
            True if user has the role
        """
        from .models import Role

        if isinstance(role_or_slug, str):
            try:
                role = Role.objects.get(slug=role_or_slug)
            except Role.DoesNotExist:
                return False
        else:
            role = role_or_slug

        user_roles = self.get_roles(include_inherited=include_inherited)
        return role in user_roles

    def has_any_role(self, roles_or_slugs, include_inherited=True) -> bool:
        """
        Check if user has any of the specified roles.

        Args:
            roles_or_slugs: List of Role instances or slug strings
            include_inherited: If True, check inherited roles too

        Returns:
            True if user has at least one of the roles
        """
        for role in roles_or_slugs:
            if self.has_role(role, include_inherited):
                return True
        return False

    def has_all_roles(self, roles_or_slugs, include_inherited=True) -> bool:
        """
        Check if user has all of the specified roles.

        Args:
            roles_or_slugs: List of Role instances or slug strings
            include_inherited: If True, check inherited roles too

        Returns:
            True if user has all of the roles
        """
        for role in roles_or_slugs:
            if not self.has_role(role, include_inherited):
                return False
        return True

    def get_highest_priority_role(self):
        """
        Get the user's highest priority role.

        Returns:
            Role with highest priority, or None
        """
        roles = self.get_roles(include_inherited=False)
        if not roles:
            return None
        return max(roles, key=lambda r: r.priority)

    def assign_role(self, role, assigned_by=None, reason='', valid_from=None):
        """
        Assign a role to this user.

        Args:
            role: Role instance to assign
            assigned_by: User who is assigning the role
            reason: Reason for assignment
            valid_from: When assignment becomes effective

        Returns:
            UserRole instance
        """
        from .models import UserRole
        from django.utils import timezone

        return UserRole.objects.create(
            user=self,
            role=role,
            assigned_by=assigned_by,
            reason=reason,
            valid_from=valid_from or timezone.now()
        )

    def revoke_role(self, role, reason=''):
        """
        Revoke a role from this user.

        Args:
            role: Role instance to revoke
            reason: Reason for revocation

        Returns:
            Updated UserRole instance or None
        """
        from .models import UserRole
        from django.utils import timezone

        try:
            assignment = UserRole.objects.filter(
                user=self, role=role
            ).current().get()
            assignment.valid_to = timezone.now()
            assignment.save(update_fields=['valid_to'])
            return assignment
        except UserRole.DoesNotExist:
            return None
```

## Test Cases (30 tests)

### Role Model Tests (10 tests)
1. `test_role_creation` - Create with required fields
2. `test_role_has_uuid_pk` - UUID primary key
3. `test_role_unique_name` - Unique name constraint
4. `test_role_unique_slug` - Unique slug constraint
5. `test_role_parent_hierarchy` - Parent FK works
6. `test_role_get_ancestors` - Returns parent chain
7. `test_role_get_descendants` - Returns children chain
8. `test_role_inherits_from` - Checks inheritance
9. `test_role_ordering` - Ordered by priority, name
10. `test_role_soft_delete` - Soft delete works

### UserRole Model Tests (8 tests)
1. `test_userrole_creation` - Create assignment
2. `test_userrole_has_uuid_pk` - UUID primary key
3. `test_userrole_valid_from_defaults_to_now` - Default value
4. `test_userrole_valid_to_nullable` - Can be indefinite
5. `test_userrole_is_active_property` - Active check
6. `test_userrole_unique_active_constraint` - No duplicate active
7. `test_userrole_can_have_historical` - Multiple historical
8. `test_userrole_str_representation` - String format

### EffectiveDatedQuerySet Tests (6 tests)
1. `test_current_returns_active` - Currently valid only
2. `test_current_excludes_expired` - Expired excluded
3. `test_current_excludes_future` - Future excluded
4. `test_as_of_returns_valid_at_time` - Historical query
5. `test_expired_returns_only_expired` - Expired filter
6. `test_future_returns_only_future` - Future filter

### RBACUserMixin Tests (6 tests)
1. `test_get_roles_returns_direct_roles` - Direct assignments
2. `test_get_roles_includes_inherited` - Hierarchy included
3. `test_has_role_by_instance` - Check by Role object
4. `test_has_role_by_slug` - Check by slug string
5. `test_assign_role_creates_assignment` - Assignment creation
6. `test_revoke_role_sets_valid_to` - Revocation works

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'Role',
    'UserRole',
    'RBACUserMixin',
    'EffectiveDatedQuerySet',
]

def __getattr__(name):
    if name in ('Role', 'UserRole'):
        from .models import Role, UserRole
        return locals()[name]
    if name == 'RBACUserMixin':
        from .mixins import RBACUserMixin
        return RBACUserMixin
    if name == 'EffectiveDatedQuerySet':
        from .querysets import EffectiveDatedQuerySet
        return EffectiveDatedQuerySet
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **Effective Dating**: valid_from/valid_to for temporal role assignments
2. **Role Hierarchy**: Parent/child relationships with inheritance
3. **Unique Active Constraint**: Only one active assignment per user+role
4. **Query Methods**: current(), as_of(), expired(), future()
5. **User Mixin**: get_roles(), has_role(), assign_role(), revoke_role()

## Usage Examples

```python
from django_rbac import Role, UserRole, RBACUserMixin
from django.contrib.auth.models import AbstractUser

# User model with RBAC
class User(AbstractUser, RBACUserMixin):
    pass

# Create role hierarchy
admin_role = Role.objects.create(name='Admin', slug='admin', priority=100)
editor_role = Role.objects.create(
    name='Editor', slug='editor', priority=50, parent=admin_role
)
viewer_role = Role.objects.create(
    name='Viewer', slug='viewer', priority=10, parent=editor_role
)

# Assign role to user
user.assign_role(editor_role, assigned_by=admin_user, reason='Promoted')

# Check roles
user.has_role('editor')  # True
user.has_role('viewer')  # True (inherited from editor)
user.has_role('admin')   # False (editor doesn't inherit admin)

# Get all roles
roles = user.get_roles()  # {editor_role, viewer_role}

# Revoke role
user.revoke_role(editor_role, reason='Left project')

# Query historical assignments
UserRole.objects.filter(user=user).as_of(some_past_date)
```

## Acceptance Criteria

- [ ] Role model with hierarchy support
- [ ] UserRole model with effective dating
- [ ] EffectiveDatedQuerySet with temporal methods
- [ ] RBACUserMixin with role checking methods
- [ ] Unique active assignment constraint
- [ ] All 30 tests passing
- [ ] README with usage examples
