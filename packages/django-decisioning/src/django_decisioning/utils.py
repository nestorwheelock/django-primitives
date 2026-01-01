"""Utility classes for decisioning."""
from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType


@dataclass
class TargetRef:
    """
    Utility for GenericFK handling.

    Always uses string for object_id to support UUIDs.

    From POSTGRES_GOTCHAS.md:
    - GenericFK object IDs should always be CharField(max_length=255)
    - This is a UUID-first framework, integer assumptions will bite you

    Usage:
        # Create from model instance
        ref = TargetRef.from_instance(my_basket)

        # Store in Decision
        decision = Decision.objects.create(
            target_type=ref.content_type,
            target_id=ref.object_id,
            ...
        )

        # Resolve back to instance
        basket = ref.resolve()
    """

    content_type: ContentType
    object_id: str  # Always string for UUID support

    @classmethod
    def from_instance(cls, obj: Any) -> 'TargetRef':
        """
        Create a TargetRef from a model instance.

        Args:
            obj: A Django model instance

        Returns:
            TargetRef with content_type and string object_id
        """
        return cls(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk)  # Always convert to string
        )

    def resolve(self) -> Any:
        """
        Resolve the reference back to the model instance.

        Returns:
            The model instance

        Raises:
            Model.DoesNotExist: If the object no longer exists
        """
        model = self.content_type.model_class()
        return model.objects.get(pk=self.object_id)
