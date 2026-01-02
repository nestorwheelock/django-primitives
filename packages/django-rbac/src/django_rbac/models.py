"""
Django RBAC models - Role-based access control with hierarchy enforcement.

This module provides:
- Role: Custom roles with hierarchy levels (10-100)
- UserRole: Links users to roles with assignment tracking

Key Design Principle (CONTRACT Rule 2):
- Users can only manage users with LOWER hierarchy levels
- No escalation via convenience flags
- All escalation requires explicit role assignment
- No "is_superuser" shortcuts that bypass hierarchy

Hierarchy levels:
| Level | Role | Description |
|-------|------|-------------|
| 100 | Superuser | System admin |
| 80 | Administrator | Full system access |
| 60 | Manager | Team leads |
| 40 | Professional | Licensed professionals |
| 30 | Technician | Support staff |
| 20 | Staff | Front desk |
| 10 | Customer | End users |
"""

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_basemodels import BaseModel
from django_decisioning.querysets import EffectiveDatedQuerySet


class Role(BaseModel):
    """Custom role with configurable permissions and hierarchy.

    Each Role is linked to a Django Group for permission management.
    The hierarchy_level determines what other users this role can manage.

    Examples:
        # Create a manager role
        group = Group.objects.create(name='Practice Manager')
        role = Role.objects.create(
            name='Practice Manager',
            slug='practice-manager',
            hierarchy_level=60,
            group=group,
        )

        # Add permissions via the linked group
        role.group.permissions.add(practice_view_permission)
    """

    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    hierarchy_level = models.IntegerField(
        _('hierarchy level'),
        default=20,
        help_text=_('Higher number = more authority (10-100). Users can only manage users with LOWER levels.')
    )
    is_active = models.BooleanField(_('active'), default=True)

    # Link to Django's built-in Group for permissions
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='rbac_role',
        verbose_name=_('group'),
        help_text=_('Django Group for permission management'),
    )

    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        ordering = ['-hierarchy_level', 'name']

    def __str__(self):
        return self.name


class UserRole(BaseModel):
    """Links users to roles with assignment tracking and effective dating.

    This is the many-to-many relationship between User and Role,
    with additional metadata like who assigned the role and when.

    Effective dating allows:
    - valid_from: When this role assignment becomes effective
    - valid_to: When this role assignment expires (null = indefinite)

    This enables:
    - Role revocation by setting valid_to
    - Historical queries: UserRole.objects.as_of(some_past_date)
    - Current roles only: UserRole.objects.current()
    - Multiple historical assignments of the same role to same user

    Examples:
        # Assign a role to a user (currently effective)
        UserRole.objects.create(
            user=staff_member,
            role=staff_role,
            assigned_by=manager,
            is_primary=True,
        )

        # Get only currently valid roles for a user
        current_roles = UserRole.objects.current().filter(user=user)

        # Get roles valid at a specific point in time
        roles_then = UserRole.objects.as_of(some_date).filter(user=user)

        # Revoke a role by setting valid_to
        user_role.valid_to = timezone.now()
        user_role.save()
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_roles',
        verbose_name=_('user'),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles',
        verbose_name=_('role'),
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_assigned',
        verbose_name=_('assigned by'),
        help_text=_('User who assigned this role'),
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(
        _('is primary'),
        default=False,
        help_text=_("User's main role for display purposes"),
    )

    valid_from = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_('When this role assignment becomes effective'),
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this role assignment expires (null = indefinite)'),
    )

    objects = EffectiveDatedQuerySet.as_manager()

    class Meta:
        verbose_name = _('user role')
        verbose_name_plural = _('user roles')
        ordering = ['-assigned_at']

    def __str__(self):
        return f'{self.user} - {self.role}'
