"""Relationship models for DiveOps.

This module contains models for managing relationships between divers
and their emergency contacts:
- EmergencyContact: Emergency contact for a diver
- DiverRelationship: Relationship between two divers (bidirectional)
- DiverRelationshipMeta: DiveOps extension metadata for PartyRelationship
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from django_basemodels import BaseModel


class EmergencyContact(BaseModel):
    """Emergency contact for a diver.

    Links to a Person from django-parties. Supports multiple contacts
    with priority ordering. If the emergency contact is also a diver,
    a secondary contact should be added for situations where both
    might be on the same trip (e.g., spouses who dive together).

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("parent", "Parent"),
        ("child", "Child (Adult)"),
        ("sibling", "Sibling"),
        ("friend", "Friend"),
        ("other_family", "Other Family Member"),
        ("employer", "Employer"),
        ("other", "Other"),
    ]

    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.CASCADE,
        related_name="emergency_contact_entries",
    )
    contact_person = models.ForeignKey(
        "django_parties.Person",
        on_delete=models.PROTECT,
        related_name="emergency_contact_for",
        help_text="The person to contact in an emergency",
    )
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        help_text="Relationship to the diver",
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
        help_text="Contact priority (1 = primary, 2 = secondary, etc.)",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes (e.g., 'Also a diver - may be on same trip')",
    )

    class Meta:
        ordering = ["diver", "priority"]
        constraints = [
            # Unique priority per diver (no duplicate priorities)
            models.UniqueConstraint(
                fields=["diver", "priority"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_emergency_contact_priority",
            ),
        ]
        indexes = [
            models.Index(fields=["diver", "priority"]),
        ]

    def __str__(self):
        return f"{self.contact_person} ({self.get_relationship_display()}) for {self.diver.person}"

    @property
    def is_also_diver(self) -> bool:
        """Check if the emergency contact is also a registered diver."""
        return hasattr(self.contact_person, "diver_profile") and \
               self.contact_person.diver_profile is not None and \
               self.contact_person.diver_profile.deleted_at is None

    def would_be_on_excursion(self, excursion) -> bool:
        """Check if this emergency contact is on a specific excursion roster.

        Use this to warn when both diver and emergency contact are on the
        same trip (e.g., spouses who dive together need a third contact).
        """
        from .._models_all import ExcursionRoster

        if not self.is_also_diver:
            return False
        # Check if the contact's diver profile is on this excursion
        return ExcursionRoster.objects.filter(
            excursion=excursion,
            diver=self.contact_person.diver_profile,
            deleted_at__isnull=True,
        ).exists()


class DiverRelationship(BaseModel):
    """Relationship between two divers.

    Tracks social and diving connections between divers:
    - Spouses/partners who dive together
    - Regular dive buddies
    - Friends who travel together
    - Family members

    Relationships are bidirectional - creating one creates the inverse.
    Used for buddy pairing suggestions and group management.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("buddy", "Dive Buddy"),
        ("friend", "Friend"),
        ("family", "Family Member"),
        ("instructor_student", "Instructor/Student"),
        ("travel_companion", "Travel Companion"),
    ]

    from_diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.CASCADE,
        related_name="relationships_from",
    )
    to_diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.CASCADE,
        related_name="relationships_to",
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
    )
    is_preferred_buddy = models.BooleanField(
        default=False,
        help_text="Prefer to pair these divers together",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["from_diver", "relationship_type"]
        constraints = [
            # No duplicate relationships (same pair, same type)
            models.UniqueConstraint(
                fields=["from_diver", "to_diver", "relationship_type"],
                condition=Q(deleted_at__isnull=True),
                name="diveops_unique_diver_relationship",
            ),
            # Can't have relationship with self
            models.CheckConstraint(
                condition=~Q(from_diver=models.F("to_diver")),
                name="diveops_no_self_relationship",
            ),
        ]
        indexes = [
            models.Index(fields=["from_diver", "to_diver"]),
            models.Index(fields=["relationship_type"]),
        ]

    def __str__(self):
        return f"{self.from_diver.person} - {self.get_relationship_type_display()} - {self.to_diver.person}"

    @classmethod
    def get_or_create_bidirectional(cls, diver1, diver2, relationship_type, **kwargs):
        """Create relationship in both directions."""
        rel1, created1 = cls.objects.get_or_create(
            from_diver=diver1,
            to_diver=diver2,
            relationship_type=relationship_type,
            defaults=kwargs,
        )
        rel2, created2 = cls.objects.get_or_create(
            from_diver=diver2,
            to_diver=diver1,
            relationship_type=relationship_type,
            defaults=kwargs,
        )
        return rel1, rel2, created1 or created2


class DiverRelationshipMeta(BaseModel):
    """DiveOps extension metadata for PartyRelationship.

    Adds dive-specific fields to the canonical django-parties PartyRelationship.
    This follows the primitives architecture: use PartyRelationship for identity
    relationships, extend with domain-specific metadata.

    See: docs/ADR-001-RELATIONSHIP-CONSOLIDATION.md

    Fields extended:
    - priority: For emergency contact ordering (1=primary, 2=secondary, etc.)
    - is_preferred_buddy: For pairing divers together on excursions
    - notes: Dive-specific notes (e.g., "prefers morning dives")

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    party_relationship = models.OneToOneField(
        "django_parties.PartyRelationship",
        on_delete=models.CASCADE,
        related_name="diver_meta",
        help_text="The canonical PartyRelationship being extended",
    )

    # Emergency contact ordering
    priority = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Contact priority (1=primary, 2=secondary). Only for emergency_contact type.",
    )

    # Dive buddy pairing
    is_preferred_buddy = models.BooleanField(
        default=False,
        help_text="Prefer to pair these divers together on excursions",
    )

    # Dive-specific notes (separate from PartyRelationship.title)
    notes = models.TextField(
        blank=True,
        help_text="Dive-specific notes about this relationship",
    )

    class Meta:
        verbose_name = "Diver Relationship Metadata"
        verbose_name_plural = "Diver Relationship Metadata"
        constraints = [
            # Priority only makes sense for emergency contacts
            # (can't enforce at DB level which relationship_type, but we validate in clean())
        ]
        indexes = [
            models.Index(fields=["priority"]),
            models.Index(fields=["is_preferred_buddy"]),
        ]

    def __str__(self):
        return f"DiverMeta for {self.party_relationship}"

    def clean(self):
        """Validate business rules."""
        super().clean()
        # Priority is only meaningful for emergency_contact relationships
        if self.priority is not None:
            if self.party_relationship.relationship_type != "emergency_contact":
                raise ValidationError(
                    {"priority": "Priority is only valid for emergency contact relationships."}
                )
