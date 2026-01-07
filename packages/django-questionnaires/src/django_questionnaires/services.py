"""Services for django-questionnaires.

Domain-agnostic service functions for managing questionnaire definitions,
instances, and responses.
"""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .models import (
    QuestionnaireDefinition,
    Question,
    QuestionnaireInstance,
    Response,
    DefinitionStatus,
    QuestionType,
    InstanceStatus,
)
from .exceptions import (
    DefinitionNotFoundError,
    DefinitionNotPublishedError,
    DefinitionAlreadyPublishedError,
    InstanceAlreadyCompletedError,
    InstanceExpiredError,
    MissingRequiredResponseError,
    InstanceNotFlaggedError,
)


def create_definition(
    slug: str,
    name: str,
    description: str,
    version: str,
    questions_data: list[dict],
    actor: Any,
    validity_days: int | None = None,
    metadata: dict | None = None,
) -> QuestionnaireDefinition:
    """Create a new questionnaire definition with questions.

    Creates a draft definition that can later be published.

    Args:
        slug: Unique identifier for the definition
        name: Human-readable name
        description: Detailed description
        version: Semantic version string
        questions_data: List of question configurations
        actor: User performing the action (for audit)
        validity_days: Optional validity period in days
        metadata: Optional domain-specific metadata

    Returns:
        The created QuestionnaireDefinition
    """
    with transaction.atomic():
        definition = QuestionnaireDefinition.objects.create(
            slug=slug,
            name=name,
            description=description,
            version=version,
            status=DefinitionStatus.DRAFT,
            validity_days=validity_days,
            metadata=metadata or {},
        )

        for q_data in questions_data:
            Question.objects.create(
                definition=definition,
                sequence=q_data.get("sequence", 0),
                category=q_data.get("category", ""),
                question_type=q_data.get("question_type", QuestionType.TEXT),
                question_text=q_data.get("question_text", ""),
                help_text=q_data.get("help_text", ""),
                is_required=q_data.get("is_required", True),
                triggers_flag=q_data.get("triggers_flag", False),
                choices=q_data.get("choices", []),
                validation_rules=q_data.get("validation_rules", {}),
            )

        return definition


def publish_definition(
    definition: QuestionnaireDefinition,
    actor: Any,
) -> QuestionnaireDefinition:
    """Publish a draft questionnaire definition.

    Once published, the definition can be used to create instances.

    Args:
        definition: The definition to publish
        actor: User performing the action (for audit)

    Returns:
        The published definition

    Raises:
        DefinitionAlreadyPublishedError: If already published
    """
    if definition.status == DefinitionStatus.PUBLISHED:
        raise DefinitionAlreadyPublishedError(
            f"Definition '{definition.slug}' is already published"
        )

    definition.status = DefinitionStatus.PUBLISHED
    definition.save(update_fields=["status", "updated_at"])
    return definition


def archive_definition(
    definition: QuestionnaireDefinition,
    actor: Any,
) -> QuestionnaireDefinition:
    """Archive a questionnaire definition.

    Archived definitions cannot be used to create new instances.

    Args:
        definition: The definition to archive
        actor: User performing the action (for audit)

    Returns:
        The archived definition
    """
    definition.status = DefinitionStatus.ARCHIVED
    definition.save(update_fields=["status", "updated_at"])
    return definition


def import_definition_from_json(
    json_path: Path,
    actor: Any,
) -> QuestionnaireDefinition:
    """Import a questionnaire definition from a JSON file.

    The JSON should contain:
    - slug, name, description, version (required)
    - validity_days, metadata (optional)
    - categories (optional, stored in metadata)
    - questions (list of question configurations)

    Args:
        json_path: Path to the JSON file
        actor: User performing the action (for audit)

    Returns:
        The created QuestionnaireDefinition
    """
    with open(json_path, "r") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})

    # Store categories in metadata if provided
    if "categories" in data:
        metadata["categories"] = data["categories"]

    return create_definition(
        slug=data["slug"],
        name=data["name"],
        description=data.get("description", ""),
        version=data["version"],
        questions_data=data.get("questions", []),
        actor=actor,
        validity_days=data.get("validity_days"),
        metadata=metadata,
    )


def create_instance(
    definition_slug: str,
    respondent: Any,
    expires_in_days: int,
    actor: Any,
) -> QuestionnaireInstance:
    """Create a questionnaire instance for a respondent.

    Args:
        definition_slug: Slug of the published definition to use
        respondent: The model instance that will fill out the questionnaire
        expires_in_days: Number of days until the instance expires
        actor: User performing the action (for audit)

    Returns:
        The created QuestionnaireInstance

    Raises:
        DefinitionNotFoundError: If definition doesn't exist
        DefinitionNotPublishedError: If definition is not published
    """
    try:
        definition = QuestionnaireDefinition.objects.get(
            slug=definition_slug,
            deleted_at__isnull=True,
        )
    except QuestionnaireDefinition.DoesNotExist:
        raise DefinitionNotFoundError(f"Definition '{definition_slug}' not found")

    if definition.status != DefinitionStatus.PUBLISHED:
        raise DefinitionNotPublishedError(
            f"Definition '{definition_slug}' is not published"
        )

    content_type = ContentType.objects.get_for_model(respondent)
    expires_at = timezone.now() + timedelta(days=expires_in_days)

    instance = QuestionnaireInstance.objects.create(
        definition=definition,
        definition_version=definition.version,
        respondent_content_type=content_type,
        respondent_object_id=str(respondent.pk),
        status=InstanceStatus.PENDING,
        expires_at=expires_at,
    )

    return instance


