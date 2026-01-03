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
class TestRoleHierarchyLevelConstraint:
    """Tests for hierarchy_level range constraint (10-100).

    The Role model docstring says: "Higher number = more authority (10-100)"
    This is enforced by a CheckConstraint.
    """

    def test_cannot_create_role_with_level_below_10(self):
        """Cannot create role with hierarchy_level below 10."""
        from django.db import IntegrityError

        group = Group.objects.create(name='Too Low')
        with pytest.raises(IntegrityError):
            Role.objects.create(
                name='Too Low',
                slug='too-low',
                hierarchy_level=5,
                group=group,
            )

    def test_cannot_create_role_with_level_above_100(self):
        """Cannot create role with hierarchy_level above 100."""
        from django.db import IntegrityError

        group = Group.objects.create(name='Too High')
        with pytest.raises(IntegrityError):
            Role.objects.create(
                name='Too High',
                slug='too-high',
                hierarchy_level=101,
                group=group,
            )

    def test_can_create_role_at_minimum_level(self):
        """Can create role at minimum hierarchy_level (10)."""
        group = Group.objects.create(name='Min Level')
        role = Role.objects.create(
            name='Min Level',
            slug='min-level',
            hierarchy_level=10,
            group=group,
        )
        assert role.hierarchy_level == 10

    def test_can_create_role_at_maximum_level(self):
        """Can create role at maximum hierarchy_level (100)."""
        group = Group.objects.create(name='Max Level')
        role = Role.objects.create(
            name='Max Level',
            slug='max-level',
            hierarchy_level=100,
            group=group,
        )
        assert role.hierarchy_level == 100

    def test_can_create_role_at_mid_level(self):
        """Can create role at valid mid-range hierarchy_level."""
        group = Group.objects.create(name='Mid Level')
        role = Role.objects.create(
            name='Mid Level',
            slug='mid-level',
            hierarchy_level=50,
            group=group,
        )
        assert role.hierarchy_level == 50


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

    def test_user_role_allows_historical_assignments(self):
        """Same user can have same role multiple times with different validity periods."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='multi', password='pass')
        group = Group.objects.create(name='Multi Role')
        role = Role.objects.create(name='Multi Role', slug='multi-role', group=group)

        now = timezone.now()
        past = now - datetime.timedelta(days=30)
        mid = now - datetime.timedelta(days=15)

        # First assignment: historical (expired)
        UserRole.objects.create(user=user, role=role, valid_from=past, valid_to=mid)

        # Second assignment: current
        UserRole.objects.create(user=user, role=role, valid_from=now)

        # Both assignments exist
        all_assignments = UserRole.objects.filter(user=user, role=role)
        assert all_assignments.count() == 2

        # Only one is current
        current_assignments = UserRole.objects.current().filter(user=user, role=role)
        assert current_assignments.count() == 1


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


@pytest.mark.django_db
class TestUserRoleEffectiveDating:
    """Tests for UserRole effective dating (valid_from/valid_to)."""

    def test_userrole_has_valid_from_field(self):
        """UserRole should have valid_from field."""
        from tests.models import User

        user = User.objects.create_user(username='validfrom', password='pass')
        group = Group.objects.create(name='ValidFrom Role')
        role = Role.objects.create(name='ValidFrom Role', slug='validfrom-role', group=group)

        user_role = UserRole.objects.create(user=user, role=role)

        assert hasattr(user_role, 'valid_from')
        assert user_role.valid_from is not None

    def test_userrole_has_valid_to_nullable(self):
        """UserRole should have nullable valid_to field."""
        from tests.models import User

        user = User.objects.create_user(username='validto', password='pass')
        group = Group.objects.create(name='ValidTo Role')
        role = Role.objects.create(name='ValidTo Role', slug='validto-role', group=group)

        user_role = UserRole.objects.create(user=user, role=role)

        assert hasattr(user_role, 'valid_to')
        assert user_role.valid_to is None  # Defaults to null (indefinite)

    def test_userrole_valid_from_defaults_to_now(self):
        """UserRole valid_from should default to now."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='defaultnow', password='pass')
        group = Group.objects.create(name='DefaultNow Role')
        role = Role.objects.create(name='DefaultNow Role', slug='defaultnow-role', group=group)

        before = timezone.now()
        user_role = UserRole.objects.create(user=user, role=role)
        after = timezone.now()

        assert user_role.valid_from >= before
        assert user_role.valid_from <= after

    def test_current_returns_only_active_roles(self):
        """UserRole.objects.current() returns only currently valid roles."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='current', password='pass')
        group1 = Group.objects.create(name='Current Role')
        group2 = Group.objects.create(name='Expired Role')
        role1 = Role.objects.create(name='Current Role', slug='current-role', group=group1)
        role2 = Role.objects.create(name='Expired Role', slug='expired-role', group=group2)

        # Active role (no end date)
        UserRole.objects.create(user=user, role=role1)

        # Expired role (valid_to in the past, valid_from before that)
        past = timezone.now() - datetime.timedelta(days=1)
        earlier = timezone.now() - datetime.timedelta(days=30)
        UserRole.objects.create(user=user, role=role2, valid_from=earlier, valid_to=past)

        current_roles = UserRole.objects.current().filter(user=user)
        assert current_roles.count() == 1
        assert current_roles.first().role == role1

    def test_as_of_returns_roles_valid_at_timestamp(self):
        """UserRole.objects.as_of(timestamp) returns roles valid at that time."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='asof', password='pass')
        group1 = Group.objects.create(name='Old Role')
        group2 = Group.objects.create(name='New Role')
        role1 = Role.objects.create(name='Old Role', slug='old-role', group=group1)
        role2 = Role.objects.create(name='New Role', slug='new-role', group=group2)

        now = timezone.now()
        past = now - datetime.timedelta(days=30)
        mid = now - datetime.timedelta(days=15)

        # Old role: valid from 30 days ago, ended 15 days ago
        UserRole.objects.create(user=user, role=role1, valid_from=past, valid_to=mid)

        # New role: started 15 days ago, still active
        UserRole.objects.create(user=user, role=role2, valid_from=mid)

        # Query as of 20 days ago (should only see old role)
        twenty_days_ago = now - datetime.timedelta(days=20)
        roles_then = UserRole.objects.as_of(twenty_days_ago).filter(user=user)
        assert roles_then.count() == 1
        assert roles_then.first().role == role1

        # Query as of now (should only see new role)
        roles_now = UserRole.objects.as_of(now).filter(user=user)
        assert roles_now.count() == 1
        assert roles_now.first().role == role2

    def test_expired_role_excluded_from_current(self):
        """Roles with valid_to in the past are excluded from current()."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='expired', password='pass')
        group = Group.objects.create(name='Expired Test')
        role = Role.objects.create(name='Expired Test', slug='expired-test', group=group)

        past = timezone.now() - datetime.timedelta(days=1)
        earlier = timezone.now() - datetime.timedelta(days=30)
        UserRole.objects.create(user=user, role=role, valid_from=earlier, valid_to=past)

        current_roles = UserRole.objects.current().filter(user=user)
        assert current_roles.count() == 0

    def test_future_role_excluded_from_current(self):
        """Roles with valid_from in the future are excluded from current()."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='future', password='pass')
        group = Group.objects.create(name='Future Test')
        role = Role.objects.create(name='Future Test', slug='future-test', group=group)

        future = timezone.now() + datetime.timedelta(days=1)
        UserRole.objects.create(user=user, role=role, valid_from=future)

        current_roles = UserRole.objects.current().filter(user=user)
        assert current_roles.count() == 0

    def test_can_have_multiple_historical_assignments(self):
        """User can have same role multiple times in history (different validity periods)."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='history', password='pass')
        group = Group.objects.create(name='History Role')
        role = Role.objects.create(name='History Role', slug='history-role', group=group)

        now = timezone.now()
        past = now - datetime.timedelta(days=60)
        mid = now - datetime.timedelta(days=30)

        # First assignment: 60-30 days ago
        UserRole.objects.create(user=user, role=role, valid_from=past, valid_to=mid)

        # Second assignment: from now (currently active)
        UserRole.objects.create(user=user, role=role, valid_from=now)

        # All assignments for this user+role
        all_roles = UserRole.objects.filter(user=user, role=role)
        assert all_roles.count() == 2

        # Only one is current
        current_roles = UserRole.objects.current().filter(user=user, role=role)
        assert current_roles.count() == 1

    def test_user_hierarchy_level_uses_current_roles(self):
        """User hierarchy_level only considers currently valid roles."""
        from tests.models import User
        from django.utils import timezone
        import datetime

        user = User.objects.create_user(username='levelcurrent', password='pass')
        group1 = Group.objects.create(name='Manager Expired')
        group2 = Group.objects.create(name='Staff Current')
        manager_role = Role.objects.create(name='Manager Expired', slug='manager-expired', hierarchy_level=60, group=group1)
        staff_role = Role.objects.create(name='Staff Current', slug='staff-current', hierarchy_level=20, group=group2)

        past = timezone.now() - datetime.timedelta(days=1)
        earlier = timezone.now() - datetime.timedelta(days=30)

        # Manager role expired yesterday (was valid from 30 days ago)
        UserRole.objects.create(user=user, role=manager_role, valid_from=earlier, valid_to=past)

        # Staff role is current
        UserRole.objects.create(user=user, role=staff_role)

        # User's level should be 20 (staff), not 60 (expired manager)
        assert user.hierarchy_level == 20


@pytest.mark.django_db
class TestUserRoleSoftDelete:
    """Tests for UserRole soft delete combined with effective dating."""

    def test_deleted_userrole_excluded_from_objects(self):
        """Soft-deleted UserRole is excluded from objects.all()."""
        from tests.models import User

        user = User.objects.create_user(username='softdel', password='pass')
        group = Group.objects.create(name='SoftDel Role')
        role = Role.objects.create(name='SoftDel Role', slug='softdel-role', group=group)

        user_role = UserRole.objects.create(user=user, role=role)
        assert UserRole.objects.filter(user=user).count() == 1

        # Soft delete
        user_role.delete()

        # Should be excluded from default queryset
        assert UserRole.objects.filter(user=user).count() == 0

    def test_deleted_userrole_excluded_from_current(self):
        """Soft-deleted UserRole is excluded from current()."""
        from tests.models import User

        user = User.objects.create_user(username='softdelcurr', password='pass')
        group = Group.objects.create(name='SoftDelCurr Role')
        role = Role.objects.create(name='SoftDelCurr Role', slug='softdelcurr-role', group=group)

        user_role = UserRole.objects.create(user=user, role=role)
        assert UserRole.objects.current().filter(user=user).count() == 1

        # Soft delete
        user_role.delete()

        # Should be excluded from current()
        assert UserRole.objects.current().filter(user=user).count() == 0

    def test_deleted_userrole_accessible_via_all_objects(self):
        """Soft-deleted UserRole is accessible via all_objects."""
        from tests.models import User

        user = User.objects.create_user(username='allobj', password='pass')
        group = Group.objects.create(name='AllObj Role')
        role = Role.objects.create(name='AllObj Role', slug='allobj-role', group=group)

        user_role = UserRole.objects.create(user=user, role=role)
        user_role.delete()

        # all_objects should include deleted
        assert UserRole.all_objects.filter(user=user).count() == 1
        assert UserRole.all_objects.filter(user=user).first().is_deleted
