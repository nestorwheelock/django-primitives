"""Preference models for progressive diver preference collection.

This module provides:
- PreferenceDefinition: Registry of preference keys with metadata
- PartyPreference: Actual preference values attached to Person

Preferences attach to Person (django-parties), not User or DiverProfile,
since Person is the canonical party identity.
"""

from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel


class ValueType(models.TextChoices):
    """Supported value types for preferences."""

    BOOL = "bool", "Boolean"
    INT = "int", "Integer"
    STR = "str", "String"
    TEXT = "text", "Text"
    CHOICE = "choice", "Single Choice"
    MULTI_CHOICE = "multi_choice", "Multiple Choice"
    DATE = "date", "Date"
    JSON = "json", "JSON"


class Sensitivity(models.TextChoices):
    """Sensitivity levels for preferences.

    - PUBLIC: Visible to all staff, can be shared
    - INTERNAL: Visible to staff, internal use only
    - SENSITIVE: Restricted access (manager/admin only)
    """

    PUBLIC = "public", "Public"
    INTERNAL = "internal", "Internal"
    SENSITIVE = "sensitive", "Sensitive"


class Source(models.TextChoices):
    """Source of how preference was collected."""

    SURVEY = "survey", "Survey/Questionnaire"
    STAFF = "staff", "Staff Entry"
    IMPORT = "import", "Data Import"
    SELF = "self", "Self-Service Entry"


class PreferenceDefinition(BaseModel):
    """Registry of preference keys with metadata.

    Defines the schema for a preference type including:
    - Unique key for programmatic access
    - Human-readable label
    - Category for grouping
    - Value type and valid choices
    - Sensitivity level for access control

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique key (e.g., 'diving.interests', 'food.dietary_restrictions')",
    )
    label = models.CharField(
        max_length=200,
        help_text="Human-readable label",
    )
    category = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Category for grouping (e.g., 'demographics', 'diving', 'food')",
    )
    value_type = models.CharField(
        max_length=20,
        choices=ValueType.choices,
        help_text="Data type for the preference value",
    )
    choices_json = models.JSONField(
        default=list,
        blank=True,
        help_text="Valid choices for choice/multi_choice types",
    )
    sensitivity = models.CharField(
        max_length=20,
        choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
        help_text="Access control level",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this preference is currently in use",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Display order within category",
    )

    class Meta:
        ordering = ["category", "sort_order", "key"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return self.key


class PartyPreference(BaseModel):
    """Actual preference value for a person.

    Stores the collected preference value attached to a Person.
    Uses typed value fields based on the definition's value_type.

    Only one value per person per definition is stored (unique constraint).
    Updates overwrite existing values.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at,
    objects (excludes deleted), all_objects (includes deleted).
    """

    person = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.CASCADE,
        related_name="preferences",
        help_text="The person this preference belongs to",
    )
    definition = models.ForeignKey(
        PreferenceDefinition,
        on_delete=models.PROTECT,
        related_name="values",
        help_text="The preference definition this value is for",
    )

    # Typed value storage - only one field is used based on value_type
    value_text = models.TextField(
        null=True,
        blank=True,
        help_text="Text/string value",
    )
    value_bool = models.BooleanField(
        null=True,
        blank=True,
        help_text="Boolean value",
    )
    value_int = models.IntegerField(
        null=True,
        blank=True,
        help_text="Integer value",
    )
    value_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date value",
    )
    value_json = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON value (for multi_choice, complex data)",
    )

    # Provenance tracking
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SURVEY,
        help_text="How this preference was collected",
    )
    source_instance_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Questionnaire instance ID if collected via survey",
    )
    collected_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this preference was collected/updated",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "definition"],
                name="unique_person_preference",
            ),
        ]
        indexes = [
            models.Index(fields=["person", "definition"]),
        ]

    def __str__(self):
        return f"{self.person} - {self.definition.key}"

    def set_value(self, value):
        """Set value based on definition's value_type.

        Args:
            value: The value to set, type depends on definition.value_type
        """
        vtype = self.definition.value_type

        # Clear all value fields first
        self.value_text = None
        self.value_bool = None
        self.value_int = None
        self.value_date = None
        self.value_json = None

        if vtype == ValueType.BOOL:
            self.value_bool = bool(value) if value is not None else None
        elif vtype == ValueType.INT:
            self.value_int = int(value) if value is not None else None
        elif vtype in (ValueType.STR, ValueType.TEXT, ValueType.CHOICE):
            self.value_text = str(value) if value is not None else None
        elif vtype == ValueType.DATE:
            self.value_date = value
        elif vtype in (ValueType.MULTI_CHOICE, ValueType.JSON):
            self.value_json = value

        self.collected_at = timezone.now()

    def get_value(self):
        """Get value based on definition's value_type.

        Returns:
            The stored value in the appropriate type
        """
        vtype = self.definition.value_type

        if vtype == ValueType.BOOL:
            return self.value_bool
        elif vtype == ValueType.INT:
            return self.value_int
        elif vtype in (ValueType.STR, ValueType.TEXT, ValueType.CHOICE):
            return self.value_text
        elif vtype == ValueType.DATE:
            return self.value_date
        elif vtype in (ValueType.MULTI_CHOICE, ValueType.JSON):
            return self.value_json
        return None
