"""Tests for TargetRef utility."""
import pytest
from django.contrib.contenttypes.models import ContentType

from django_decisioning.utils import TargetRef
from tests.models import TimeSemanticTestModel


@pytest.mark.django_db
class TestTargetRef:
    """Test suite for TargetRef utility."""

    def test_from_instance_creates_ref(self):
        """from_instance() should create a TargetRef from a model instance."""
        instance = TimeSemanticTestModel.objects.create(name="test object")

        ref = TargetRef.from_instance(instance)

        expected_content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)
        assert ref.content_type == expected_content_type
        assert ref.object_id == str(instance.pk)

    def test_resolve_returns_instance(self):
        """resolve() should return the original model instance."""
        instance = TimeSemanticTestModel.objects.create(name="resolvable")

        ref = TargetRef.from_instance(instance)
        resolved = ref.resolve()

        assert resolved.pk == instance.pk
        assert resolved.name == "resolvable"

    def test_object_id_always_string(self):
        """object_id should always be a string (for UUID support)."""
        instance = TimeSemanticTestModel.objects.create(name="string pk")

        ref = TargetRef.from_instance(instance)

        # Even if pk is an integer, object_id should be a string
        assert isinstance(ref.object_id, str)
        assert ref.object_id == str(instance.pk)

    def test_resolve_handles_uuid_pk(self):
        """resolve() should work with UUID primary keys stored as strings."""
        instance = TimeSemanticTestModel.objects.create(name="uuid test")
        content_type = ContentType.objects.get_for_model(TimeSemanticTestModel)

        # Create ref manually with string ID
        ref = TargetRef(
            content_type=content_type,
            object_id=str(instance.pk)
        )

        resolved = ref.resolve()
        assert resolved.pk == instance.pk

    def test_ref_equality(self):
        """Two refs pointing to the same object should be equal."""
        instance = TimeSemanticTestModel.objects.create(name="equality test")

        ref1 = TargetRef.from_instance(instance)
        ref2 = TargetRef.from_instance(instance)

        assert ref1 == ref2

    def test_ref_inequality(self):
        """Refs pointing to different objects should not be equal."""
        instance1 = TimeSemanticTestModel.objects.create(name="obj1")
        instance2 = TimeSemanticTestModel.objects.create(name="obj2")

        ref1 = TargetRef.from_instance(instance1)
        ref2 = TargetRef.from_instance(instance2)

        assert ref1 != ref2

    def test_resolve_raises_for_deleted_object(self):
        """resolve() should raise DoesNotExist for deleted objects."""
        instance = TimeSemanticTestModel.objects.create(name="will be deleted")
        ref = TargetRef.from_instance(instance)

        # Delete the instance
        instance.delete()

        # Resolve should raise
        with pytest.raises(TimeSemanticTestModel.DoesNotExist):
            ref.resolve()
