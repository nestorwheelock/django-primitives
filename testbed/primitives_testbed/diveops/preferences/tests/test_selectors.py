"""Tests for preference selectors.

Tests cover:
- get_diver_preference_status: Get preference completion status for a diver
- list_diver_preferences_by_category: Get preferences grouped by category
"""

import pytest
from django_parties.models import Person

from ..models import PreferenceDefinition, PartyPreference, ValueType, Sensitivity
from ..selectors import (
    get_diver_preference_status,
    list_diver_preferences_by_category,
)
from ...models import DiverProfile


@pytest.fixture
def person(db):
    """Create a test person."""
    return Person.objects.create(
        first_name="Test",
        last_name="Diver",
        email="test@example.com",
    )


@pytest.fixture
def diver(person, db):
    """Create a test diver profile."""
    return DiverProfile.objects.create(
        person=person,
    )


@pytest.fixture
def preference_definitions(db):
    """Create MVP preference definitions."""
    defs = []
    # Diving preferences
    defs.append(PreferenceDefinition.objects.create(
        key="diving.interests",
        label="Diving Interests",
        category="diving",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["Reef", "Wreck", "Cenote"],
        sensitivity=Sensitivity.PUBLIC,
        sort_order=1,
    ))
    defs.append(PreferenceDefinition.objects.create(
        key="diving.experience_level",
        label="Experience Level",
        category="diving",
        value_type=ValueType.CHOICE,
        choices_json=["Beginner", "Intermediate", "Advanced"],
        sensitivity=Sensitivity.PUBLIC,
        sort_order=2,
    ))
    # Food preferences
    defs.append(PreferenceDefinition.objects.create(
        key="food.dietary_restrictions",
        label="Dietary Restrictions",
        category="food",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["Vegetarian", "Vegan", "None"],
        sensitivity=Sensitivity.INTERNAL,
        sort_order=1,
    ))
    defs.append(PreferenceDefinition.objects.create(
        key="food.allergies",
        label="Food Allergies",
        category="food",
        value_type=ValueType.TEXT,
        sensitivity=Sensitivity.SENSITIVE,
        sort_order=2,
    ))
    # Demographics
    defs.append(PreferenceDefinition.objects.create(
        key="demographics.language_primary",
        label="Primary Language",
        category="demographics",
        value_type=ValueType.CHOICE,
        choices_json=["English", "Spanish", "French"],
        sensitivity=Sensitivity.INTERNAL,
        sort_order=1,
    ))
    return defs


@pytest.mark.django_db
class TestGetDiverPreferenceStatus:
    """Tests for get_diver_preference_status selector."""

    def test_returns_status_dict(self, diver, preference_definitions):
        """Returns dict with expected keys."""
        status = get_diver_preference_status(diver)

        assert "total_definitions" in status
        assert "collected_count" in status
        assert "missing_count" in status
        assert "completion_percent" in status
        assert "categories" in status
        assert "needs_intake_survey" in status

    def test_shows_no_preferences_collected_initially(self, diver, preference_definitions):
        """Shows 0% completion when no preferences collected."""
        status = get_diver_preference_status(diver)

        assert status["collected_count"] == 0
        assert status["missing_count"] == 5
        assert status["completion_percent"] == 0

    def test_shows_partial_completion(self, diver, preference_definitions):
        """Shows partial completion when some preferences collected."""
        # Collect 2 of 5 preferences
        for pdef in preference_definitions[:2]:
            PartyPreference.objects.create(
                person=diver.person,
                definition=pdef,
                value_text="test",
            )

        status = get_diver_preference_status(diver)

        assert status["collected_count"] == 2
        assert status["missing_count"] == 3
        assert status["completion_percent"] == 40

    def test_shows_full_completion(self, diver, preference_definitions):
        """Shows 100% completion when all preferences collected."""
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=diver.person,
                definition=pdef,
                value_text="test",
            )

        status = get_diver_preference_status(diver)

        assert status["collected_count"] == 5
        assert status["missing_count"] == 0
        assert status["completion_percent"] == 100

    def test_needs_intake_survey_when_incomplete(self, diver, preference_definitions):
        """needs_intake_survey is True when preferences not all collected."""
        status = get_diver_preference_status(diver)

        assert status["needs_intake_survey"] is True

    def test_no_intake_survey_needed_when_complete(self, diver, preference_definitions):
        """needs_intake_survey is False when all preferences collected."""
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=diver.person,
                definition=pdef,
                value_text="test",
            )

        status = get_diver_preference_status(diver)

        assert status["needs_intake_survey"] is False

    def test_categories_shows_breakdown(self, diver, preference_definitions):
        """Categories dict shows breakdown by category."""
        # Collect all diving preferences
        for pdef in preference_definitions:
            if pdef.category == "diving":
                PartyPreference.objects.create(
                    person=diver.person,
                    definition=pdef,
                    value_text="test",
                )

        status = get_diver_preference_status(diver)

        assert "diving" in status["categories"]
        assert "food" in status["categories"]
        assert "demographics" in status["categories"]

        assert status["categories"]["diving"]["collected"] == 2
        assert status["categories"]["diving"]["total"] == 2
        assert status["categories"]["diving"]["complete"] is True

        assert status["categories"]["food"]["collected"] == 0
        assert status["categories"]["food"]["total"] == 2
        assert status["categories"]["food"]["complete"] is False

    def test_handles_no_definitions(self, diver, db):
        """Handles case where no preference definitions exist."""
        # No definitions created
        status = get_diver_preference_status(diver)

        assert status["total_definitions"] == 0
        assert status["collected_count"] == 0
        assert status["completion_percent"] == 100  # Nothing to collect = complete
        assert status["needs_intake_survey"] is False