def submit_response(
    instance: QuestionnaireInstance,
    answers: dict[str, dict],
    actor: Any,
) -> QuestionnaireInstance:
    """Submit responses to a questionnaire instance.

    Args:
        instance: The instance to submit responses for
        answers: Dict mapping question ID to answer data
        actor: User performing the action (for audit)

    Returns:
        The updated instance (completed or flagged)

    Raises:
        InstanceAlreadyCompletedError: If instance is already completed
        InstanceExpiredError: If instance has expired
        MissingRequiredResponseError: If required questions not answered
    """
    # Refresh from database
    instance.refresh_from_db()

    # Check if already completed or flagged or cleared
    if instance.status in [
        InstanceStatus.COMPLETED,
        InstanceStatus.FLAGGED,
        InstanceStatus.CLEARED,
    ]:
        raise InstanceAlreadyCompletedError(
            f"Instance is already {instance.status}"
        )

    # Check expiration
    if instance.is_expired:
        raise InstanceExpiredError("Instance has expired")

    # Get all questions for this definition
    questions = list(instance.definition.questions.all())
    required_questions = [q for q in questions if q.is_required]

    # Check required questions are answered
    answered_ids = set(answers.keys())
    required_ids = {str(q.id) for q in required_questions}
    missing = required_ids - answered_ids

    if missing:
        raise MissingRequiredResponseError(
            f"Missing required responses: {missing}"
        )

    # Track if any answer triggers a flag
    has_flag = False

    with transaction.atomic():
        for question in questions:
            q_id = str(question.id)
            if q_id not in answers:
                continue

            answer_data = answers[q_id]
            triggered_flag = False

            # Check if this answer triggers a flag
            if question.triggers_flag:
                if question.question_type == QuestionType.YES_NO:
                    if answer_data.get("answer_bool") is True:
                        triggered_flag = True
                        has_flag = True

            # Create response
            Response.objects.create(
                instance=instance,
                question=question,
                answer_text=answer_data.get("answer_text"),
                answer_bool=answer_data.get("answer_bool"),
                answer_date=answer_data.get("answer_date"),
                answer_number=_parse_number(answer_data.get("answer_number")),
                answer_choices=answer_data.get("answer_choices"),
                triggered_flag=triggered_flag,
            )

        # Update instance status
        now = timezone.now()
        if has_flag:
            instance.status = InstanceStatus.FLAGGED
            instance.flagged_at = now
        else:
            instance.status = InstanceStatus.COMPLETED

        instance.completed_at = now
        instance.save(update_fields=["status", "completed_at", "flagged_at", "updated_at"])

    return instance


def _parse_number(value: Any) -> Decimal | None:
    """Parse a value to Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def clear_instance(
    instance: QuestionnaireInstance,
    cleared_by: Any,
    notes: str = "",
    clearance_document: Any = None,
) -> QuestionnaireInstance:
    """Clear a flagged questionnaire instance.

    Args:
        instance: The flagged instance to clear
        cleared_by: User who is clearing the instance
        notes: Optional clearance notes
        clearance_document: Optional attached document (GenericFK)

    Returns:
        The cleared instance

    Raises:
        InstanceNotFlaggedError: If instance is not flagged
    """
    instance.refresh_from_db()

    if instance.status != InstanceStatus.FLAGGED:
        raise InstanceNotFlaggedError(
            f"Instance is not flagged (status: {instance.status})"
        )

    instance.status = InstanceStatus.CLEARED
    instance.cleared_at = timezone.now()
    instance.cleared_by = cleared_by
    instance.clearance_notes = notes

    if clearance_document:
        content_type = ContentType.objects.get_for_model(clearance_document)
        instance.clearance_document_content_type = content_type
        instance.clearance_document_object_id = str(clearance_document.pk)

    instance.save()
    return instance


def get_current_instance(
    respondent: Any,
    definition_slug: str,
) -> QuestionnaireInstance | None:
    """Get the most recent questionnaire instance for a respondent.

    Args:
        respondent: The respondent model instance
        definition_slug: Slug of the definition to look for

    Returns:
        The most recent instance, or None if none exist
    """
    content_type = ContentType.objects.get_for_model(respondent)

    try:
        return QuestionnaireInstance.objects.filter(
            definition__slug=definition_slug,
            respondent_content_type=content_type,
            respondent_object_id=str(respondent.pk),
            deleted_at__isnull=True,
        ).order_by("-created_at").first()
    except QuestionnaireInstance.DoesNotExist:
        return None


def is_instance_valid(
    instance: QuestionnaireInstance,
    as_of_date: Any = None,
) -> bool:
    """Check if a questionnaire instance is valid.

    An instance is valid if:
    - Status is COMPLETED or CLEARED
    - Not expired (expires_at > as_of_date)

    Args:
        instance: The instance to check
        as_of_date: Date to check validity against (defaults to now)

    Returns:
        True if valid, False otherwise
    """
    instance.refresh_from_db()

    # Must be completed or cleared
    if instance.status not in [InstanceStatus.COMPLETED, InstanceStatus.CLEARED]:
        return False

    # Check expiration
    check_time = as_of_date or timezone.now()
    if instance.expires_at < check_time:
        return False

    return True


def get_flagged_questions(
    instance: QuestionnaireInstance,
) -> list[Question]:
    """Get all questions that triggered flags for an instance.

    Args:
        instance: The questionnaire instance

    Returns:
        List of Question objects that triggered flags
    """
    flagged_responses = instance.responses.filter(triggered_flag=True)
    return [r.question for r in flagged_responses]
