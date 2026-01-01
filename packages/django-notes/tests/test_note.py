"""Tests for Note model."""
import pytest
from django.contrib.auth import get_user_model

from django_notes.models import Note
from tests.models import Organization, Project, Task


User = get_user_model()


@pytest.mark.django_db
class TestNoteModel:
    """Test suite for Note model."""

    @pytest.fixture
    def org(self):
        """Create a test organization."""
        return Organization.objects.create(name="Test Org")

    @pytest.fixture
    def project(self, org):
        """Create a test project."""
        return Project.objects.create(name="Test Project", org=org)

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    def test_note_has_target_generic_fk(self, project, user):
        """Note should have target via GenericFK."""
        note = Note.objects.create(
            target=project,
            content="This is a note",
            author=user,
        )
        assert note.target == project

    def test_note_target_id_is_charfield(self, project, user):
        """Note target_id should be CharField (UUID support)."""
        note = Note.objects.create(
            target=project,
            content="This is a note",
            author=user,
        )
        assert isinstance(note.target_id, str)
        assert note.target_id == str(project.pk)

    def test_note_has_content_field(self, project, user):
        """Note should have content text field."""
        note = Note.objects.create(
            target=project,
            content="This is the note content with details.",
            author=user,
        )
        assert note.content == "This is the note content with details."

    def test_note_has_author_fk(self, project, user):
        """Note should have author ForeignKey to User."""
        note = Note.objects.create(
            target=project,
            content="Note content",
            author=user,
        )
        assert note.author == user

    def test_note_author_is_nullable(self, project):
        """Note author should be nullable for system-generated notes."""
        note = Note.objects.create(
            target=project,
            content="System-generated note",
            author=None,
        )
        assert note.author is None

    def test_note_has_visibility_field(self, project, user):
        """Note should have visibility field."""
        note = Note.objects.create(
            target=project,
            content="Note content",
            author=user,
            visibility='internal',
        )
        assert note.visibility == 'internal'

    def test_note_visibility_defaults_to_internal(self, project, user):
        """Note visibility should default to 'internal'."""
        note = Note.objects.create(
            target=project,
            content="Note content",
            author=user,
        )
        assert note.visibility == 'internal'

    def test_note_visibility_choices(self, project, user):
        """Note should support public, internal, and private visibility."""
        for visibility in ['public', 'internal', 'private']:
            note = Note.objects.create(
                target=project,
                content=f"Note with {visibility} visibility",
                author=user,
                visibility=visibility,
            )
            assert note.visibility == visibility

    def test_note_has_timestamps(self, project, user):
        """Note should have created_at and updated_at."""
        note = Note.objects.create(
            target=project,
            content="Note content",
            author=user,
        )
        assert note.created_at is not None
        assert note.updated_at is not None

    def test_note_has_metadata_json_field(self, project, user):
        """Note should have metadata JSONField."""
        note = Note.objects.create(
            target=project,
            content="Note content",
            author=user,
            metadata={"source": "email", "category": "feedback"},
        )
        assert note.metadata["source"] == "email"
        assert note.metadata["category"] == "feedback"

    def test_note_metadata_defaults_to_empty_dict(self, project, user):
        """Note metadata should default to empty dict."""
        note = Note.objects.create(
            target=project,
            content="Note content",
            author=user,
        )
        assert note.metadata == {}


@pytest.mark.django_db
class TestNoteQuerySet:
    """Test suite for Note queryset methods."""

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

    def test_for_target_returns_notes_for_object(self, project, task, user):
        """for_target() should return notes attached to specific object."""
        note1 = Note.objects.create(target=project, content="Project note 1", author=user)
        note2 = Note.objects.create(target=project, content="Project note 2", author=user)
        note3 = Note.objects.create(target=task, content="Task note", author=user)

        project_notes = Note.objects.for_target(project)
        assert project_notes.count() == 2
        assert note1 in project_notes
        assert note2 in project_notes
        assert note3 not in project_notes

    def test_by_visibility_filters_notes(self, project, user):
        """by_visibility() should filter notes by visibility level."""
        Note.objects.create(target=project, content="Public", author=user, visibility='public')
        Note.objects.create(target=project, content="Internal", author=user, visibility='internal')
        Note.objects.create(target=project, content="Private", author=user, visibility='private')

        public_notes = Note.objects.by_visibility('public')
        assert public_notes.count() == 1

        internal_notes = Note.objects.by_visibility('internal')
        assert internal_notes.count() == 1

        private_notes = Note.objects.by_visibility('private')
        assert private_notes.count() == 1

    def test_public_queryset_method(self, project, user):
        """public() should return only public notes."""
        Note.objects.create(target=project, content="Public", author=user, visibility='public')
        Note.objects.create(target=project, content="Internal", author=user, visibility='internal')

        public_notes = Note.objects.public()
        assert public_notes.count() == 1
        assert public_notes.first().visibility == 'public'

    def test_by_author_filters_notes(self, project, user):
        """by_author() should filter notes by author."""
        user2 = User.objects.create_user(username="user2", password="pass")

        note1 = Note.objects.create(target=project, content="User 1 note", author=user)
        note2 = Note.objects.create(target=project, content="User 2 note", author=user2)

        user_notes = Note.objects.by_author(user)
        assert user_notes.count() == 1
        assert note1 in user_notes
        assert note2 not in user_notes
