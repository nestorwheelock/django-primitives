"""Integration and torture tests for django-decisioning."""
import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_decisioning.decorators import idempotent
from django_decisioning.models import IdempotencyKey, Decision
from django_decisioning.mixins import TimeSemanticsMixin
from django_decisioning.querysets import EventAsOfQuerySet
from django_decisioning.utils import TargetRef
from tests.models import TimeSemanticTestModel, EventTestModel

User = get_user_model()


@pytest.mark.django_db
class TestIdempotencyTortureTests:
    """Torture tests for idempotency."""

    def test_retry_same_request_3x_one_effect(self):
        """Retry test: same request 3x -> exactly one effect."""
        effect_count = 0
        created_items = []

        @idempotent(scope="torture_test", key_from=lambda request_id: request_id)
        def create_work_item(request_id):
            nonlocal effect_count
            effect_count += 1
            item = TimeSemanticTestModel.objects.create(name=f"item-{request_id}")
            created_items.append(item.pk)
            return {"created_id": str(item.pk)}

        # Call 3 times with same request_id
        result1 = create_work_item("req-123")
        result2 = create_work_item("req-123")
        result3 = create_work_item("req-123")

        # Exactly one effect (one item created)
        assert effect_count == 1
        assert len(created_items) == 1
        assert TimeSemanticTestModel.objects.filter(name__startswith="item-req-123").count() == 1

        # All results are identical
        assert result1 == result2 == result3
        assert result1["created_id"] == str(created_items[0])

    def test_failed_request_can_be_retried(self):
        """Failed operations should allow retry with different outcome."""
        attempt_count = 0

        @idempotent(scope="retry_test", key_from=lambda request_id, should_fail=False: request_id)
        def flaky_operation(request_id, should_fail=False):
            nonlocal attempt_count
            attempt_count += 1
            if should_fail:
                raise ValueError("Simulated failure")
            return {"success": True, "attempt": attempt_count}

        # First attempt fails
        with pytest.raises(ValueError):
            flaky_operation("flaky-req", should_fail=True)

        # Verify failure was recorded
        idem = IdempotencyKey.objects.get(scope="retry_test", key="flaky-req")
        assert idem.state == IdempotencyKey.State.FAILED

        # Second attempt succeeds
        result = flaky_operation("flaky-req", should_fail=False)

        assert result["success"] is True
        assert attempt_count == 2  # Both attempts executed

        # Verify success was recorded
        idem.refresh_from_db()
        assert idem.state == IdempotencyKey.State.SUCCEEDED


@pytest.mark.django_db
class TestTimeSemanticsIntegration:
    """Integration tests for time semantics."""

    def test_backdate_coherent(self):
        """Backdate test: effective yesterday, recorded today -> coherent."""
        now = timezone.now()
        yesterday = now - timedelta(days=1)

        # Create event with backdated effective_at
        event = EventTestModel.objects.create(
            name="backdated_event",
            effective_at=yesterday
        )

        # Verify recorded_at is approximately now
        assert event.recorded_at is not None
        assert event.recorded_at >= now - timedelta(seconds=5)

        # Verify effective_at is yesterday
        assert event.effective_at == yesterday

        # Query as of now should include the event
        results_now = EventTestModel.objects.as_of(now)
        assert event in results_now

        # Query as of before the effective date should exclude
        before_event = yesterday - timedelta(hours=1)
        results_before = EventTestModel.objects.as_of(before_event)
        assert event not in results_before

    def test_as_of_query_consistency(self):
        """Time queries should be consistent and reproducible."""
        now = timezone.now()

        # Create events at different effective times
        events = []
        for i in range(5):
            event = EventTestModel.objects.create(
                name=f"event_{i}",
                effective_at=now - timedelta(days=i)
            )
            events.append(event)

        # Query as of 2 days ago should return events 2, 3, 4
        two_days_ago = now - timedelta(days=2)
        results = list(EventTestModel.objects.as_of(two_days_ago))

        assert events[2] in results  # 2 days ago
        assert events[3] in results  # 3 days ago
        assert events[4] in results  # 4 days ago
        assert events[0] not in results  # today
        assert events[1] not in results  # yesterday


