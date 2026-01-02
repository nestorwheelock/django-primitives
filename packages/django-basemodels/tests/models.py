"""Concrete test models for testing abstract base classes."""
from django.db import models
from django_basemodels import (
    BaseModel,
    TimeStampedModel,
    UUIDModel,
    SoftDeleteModel,
)


class TimestampedTestModel(TimeStampedModel):
    """Concrete model for testing TimeStampedModel."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'


class UUIDTestModel(UUIDModel):
    """Concrete model for testing UUIDModel."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'


class SoftDeleteTestModel(SoftDeleteModel):
    """Concrete model for testing SoftDeleteModel."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'


class BaseTestModel(BaseModel):
    """Concrete model for testing BaseModel (combined functionality)."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'


class BaseModelWithConstraintTest(BaseModel):
    """Test model demonstrating BaseModel with soft-delete-aware unique constraint."""
    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        app_label = 'tests'
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_test_email'
            )
        ]
