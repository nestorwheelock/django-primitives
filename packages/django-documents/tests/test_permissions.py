"""Tests for FolderPermission model and permission operations."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError


User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(username="otheruser", password="testpass")


@pytest.mark.django_db
class TestFolderPermissionModel:
    """Tests for FolderPermission model."""

    def test_folder_permission_model_exists(self):
        """FolderPermission model should exist."""
        from django_documents.models import FolderPermission

        assert FolderPermission is not None

    def test_folder_permission_has_required_fields(self):
        """FolderPermission should have all required fields."""
        from django_documents.models import FolderPermission

        field_names = [f.name for f in FolderPermission._meta.get_fields()]
        assert "folder" in field_names
        assert "grantee_content_type" in field_names
        assert "grantee_id" in field_names
        assert "level" in field_names
        assert "inherited" in field_names

    def test_permission_level_choices_exist(self):
        """PermissionLevel choices should exist with correct values."""
        from django_documents.models import PermissionLevel

        assert PermissionLevel.VIEW == 10
        assert PermissionLevel.DOWNLOAD == 20
        assert PermissionLevel.UPLOAD == 30
        assert PermissionLevel.EDIT == 40
        assert PermissionLevel.MANAGE == 50


@pytest.mark.django_db
class TestGrantPermission:
    """Tests for grant_folder_permission service."""

    def test_grant_permission_creates_record(self, user):
        """grant_folder_permission should create a FolderPermission record."""
        from django_documents.models import FolderPermission, PermissionLevel
        from django_documents.services import create_folder, grant_folder_permission

        folder = create_folder(name="Test Folder", actor=None)
        perm = grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.VIEW,
            actor=None,
        )

        assert perm.pk is not None
        assert perm.folder == folder
        assert perm.level == PermissionLevel.VIEW

    def test_grant_permission_default_inherited(self, user):
        """Permissions should be inherited by default."""
        from django_documents.models import PermissionLevel
        from django_documents.services import create_folder, grant_folder_permission

        folder = create_folder(name="Test Folder", actor=None)
        perm = grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.VIEW,
            actor=None,
        )

        assert perm.inherited is True

    def test_grant_permission_non_inherited(self, user):
        """Can grant non-inherited permission."""
        from django_documents.models import PermissionLevel
        from django_documents.services import create_folder, grant_folder_permission

        folder = create_folder(name="Test Folder", actor=None)
        perm = grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.EDIT,
            inherited=False,
            actor=None,
        )

        assert perm.inherited is False

    def test_unique_permission_per_grantee_per_folder(self, user):
        """Only one permission per user per folder allowed."""
        from django_documents.models import PermissionLevel
        from django_documents.services import create_folder, grant_folder_permission

        folder = create_folder(name="Test Folder", actor=None)
        grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.VIEW,
            actor=None,
        )

        # Second grant to same user on same folder should fail
        with pytest.raises(IntegrityError):
            grant_folder_permission(
                folder=folder,
                grantee=user,
                level=PermissionLevel.EDIT,
                actor=None,
            )


@pytest.mark.django_db
class TestCheckPermission:
    """Tests for check_permission service."""

    def test_check_permission_returns_true_when_granted(self, user):
        """check_permission returns True when user has required level."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            check_permission,
        )

        folder = create_folder(name="Test Folder", actor=None)
        grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.EDIT,
            actor=None,
        )

        assert check_permission(user, folder, PermissionLevel.VIEW) is True
        assert check_permission(user, folder, PermissionLevel.DOWNLOAD) is True
        assert check_permission(user, folder, PermissionLevel.UPLOAD) is True
        assert check_permission(user, folder, PermissionLevel.EDIT) is True

    def test_check_permission_returns_false_when_insufficient(self, user):
        """check_permission returns False when user has lower level."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            check_permission,
        )

        folder = create_folder(name="Test Folder", actor=None)
        grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.VIEW,
            actor=None,
        )

        assert check_permission(user, folder, PermissionLevel.VIEW) is True
        assert check_permission(user, folder, PermissionLevel.DOWNLOAD) is False
        assert check_permission(user, folder, PermissionLevel.EDIT) is False

    def test_check_permission_returns_false_when_no_permission(self, user):
        """check_permission returns False when user has no permission."""
        from django_documents.models import PermissionLevel
        from django_documents.services import create_folder, check_permission

        folder = create_folder(name="Test Folder", actor=None)

        assert check_permission(user, folder, PermissionLevel.VIEW) is False

    def test_permission_inheritance_to_child_folder(self, user):
        """Permission on parent folder applies to child folder."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            check_permission,
        )

        parent = create_folder(name="Parent", actor=None)
        child = create_folder(name="Child", parent=parent, actor=None)

        grant_folder_permission(
            folder=parent,
            grantee=user,
            level=PermissionLevel.EDIT,
            inherited=True,
            actor=None,
        )

        # Permission should apply to child
        assert check_permission(user, child, PermissionLevel.EDIT) is True

    def test_non_inherited_permission_does_not_apply_to_child(self, user):
        """Non-inherited permission does not apply to child folder."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            check_permission,
        )

        parent = create_folder(name="Parent", actor=None)
        child = create_folder(name="Child", parent=parent, actor=None)

        grant_folder_permission(
            folder=parent,
            grantee=user,
            level=PermissionLevel.EDIT,
            inherited=False,
            actor=None,
        )

        # Permission should NOT apply to child
        assert check_permission(user, parent, PermissionLevel.EDIT) is True
        assert check_permission(user, child, PermissionLevel.EDIT) is False

    def test_permission_inheritance_through_multiple_levels(self, user):
        """Permission inherits through multiple folder levels."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            check_permission,
        )

        level1 = create_folder(name="Level1", actor=None)
        level2 = create_folder(name="Level2", parent=level1, actor=None)
        level3 = create_folder(name="Level3", parent=level2, actor=None)

        grant_folder_permission(
            folder=level1,
            grantee=user,
            level=PermissionLevel.DOWNLOAD,
            inherited=True,
            actor=None,
        )

        assert check_permission(user, level3, PermissionLevel.DOWNLOAD) is True


