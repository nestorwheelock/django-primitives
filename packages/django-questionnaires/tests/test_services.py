"""Tests for django-questionnaires services."""

import json
import pytest
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_questionnaires.models import (
    QuestionnaireDefinition,
    Question,
    QuestionnaireInstance,
    Response,
    DefinitionStatus,
    QuestionType,
    InstanceStatus,
)
from django_questionnaires.services import (
    create_definition,
    publish_definition,
    archive_definition,
    import_definition_from_json,
    create_instance,
    submit_response,
    clear_instance,
    get_current_instance,
    is_instance_valid,
    get_flagged_questions,
)
from django_questionnaires.exceptions import (
    DefinitionNotFoundError,
    DefinitionNotPublishedError,
    DefinitionAlreadyPublishedError,
    InstanceNotFoundError,
    InstanceAlreadyCompletedError,
    InstanceExpiredError,
    MissingRequiredResponseError,
    InstanceNotFlaggedError,
)


User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username="admin", password="adminpass", email="admin@example.com"
    )


@pytest.fixture
def questions_data():
    """Sample questions data for creating definitions."""
    return [
        {
            "sequence": 1,
            "category": "general",
            "question_type": "yes_no",
            "question_text": "Do you have any allergies?",
            "is_required": True,
            "triggers_flag": True,
        },
        {
            "sequence": 2,
            "category": "general",
            "question_type": "text",
            "question_text": "If yes, please describe.",
            "help_text": "List all known allergies.",
            "is_required": False,
            "triggers_flag": False,
        },
        {
            "sequence": 3,
            "category": "metrics",
            "question_type": "number",
            "question_text": "What is your age?",
            "is_required": True,
            "triggers_flag": False,
            "validation_rules": {"min": 1, "max": 120},
        },
    ]


@pytest.fixture
def draft_definition(db, user, questions_data):
    """Create a draft definition using the service."""
    return create_definition(
        slug="test-form",
        name="Test Form",
        description="A test form",
        version="1.0.0",
        questions_data=questions_data,
        actor=user,
    )


@pytest.fixture
def published_definition(db, user, questions_data):
    """Create a published definition."""
    definition = create_definition(
        slug="published-form",
        name="Published Form",
        description="A published form",
        version="1.0.0",
        questions_data=questions_data,
        actor=user,
    )
    return publish_definition(definition, actor=user)


class TestCreateDefinition:
    """Tests for create_definition service."""

    def test_create_definition_basic(self, db, user, questions_data):
        """Test creating a basic definition."""
        definition = create_definition(
            slug="health-check",
            name="Health Check",
            description="Basic health questionnaire",
            version="1.0.0",
            questions_data=questions_data,
            actor=user,
        )

        assert definition.id is not None
        assert definition.slug == "health-check"
        assert definition.name == "Health Check"
        assert definition.version == "1.0.0"
        assert definition.status == DefinitionStatus.DRAFT
        assert definition.questions.count() == 3

    def test_create_definition_with_validity_days(self, db, user, questions_data):
        """Test creating definition with validity period."""
        definition = create_definition(
            slug="annual-check",
            name="Annual Check",
            description="Annual questionnaire",
            version="1.0.0",
            questions_data=questions_data,
            actor=user,
            validity_days=365,
        )
        assert definition.validity_days == 365

    def test_create_definition_with_metadata(self, db, user, questions_data):
        """Test creating definition with metadata."""
        metadata = {"standard": "RSTC", "year": "2020"}
        definition = create_definition(
            slug="rstc-medical",
            name="RSTC Medical",
            description="RSTC standard questionnaire",
            version="1.0.0",
            questions_data=questions_data,
            actor=user,
            metadata=metadata,
        )
        assert definition.metadata == metadata

    def test_create_definition_questions_created(self, db, user, questions_data):
        """Test that questions are created correctly."""
        definition = create_definition(
            slug="with-questions",
            name="With Questions",
            description="Testing questions",
            version="1.0.0",
            questions_data=questions_data,
            actor=user,
        )

        questions = list(definition.questions.all())
        assert len(questions) == 3
        assert questions[0].question_type == QuestionType.YES_NO
        assert questions[0].triggers_flag is True
        assert questions[1].question_type == QuestionType.TEXT
        assert questions[2].question_type == QuestionType.NUMBER
        assert questions[2].validation_rules == {"min": 1, "max": 120}


class TestPublishDefinition:
    """Tests for publish_definition service."""

    def test_publish_draft_definition(self, draft_definition, user):
        """Test publishing a draft definition."""
        published = publish_definition(draft_definition, actor=user)

        assert published.status == DefinitionStatus.PUBLISHED
        assert published.id == draft_definition.id

    def test_publish_already_published_raises_error(self, published_definition, user):
        """Test that publishing already published definition raises error."""
        with pytest.raises(DefinitionAlreadyPublishedError):
            publish_definition(published_definition, actor=user)


