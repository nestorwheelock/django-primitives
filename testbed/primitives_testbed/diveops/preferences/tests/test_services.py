"""Tests for preference services.

Tests cover:
- apply_questionnaire_to_preferences: Map questionnaire responses to preferences
- get_missing_preference_keys: Return preference keys not yet collected
- filter_questions_for_person: Exclude questions already answered
- should_send_survey: Check if survey has unanswered questions
"""

import pytest
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_parties.models import Person
from django_questionnaires.models import (
    QuestionnaireDefinition,
    Question,
    QuestionnaireInstance,
    Response,
    QuestionType,
    DefinitionStatus,
    InstanceStatus,
)

from ..models import PreferenceDefinition, PartyPreference, ValueType, Sensitivity, Source
from ..services import (
    apply_questionnaire_to_preferences,
    get_missing_preference_keys,
    filter_questions_for_person,
    should_send_survey,
)


@pytest.fixture
def person(db):
    """Create a test person."""
    return Person.objects.create(
        first_name="Test",
        last_name="Diver",
        email="test@example.com",
    )


@pytest.fixture
def preference_definitions(db):
    """Create test preference definitions."""
    defs = []
    defs.append(PreferenceDefinition.objects.create(
        key="diving.interests",
        label="Diving Interests",
        category="diving",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["Reef", "Wreck", "Cenote", "Night diving"],
        sensitivity=Sensitivity.PUBLIC,
    ))
    defs.append(PreferenceDefinition.objects.create(
        key="diving.experience_level",
        label="Experience Level",
        category="diving",
        value_type=ValueType.CHOICE,
        choices_json=["Beginner", "Intermediate", "Advanced", "Expert"],
        sensitivity=Sensitivity.PUBLIC,
    ))
    defs.append(PreferenceDefinition.objects.create(
        key="diving.likes_photography",
        label="Likes Photography",
        category="diving",
        value_type=ValueType.BOOL,
        sensitivity=Sensitivity.PUBLIC,
    ))
    defs.append(PreferenceDefinition.objects.create(
        key="food.dietary_restrictions",
        label="Dietary Restrictions",
        category="food",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["Vegetarian", "Vegan", "Gluten-free", "None"],
        sensitivity=Sensitivity.INTERNAL,
    ))
    return defs


@pytest.fixture
def questionnaire_definition(db, preference_definitions):
    """Create a questionnaire definition with preference-linked questions."""
    definition = QuestionnaireDefinition.objects.create(
        slug="diver-preferences-intake",
        name="Diver Preferences Intake",
        version="1.0.0",
        status=DefinitionStatus.PUBLISHED,
    )

    Question.objects.create(
        definition=definition,
        sequence=1,
        question_type=QuestionType.MULTI_CHOICE,
        question_text="What types of diving interest you?",
        choices=["Reef", "Wreck", "Cenote", "Night diving"],
        validation_rules={"preference_key": "diving.interests"},
    )

    Question.objects.create(
        definition=definition,
        sequence=2,
        question_type=QuestionType.CHOICE,
        question_text="How would you describe your diving experience?",
        choices=["Beginner", "Intermediate", "Advanced", "Expert"],
        validation_rules={"preference_key": "diving.experience_level"},
    )

    Question.objects.create(
        definition=definition,
        sequence=3,
        question_type=QuestionType.YES_NO,
        question_text="Are you interested in underwater photography?",
        validation_rules={"preference_key": "diving.likes_photography"},
    )

    Question.objects.create(
        definition=definition,
        sequence=4,
        question_type=QuestionType.MULTI_CHOICE,
        question_text="Do you have any dietary restrictions?",
        choices=["Vegetarian", "Vegan", "Gluten-free", "None"],
        validation_rules={"preference_key": "food.dietary_restrictions"},
    )

    # Question without preference mapping (should be ignored)
    Question.objects.create(
        definition=definition,
        sequence=5,
        question_type=QuestionType.TEXT,
        question_text="Any additional comments?",
        is_required=False,
        validation_rules={},
    )

    return definition


@pytest.fixture
def completed_instance(db, questionnaire_definition, person):
    """Create a completed questionnaire instance with responses."""
    person_ct = ContentType.objects.get_for_model(Person)

    instance = QuestionnaireInstance.objects.create(
        definition=questionnaire_definition,
        definition_version=questionnaire_definition.version,
        respondent_content_type=person_ct,
        respondent_object_id=str(person.pk),
        status=InstanceStatus.COMPLETED,
        expires_at=timezone.now() + timedelta(days=365),
        completed_at=timezone.now(),
    )

    questions = list(questionnaire_definition.questions.all())

    # Multi-choice response
    Response.objects.create(
        instance=instance,
        question=questions[0],
        answer_choices=["Reef", "Cenote"],
    )

    # Single choice response
    Response.objects.create(
        instance=instance,
        question=questions[1],
        answer_text="Advanced",
    )

    # Yes/No response
    Response.objects.create(
        instance=instance,
        question=questions[2],
        answer_bool=True,
    )

    # Multi-choice response
    Response.objects.create(
        instance=instance,
        question=questions[3],
        answer_choices=["Vegetarian"],
    )

    # Text response (no preference mapping)
    Response.objects.create(
        instance=instance,
        question=questions[4],
        answer_text="Looking forward to diving!",
    )

    return instance


