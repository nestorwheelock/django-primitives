"""Services for preference management.

Provides business logic for:
- Mapping questionnaire responses to preferences
- Progressive preference collection (skip already-answered questions)
- Checking if surveys should be sent
"""

from django.db import transaction

from django_questionnaires.models import QuestionType

from .models import PreferenceDefinition, PartyPreference, ValueType, Source


def apply_questionnaire_to_preferences(instance, person):
    """Map questionnaire responses to person preferences.

    Reads all responses from a completed questionnaire instance and creates/updates
    PartyPreference records for questions that have a preference_key in their
    validation_rules.

    Args:
        instance: QuestionnaireInstance that has been completed
        person: Person model instance to attach preferences to

    Returns:
        dict with counts: {"created": int, "updated": int, "skipped": int}
    """
    created = 0
    updated = 0
    skipped = 0

    with transaction.atomic():
        for response in instance.responses.select_related("question"):
            question = response.question
            preference_key = question.validation_rules.get("preference_key")

            if not preference_key:
                continue

            try:
                definition = PreferenceDefinition.objects.get(key=preference_key)
            except PreferenceDefinition.DoesNotExist:
                skipped += 1
                continue

            value = _extract_response_value(response, question.question_type, definition.value_type)

            pref, was_created = PartyPreference.objects.get_or_create(
                person=person,
                definition=definition,
                defaults={
                    "source": Source.SURVEY,
                    "source_instance_id": str(instance.pk),
                }
            )

            pref.set_value(value)
            pref.source = Source.SURVEY
            pref.source_instance_id = str(instance.pk)
            pref.save()

            if was_created:
                created += 1
            else:
                updated += 1

    return {"created": created, "updated": updated, "skipped": skipped}


def _extract_response_value(response, question_type, value_type):
    """Extract the appropriate value from a response based on question and preference types.

    Args:
        response: Response model instance
        question_type: QuestionType enum value
        value_type: ValueType enum value for the preference

    Returns:
        The extracted value in the appropriate format
    """
    if question_type == QuestionType.YES_NO:
        return response.answer_bool

    if question_type == QuestionType.TEXT:
        return response.answer_text

    if question_type == QuestionType.NUMBER:
        return int(response.answer_number) if response.answer_number else None

    if question_type == QuestionType.DATE:
        return response.answer_date

    if question_type == QuestionType.CHOICE:
        # Single choice: return as text (first choice or answer_text)
        if response.answer_choices:
            return response.answer_choices[0] if len(response.answer_choices) == 1 else response.answer_choices
        return response.answer_text

    if question_type == QuestionType.MULTI_CHOICE:
        # Multi-choice: return as list
        return response.answer_choices

    return response.answer_text


def get_missing_preference_keys(person, keys):
    """Get preference keys that haven't been collected for a person.

    Args:
        person: Person model instance
        keys: List of preference keys to check

    Returns:
        List of keys that the person doesn't have preferences for
    """
    if not keys:
        return []

    # Get keys that actually exist as preference definitions
    valid_keys = set(
        PreferenceDefinition.objects.filter(key__in=keys).values_list("key", flat=True)
    )

    # Get keys the person already has
    collected_keys = set(
        PartyPreference.objects.filter(
            person=person,
            definition__key__in=keys,
        ).values_list("definition__key", flat=True)
    )

    # Return valid keys that aren't collected
    return [k for k in keys if k in valid_keys and k not in collected_keys]


def filter_questions_for_person(definition, person):
    """Filter questionnaire questions to exclude already-answered preferences.

    Returns questions that either:
    - Don't have a preference_key (always include)
    - Have a preference_key that the person hasn't answered yet

    Args:
        definition: QuestionnaireDefinition model instance
        person: Person model instance

    Returns:
        List of Question objects to include in the survey
    """
    questions = list(definition.questions.all())

    # Get preference keys the person has already answered
    answered_keys = set(
        PartyPreference.objects.filter(person=person).values_list(
            "definition__key", flat=True
        )
    )

    filtered = []
    for question in questions:
        preference_key = question.validation_rules.get("preference_key")

        if not preference_key:
            # No preference mapping, always include
            filtered.append(question)
        elif preference_key not in answered_keys:
            # Has preference mapping, but not yet answered
            filtered.append(question)
        # else: skip (already answered)

    return filtered


def should_send_survey(person, definition):
    """Check if a survey should be sent to a person.

    Returns True if there are any unanswered questions in the survey.

    Args:
        person: Person model instance
        definition: QuestionnaireDefinition model instance

    Returns:
        bool: True if survey has questions the person hasn't answered
    """
    remaining_questions = filter_questions_for_person(definition, person)
    return len(remaining_questions) > 0
