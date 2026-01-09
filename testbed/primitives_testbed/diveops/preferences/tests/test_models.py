"""Tests for diveops preferences models.

Tests cover:
- PreferenceDefinition creation and validation
- PartyPreference creation and value handling
- Unique constraint enforcement
- Value type conversions
"""

import pytest
from django.db import IntegrityError

from django_parties.models import Person

from ..models import (
    PreferenceDefinition,
    PartyPreference,
    ValueType,
    Sensitivity,
    Source,
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
def preference_definition(db):
    """Create a test preference definition."""
    return PreferenceDefinition.objects.create(
        key="diving.interests",
        label="Diving Interests",
        category="diving",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["reef", "wreck", "cenote", "cavern", "night"],
        sensitivity=Sensitivity.PUBLIC,
    )


@pytest.mark.django_db
class TestPreferenceDefinition:
    """Tests for PreferenceDefinition model."""

    def test_creation_with_required_fields(self, db):
        """PreferenceDefinition can be created with required fields."""
        definition = PreferenceDefinition.objects.create(
            key="demographics.language",
            label="Primary Language",
            category="demographics",
            value_type=ValueType.CHOICE,
        )
        assert definition.pk is not None
        assert definition.key == "demographics.language"
        assert definition.is_active is True
        assert definition.sensitivity == Sensitivity.INTERNAL

    def test_key_unique_constraint(self, preference_definition):
        """Key must be unique across definitions."""
        with pytest.raises(IntegrityError):
            PreferenceDefinition.objects.create(
                key="diving.interests",  # Same key
                label="Another Label",
                category="diving",
                value_type=ValueType.TEXT,
            )

    def test_choices_json_default_empty_list(self, db):
        """choices_json defaults to empty list."""
        definition = PreferenceDefinition.objects.create(
            key="diving.likes_photography",
            label="Likes Photography",
            category="diving",
            value_type=ValueType.BOOL,
        )
        assert definition.choices_json == []

    def test_soft_delete(self, preference_definition):
        """Soft delete sets deleted_at, doesn't hard delete."""
        pk = preference_definition.pk
        preference_definition.delete()

        # Should not be found via default manager
        assert not PreferenceDefinition.objects.filter(pk=pk).exists()

        # Should be found via all_objects
        assert PreferenceDefinition.all_objects.filter(pk=pk).exists()

    def test_str_representation(self, preference_definition):
        """String representation shows key."""
        assert str(preference_definition) == "diving.interests"


@pytest.mark.django_db
class TestPartyPreference:
    """Tests for PartyPreference model."""

    def test_creation_with_text_value(self, person, preference_definition):
        """PartyPreference can store text value."""
        pref = PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
            value_text="reef,wreck",
        )
        assert pref.pk is not None
        assert pref.value_text == "reef,wreck"
        assert pref.source == Source.SURVEY

    def test_creation_with_bool_value(self, db, person):
        """PartyPreference can store boolean value."""
        definition = PreferenceDefinition.objects.create(
            key="diving.likes_photography",
            label="Likes Photography",
            category="diving",
            value_type=ValueType.BOOL,
        )
        pref = PartyPreference.objects.create(
            person=person,
            definition=definition,
            value_bool=True,
        )
        assert pref.value_bool is True

    def test_creation_with_json_value(self, person, preference_definition):
        """PartyPreference can store JSON value for multi-choice."""
        pref = PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
            value_json=["reef", "wreck", "cenote"],
        )
        assert pref.value_json == ["reef", "wreck", "cenote"]

    def test_unique_constraint_person_definition(self, person, preference_definition):
        """Only one preference per person per definition."""
        PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
            value_text="reef",
        )
        with pytest.raises(IntegrityError):
            PartyPreference.objects.create(
                person=person,
                definition=preference_definition,
                value_text="wreck",
            )

    def test_set_value_bool(self, person, db):
        """set_value correctly sets boolean value."""
        definition = PreferenceDefinition.objects.create(
            key="test.bool_pref",
            label="Test Bool",
            category="test",
            value_type=ValueType.BOOL,
        )
        pref = PartyPreference.objects.create(
            person=person,
            definition=definition,
        )
        pref.set_value(True)
        pref.save()
        pref.refresh_from_db()
        assert pref.value_bool is True

    def test_set_value_text(self, person, db):
        """set_value correctly sets text value."""
        definition = PreferenceDefinition.objects.create(
            key="test.text_pref",
            label="Test Text",
            category="test",
            value_type=ValueType.TEXT,
        )
        pref = PartyPreference.objects.create(
            person=person,
            definition=definition,
        )
        pref.set_value("My favorite dive site is Coral Gardens")
        pref.save()
        pref.refresh_from_db()
        assert pref.value_text == "My favorite dive site is Coral Gardens"

    def test_set_value_multi_choice(self, person, preference_definition):
        """set_value correctly sets multi-choice as JSON."""
        pref = PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
        )
        pref.set_value(["reef", "night"])
        pref.save()
        pref.refresh_from_db()
        assert pref.value_json == ["reef", "night"]

    def test_get_value_returns_correct_type(self, person, db):
        """get_value returns value based on definition's value_type."""
        definition = PreferenceDefinition.objects.create(
            key="test.int_pref",
            label="Test Int",
            category="test",
            value_type=ValueType.INT,
        )
        pref = PartyPreference.objects.create(
            person=person,
            definition=definition,
            value_int=42,
        )
        assert pref.get_value() == 42

    def test_upsert_updates_existing(self, person, preference_definition):
        """Updating value_text on existing preference works."""
        pref = PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
            value_json=["reef"],
        )
        # Update the value
        pref.value_json = ["reef", "wreck"]
        pref.save()

        pref.refresh_from_db()
        assert pref.value_json == ["reef", "wreck"]

        # Only one record exists
        assert PartyPreference.objects.filter(
            person=person,
            definition=preference_definition,
        ).count() == 1

    def test_source_instance_tracking(self, person, preference_definition):
        """source_instance_id tracks questionnaire instance."""
        pref = PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
            value_json=["reef"],
            source=Source.SURVEY,
            source_instance_id="abc123-def456",
        )
        assert pref.source == Source.SURVEY
        assert pref.source_instance_id == "abc123-def456"

    def test_collected_at_auto_set(self, person, preference_definition):
        """collected_at is automatically set on creation."""
        pref = PartyPreference.objects.create(
            person=person,
            definition=preference_definition,
            value_json=["reef"],
        )
        assert pref.collected_at is not None