@pytest.mark.django_db
class TestListDiverPreferencesByCategory:
    """Tests for list_diver_preferences_by_category selector."""

    def test_returns_dict_grouped_by_category(self, diver, preference_definitions):
        """Returns preferences grouped by category."""
        # Collect some preferences
        for pdef in preference_definitions[:3]:
            PartyPreference.objects.create(
                person=diver.person,
                definition=pdef,
                value_json=["Test Value"],
            )

        result = list_diver_preferences_by_category(diver)

        assert "diving" in result
        assert "food" in result
        assert "demographics" not in result  # No preference collected

    def test_each_category_has_preferences_list(self, diver, preference_definitions):
        """Each category contains a list of preference data."""
        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions[0],  # diving.interests
            value_json=["Reef", "Cenote"],
        )

        result = list_diver_preferences_by_category(diver)

        assert len(result["diving"]) == 1
        pref_data = result["diving"][0]
        assert pref_data["key"] == "diving.interests"
        assert pref_data["label"] == "Diving Interests"
        assert pref_data["value"] == ["Reef", "Cenote"]

    def test_excludes_sensitive_by_default(self, diver, preference_definitions):
        """Sensitive preferences excluded by default."""
        # Create preferences including sensitive one
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=diver.person,
                definition=pdef,
                value_text="test",
            )

        result = list_diver_preferences_by_category(diver)

        # Check that food.allergies (sensitive) is not included
        if "food" in result:
            keys = [p["key"] for p in result["food"]]
            assert "food.allergies" not in keys

    def test_includes_sensitive_when_requested(self, diver, preference_definitions):
        """Sensitive preferences included when include_sensitive=True."""
        # Create preferences including sensitive one
        for pdef in preference_definitions:
            PartyPreference.objects.create(
                person=diver.person,
                definition=pdef,
                value_text="test",
            )

        result = list_diver_preferences_by_category(diver, include_sensitive=True)

        assert "food" in result
        keys = [p["key"] for p in result["food"]]
        assert "food.allergies" in keys

    def test_returns_empty_dict_when_no_preferences(self, diver, preference_definitions):
        """Returns empty dict when diver has no preferences."""
        result = list_diver_preferences_by_category(diver)

        assert result == {}

    def test_orders_by_sort_order_within_category(self, diver, preference_definitions):
        """Preferences are ordered by sort_order within each category."""
        # Create both diving preferences
        for pdef in preference_definitions:
            if pdef.category == "diving":
                PartyPreference.objects.create(
                    person=diver.person,
                    definition=pdef,
                    value_text="test",
                )

        result = list_diver_preferences_by_category(diver)

        # diving.interests has sort_order=1, diving.experience_level has sort_order=2
        assert result["diving"][0]["key"] == "diving.interests"
        assert result["diving"][1]["key"] == "diving.experience_level"
