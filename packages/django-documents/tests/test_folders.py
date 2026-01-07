"""Tests for DocumentFolder model and folder operations."""

import pytest
from django.db import IntegrityError
from django.utils.text import slugify


@pytest.mark.django_db
class TestDocumentFolderModel:
    """Tests for DocumentFolder model."""

    def test_document_folder_model_exists(self):
        """DocumentFolder model should exist."""
        from django_documents.models import DocumentFolder

        assert DocumentFolder is not None

    def test_document_folder_has_required_fields(self):
        """DocumentFolder should have all required fields."""
        from django_documents.models import DocumentFolder

        field_names = [f.name for f in DocumentFolder._meta.get_fields()]
        assert "name" in field_names
        assert "slug" in field_names
        assert "description" in field_names
        assert "parent" in field_names
        assert "path" in field_names
        assert "depth" in field_names
        assert "owner_content_type" in field_names
        assert "owner_id" in field_names

    def test_create_root_folder(self):
        """Root folder should have depth=0 and path=/<id>/."""
        from django_documents.models import DocumentFolder
        from django_documents.services import create_folder

        folder = create_folder(name="Documents", actor=None)

        assert folder.pk is not None
        assert folder.parent is None
        assert folder.depth == 0
        assert f"/{folder.pk}/" in folder.path

    def test_create_nested_folder(self):
        """Nested folder should have correct depth and path."""
        from django_documents.models import DocumentFolder
        from django_documents.services import create_folder

        root = create_folder(name="Documents", actor=None)
        child = create_folder(name="Invoices", parent=root, actor=None)

        assert child.parent == root
        assert child.depth == 1
        assert str(root.pk) in child.path
        assert str(child.pk) in child.path

    def test_create_deeply_nested_folder(self):
        """Deeply nested folder should accumulate path correctly."""
        from django_documents.services import create_folder

        level1 = create_folder(name="Documents", actor=None)
        level2 = create_folder(name="2024", parent=level1, actor=None)
        level3 = create_folder(name="Q1", parent=level2, actor=None)
        level4 = create_folder(name="Invoices", parent=level3, actor=None)

        assert level4.depth == 3
        assert str(level1.pk) in level4.path
        assert str(level2.pk) in level4.path
        assert str(level3.pk) in level4.path
        assert str(level4.pk) in level4.path

    def test_folder_slug_auto_generated(self):
        """Folder slug should be auto-generated from name if not provided."""
        from django_documents.services import create_folder

        folder = create_folder(name="Marketing Materials", actor=None)

        assert folder.slug == "marketing-materials"

    def test_unique_slug_per_parent(self):
        """Slugs must be unique within the same parent folder."""
        from django_documents.models import DocumentFolder
        from django_documents.services import create_folder

        root = create_folder(name="Documents", actor=None)
        create_folder(name="Invoices", parent=root, actor=None)

        # Same name (slug) under same parent should fail
        with pytest.raises(IntegrityError):
            create_folder(name="Invoices", parent=root, actor=None)

    def test_same_slug_different_parent_allowed(self):
        """Same slug under different parents should be allowed."""
        from django_documents.services import create_folder

        root1 = create_folder(name="Sales", actor=None)
        root2 = create_folder(name="Marketing", actor=None)

        # Same name under different parents - should work
        folder1 = create_folder(name="Invoices", parent=root1, actor=None)
        folder2 = create_folder(name="Invoices", parent=root2, actor=None)

        assert folder1.slug == folder2.slug
        assert folder1.parent != folder2.parent