@pytest.mark.django_db
class TestDecisionIntegration:
    """Integration tests for Decision model."""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="decision_user", password="test")

    @pytest.fixture
    def delegate_user(self):
        return User.objects.create_user(username="delegate", password="test")

    def test_delegation_captured(self, user, delegate_user):
        """Delegation test: actor vs on_behalf_of captured."""
        target = TimeSemanticTestModel.objects.create(name="delegation_target")
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        # User makes decision on behalf of delegate
        decision = Decision.objects.create(
            actor_user=user,  # The person who entered it
            on_behalf_of_user=delegate_user,  # The person who authorized it
            target_type=content_type,
            target_id=str(target.pk),
            action="approve",
            snapshot={"approved_by": user.username, "for": delegate_user.username},
            authority_context={
                "acting_role": "clerk",
                "delegated_from": "manager"
            }
        )

        decision.refresh_from_db()

        # Both actors are captured
        assert decision.actor_user == user
        assert decision.on_behalf_of_user == delegate_user

        # Authority context preserved
        assert decision.authority_context["acting_role"] == "clerk"
        assert decision.authority_context["delegated_from"] == "manager"

    def test_snapshot_immutability(self, user):
        """Snapshot test: reconstruct decision without mutable state."""
        target = TimeSemanticTestModel.objects.create(name="snapshot_target")
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        original_name = target.name
        snapshot = {
            "target_name": original_name,
            "captured_at": str(timezone.now())
        }

        decision = Decision.objects.create(
            actor_user=user,
            target_type=content_type,
            target_id=str(target.pk),
            action="record",
            snapshot=snapshot
        )

        # Mutate the target
        target.name = "mutated_name"
        target.save()

        # Decision snapshot should still have original values
        decision.refresh_from_db()
        assert decision.snapshot["target_name"] == original_name
        assert decision.snapshot["target_name"] != target.name


@pytest.mark.django_db
class TestTargetRefIntegration:
    """Integration tests for TargetRef utility."""

    def test_targetref_with_decision(self):
        """TargetRef should integrate seamlessly with Decision."""
        user = User.objects.create_user(username="ref_user", password="test")
        target = TimeSemanticTestModel.objects.create(name="ref_target")

        # Create ref from instance
        ref = TargetRef.from_instance(target)

        # Use ref to create decision
        decision = Decision.objects.create(
            actor_user=user,
            target_type=ref.content_type,
            target_id=ref.object_id,
            action="test",
            snapshot={}
        )

        # Resolve ref and verify it matches decision's target
        resolved = ref.resolve()
        assert resolved.pk == target.pk

        # Decision should have correct target reference
        assert decision.target_id == ref.object_id
        assert decision.target_type == ref.content_type


@pytest.mark.django_db
class TestFullWorkflow:
    """Full workflow integration tests."""

    def test_complete_decision_workflow(self):
        """Test complete workflow: create target -> make decision -> finalize."""
        user = User.objects.create_user(username="workflow_user", password="test")

        # Step 1: Create target
        target = TimeSemanticTestModel.objects.create(name="workflow_target")

        # Step 2: Create decision using TargetRef
        ref = TargetRef.from_instance(target)
        decision = Decision.objects.create(
            actor_user=user,
            target_type=ref.content_type,
            target_id=ref.object_id,
            action="approve",
            snapshot={"target_name": target.name},
            effective_at=timezone.now()
        )

        # Verify decision is not final
        assert decision.is_final is False

        # Step 3: Finalize decision
        decision.finalized_at = timezone.now()
        decision.outcome = {"status": "approved", "workflow_complete": True}
        decision.save()

        decision.refresh_from_db()
        assert decision.is_final is True
        assert decision.outcome["workflow_complete"] is True

    def test_idempotent_decision_creation(self):
        """Test idempotent decision creation workflow."""
        user = User.objects.create_user(username="idem_user", password="test")
        target = TimeSemanticTestModel.objects.create(name="idem_target")

        @idempotent(scope="decision_creation", key_from=lambda u, t: f"{u.pk}:{t.pk}")
        def create_decision(actor, target_instance):
            ref = TargetRef.from_instance(target_instance)
            decision = Decision.objects.create(
                actor_user=actor,
                target_type=ref.content_type,
                target_id=ref.object_id,
                action="commit",
                snapshot={"target_pk": str(target_instance.pk)}
            )
            return {"decision_id": str(decision.pk)}

        # Call multiple times
        result1 = create_decision(user, target)
        result2 = create_decision(user, target)
        result3 = create_decision(user, target)

        # Only one decision created
        assert Decision.objects.filter(actor_user=user).count() == 1

        # All results identical
        assert result1 == result2 == result3
