"""Tests for django-rbac models.

=== TDD STOP GATE ===
Task: django-rbac package creation
[x] I have read the CONTRACT.md RBAC requirements
[x] I have read the VetFriendly RBAC implementation
[x] I am writing TESTS FIRST (not implementation)
=== PROCEEDING WITH FAILING TESTS ===
"""

import pytest
import uuid
from django.contrib.auth.models import Group

from django_rbac.models import Role, UserRole


@pytest.mark.django_db
class TestRoleModel:
    """Tests for Role model."""

    def test_create_role(self):
        """Can create a Role with basic fields."""
        group = Group.objects.create(name='Test Staff')
        role = Role.objects.create(
            name='Test Staff',
            slug='test-staff',
            hierarchy_level=20,
            group=group,
        )
        assert role.pk is not None
        assert isinstance(role.pk, uuid.UUID)
        assert role.name == 'Test Staff'
        assert role.hierarchy_level == 20

    def test_role_has_uuid_pk(self):
        """Role should use UUID as primary key."""
        group = Group.objects.create(name='UUID Test')
        role = Role.objects.create(
            name='UUID Test',
            slug='uuid-test',
            group=group,
        )
        assert isinstance(role.id, uuid.UUID)

    def test_role_has_timestamps(self):
        """Role should have created_at and updated_at."""
        group = Group.objects.create(name='Timestamp Test')
        role = Role.objects.create(
            name='Timestamp Test',
            slug='timestamp-test',
            group=group,
        )
        assert role.created_at is not None
        assert role.updated_at is not None

    def test_role_default_hierarchy_level(self):
        """Role defaults to hierarchy level 20."""
        group = Group.objects.create(name='Default Level')
        role = Role.objects.create(
            name='Default Level',
            slug='default-level',
            group=group,
        )
        assert role.hierarchy_level == 20

    def test_role_str_method(self):
        """__str__ returns role name."""
        group = Group.objects.create(name='Str Test')
        role = Role.objects.create(
            name='Str Test',
            slug='str-test',
            group=group,
        )
        assert str(role) == 'Str Test'

    def test_role_slug_is_unique(self):
        """Role slug must be unique."""
        group1 = Group.objects.create(name='Unique Slug 1')
        group2 = Group.objects.create(name='Unique Slug 2')
        Role.objects.create(
            name='Unique Slug 1',
            slug='unique-slug',
            group=group1,
        )
        with pytest.raises(Exception):
            Role.objects.create(
                name='Unique Slug 2',
                slug='unique-slug',  # Same slug should fail
                group=group2,
            )

    def test_role_soft_delete(self):
        """Role soft delete sets deleted_at."""
        group = Group.objects.create(name='Soft Delete')
        role = Role.objects.create(
            name='Soft Delete',
            slug='soft-delete',
            group=group,
        )
        role.delete()

        assert role.is_deleted is True
        assert Role.objects.filter(pk=role.pk).exists() is False
        assert Role.all_objects.filter(pk=role.pk).exists() is True

    def test_role_ordering_by_hierarchy(self):
        """Roles are ordered by hierarchy level descending."""
        group1 = Group.objects.create(name='Low')
        group2 = Group.objects.create(name='High')
        Role.objects.create(name='Low', slug='low', hierarchy_level=20, group=group1)
        Role.objects.create(name='High', slug='high', hierarchy_level=80, group=group2)

        roles = list(Role.objects.all())
        assert roles[0].hierarchy_level > roles[1].hierarchy_level


@pytest.mark.django_db
class TestUserRoleModel:
    """Tests for UserRole model."""

    def test_create_user_role(self):
        """Can create a UserRole linking user and role."""
        from tests.models import User

        user = User.objects.create_user(username='testuser', password='pass')
        group = Group.objects.create(name='Test Role')
        role = Role.objects.create(
            name='Test Role',
            slug='test-role',
            group=group,
        )

        user_role = UserRole.objects.create(
            user=user,
            role=role,
            is_primary=True,
        )

        assert user_role.pk is not None
        assert user_role.user == user
        assert user_role.role == role
        assert user_role.is_primary is True

    def test_user_role_has_timestamps(self):
        """UserRole should have assigned_at timestamp."""
        from tests.models import User

        user = User.objects.create_user(username='timestamp', password='pass')
        group = Group.objects.create(name='Timestamp Role')
        role = Role.objects.create(name='Timestamp Role', slug='timestamp-role', group=group)

        user_role = UserRole.objects.create(user=user, role=role)

        assert user_role.assigned_at is not None

    def test_user_role_tracks_assigned_by(self):
        """UserRole can track who assigned the role."""
        from tests.models import User

        admin = User.objects.create_user(username='admin', password='pass')
        user = User.objects.create_user(username='user', password='pass')
        group = Group.objects.create(name='Assigned Role')
        role = Role.objects.create(name='Assigned Role', slug='assigned-role', group=group)

        user_role = UserRole.objects.create(
            user=user,
            role=role,
            assigned_by=admin,
        )

        assert user_role.assigned_by == admin

    def test_user_role_unique_together(self):
        """Same user cannot have same role twice."""
        from tests.models import User

        user = User.objects.create_user(username='unique', password='pass')
        group = Group.objects.create(name='Unique Role')
        role = Role.objects.create(name='Unique Role', slug='unique-role', group=group)

        UserRole.objects.create(user=user, role=role)
        with pytest.raises(Exception):
            UserRole.objects.create(user=user, role=role)


