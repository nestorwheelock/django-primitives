"""Tests for django-questionnaires models."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta

from django_questionnaires.models import (
    QuestionnaireDefinition,
    Question,
    QuestionnaireInstance,
    Response,
    DefinitionStatus,
    QuestionType,
    InstanceStatus,
)


User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def definition(db):
    """Create a basic questionnaire definition."""
    return QuestionnaireDefinition.objects.create(
        slug="test-questionnaire",
        name="Test Questionnaire",
        description="A test questionnaire",
        version="1.0.0",
        status=DefinitionStatus.DRAFT,
        validity_days=30,
    )


@pytest.fixture
def published_definition(db):
    """Create a published questionnaire definition."""
    return QuestionnaireDefinition.objects.create(
        slug="published-questionnaire",
        name="Published Questionnaire",
        description="A published questionnaire",
        version="1.0.0",
        status=DefinitionStatus.PUBLISHED,
        validity_days=365,
    )


@pytest.fixture
def question(definition):
    """Create a basic question."""
    return Question.objects.create(
        definition=definition,
        sequence=1,
        category="general",
        question_type=QuestionType.YES_NO,
        question_text="Is this a test question?",
        is_required=True,
        triggers_flag=True,
    )


class TestQuestionnaireDefinition:
    """Tests for QuestionnaireDefinition model."""

    def test_create_definition(self, db):
        """Test creating a questionnaire definition."""
        definition = QuestionnaireDefinition.objects.create(
            slug="health-check",
            name="Health Check",
            description="Basic health questionnaire",
            version="1.0.0",
            status=DefinitionStatus.DRAFT,
        )
        assert definition.id is not None
        assert definition.slug == "health-check"
        assert definition.name == "Health Check"
        assert definition.version == "1.0.0"
        assert definition.status == DefinitionStatus.DRAFT
        assert definition.validity_days is None
        assert definition.metadata == {}

    def test_definition_with_validity_days(self, db):
        """Test creating definition with validity period."""
        definition = QuestionnaireDefinition.objects.create(
            slug="annual-check",
            name="Annual Check",
            description="Annual questionnaire",
            version="1.0.0",
            status=DefinitionStatus.DRAFT,
            validity_days=365,
        )
        assert definition.validity_days == 365

    def test_definition_with_metadata(self, db):
        """Test creating definition with metadata."""
        metadata = {"standard": "RSTC", "year": "2020"}
        definition = QuestionnaireDefinition.objects.create(
            slug="rstc-medical",
            name="RSTC Medical",
            description="RSTC standard medical questionnaire",
            version="1.0.0",
            status=DefinitionStatus.DRAFT,
            metadata=metadata,
        )
        assert definition.metadata == metadata
        assert definition.metadata["standard"] == "RSTC"

    def test_definition_statuses(self, db):
        """Test all definition statuses."""
        for status in [DefinitionStatus.DRAFT, DefinitionStatus.PUBLISHED, DefinitionStatus.ARCHIVED]:
            definition = QuestionnaireDefinition.objects.create(
                slug=f"status-test-{status}",
                name=f"Status Test {status}",
                description="Testing statuses",
                version="1.0.0",
                status=status,
            )
            assert definition.status == status

    def test_definition_str(self, definition):
        """Test string representation."""
        assert str(definition) == "Test Questionnaire v1.0.0"

    def test_definition_timestamps(self, definition):
        """Test that timestamps are set."""
        assert definition.created_at is not None
        assert definition.updated_at is not None

    def test_definition_soft_delete(self, definition):
        """Test soft delete functionality."""
        definition.delete()
        assert definition.is_deleted
        assert definition.deleted_at is not None
        assert QuestionnaireDefinition.objects.filter(id=definition.id).count() == 0
        assert QuestionnaireDefinition.all_objects.filter(id=definition.id).count() == 1


class TestQuestion:
    """Tests for Question model."""

    def test_create_yes_no_question(self, definition):
        """Test creating a yes/no question."""
        question = Question.objects.create(
            definition=definition,
            sequence=1,
            category="general",
            question_type=QuestionType.YES_NO,
            question_text="Do you have any allergies?",
            is_required=True,
            triggers_flag=True,
        )
        assert question.id is not None
        assert question.definition == definition
        assert question.sequence == 1
        assert question.question_type == QuestionType.YES_NO
        assert question.triggers_flag is True

    def test_create_text_question(self, definition):
        """Test creating a text question."""
        question = Question.objects.create(
            definition=definition,
            sequence=2,
            category="details",
            question_type=QuestionType.TEXT,
            question_text="Please describe your condition.",
            help_text="Provide as much detail as possible.",
            is_required=False,
            triggers_flag=False,
        )
        assert question.question_type == QuestionType.TEXT
        assert question.help_text == "Provide as much detail as possible."

    def test_create_choice_question(self, definition):
        """Test creating a single choice question."""
        choices = [
            {"value": "a", "label": "Option A"},
            {"value": "b", "label": "Option B"},
            {"value": "c", "label": "Option C"},
        ]
        question = Question.objects.create(
            definition=definition,
            sequence=3,
            category="preferences",
            question_type=QuestionType.CHOICE,
            question_text="Select your preference.",
            is_required=True,
            triggers_flag=False,
            choices=choices,
        )
        assert question.question_type == QuestionType.CHOICE
        assert question.choices == choices
        assert len(question.choices) == 3

    def test_create_multi_choice_question(self, definition):
        """Test creating a multi-choice question."""
        choices = [
            {"value": "1", "label": "Item 1"},
            {"value": "2", "label": "Item 2"},
        ]
        question = Question.objects.create(
            definition=definition,
            sequence=4,
            category="selections",
            question_type=QuestionType.MULTI_CHOICE,
            question_text="Select all that apply.",
            is_required=True,
            triggers_flag=False,
            choices=choices,
        )
        assert question.question_type == QuestionType.MULTI_CHOICE

    def test_create_number_question(self, definition):
        """Test creating a number question with validation."""
        validation_rules = {"min": 0, "max": 100}
        question = Question.objects.create(
            definition=definition,
            sequence=5,
            category="metrics",
            question_type=QuestionType.NUMBER,
            question_text="Enter your age.",
            is_required=True,
            triggers_flag=False,
            validation_rules=validation_rules,
        )
        assert question.question_type == QuestionType.NUMBER
        assert question.validation_rules == validation_rules

    def test_create_date_question(self, definition):
        """Test creating a date question."""
        question = Question.objects.create(
            definition=definition,
            sequence=6,
            category="dates",
            question_type=QuestionType.DATE,
            question_text="When did this occur?",
            is_required=False,
            triggers_flag=False,
        )
        assert question.question_type == QuestionType.DATE

    def test_question_ordering(self, definition):
        """Test that questions are ordered by sequence."""
        q3 = Question.objects.create(
            definition=definition, sequence=3, question_type=QuestionType.TEXT,
            question_text="Third", is_required=False, triggers_flag=False,
        )
        q1 = Question.objects.create(
            definition=definition, sequence=1, question_type=QuestionType.TEXT,
            question_text="First", is_required=False, triggers_flag=False,
        )
        q2 = Question.objects.create(
            definition=definition, sequence=2, question_type=QuestionType.TEXT,
            question_text="Second", is_required=False, triggers_flag=False,
        )
        questions = list(definition.questions.all())
        assert questions[0].sequence == 1
        assert questions[1].sequence == 2
        assert questions[2].sequence == 3

    def test_question_str(self, question):
        """Test string representation."""
        assert str(question) == "Q1: Is this a test question?"


class TestQuestionnaireInstance:
    """Tests for QuestionnaireInstance model."""

    def test_create_instance(self, published_definition, user):
        """Test creating a questionnaire instance."""
        content_type = ContentType.objects.get_for_model(User)
        expires_at = timezone.now() + timedelta(days=30)

        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=expires_at,
        )
        assert instance.id is not None
        assert instance.definition == published_definition
        assert instance.definition_version == "1.0.0"
        assert instance.status == InstanceStatus.PENDING
        assert instance.respondent == user

    def test_instance_statuses(self, published_definition, user):
        """Test all instance statuses."""
        content_type = ContentType.objects.get_for_model(User)
        expires_at = timezone.now() + timedelta(days=30)

        for status in [InstanceStatus.PENDING, InstanceStatus.COMPLETED,
                       InstanceStatus.FLAGGED, InstanceStatus.CLEARED,
                       InstanceStatus.EXPIRED]:
            instance = QuestionnaireInstance.objects.create(
                definition=published_definition,
                definition_version=published_definition.version,
                respondent_content_type=content_type,
                respondent_object_id=str(user.id),
                status=status,
                expires_at=expires_at,
            )
            assert instance.status == status

    def test_instance_with_clearance(self, published_definition, user):
        """Test instance with clearance information."""
        content_type = ContentType.objects.get_for_model(User)
        expires_at = timezone.now() + timedelta(days=30)
        cleared_at = timezone.now()

        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.CLEARED,
            expires_at=expires_at,
            cleared_at=cleared_at,
            cleared_by=user,
            clearance_notes="Approved by physician.",
        )
        assert instance.cleared_at == cleared_at
        assert instance.cleared_by == user
        assert instance.clearance_notes == "Approved by physician."

    def test_instance_is_expired_property(self, published_definition, user):
        """Test is_expired property."""
        content_type = ContentType.objects.get_for_model(User)

        # Not expired
        future_instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=30),
        )
        assert future_instance.is_expired is False

        # Expired
        past_instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() - timedelta(days=1),
        )
        assert past_instance.is_expired is True


class TestResponse:
    """Tests for Response model."""

    def test_create_bool_response(self, published_definition, user, question):
        """Test creating a boolean response."""
        content_type = ContentType.objects.get_for_model(User)
        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Need to create a question for the published definition
        q = Question.objects.create(
            definition=published_definition,
            sequence=1,
            question_type=QuestionType.YES_NO,
            question_text="Test question?",
            is_required=True,
            triggers_flag=True,
        )

        response = Response.objects.create(
            instance=instance,
            question=q,
            answer_bool=True,
            triggered_flag=True,
        )
        assert response.id is not None
        assert response.answer_bool is True
        assert response.triggered_flag is True

    def test_create_text_response(self, published_definition, user):
        """Test creating a text response."""
        content_type = ContentType.objects.get_for_model(User)
        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=30),
        )
        q = Question.objects.create(
            definition=published_definition,
            sequence=1,
            question_type=QuestionType.TEXT,
            question_text="Describe your issue.",
            is_required=True,
            triggers_flag=False,
        )

        response = Response.objects.create(
            instance=instance,
            question=q,
            answer_text="I have a minor headache.",
            triggered_flag=False,
        )
        assert response.answer_text == "I have a minor headache."

    def test_create_number_response(self, published_definition, user):
        """Test creating a number response."""
        content_type = ContentType.objects.get_for_model(User)
        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=30),
        )
        q = Question.objects.create(
            definition=published_definition,
            sequence=1,
            question_type=QuestionType.NUMBER,
            question_text="Enter your age.",
            is_required=True,
            triggers_flag=False,
        )

        from decimal import Decimal
        response = Response.objects.create(
            instance=instance,
            question=q,
            answer_number=Decimal("35"),
            triggered_flag=False,
        )
        assert response.answer_number == Decimal("35")

    def test_create_date_response(self, published_definition, user):
        """Test creating a date response."""
        content_type = ContentType.objects.get_for_model(User)
        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=30),
        )
        q = Question.objects.create(
            definition=published_definition,
            sequence=1,
            question_type=QuestionType.DATE,
            question_text="When did this occur?",
            is_required=True,
            triggers_flag=False,
        )

        from datetime import date
        response = Response.objects.create(
            instance=instance,
            question=q,
            answer_date=date(2024, 1, 15),
            triggered_flag=False,
        )
        assert response.answer_date == date(2024, 1, 15)

    def test_create_choices_response(self, published_definition, user):
        """Test creating a choices response."""
        content_type = ContentType.objects.get_for_model(User)
        instance = QuestionnaireInstance.objects.create(
            definition=published_definition,
            definition_version=published_definition.version,
            respondent_content_type=content_type,
            respondent_object_id=str(user.id),
            status=InstanceStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=30),
        )
        q = Question.objects.create(
            definition=published_definition,
            sequence=1,
            question_type=QuestionType.MULTI_CHOICE,
            question_text="Select all that apply.",
            is_required=True,
            triggers_flag=False,
            choices=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
        )

        response = Response.objects.create(
            instance=instance,
            question=q,
            answer_choices=["a", "b"],
            triggered_flag=False,
        )
        assert response.answer_choices == ["a", "b"]
