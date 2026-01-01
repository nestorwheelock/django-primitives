"""Tests for Tag and ObjectTag models."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from django_notes.models import Tag, ObjectTag
from tests.models import Organization, Project, Task


User = get_user_model()


@pytest.mark.django_db
class TestTagModel:
    """Test suite for Tag model."""

    def test_tag_has_name_field(self):
        """Tag should have a name field."""
        tag = Tag.objects.create(name="Urgent", slug="urgent")
        assert tag.name == "Urgent"

    def test_tag_has_slug_field(self):
        """Tag should have a slug field."""
        tag = Tag.objects.create(name="High Priority", slug="high-priority")
        assert tag.slug == "high-priority"

    def test_tag_slug_is_unique(self):
        """Tag slug should be unique."""
        Tag.objects.create(name="Urgent", slug="urgent")
        with pytest.raises(IntegrityError):
            Tag.objects.create(name="Also Urgent", slug="urgent")

    def test_tag_has_color_field(self):
        """Tag should have a color field."""
        tag = Tag.objects.create(name="Error", slug="error", color="#FF0000")
        assert tag.color == "#FF0000"

    def test_tag_color_defaults_to_gray(self):
        """Tag color should default to gray."""
        tag = Tag.objects.create(name="Default", slug="default")
        assert tag.color == "#808080"

    def test_tag_has_description_field(self):
        """Tag should have an optional description."""
        tag = Tag.objects.create(
            name="Urgent",
            slug="urgent",
            description="Items requiring immediate attention",
        )
        assert tag.description == "Items requiring immediate attention"

    def test_tag_description_is_optional(self):
        """Tag description should be optional."""
        tag = Tag.objects.create(name="Simple", slug="simple")
        assert tag.description == ""

    def test_tag_has_timestamps(self):
        """Tag should have created_at and updated_at."""
        tag = Tag.objects.create(name="New", slug="new")
        assert tag.created_at is not None
        assert tag.updated_at is not None

    def test_tag_str_representation(self):
        """Tag __str__ should return name."""
        tag = Tag.objects.create(name="Important", slug="important")
        assert str(tag) == "Important"


@pytest.mark.django_db
class TestObjectTagModel:
    """Test suite for ObjectTag model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def project(self, org):
        """Create a test project."""
        return Project.objects.create(name="Test Project", org=org)

    @pytest.fixture
    def task(self, project):
        """Create a test task."""
        return Task.objects.create(title="Test Task", project=project)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def urgent_tag(self):
        """Create an urgent tag."""
        return Tag.objects.create(name="Urgent", slug="urgent", color="#FF0000")

    @pytest.fixture
    def important_tag(self):
        """Create an important tag."""
        return Tag.objects.create(name="Important", slug="important", color="#FFA500")

    def test_object_tag_has_target_generic_fk(self, project, urgent_tag, user):
        """ObjectTag should have target via GenericFK."""
        obj_tag = ObjectTag.objects.create(
            target=project,
            tag=urgent_tag,
            tagged_by=user,
        )
        assert obj_tag.target == project

    def test_object_tag_target_id_is_charfield(self, project, urgent_tag, user):
        """ObjectTag target_id should be CharField."""
        obj_tag = ObjectTag.objects.create(
            target=project,
            tag=urgent_tag,
            tagged_by=user,
        )
        assert isinstance(obj_tag.target_id, str)

    def test_object_tag_has_tag_fk(self, project, urgent_tag, user):
        """ObjectTag should have tag ForeignKey."""
        obj_tag = ObjectTag.objects.create(
            target=project,
            tag=urgent_tag,
            tagged_by=user,
        )
        assert obj_tag.tag == urgent_tag

    def test_object_tag_has_tagged_by(self, project, urgent_tag, user):
        """ObjectTag should track who tagged it."""
        obj_tag = ObjectTag.objects.create(
            target=project,
            tag=urgent_tag,
            tagged_by=user,
        )
        assert obj_tag.tagged_by == user

    def test_object_tag_tagged_by_is_nullable(self, project, urgent_tag):
        """ObjectTag tagged_by should be nullable."""
        obj_tag = ObjectTag.objects.create(
            target=project,
            tag=urgent_tag,
            tagged_by=None,
        )
        assert obj_tag.tagged_by is None

    def test_object_tag_has_created_at(self, project, urgent_tag, user):
        """ObjectTag should have created_at timestamp."""
        obj_tag = ObjectTag.objects.create(
            target=project,
            tag=urgent_tag,
            tagged_by=user,
        )
        assert obj_tag.created_at is not None

    def test_object_tag_unique_constraint(self, project, urgent_tag, user):
        """Same tag cannot be applied twice to same object."""
        ObjectTag.objects.create(target=project, tag=urgent_tag, tagged_by=user)
        with pytest.raises(IntegrityError):
            ObjectTag.objects.create(target=project, tag=urgent_tag, tagged_by=user)

    def test_different_tags_on_same_object(self, project, urgent_tag, important_tag, user):
        """Different tags can be applied to the same object."""
        obj_tag1 = ObjectTag.objects.create(target=project, tag=urgent_tag, tagged_by=user)
        obj_tag2 = ObjectTag.objects.create(target=project, tag=important_tag, tagged_by=user)

        assert obj_tag1.pk != obj_tag2.pk

    def test_same_tag_on_different_objects(self, project, task, urgent_tag, user):
        """Same tag can be applied to different objects."""
        obj_tag1 = ObjectTag.objects.create(target=project, tag=urgent_tag, tagged_by=user)
        obj_tag2 = ObjectTag.objects.create(target=task, tag=urgent_tag, tagged_by=user)

        assert obj_tag1.pk != obj_tag2.pk