@pytest.mark.django_db
class TestRBACUserMixin:
    """Tests for RBACUserMixin on User model."""

    def test_user_hierarchy_level_from_roles(self):
        """User hierarchy level comes from highest role."""
        from tests.models import User

        user = User.objects.create_user(username='hierarchy', password='pass')
        group1 = Group.objects.create(name='Low Role')
        group2 = Group.objects.create(name='High Role')
        role1 = Role.objects.create(name='Low Role', slug='low-role', hierarchy_level=20, group=group1)
        role2 = Role.objects.create(name='High Role', slug='high-role', hierarchy_level=60, group=group2)

        UserRole.objects.create(user=user, role=role1)
        UserRole.objects.create(user=user, role=role2)

        assert user.hierarchy_level == 60

    def test_user_without_roles_has_level_zero(self):
        """User without any roles has hierarchy level 0."""
        from tests.models import User

        user = User.objects.create_user(username='noroles', password='pass')
        assert user.hierarchy_level == 0

    def test_superuser_has_level_100(self):
        """Superuser always has hierarchy level 100."""
        from tests.models import User

        superuser = User.objects.create_superuser(
            username='super', email='super@test.com', password='pass'
        )
        assert superuser.hierarchy_level == 100

    def test_manager_can_manage_staff(self):
        """Manager (level 60) can manage staff (level 20)."""
        from tests.models import User

        staff = User.objects.create_user(username='staff', password='pass')
        manager = User.objects.create_user(username='manager', password='pass')

        staff_group = Group.objects.create(name='Staff')
        manager_group = Group.objects.create(name='Manager')
        staff_role = Role.objects.create(name='Staff', slug='staff', hierarchy_level=20, group=staff_group)
        manager_role = Role.objects.create(name='Manager', slug='manager', hierarchy_level=60, group=manager_group)

        UserRole.objects.create(user=staff, role=staff_role)
        UserRole.objects.create(user=manager, role=manager_role)

        assert manager.can_manage_user(staff) is True

    def test_staff_cannot_manage_manager(self):
        """Staff (level 20) cannot manage manager (level 60)."""
        from tests.models import User

        staff = User.objects.create_user(username='staff2', password='pass')
        manager = User.objects.create_user(username='manager2', password='pass')

        staff_group = Group.objects.create(name='Staff2')
        manager_group = Group.objects.create(name='Manager2')
        staff_role = Role.objects.create(name='Staff2', slug='staff2', hierarchy_level=20, group=staff_group)
        manager_role = Role.objects.create(name='Manager2', slug='manager2', hierarchy_level=60, group=manager_group)

        UserRole.objects.create(user=staff, role=staff_role)
        UserRole.objects.create(user=manager, role=manager_role)

        assert staff.can_manage_user(manager) is False

    def test_same_level_cannot_manage_each_other(self):
        """Users at same hierarchy level cannot manage each other."""
        from tests.models import User

        user1 = User.objects.create_user(username='peer1', password='pass')
        user2 = User.objects.create_user(username='peer2', password='pass')

        group = Group.objects.create(name='Peer')
        role = Role.objects.create(name='Peer', slug='peer', hierarchy_level=40, group=group)

        UserRole.objects.create(user=user1, role=role)
        UserRole.objects.create(user=user2, role=role)

        assert user1.can_manage_user(user2) is False
        assert user2.can_manage_user(user1) is False

    def test_get_manageable_roles(self):
        """get_manageable_roles returns roles below user's level."""
        from tests.models import User

        manager = User.objects.create_user(username='mgr', password='pass')

        staff_group = Group.objects.create(name='StaffG')
        manager_group = Group.objects.create(name='MgrG')
        admin_group = Group.objects.create(name='AdminG')

        staff_role = Role.objects.create(name='StaffG', slug='staff-g', hierarchy_level=20, group=staff_group)
        manager_role = Role.objects.create(name='MgrG', slug='mgr-g', hierarchy_level=60, group=manager_group)
        admin_role = Role.objects.create(name='AdminG', slug='admin-g', hierarchy_level=80, group=admin_group)

        UserRole.objects.create(user=manager, role=manager_role)

        manageable = list(manager.get_manageable_roles())
        slugs = [r.slug for r in manageable]

        assert 'staff-g' in slugs  # Below 60
        assert 'mgr-g' not in slugs  # Same level
        assert 'admin-g' not in slugs  # Above 60

    def test_has_module_permission_superuser(self):
        """Superuser has all module permissions."""
        from tests.models import User

        superuser = User.objects.create_superuser(
            username='superperm', email='superperm@test.com', password='pass'
        )
        assert superuser.has_module_permission('anything', 'any_action') is True

    def test_has_module_permission_via_role(self):
        """User gets permissions from role's group."""
        from tests.models import User
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        user = User.objects.create_user(username='permuser', password='pass')

        # Create group with permission
        group = Group.objects.create(name='PermGroup')
        content_type = ContentType.objects.get_for_model(User)
        perm, _ = Permission.objects.get_or_create(
            codename='practice.view',
            defaults={'name': 'Can view practice', 'content_type': content_type}
        )
        group.permissions.add(perm)

        role = Role.objects.create(name='PermRole', slug='perm-role', group=group)
        UserRole.objects.create(user=user, role=role)

        assert user.has_module_permission('practice', 'view') is True
        assert user.has_module_permission('practice', 'manage') is False

    def test_user_without_permission(self):
        """User without permission returns False."""
        from tests.models import User

        user = User.objects.create_user(username='noperm', password='pass')
        assert user.has_module_permission('anything', 'any') is False
