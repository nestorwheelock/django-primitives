"""Models for django-questionnaires.

Domain-agnostic questionnaire models for managing versioned questionnaire
definitions, instances, and responses.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel


class DefinitionStatus(models.TextChoices):
    """Status choices for questionnaire definitions."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class QuestionType(models.TextChoices):
    """Question type choices."""

    YES_NO = "yes_no", "Yes/No"
    TEXT = "text", "Text"
    NUMBER = "number", "Number"
    DATE = "date", "Date"
    CHOICE = "choice", "Single Choice"
    MULTI_CHOICE = "multi_choice", "Multiple Choice"


class InstanceStatus(models.TextChoices):
    """Status choices for questionnaire instances."""

    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FLAGGED = "flagged", "Flagged"
    CLEARED = "cleared", "Cleared"
    EXPIRED = "expired", "Expired"


class QuestionnaireDefinition(BaseModel):
    """Versioned template for a questionnaire.

    Represents a reusable questionnaire template that can be versioned
    and published. Once published, the definition should not be modified
    (create a new version instead).

    Attributes:
        slug: Unique identifier among active (non-archived) definitions
        name: Human-readable name
        description: Detailed description of the questionnaire purpose
        version: Semantic version string (e.g., "1.0.0")
        status: Current status (draft, published, archived)
        validity_days: How long responses remain valid (null = forever)
        metadata: Arbitrary JSON data for domain-specific configuration
    """

    slug = models.SlugField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    version = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=DefinitionStatus.choices,
        default=DefinitionStatus.DRAFT,
    )
    validity_days = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(deleted_at__isnull=True)
                & ~models.Q(status="archived"),
                name="unique_active_definition_slug",
            ),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"


class Question(BaseModel):
    """Individual question within a questionnaire definition.

    Represents a single question with its configuration including
    type, validation rules, and flag behavior.

    Attributes:
        definition: Parent questionnaire definition
        sequence: Order within the questionnaire
        category: Grouping category for UI organization
        question_type: Type of question (yes_no, text, etc.)
        question_text: The actual question text
        help_text: Optional help text for respondents
        is_required: Whether the question must be answered
        triggers_flag: Whether certain answers should flag the instance
        choices: JSON list of choices for choice types
        validation_rules: JSON validation configuration
    """

    definition = models.ForeignKey(
        QuestionnaireDefinition,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    sequence = models.PositiveIntegerField()
    category = models.CharField(max_length=100, blank=True, default="")
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    question_text = models.TextField()
    help_text = models.TextField(blank=True, default="")
    is_required = models.BooleanField(default=True)
    triggers_flag = models.BooleanField(default=False)
    choices = models.JSONField(default=list, blank=True)
    validation_rules = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "sequence"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_question_sequence",
            ),
        ]

    def __str__(self):
        return f"Q{self.sequence}: {self.question_text[:50]}"


class QuestionnaireInstance(BaseModel):
    """Instance of a questionnaire sent to a respondent.

    Represents a specific questionnaire sent to a respondent
    (any model via GenericFK). Tracks the completion status,
    clearance workflow, and expiration.

    Attributes:
        definition: The questionnaire definition this instance is based on
        definition_version: Snapshot of version at time of creation
        respondent: GenericFK to any model that is filling out the questionnaire
        status: Current status (pending, completed, flagged, cleared, expired)
        expires_at: When this instance expires
        completed_at: When the respondent completed the questionnaire
        flagged_at: When the instance was flagged
        cleared_at: When a flagged instance was cleared
        cleared_by: Who cleared the flagged instance
        clearance_notes: Notes about the clearance
        clearance_document: GenericFK to optional attached document
    """

    definition = models.ForeignKey(
        QuestionnaireDefinition,
        on_delete=models.PROTECT,
        related_name="instances",
    )
    definition_version = models.CharField(max_length=20)

    # GenericFK for respondent (can be any model)
    respondent_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="questionnaire_instances",
    )
    respondent_object_id = models.CharField(max_length=255)
    respondent = GenericForeignKey("respondent_content_type", "respondent_object_id")

    status = models.CharField(
        max_length=20,
        choices=InstanceStatus.choices,
        default=InstanceStatus.PENDING,
    )
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    flagged_at = models.DateTimeField(null=True, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)
    cleared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cleared_questionnaires",
    )
    clearance_notes = models.TextField(blank=True, default="")

    # GenericFK for clearance document (optional)
    clearance_document_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clearance_documents",
    )
    clearance_document_object_id = models.CharField(max_length=255, blank=True, default="")
    clearance_document = GenericForeignKey(
        "clearance_document_content_type",
        "clearance_document_object_id",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["respondent_content_type", "respondent_object_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Instance of {self.definition.slug} ({self.status})"

    @property
    def is_expired(self):
        """Check if this instance has expired."""
        return timezone.now() > self.expires_at


class Response(BaseModel):
    """Individual answer to a question.

    Stores the respondent's answer to a specific question.
    Uses typed fields for different answer types.

    Attributes:
        instance: The questionnaire instance this response belongs to
        question: The question being answered
        answer_text: Text answer (for text questions)
        answer_bool: Boolean answer (for yes/no questions)
        answer_date: Date answer (for date questions)
        answer_number: Numeric answer (for number questions)
        answer_choices: List of selected choices (for choice questions)
        triggered_flag: Whether this answer triggered a flag
    """

    instance = models.ForeignKey(
        QuestionnaireInstance,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="responses",
    )
    answer_text = models.TextField(null=True, blank=True)
    answer_bool = models.BooleanField(null=True, blank=True)
    answer_date = models.DateField(null=True, blank=True)
    answer_number = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
    )
    answer_choices = models.JSONField(null=True, blank=True)
    triggered_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ["question__sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["instance", "question"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_response_per_question",
            ),
        ]

    def __str__(self):
        return f"Response to Q{self.question.sequence}"