@pytest.mark.django_db
class TestObjectTagQuerySet:
    """Test suite for ObjectTag queryset methods."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def project(self, org):
        """Create a test project."""
        return Project.objects.create(name="Test Project", org=org)

    @pytest.fixture
    def task(self, project):
        """Create a test task."""
        return Task.objects.create(title="Test Task", project=project)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def tags(self):
        """Create multiple tags."""
        return [
            Tag.objects.create(name="Urgent", slug="urgent", color="#FF0000"),
            Tag.objects.create(name="Important", slug="important", color="#FFA500"),
            Tag.objects.create(name="Review", slug="review", color="#0000FF"),
        ]

    def test_for_target_returns_tags_for_object(self, project, task, tags, user):
        """for_target() should return tags for specific object."""
        ObjectTag.objects.create(target=project, tag=tags[0], tagged_by=user)
        ObjectTag.objects.create(target=project, tag=tags[1], tagged_by=user)
        ObjectTag.objects.create(target=task, tag=tags[2], tagged_by=user)

        project_tags = ObjectTag.objects.for_target(project)
        assert project_tags.count() == 2

        task_tags = ObjectTag.objects.for_target(task)
        assert task_tags.count() == 1

    def test_with_tag_filters_by_tag_object(self, project, task, tags, user):
        """with_tag() should filter by tag object."""
        ObjectTag.objects.create(target=project, tag=tags[0], tagged_by=user)
        ObjectTag.objects.create(target=task, tag=tags[0], tagged_by=user)
        ObjectTag.objects.create(target=project, tag=tags[1], tagged_by=user)

        urgent_objects = ObjectTag.objects.with_tag(tags[0])
        assert urgent_objects.count() == 2

        important_objects = ObjectTag.objects.with_tag(tags[1])
        assert important_objects.count() == 1

    def test_with_tag_filters_by_slug(self, project, task, tags, user):
        """with_tag() should filter by tag slug string."""
        ObjectTag.objects.create(target=project, tag=tags[0], tagged_by=user)
        ObjectTag.objects.create(target=task, tag=tags[0], tagged_by=user)

        urgent_objects = ObjectTag.objects.with_tag("urgent")
        assert urgent_objects.count() == 2

    def test_chained_queries(self, project, task, tags, user):
        """Queryset methods should be chainable."""
        ObjectTag.objects.create(target=project, tag=tags[0], tagged_by=user)
        ObjectTag.objects.create(target=project, tag=tags[1], tagged_by=user)
        ObjectTag.objects.create(target=task, tag=tags[0], tagged_by=user)

        # Get urgent tags for project only
        result = ObjectTag.objects.for_target(project).with_tag(tags[0])
        assert result.count() == 1
