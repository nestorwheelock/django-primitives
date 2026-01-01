"""Tests for Decision model."""
import pytest
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_decisioning.models import Decision
from tests.models import TimeSemanticTestModel

User = get_user_model()


@pytest.mark.django_db
class TestDecisionModel:
    """Test suite for Decision model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(username="testuser", password="testpass")

    @pytest.fixture
    def target_instance(self):
        """Create a test target instance."""
        return TimeSemanticTestModel.objects.create(name="target")

    def test_requires_at_least_one_actor(self, target_instance):
        """Decision must have at least one actor (user or party)."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        decision = Decision(
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="approve",
            snapshot={"data": "test"},
            # No actor_user or actor_party
        )

        with pytest.raises(ValidationError) as exc_info:
            decision.full_clean()

        # Should mention actor requirement
        assert "actor" in str(exc_info.value).lower()

    def test_actor_user_satisfies_requirement(self, user, target_instance):
        """actor_user alone satisfies the actor requirement."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        decision = Decision(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="approve",
            snapshot={"data": "test"},
        )

        # Should not raise
        decision.full_clean()
        decision.save()
        assert decision.pk is not None

    def test_target_id_is_charfield_for_uuid(self, user, target_instance):
        """target_id should be CharField to support UUIDs."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        # UUID-like string should work
        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id="550e8400-e29b-41d4-a716-446655440000",  # UUID format
            action="approve",
            snapshot={"data": "test"},
        )

        decision.refresh_from_db()
        assert decision.target_id == "550e8400-e29b-41d4-a716-446655440000"

        # Verify field type
        field = Decision._meta.get_field('target_id')
        assert field.max_length >= 255

    def test_snapshot_is_json(self, user, target_instance):
        """snapshot field should store JSON data."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        snapshot_data = {
            "basket_items": [
                {"sku": "ABC123", "qty": 2, "price": "10.00"},
                {"sku": "XYZ789", "qty": 1, "price": "25.00"},
            ],
            "total": "45.00",
            "captured_at": "2025-06-15T12:00:00Z"
        }

        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="commit",
            snapshot=snapshot_data,
        )

        decision.refresh_from_db()
        assert decision.snapshot == snapshot_data
        assert decision.snapshot["basket_items"][0]["sku"] == "ABC123"

    def test_finalized_at_marks_permanence(self, user, target_instance):
        """finalized_at should mark when decision became permanent."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="draft",
            snapshot={},
        )

        # Not finalized yet
        assert decision.is_final is False
        assert decision.finalized_at is None

        # Finalize
        decision.finalized_at = timezone.now()
        decision.save()

        decision.refresh_from_db()
        assert decision.is_final is True
        assert decision.finalized_at is not None

    def test_inherits_time_semantics(self, user, target_instance):
        """Decision should have effective_at and recorded_at fields."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        before = timezone.now()
        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="approve",
            snapshot={},
        )
        after = timezone.now()

        assert decision.effective_at is not None
        assert decision.recorded_at is not None
        assert before <= decision.effective_at <= after
        assert before <= decision.recorded_at <= after

    def test_action_required(self, user, target_instance):
        """action field should be required (not blank)."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        decision = Decision(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="",  # Empty action
            snapshot={},
        )

        with pytest.raises(ValidationError):
            decision.full_clean()

    def test_effective_at_can_be_backdated(self, user, target_instance):
        """effective_at can be set to a past date (backdating)."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)
        past = timezone.now() - timedelta(days=7)

        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="record",
            snapshot={},
            effective_at=past,
        )

        decision.refresh_from_db()
        assert decision.effective_at == past

    def test_outcome_stores_result_reference(self, user, target_instance):
        """outcome field should store result reference as JSON."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        outcome_data = {
            "work_items_created": ["wi-001", "wi-002"],
            "notifications_sent": 3
        }

        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="commit",
            snapshot={},
            outcome=outcome_data,
        )

        decision.refresh_from_db()
        assert decision.outcome == outcome_data

    def test_authority_context_stores_role_info(self, user, target_instance):
        """authority_context should store role/org snapshot."""
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        authority = {
            "role": "manager",
            "org_id": "org-123",
            "permissions": ["approve", "reject"]
        }

        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target_instance.pk),
            action="approve",
            snapshot={},
            authority_context=authority,
        )

        decision.refresh_from_db()
        assert decision.authority_context == authority