@pytest.mark.django_db
class TestApplyQuestionnaireToPrefernces:
    """Tests for apply_questionnaire_to_preferences service."""

    def test_creates_preferences_from_responses(
        self, completed_instance, person, preference_definitions
    ):
        """Service creates PartyPreference records from questionnaire responses."""
        assert PartyPreference.objects.filter(person=person).count() == 0

        result = apply_questionnaire_to_preferences(completed_instance, person)

        # Should create 4 preferences (one has no preference_key)
        assert PartyPreference.objects.filter(person=person).count() == 4
        assert result["created"] == 4
        assert result["updated"] == 0

    def test_sets_correct_values_for_multi_choice(
        self, completed_instance, person, preference_definitions
    ):
        """Multi-choice answers are stored as JSON arrays."""
        apply_questionnaire_to_preferences(completed_instance, person)

        pref = PartyPreference.objects.get(
            person=person,
            definition__key="diving.interests",
        )
        assert pref.get_value() == ["Reef", "Cenote"]

    def test_sets_correct_values_for_single_choice(
        self, completed_instance, person, preference_definitions
    ):
        """Single choice answers are stored as text."""
        apply_questionnaire_to_preferences(completed_instance, person)

        pref = PartyPreference.objects.get(
            person=person,
            definition__key="diving.experience_level",
        )
        assert pref.get_value() == "Advanced"

    def test_sets_correct_values_for_bool(
        self, completed_instance, person, preference_definitions
    ):
        """Yes/No answers are stored as boolean."""
        apply_questionnaire_to_preferences(completed_instance, person)

        pref = PartyPreference.objects.get(
            person=person,
            definition__key="diving.likes_photography",
        )
        assert pref.get_value() is True

    def test_sets_source_to_survey(
        self, completed_instance, person, preference_definitions
    ):
        """Created preferences have source=SURVEY."""
        apply_questionnaire_to_preferences(completed_instance, person)

        pref = PartyPreference.objects.get(
            person=person,
            definition__key="diving.interests",
        )
        assert pref.source == Source.SURVEY

    def test_sets_source_instance_id(
        self, completed_instance, person, preference_definitions
    ):
        """Created preferences reference the questionnaire instance."""
        apply_questionnaire_to_preferences(completed_instance, person)

        pref = PartyPreference.objects.get(
            person=person,
            definition__key="diving.interests",
        )
        assert pref.source_instance_id == str(completed_instance.pk)

    def test_updates_existing_preferences(
        self, completed_instance, person, preference_definitions
    ):
        """Service updates existing preferences rather than creating duplicates."""
        # Create existing preference with different value
        interests_def = PreferenceDefinition.objects.get(key="diving.interests")
        existing = PartyPreference.objects.create(
            person=person,
            definition=interests_def,
            value_json=["Wreck"],
            source=Source.STAFF,
        )

        result = apply_questionnaire_to_preferences(completed_instance, person)

        # Should update 1, create 3
        assert result["updated"] == 1
        assert result["created"] == 3

        existing.refresh_from_db()
        assert existing.get_value() == ["Reef", "Cenote"]
        assert existing.source == Source.SURVEY

    def test_ignores_questions_without_preference_key(
        self, completed_instance, person, preference_definitions
    ):
        """Questions without preference_key in validation_rules are skipped."""
        apply_questionnaire_to_preferences(completed_instance, person)

        # Should only have 4 preferences, not 5
        assert PartyPreference.objects.filter(person=person).count() == 4

    def test_ignores_missing_preference_definitions(
        self, completed_instance, person, db
    ):
        """Responses for undefined preference keys are skipped gracefully."""
        # Delete preference definitions
        PreferenceDefinition.objects.all().delete()

        result = apply_questionnaire_to_preferences(completed_instance, person)

        assert result["created"] == 0
        assert result["skipped"] == 4  # 4 questions have preference_key but no def


