"""Tests for django-rbac decorators and view mixins."""

import pytest
from django.test import RequestFactory
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import Group, Permission, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse

from django_rbac.models import Role, UserRole
from django_rbac.decorators import require_permission, requires_hierarchy_level


@pytest.fixture
def rf():
    """Request factory fixture."""
    return RequestFactory()


@pytest.mark.django_db
class TestRequirePermissionDecorator:
    """Tests for @require_permission decorator."""

    def test_allows_user_with_permission(self, rf):
        """User with required permission can access view."""
        from tests.models import User

        @require_permission('practice', 'view')
        def protected_view(request):
            return HttpResponse('OK')

        # Create user with permission
        user = User.objects.create_user(username='permuser', password='pass')
        group = Group.objects.create(name='PracticeViewers')
        content_type = ContentType.objects.get_for_model(User)
        perm, _ = Permission.objects.get_or_create(
            codename='practice.view',
            defaults={'name': 'Can view practice', 'content_type': content_type}
        )
        group.permissions.add(perm)
        role = Role.objects.create(name='PracticeViewer', slug='practice-viewer', group=group)
        UserRole.objects.create(user=user, role=role)

        request = rf.get('/protected/')
        request.user = user

        response = protected_view(request)
        assert response.status_code == 200

    def test_denies_user_without_permission(self, rf):
        """User without required permission is denied."""
        from tests.models import User

        @require_permission('practice', 'manage')
        def protected_view(request):
            return HttpResponse('OK')

        user = User.objects.create_user(username='noperm', password='pass')
        request = rf.get('/protected/')
        request.user = user

        with pytest.raises(PermissionDenied):
            protected_view(request)

    def test_denies_anonymous_user(self, rf):
        """Anonymous user is denied."""
        @require_permission('practice', 'view')
        def protected_view(request):
            return HttpResponse('OK')

        request = rf.get('/protected/')
        request.user = AnonymousUser()

        with pytest.raises(PermissionDenied):
            protected_view(request)

    def test_superuser_always_allowed(self, rf):
        """Superuser can access any protected view."""
        from tests.models import User

        @require_permission('anything', 'any_action')
        def protected_view(request):
            return HttpResponse('OK')

        superuser = User.objects.create_superuser(
            username='super', email='super@test.com', password='pass'
        )
        request = rf.get('/protected/')
        request.user = superuser

        response = protected_view(request)
        assert response.status_code == 200


@pytest.mark.django_db
class TestRequiresHierarchyLevelDecorator:
    """Tests for @requires_hierarchy_level decorator."""

    def test_allows_user_with_sufficient_level(self, rf):
        """User with sufficient hierarchy level can access view."""
        from tests.models import User

        @requires_hierarchy_level(60)
        def manager_view(request):
            return HttpResponse('OK')

        user = User.objects.create_user(username='manager', password='pass')
        group = Group.objects.create(name='Managers')
        role = Role.objects.create(
            name='Manager', slug='manager', hierarchy_level=60, group=group
        )
        UserRole.objects.create(user=user, role=role)

        request = rf.get('/manager/')
        request.user = user

        response = manager_view(request)
        assert response.status_code == 200

    def test_denies_user_with_insufficient_level(self, rf):
        """User with insufficient hierarchy level is denied."""
        from tests.models import User

        @requires_hierarchy_level(60)
        def manager_view(request):
            return HttpResponse('OK')

        user = User.objects.create_user(username='staff', password='pass')
        group = Group.objects.create(name='Staff')
        role = Role.objects.create(
            name='Staff', slug='staff', hierarchy_level=20, group=group
        )
        UserRole.objects.create(user=user, role=role)

        request = rf.get('/manager/')
        request.user = user

        with pytest.raises(PermissionDenied):
            manager_view(request)

    def test_superuser_always_allowed(self, rf):
        """Superuser (level 100) can access any level view."""
        from tests.models import User

        @requires_hierarchy_level(99)
        def admin_view(request):
            return HttpResponse('OK')

        superuser = User.objects.create_superuser(
            username='super2', email='super2@test.com', password='pass'
        )
        request = rf.get('/admin/')
        request.user = superuser

        response = admin_view(request)
        assert response.status_code == 200

    def test_user_without_roles_denied(self, rf):
        """User without any roles (level 0) is denied."""
        from tests.models import User

        @requires_hierarchy_level(10)  # Minimum level
        def customer_view(request):
            return HttpResponse('OK')

        user = User.objects.create_user(username='noroles', password='pass')
        request = rf.get('/customer/')
        request.user = user

        with pytest.raises(PermissionDenied):
            customer_view(request)