class TestArchiveDefinition:
    """Tests for archive_definition service."""

    def test_archive_published_definition(self, published_definition, user):
        """Test archiving a published definition."""
        archived = archive_definition(published_definition, actor=user)

        assert archived.status == DefinitionStatus.ARCHIVED

    def test_archive_draft_definition(self, draft_definition, user):
        """Test archiving a draft definition."""
        archived = archive_definition(draft_definition, actor=user)

        assert archived.status == DefinitionStatus.ARCHIVED


class TestImportDefinitionFromJson:
    """Tests for import_definition_from_json service."""

    def test_import_from_json_file(self, db, user):
        """Test importing definition from JSON file."""
        json_data = {
            "slug": "imported-form",
            "name": "Imported Form",
            "description": "Form imported from JSON",
            "version": "1.0.0",
            "validity_days": 90,
            "metadata": {"source": "test"},
            "questions": [
                {
                    "sequence": 1,
                    "category": "test",
                    "question_type": "yes_no",
                    "question_text": "Is this imported?",
                    "is_required": True,
                    "triggers_flag": False,
                },
            ],
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_data, f)
            f.flush()

            definition = import_definition_from_json(Path(f.name), actor=user)

            assert definition.slug == "imported-form"
            assert definition.name == "Imported Form"
            assert definition.version == "1.0.0"
            assert definition.validity_days == 90
            assert definition.questions.count() == 1

    def test_import_with_categories(self, db, user):
        """Test importing definition with category metadata."""
        json_data = {
            "slug": "categorized-form",
            "name": "Categorized Form",
            "description": "Form with categories",
            "version": "1.0.0",
            "categories": [
                {"key": "general", "label": "General", "sequence": 1},
                {"key": "medical", "label": "Medical", "sequence": 2},
            ],
            "questions": [
                {
                    "sequence": 1,
                    "category": "general",
                    "question_type": "text",
                    "question_text": "Name?",
                    "is_required": True,
                    "triggers_flag": False,
                },
            ],
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_data, f)
            f.flush()

            definition = import_definition_from_json(Path(f.name), actor=user)

            # Categories should be stored in metadata
            assert "categories" in definition.metadata
            assert len(definition.metadata["categories"]) == 2


class TestCreateInstance:
    """Tests for create_instance service."""

    def test_create_instance_basic(self, published_definition, user):
        """Test creating an instance for a respondent."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        assert instance.id is not None
        assert instance.definition == published_definition
        assert instance.definition_version == "1.0.0"
        assert instance.status == InstanceStatus.PENDING
        assert instance.respondent == user
        assert instance.expires_at is not None

    def test_create_instance_nonexistent_definition_raises_error(self, db, user):
        """Test creating instance for non-existent definition raises error."""
        with pytest.raises(DefinitionNotFoundError):
            create_instance(
                definition_slug="nonexistent",
                respondent=user,
                expires_in_days=30,
                actor=user,
            )

    def test_create_instance_unpublished_definition_raises_error(
        self, draft_definition, user
    ):
        """Test creating instance from unpublished definition raises error."""
        with pytest.raises(DefinitionNotPublishedError):
            create_instance(
                definition_slug="test-form",
                respondent=user,
                expires_in_days=30,
                actor=user,
            )

    def test_create_instance_expires_at_calculated(self, published_definition, user):
        """Test that expires_at is calculated correctly."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=7,
            actor=user,
        )

        expected_expiry = timezone.now() + timedelta(days=7)
        # Allow 1 minute tolerance
        assert abs((instance.expires_at - expected_expiry).total_seconds()) < 60