@pytest.mark.django_db
class TestGetMissingPreferenceKeys:
    """Tests for get_missing_preference_keys service."""

    def test_returns_all_keys_when_none_collected(self, person, preference_definitions):
        """Returns all requested keys when person has no preferences."""
        keys = ["diving.interests", "diving.experience_level", "food.dietary_restrictions"]

        missing = get_missing_preference_keys(person, keys)

        assert set(missing) == set(keys)

    def test_excludes_collected_keys(self, person, preference_definitions):
        """Excludes keys that person already has preferences for."""
        # Create one preference
        interests_def = PreferenceDefinition.objects.get(key="diving.interests")
        PartyPreference.objects.create(
            person=person,
            definition=interests_def,
            value_json=["Reef"],
        )

        keys = ["diving.interests", "diving.experience_level", "food.dietary_restrictions"]
        missing = get_missing_preference_keys(person, keys)

        assert "diving.interests" not in missing
        assert "diving.experience_level" in missing
        assert "food.dietary_restrictions" in missing

    def test_returns_empty_list_when_all_collected(self, person, preference_definitions):
        """Returns empty list when all requested keys are collected."""
        # Create all preferences
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=person,
                definition=pdef,
                value_text="test",
            )

        keys = [pdef.key for pdef in preference_definitions]
        missing = get_missing_preference_keys(person, keys)

        assert missing == []

    def test_handles_empty_key_list(self, person, preference_definitions):
        """Handles empty key list gracefully."""
        missing = get_missing_preference_keys(person, [])
        assert missing == []

    def test_ignores_undefined_keys(self, person, preference_definitions):
        """Keys not in PreferenceDefinition are ignored (not returned as missing)."""
        keys = ["diving.interests", "nonexistent.key", "another.fake"]

        missing = get_missing_preference_keys(person, keys)

        # Only the valid, missing key should be returned
        assert "diving.interests" in missing
        assert "nonexistent.key" not in missing


@pytest.mark.django_db
class TestFilterQuestionsForPerson:
    """Tests for filter_questions_for_person service."""

    def test_returns_all_questions_when_no_preferences(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Returns all questions when person has no preferences."""
        questions = filter_questions_for_person(questionnaire_definition, person)

        # All 5 questions should be returned
        assert len(questions) == 5

    def test_excludes_questions_with_answered_preferences(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Excludes questions whose preference_key is already collected."""
        # Create preference for diving interests
        interests_def = PreferenceDefinition.objects.get(key="diving.interests")
        PartyPreference.objects.create(
            person=person,
            definition=interests_def,
            value_json=["Reef"],
        )

        questions = filter_questions_for_person(questionnaire_definition, person)

        # Should exclude Q1 (diving.interests), keep Q2-Q5
        assert len(questions) == 4
        keys = [q.validation_rules.get("preference_key") for q in questions]
        assert "diving.interests" not in keys

    def test_keeps_questions_without_preference_key(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Questions without preference_key are always included."""
        # Create all preferences
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=person,
                definition=pdef,
                value_text="test",
            )

        questions = filter_questions_for_person(questionnaire_definition, person)

        # Only Q5 (no preference_key) should remain
        assert len(questions) == 1
        assert questions[0].validation_rules == {}

    def test_returns_empty_list_for_fully_answered_survey(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Returns empty list when all preference-mapped questions are answered."""
        # Create all preferences
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=person,
                definition=pdef,
                value_text="test",
            )

        # Remove the question without preference_key for this test
        questionnaire_definition.questions.filter(sequence=5).delete()

        questions = filter_questions_for_person(questionnaire_definition, person)

        assert questions == []


@pytest.mark.django_db
class TestShouldSendSurvey:
    """Tests for should_send_survey service."""

    def test_returns_true_when_questions_remain(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Returns True when person has unanswered preference questions."""
        result = should_send_survey(person, questionnaire_definition)

        assert result is True

    def test_returns_true_when_some_answered(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Returns True when person has some but not all preferences."""
        # Answer some questions
        interests_def = PreferenceDefinition.objects.get(key="diving.interests")
        PartyPreference.objects.create(
            person=person,
            definition=interests_def,
            value_json=["Reef"],
        )

        result = should_send_survey(person, questionnaire_definition)

        assert result is True

    def test_returns_false_when_all_answered(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Returns False when all preference-mapped questions are answered."""
        # Create all preferences
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=person,
                definition=pdef,
                value_text="test",
            )

        # Remove question without preference_key
        questionnaire_definition.questions.filter(sequence=5).delete()

        result = should_send_survey(person, questionnaire_definition)

        assert result is False

    def test_returns_true_when_only_non_preference_questions_remain(
        self, questionnaire_definition, person, preference_definitions
    ):
        """Returns True when only questions without preference_key remain."""
        # Create all preferences
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=person,
                definition=pdef,
                value_text="test",
            )

        # Q5 has no preference_key but is still a question
        result = should_send_survey(person, questionnaire_definition)

        # Non-preference questions still count as reason to send
        assert result is True
