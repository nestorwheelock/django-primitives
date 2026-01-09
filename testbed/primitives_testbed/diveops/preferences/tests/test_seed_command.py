"""Tests for seed_preferences management command.

Tests cover:
- Command creates all MVP preference definitions
- Command is idempotent (can run multiple times safely)
- Correct categories and value types
"""

import pytest
from django.core.management import call_command

from ..models import PreferenceDefinition, ValueType, Sensitivity


@pytest.mark.django_db
class TestSeedPreferencesCommand:
    """Tests for seed_preferences management command."""

    def test_command_creates_definitions(self, db):
        """Command creates preference definitions."""
        assert PreferenceDefinition.objects.count() == 0

        call_command("seed_preferences")

        # Should have created multiple definitions
        assert PreferenceDefinition.objects.count() > 0

    def test_command_is_idempotent(self, db):
        """Running command twice produces same result."""
        call_command("seed_preferences")
        count1 = PreferenceDefinition.objects.count()

        call_command("seed_preferences")
        count2 = PreferenceDefinition.objects.count()

        assert count1 == count2

    def test_creates_demographics_category(self, db):
        """Command creates demographics preferences."""
        call_command("seed_preferences")

        demographics = PreferenceDefinition.objects.filter(category="demographics")
        assert demographics.count() >= 2

        # Check language preference exists
        lang = PreferenceDefinition.objects.filter(key="demographics.language_primary").first()
        assert lang is not None
        assert lang.value_type == ValueType.CHOICE

    def test_creates_diving_category(self, db):
        """Command creates diving preferences."""
        call_command("seed_preferences")

        diving = PreferenceDefinition.objects.filter(category="diving")
        assert diving.count() >= 4

        # Check interests preference exists
        interests = PreferenceDefinition.objects.filter(key="diving.interests").first()
        assert interests is not None
        assert interests.value_type == ValueType.MULTI_CHOICE
        assert len(interests.choices_json) > 0

    def test_creates_food_category(self, db):
        """Command creates food preferences."""
        call_command("seed_preferences")

        food = PreferenceDefinition.objects.filter(category="food")
        assert food.count() >= 1

        # Check dietary restrictions exists
        dietary = PreferenceDefinition.objects.filter(key="food.dietary_restrictions").first()
        assert dietary is not None
        assert dietary.value_type == ValueType.MULTI_CHOICE

    def test_creates_goals_category(self, db):
        """Command creates goals preferences."""
        call_command("seed_preferences")

        goals = PreferenceDefinition.objects.filter(category="goals")
        assert goals.count() >= 1

    def test_sensitive_fields_marked_correctly(self, db):
        """Sensitive fields have correct sensitivity level."""
        call_command("seed_preferences")

        # Gender should be sensitive
        gender = PreferenceDefinition.objects.filter(key="demographics.gender").first()
        assert gender is not None
        assert gender.sensitivity == Sensitivity.SENSITIVE

        # Allergies should be sensitive
        allergies = PreferenceDefinition.objects.filter(key="food.allergies").first()
        assert allergies is not None
        assert allergies.sensitivity == Sensitivity.SENSITIVE

    def test_public_fields_marked_correctly(self, db):
        """Public fields have correct sensitivity level."""
        call_command("seed_preferences")

        # Diving interests should be public
        interests = PreferenceDefinition.objects.filter(key="diving.interests").first()
        assert interests is not None
        assert interests.sensitivity == Sensitivity.PUBLIC

    def test_all_definitions_active(self, db):
        """All seeded definitions are active by default."""
        call_command("seed_preferences")

        inactive = PreferenceDefinition.objects.filter(is_active=False).count()
        assert inactive == 0