@pytest.mark.django_db
class TestFolderMove:
    """Tests for folder move operations."""

    def test_move_folder_updates_path(self):
        """Moving folder should update its path."""
        from django_documents.services import create_folder, move_folder

        root1 = create_folder(name="Source", actor=None)
        root2 = create_folder(name="Destination", actor=None)
        child = create_folder(name="Child", parent=root1, actor=None)

        # Move child from root1 to root2
        moved = move_folder(folder=child, new_parent=root2, actor=None)

        assert moved.parent == root2
        assert str(root2.pk) in moved.path
        assert str(root1.pk) not in moved.path

    def test_move_folder_updates_depth(self):
        """Moving folder should update its depth."""
        from django_documents.services import create_folder, move_folder

        root = create_folder(name="Root", actor=None)
        level1 = create_folder(name="Level1", parent=root, actor=None)
        level2 = create_folder(name="Level2", parent=level1, actor=None)

        # Move level2 to root (shallower)
        moved = move_folder(folder=level2, new_parent=root, actor=None)

        assert moved.depth == 1  # Was 2, now 1

    def test_move_folder_updates_descendants(self):
        """Moving folder should update all descendant paths."""
        from django_documents.services import create_folder, move_folder

        root1 = create_folder(name="Source", actor=None)
        root2 = create_folder(name="Destination", actor=None)
        parent = create_folder(name="Parent", parent=root1, actor=None)
        child1 = create_folder(name="Child1", parent=parent, actor=None)
        child2 = create_folder(name="Child2", parent=parent, actor=None)

        # Move parent from root1 to root2
        move_folder(folder=parent, new_parent=root2, actor=None)

        # Refresh children from DB
        child1.refresh_from_db()
        child2.refresh_from_db()

        assert str(root2.pk) in child1.path
        assert str(root1.pk) not in child1.path
        assert str(root2.pk) in child2.path
        assert str(root1.pk) not in child2.path

    def test_move_folder_to_root(self):
        """Moving folder to root (parent=None) should work."""
        from django_documents.services import create_folder, move_folder

        root = create_folder(name="Root", actor=None)
        child = create_folder(name="Child", parent=root, actor=None)

        # Move to root level
        moved = move_folder(folder=child, new_parent=None, actor=None)

        assert moved.parent is None
        assert moved.depth == 0


@pytest.mark.django_db
class TestFolderDelete:
    """Tests for folder delete operations."""

    def test_delete_empty_folder(self):
        """Deleting empty folder should succeed."""
        from django_documents.models import DocumentFolder
        from django_documents.services import create_folder, delete_folder

        folder = create_folder(name="Empty", actor=None)
        folder_id = folder.pk

        delete_folder(folder=folder, actor=None)

        assert not DocumentFolder.objects.filter(pk=folder_id).exists()

    def test_delete_non_empty_folder_fails(self):
        """Deleting folder with children should fail without recursive flag."""
        from django_documents.services import create_folder, delete_folder
        from django_documents.exceptions import FolderNotEmpty

        parent = create_folder(name="Parent", actor=None)
        create_folder(name="Child", parent=parent, actor=None)

        with pytest.raises(FolderNotEmpty):
            delete_folder(folder=parent, actor=None, recursive=False)

    def test_delete_folder_recursive(self):
        """Deleting folder with recursive=True should delete all descendants."""
        from django_documents.models import DocumentFolder
        from django_documents.services import create_folder, delete_folder

        parent = create_folder(name="Parent", actor=None)
        child1 = create_folder(name="Child1", parent=parent, actor=None)
        child2 = create_folder(name="Child2", parent=parent, actor=None)
        grandchild = create_folder(name="Grandchild", parent=child1, actor=None)

        parent_id = parent.pk
        child1_id = child1.pk
        child2_id = child2.pk
        grandchild_id = grandchild.pk

        delete_folder(folder=parent, actor=None, recursive=True)

        assert not DocumentFolder.objects.filter(pk=parent_id).exists()
        assert not DocumentFolder.objects.filter(pk=child1_id).exists()
        assert not DocumentFolder.objects.filter(pk=child2_id).exists()
        assert not DocumentFolder.objects.filter(pk=grandchild_id).exists()


@pytest.mark.django_db
class TestFolderDepthConstraint:
    """Tests for folder depth consistency constraint."""

    def test_root_folder_must_have_depth_zero(self):
        """Root folder (parent=None) must have depth=0."""
        from django_documents.models import DocumentFolder

        # Creating root with wrong depth should fail at DB level
        folder = DocumentFolder(
            name="Root",
            slug="root",
            parent=None,
            depth=1,  # Wrong! Root should be 0
            path="/test/",
        )
        with pytest.raises(IntegrityError):
            folder.save()

    def test_child_folder_must_have_positive_depth(self):
        """Child folder (parent!=None) must have depth>0."""
        from django_documents.models import DocumentFolder
        from django_documents.services import create_folder

        root = create_folder(name="Root", actor=None)

        # Creating child with depth=0 should fail
        child = DocumentFolder(
            name="Child",
            slug="child",
            parent=root,
            depth=0,  # Wrong! Child should have depth > 0
            path=f"/{root.pk}/test/",
        )
        with pytest.raises(IntegrityError):
            child.save()