class TestSubmitResponse:
    """Tests for submit_response service."""

    def test_submit_response_basic(self, published_definition, user):
        """Test submitting responses to an instance."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},
            str(questions[1].id): {"answer_text": "No allergies"},
            str(questions[2].id): {"answer_number": "30"},
        }

        completed_instance = submit_response(instance, answers=answers, actor=user)

        assert completed_instance.status == InstanceStatus.COMPLETED
        assert completed_instance.completed_at is not None
        assert completed_instance.responses.count() == 3

    def test_submit_response_triggers_flag(self, published_definition, user):
        """Test that triggering answer flags the instance."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        # Answer "Yes" to the flagging question
        answers = {
            str(questions[0].id): {"answer_bool": True},  # This triggers flag
            str(questions[1].id): {"answer_text": "Peanuts"},
            str(questions[2].id): {"answer_number": "30"},
        }

        flagged_instance = submit_response(instance, answers=answers, actor=user)

        assert flagged_instance.status == InstanceStatus.FLAGGED
        assert flagged_instance.flagged_at is not None

    def test_submit_response_already_completed_raises_error(
        self, published_definition, user
    ):
        """Test submitting to completed instance raises error."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},
            str(questions[1].id): {"answer_text": ""},
            str(questions[2].id): {"answer_number": "25"},
        }

        submit_response(instance, answers=answers, actor=user)

        with pytest.raises(InstanceAlreadyCompletedError):
            submit_response(instance, answers=answers, actor=user)

    def test_submit_response_missing_required_raises_error(
        self, published_definition, user
    ):
        """Test missing required answers raises error."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        # Missing required questions 1 and 3
        answers = {}

        with pytest.raises(MissingRequiredResponseError):
            submit_response(instance, answers=answers, actor=user)

    def test_submit_response_expired_instance_raises_error(
        self, published_definition, user
    ):
        """Test submitting to expired instance raises error."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        # Manually expire the instance
        instance.expires_at = timezone.now() - timedelta(days=1)
        instance.save()

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},
            str(questions[2].id): {"answer_number": "25"},
        }

        with pytest.raises(InstanceExpiredError):
            submit_response(instance, answers=answers, actor=user)


class TestClearInstance:
    """Tests for clear_instance service."""

    def test_clear_flagged_instance(self, published_definition, user, admin_user):
        """Test clearing a flagged instance."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": True},  # Triggers flag
            str(questions[1].id): {"answer_text": "Allergies"},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        cleared = clear_instance(
            instance=instance,
            cleared_by=admin_user,
            notes="Approved by physician",
        )

        assert cleared.status == InstanceStatus.CLEARED
        assert cleared.cleared_at is not None
        assert cleared.cleared_by == admin_user
        assert cleared.clearance_notes == "Approved by physician"

    def test_clear_non_flagged_raises_error(self, published_definition, user, admin_user):
        """Test clearing non-flagged instance raises error."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},  # Does not trigger flag
            str(questions[1].id): {"answer_text": ""},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        with pytest.raises(InstanceNotFlaggedError):
            clear_instance(instance=instance, cleared_by=admin_user, notes="Test")


class TestGetCurrentInstance:
    """Tests for get_current_instance service."""

    def test_get_current_instance_returns_latest(self, published_definition, user):
        """Test getting the current (latest) instance for a respondent."""
        # Create multiple instances
        instance1 = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )
        instance2 = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        current = get_current_instance(respondent=user, definition_slug="published-form")

        assert current.id == instance2.id

    def test_get_current_instance_none_when_no_instances(self, published_definition, user):
        """Test returns None when no instances exist."""
        current = get_current_instance(respondent=user, definition_slug="published-form")

        assert current is None


class TestIsInstanceValid:
    """Tests for is_instance_valid service."""

    def test_valid_completed_instance(self, published_definition, user):
        """Test that completed, non-expired instance is valid."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=365,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},
            str(questions[1].id): {"answer_text": ""},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        assert is_instance_valid(instance) is True

    def test_valid_cleared_instance(self, published_definition, user, admin_user):
        """Test that cleared instance is valid."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=365,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": True},
            str(questions[1].id): {"answer_text": "Peanuts"},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)
        clear_instance(instance, cleared_by=admin_user, notes="OK")

        assert is_instance_valid(instance) is True

    def test_expired_instance_not_valid(self, published_definition, user):
        """Test that expired instance is not valid."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},
            str(questions[1].id): {"answer_text": ""},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        # Manually expire
        instance.expires_at = timezone.now() - timedelta(days=1)
        instance.save()

        assert is_instance_valid(instance) is False

    def test_pending_instance_not_valid(self, published_definition, user):
        """Test that pending instance is not valid."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        assert is_instance_valid(instance) is False

    def test_flagged_instance_not_valid(self, published_definition, user):
        """Test that flagged (uncleared) instance is not valid."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": True},  # Triggers flag
            str(questions[1].id): {"answer_text": "Allergies"},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        assert is_instance_valid(instance) is False


class TestGetFlaggedQuestions:
    """Tests for get_flagged_questions service."""

    def test_get_flagged_questions_returns_flagging_questions(
        self, published_definition, user
    ):
        """Test getting questions that triggered flags."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": True},  # Triggers flag
            str(questions[1].id): {"answer_text": "Peanuts"},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        flagged = get_flagged_questions(instance)

        assert len(flagged) == 1
        assert flagged[0].id == questions[0].id

    def test_get_flagged_questions_empty_when_no_flags(
        self, published_definition, user
    ):
        """Test returns empty list when no flags triggered."""
        instance = create_instance(
            definition_slug="published-form",
            respondent=user,
            expires_in_days=30,
            actor=user,
        )

        questions = list(published_definition.questions.all())
        answers = {
            str(questions[0].id): {"answer_bool": False},  # Does not trigger
            str(questions[1].id): {"answer_text": ""},
            str(questions[2].id): {"answer_number": "30"},
        }
        submit_response(instance, answers=answers, actor=user)

        flagged = get_flagged_questions(instance)

        assert len(flagged) == 0
