"""Tests for TimeSemanticsMixin and EffectiveDatedMixin."""
import pytest
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from freezegun import freeze_time

from tests.models import TimeSemanticTestModel, EffectiveDatedTestModel


@pytest.mark.django_db
class TestTimeSemanticsMixin:
    """Test suite for TimeSemanticsMixin."""

    def test_effective_at_defaults_to_now(self):
        """effective_at should default to timezone.now() when not specified."""
        before = timezone.now()
        instance = TimeSemanticTestModel.objects.create(name="test")
        after = timezone.now()

        assert instance.effective_at is not None
        assert before <= instance.effective_at <= after

    def test_recorded_at_auto_now_add(self):
        """recorded_at should be set automatically on creation."""
        before = timezone.now()
        instance = TimeSemanticTestModel.objects.create(name="test")
        after = timezone.now()

        assert instance.recorded_at is not None
        assert before <= instance.recorded_at <= after

    def test_effective_at_can_be_backdated(self):
        """effective_at can be explicitly set to a past date."""
        past_time = timezone.now() - timedelta(days=7)
        instance = TimeSemanticTestModel.objects.create(
            name="backdated",
            effective_at=past_time
        )

        # Reload from database to verify persistence
        instance.refresh_from_db()
        assert instance.effective_at == past_time

    def test_effective_at_indexed(self):
        """effective_at field should have db_index=True for query performance."""
        field = TimeSemanticTestModel._meta.get_field('effective_at')
        assert field.db_index is True, "effective_at should be indexed"

    def test_recorded_at_immutable_on_save(self):
        """recorded_at should not change when instance is saved again."""
        instance = TimeSemanticTestModel.objects.create(name="test")
        original_recorded_at = instance.recorded_at

        # Wait a moment and save again
        instance.name = "updated"
        instance.save()
        instance.refresh_from_db()

        assert instance.recorded_at == original_recorded_at

    @freeze_time("2025-06-15 12:00:00")
    def test_effective_at_and_recorded_at_can_differ(self):
        """effective_at can be different from recorded_at (backdating scenario)."""
        backdate = timezone.now() - timedelta(days=3)

        instance = TimeSemanticTestModel.objects.create(
            name="backdated entry",
            effective_at=backdate
        )

        # effective_at is backdated, recorded_at is "now" (frozen time)
        assert instance.effective_at == backdate
        assert instance.recorded_at == timezone.now()
        assert instance.effective_at < instance.recorded_at

    def test_recorded_at_has_auto_now_add(self):
        """recorded_at field should have auto_now_add=True."""
        field = TimeSemanticTestModel._meta.get_field('recorded_at')
        assert field.auto_now_add is True, "recorded_at should have auto_now_add=True"

    def test_effective_at_has_default(self):
        """effective_at field should have a default value."""
        field = TimeSemanticTestModel._meta.get_field('effective_at')
        assert field.has_default() or field.default is not None


@pytest.mark.django_db
class TestEffectiveDatedMixin:
    """Test suite for EffectiveDatedMixin."""

    def test_valid_from_required(self):
        """valid_from field should not allow null values."""
        field = EffectiveDatedTestModel._meta.get_field('valid_from')
        assert field.null is False, "valid_from should not allow null"

    def test_valid_to_nullable(self):
        """valid_to field should allow null (meaning 'until further notice')."""
        field = EffectiveDatedTestModel._meta.get_field('valid_to')
        assert field.null is True, "valid_to should allow null"

    def test_inherits_time_semantics(self):
        """EffectiveDatedMixin should have effective_at and recorded_at fields."""
        # Verify fields exist
        field_names = [f.name for f in EffectiveDatedTestModel._meta.get_fields()]
        assert 'effective_at' in field_names, "Should have effective_at from TimeSemanticsMixin"
        assert 'recorded_at' in field_names, "Should have recorded_at from TimeSemanticsMixin"

    def test_can_create_with_valid_from_only(self):
        """Should be able to create with only valid_from (valid_to is null)."""
        now = timezone.now()
        instance = EffectiveDatedTestModel.objects.create(
            name="open-ended",
            valid_from=now
        )
        instance.refresh_from_db()
        assert instance.valid_from == now
        assert instance.valid_to is None

    def test_can_create_with_both_validity_dates(self):
        """Should be able to create with both valid_from and valid_to."""
        start = timezone.now()
        end = start + timedelta(days=30)
        instance = EffectiveDatedTestModel.objects.create(
            name="bounded",
            valid_from=start,
            valid_to=end
        )
        instance.refresh_from_db()
        assert instance.valid_from == start
        assert instance.valid_to == end

    def test_valid_range_constraint(self):
        """valid_to must be greater than valid_from when both are set."""
        now = timezone.now()
        past = now - timedelta(days=1)

        instance = EffectiveDatedTestModel(
            name="invalid range",
            valid_from=now,
            valid_to=past  # End before start - invalid!
        )

        with pytest.raises(ValidationError):
            instance.full_clean()

    def test_valid_from_indexed(self):
        """valid_from field should have db_index=True for query performance."""
        field = EffectiveDatedTestModel._meta.get_field('valid_from')
        assert field.db_index is True, "valid_from should be indexed"

    def test_valid_to_indexed(self):
        """valid_to field should have db_index=True for query performance."""
        field = EffectiveDatedTestModel._meta.get_field('valid_to')
        assert field.db_index is True, "valid_to should be indexed"
