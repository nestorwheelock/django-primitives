"""Tests for Encounter and EncounterTransition models."""

import pytest
from django.contrib.contenttypes.models import ContentType

from django_encounters.models import Encounter, EncounterDefinition, EncounterTransition
from tests.testapp.models import Subject


@pytest.fixture
def definition(db):
    """Create a test definition."""
    return EncounterDefinition.objects.create(
        key="test_workflow",
        name="Test Workflow",
        states=["pending", "active", "completed"],
        transitions={"pending": ["active"], "active": ["completed"]},
        initial_state="pending",
        terminal_states=["completed"],
    )


@pytest.fixture
def subject(db):
    """Create a test subject."""
    return Subject.objects.create(name="Test Subject")


@pytest.fixture
def user(db, django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(username="testuser", password="test")


@pytest.mark.django_db
class TestEncounterCreation:
    """Tests for Encounter model creation."""

    def test_create_encounter_with_genericfk(self, definition, subject, user):
        """Encounter can be created with GenericFK to any subject."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state=definition.initial_state,
            created_by=user,
        )

        assert encounter.pk is not None
        assert encounter.subject == subject
        assert encounter.state == "pending"
        assert encounter.created_by == user

    def test_encounter_subject_generic_relation(self, definition, subject):
        """GenericFK allows access to any model as subject."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        # Can access subject attributes through GenericFK
        assert encounter.subject.name == "Test Subject"

    def test_encounter_default_metadata(self, definition, subject):
        """Metadata defaults to empty dict."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        assert encounter.metadata == {}

    def test_encounter_ended_at_initially_null(self, definition, subject):
        """ended_at is null on creation."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        assert encounter.ended_at is None

    def test_encounter_timestamps(self, definition, subject):
        """Encounter has created_at and updated_at."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        assert encounter.created_at is not None
        assert encounter.updated_at is not None
        assert encounter.started_at is not None


@pytest.mark.django_db
class TestEncounterQuerying:
    """Tests for querying Encounter models."""

    def test_filter_by_definition(self, definition, subject):
        """Can filter encounters by definition."""
        Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        count = Encounter.objects.filter(definition=definition).count()
        assert count == 1

    def test_filter_by_state(self, definition, subject):
        """Can filter encounters by state."""
        Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="active",
        )

        pending = Encounter.objects.filter(state="pending").count()
        active = Encounter.objects.filter(state="active").count()

        assert pending == 0
        assert active == 1

    def test_filter_by_subject(self, definition, subject):
        """Can filter encounters by subject using ContentType."""
        Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        subject_ct = ContentType.objects.get_for_model(subject)
        count = Encounter.objects.filter(
            subject_type=subject_ct,
            subject_id=subject.pk
        ).count()

        assert count == 1


@pytest.mark.django_db
class TestEncounterTransitionCreation:
    """Tests for EncounterTransition model."""

    def test_create_transition(self, definition, subject, user):
        """Can create a transition record."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
        )

        assert transition.pk is not None
        assert transition.from_state == "pending"
        assert transition.to_state == "active"
        assert transition.transitioned_by == user
        assert transition.transitioned_at is not None

    def test_transition_metadata(self, definition, subject):
        """Transition can store metadata."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            metadata={"override_reason": "manager approval"},
        )

        assert transition.metadata == {"override_reason": "manager approval"}

    def test_encounter_transitions_relation(self, definition, subject, user):
        """Can access transitions via encounter.transitions."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
        )
        EncounterTransition.objects.create(
            encounter=encounter,
            from_state="active",
            to_state="completed",
            transitioned_by=user,
        )

        assert encounter.transitions.count() == 2

    def test_transitions_cascade_on_encounter_delete(self, definition, subject):
        """Transitions are deleted when encounter is hard deleted."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )
        EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
        )

        encounter_pk = encounter.pk
        encounter.hard_delete()  # Use hard_delete to test CASCADE behavior

        assert EncounterTransition.objects.filter(encounter_id=encounter_pk).count() == 0


@pytest.mark.django_db
class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_encounter_soft_delete(self, definition, subject):
        """Encounter can be soft deleted."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        encounter.delete()  # BaseModel.delete() performs soft delete

        assert encounter.is_deleted is True
        assert encounter.deleted_at is not None

    def test_encounter_restore(self, definition, subject):
        """Soft deleted encounter can be restored."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )
        encounter.delete()  # BaseModel.delete() performs soft delete
        encounter.restore()

        assert encounter.is_deleted is False
        assert encounter.deleted_at is None


@pytest.mark.django_db
class TestEncounterTransitionTimeSemantics:
    """Tests for EncounterTransition time semantics (effective_at/recorded_at).

    EncounterTransition has effective_at for when transition "happened"
    (can be backdated for late recording scenarios).
    """

    def test_transition_has_effective_at_field(self, definition, subject, user):
        """EncounterTransition should have effective_at field."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
        )

        assert hasattr(transition, 'effective_at')
        assert transition.effective_at is not None

    def test_transition_has_recorded_at_field(self, definition, subject, user):
        """EncounterTransition should have recorded_at field."""
        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
        )

        assert hasattr(transition, 'recorded_at')
        assert transition.recorded_at is not None

    def test_transition_effective_at_defaults_to_now(self, definition, subject, user):
        """EncounterTransition effective_at should default to now."""
        from django.utils import timezone

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        before = timezone.now()
        transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
        )
        after = timezone.now()

        assert transition.effective_at >= before
        assert transition.effective_at <= after

    def test_transition_can_be_backdated(self, definition, subject, user):
        """EncounterTransition effective_at can be set to past time."""
        from django.utils import timezone
        import datetime

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        past = timezone.now() - datetime.timedelta(days=7)
        transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
            effective_at=past,
        )

        assert transition.effective_at == past

    def test_transition_as_of_query(self, definition, subject, user):
        """EncounterTransition.objects.as_of(timestamp) returns transitions at that time."""
        from django.utils import timezone
        import datetime

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=ContentType.objects.get_for_model(subject),
            subject_id=subject.pk,
            state="pending",
        )

        now = timezone.now()
        past = now - datetime.timedelta(days=7)

        # Old transition
        old_transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="pending",
            to_state="active",
            transitioned_by=user,
            effective_at=past,
        )

        # New transition
        new_transition = EncounterTransition.objects.create(
            encounter=encounter,
            from_state="active",
            to_state="completed",
            transitioned_by=user,
            effective_at=now,
        )

        # Query as of 5 days ago (should only see old transition)
        five_days_ago = now - datetime.timedelta(days=5)
        trans_then = EncounterTransition.objects.as_of(five_days_ago).filter(encounter=encounter)
        assert trans_then.count() == 1
        assert trans_then.first() == old_transition

        # Query as of now (should see both)
        trans_now = EncounterTransition.objects.as_of(now).filter(encounter=encounter)
        assert trans_now.count() == 2
