"""Models for django-encounters.

Provides:
- EncounterDefinition: Define reusable state machine graphs
- Encounter: Instance attached to any subject via GenericFK
- EncounterTransition: Audit log of all state changes
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel
from django_decisioning.querysets import EventAsOfQuerySet

from .exceptions import ImmutableTransitionError
from .graph import validate_definition_graph


class EncountersBaseModel(BaseModel):
    """Base model for encounters - extends django_basemodels.BaseModel.

    Provides: UUID PK, created_at, updated_at, deleted_at, soft delete.
    """

    class Meta:
        abstract = True


class EncounterDefinition(EncountersBaseModel):
    """
    Defines a reusable state machine graph.

    Each definition represents a type of encounter workflow.
    Examples: "repair_job", "legal_case", "medical_visit"
    """

    key = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for this definition (e.g., 'repair_job')"
    )
    name = models.CharField(
        max_length=200,
        help_text="Human-readable name"
    )
    states = models.JSONField(
        help_text="List of valid state names"
    )
    transitions = models.JSONField(
        help_text="Dict mapping state -> list of reachable states"
    )
    initial_state = models.CharField(
        max_length=100,
        help_text="Starting state for new encounters"
    )
    terminal_states = models.JSONField(
        help_text="States that end the encounter (no outgoing transitions)"
    )
    validator_paths = models.JSONField(
        default=list,
        blank=True,
        help_text="List of dotted paths to validator classes"
    )
    active = models.BooleanField(
        default=True,
        help_text="Whether this definition can be used for new encounters"
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.key})"

    def clean(self):
        """Validate the state machine graph."""
        errors = validate_definition_graph(
            states=self.states or [],
            transitions=self.transitions or {},
            initial_state=self.initial_state or "",
            terminal_states=self.terminal_states or [],
        )
        if errors:
            raise ValidationError({"__all__": errors})


class Encounter(EncountersBaseModel):
    """
    A single encounter instance following a definition.

    Attached to any subject via GenericFK (patient, asset, case, etc.)
    """

    definition = models.ForeignKey(
        EncounterDefinition,
        on_delete=models.PROTECT,
        related_name="encounters",
        help_text="The definition this encounter follows"
    )

    # GenericFK for truly domain-agnostic subject attachment
    subject_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        help_text="Content type of the subject"
    )
    subject_id = models.CharField(
        max_length=255,
        help_text="Primary key of the subject (supports UUID and integer PKs)"
    )
    subject = GenericForeignKey("subject_type", "subject_id")

    state = models.CharField(
        max_length=100,
        help_text="Current state in the workflow"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_encounters",
        help_text="User who created this encounter"
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the encounter was created"
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the encounter reached a terminal state"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Domain package extensions only"
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["definition", "state"]),
            models.Index(fields=["subject_type", "subject_id"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self):
        return f"{self.definition.name} - {self.state}"


class EncounterTransition(EncountersBaseModel):
    """
    Audit log of all state changes.

    Records who changed the state, when, and any metadata.

    Time semantics:
    - effective_at: When the transition happened in business terms (can be backdated)
    - recorded_at: When the system learned about this transition (immutable)
    """

    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.CASCADE,
        related_name="transitions",
        help_text="The encounter that was transitioned"
    )
    from_state = models.CharField(
        max_length=100,
        help_text="State before transition"
    )
    to_state = models.CharField(
        max_length=100,
        help_text="State after transition"
    )
    transitioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encounter_transitions",
        help_text="User who performed the transition"
    )
    transitioned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the transition occurred"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Overrides, notes, validator responses"
    )

    # Time semantics
    effective_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the transition happened in business terms",
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the system learned about this transition",
    )

    objects = EventAsOfQuerySet.as_manager()

    class Meta:
        ordering = ["-transitioned_at"]
        indexes = [
            models.Index(fields=["encounter", "-transitioned_at"]),
            models.Index(fields=["effective_at"]),
        ]

    def save(self, *args, **kwargs):
        """Enforce immutability - transitions are audit records."""
        # Check if this is an update to an existing record (not a new insert)
        if not self._state.adding:
            raise ImmutableTransitionError(self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.encounter}: {self.from_state} -> {self.to_state}"