@pytest.mark.django_db
class TestGetEffectivePermission:
    """Tests for get_effective_permission service."""

    def test_get_effective_permission_returns_level(self, user):
        """get_effective_permission returns the permission level."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            get_effective_permission,
        )

        folder = create_folder(name="Test Folder", actor=None)
        grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel.EDIT,
            actor=None,
        )

        result = get_effective_permission(user, folder)
        assert result == PermissionLevel.EDIT

    def test_get_effective_permission_returns_none_when_no_permission(self, user):
        """get_effective_permission returns None when no permission."""
        from django_documents.services import create_folder, get_effective_permission

        folder = create_folder(name="Test Folder", actor=None)

        result = get_effective_permission(user, folder)
        assert result is None

    def test_get_effective_permission_returns_highest_from_ancestors(self, user):
        """get_effective_permission returns highest level from all ancestors."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            get_effective_permission,
        )

        parent = create_folder(name="Parent", actor=None)
        child = create_folder(name="Child", parent=parent, actor=None)

        # Grant VIEW on parent, EDIT on child
        grant_folder_permission(
            folder=parent,
            grantee=user,
            level=PermissionLevel.VIEW,
            inherited=True,
            actor=None,
        )
        grant_folder_permission(
            folder=child,
            grantee=user,
            level=PermissionLevel.EDIT,
            actor=None,
        )

        # Should return highest (EDIT)
        result = get_effective_permission(user, child)
        assert result == PermissionLevel.EDIT


@pytest.mark.django_db
class TestGetAccessibleFolders:
    """Tests for get_accessible_folders service."""

    def test_get_accessible_folders_returns_permitted_folders(self, user):
        """get_accessible_folders returns folders user can access."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            get_accessible_folders,
        )

        folder1 = create_folder(name="Folder1", actor=None)
        folder2 = create_folder(name="Folder2", actor=None)
        create_folder(name="Folder3", actor=None)  # No permission

        grant_folder_permission(
            folder=folder1,
            grantee=user,
            level=PermissionLevel.VIEW,
            actor=None,
        )
        grant_folder_permission(
            folder=folder2,
            grantee=user,
            level=PermissionLevel.EDIT,
            actor=None,
        )

        accessible = get_accessible_folders(user)
        assert folder1 in accessible
        assert folder2 in accessible
        assert accessible.count() == 2

    def test_get_accessible_folders_respects_minimum_level(self, user):
        """get_accessible_folders filters by minimum permission level."""
        from django_documents.models import PermissionLevel
        from django_documents.services import (
            create_folder,
            grant_folder_permission,
            get_accessible_folders,
        )

        folder1 = create_folder(name="Folder1", actor=None)
        folder2 = create_folder(name="Folder2", actor=None)

        grant_folder_permission(
            folder=folder1,
            grantee=user,
            level=PermissionLevel.VIEW,
            actor=None,
        )
        grant_folder_permission(
            folder=folder2,
            grantee=user,
            level=PermissionLevel.EDIT,
            actor=None,
        )

        # Only folder2 has EDIT level
        accessible = get_accessible_folders(user, min_level=PermissionLevel.EDIT)
        assert folder2 in accessible
        assert folder1 not in accessible
        assert accessible.count() == 1

    def test_get_accessible_folders_returns_empty_when_no_permission(self, user):
        """get_accessible_folders returns empty queryset when no permissions."""
        from django_documents.services import create_folder, get_accessible_folders

        create_folder(name="Folder1", actor=None)
        create_folder(name="Folder2", actor=None)

        accessible = get_accessible_folders(user)
        assert accessible.count() == 0
