"""Reusable abstract base models for Django projects.

This module provides the standard base model for django-primitives:

- BaseModel: UUID PK + timestamps + soft delete (the standard)

Component mixins are available but rarely needed directly:
- UUIDModel: UUID primary key
- TimeStampedModel: created_at/updated_at timestamps
- SoftDeleteModel: Soft delete with restore capability

Usage:
    from django_basemodels import BaseModel

    class MyModel(BaseModel):
        name = models.CharField(max_length=100)

    # That's it. You get:
    # - id: UUID primary key
    # - created_at: auto-set on create
    # - updated_at: auto-set on save
    # - deleted_at: soft delete timestamp
    # - objects: manager excluding deleted
    # - all_objects: manager including deleted
"""
import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base model with created/updated timestamps.

    Automatically tracks when records are created and last modified.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract base model with UUID primary key.

    Uses UUID4 instead of auto-incrementing integers for primary key.
    Useful for distributed systems or when IDs shouldn't be guessable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted objects by default.

    Use .with_deleted() to include soft-deleted objects.
    Use .deleted_only() to get only soft-deleted objects.
    """

    def get_queryset(self):
        """Return only non-deleted objects."""
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        """Include soft-deleted objects in queryset."""
        return super().get_queryset()

    def deleted_only(self):
        """Return only soft-deleted objects."""
        return super().get_queryset().filter(deleted_at__isnull=False)


class SoftDeleteModel(models.Model):
    """Abstract base model with soft delete functionality.

    Instead of permanently deleting records, marks them as deleted
    with a timestamp. Records can be restored if needed.

    Attributes:
        deleted_at: Timestamp when soft-deleted, None if active
        objects: Manager that excludes deleted records
        all_objects: Manager that includes all records
    """

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete the object by setting deleted_at timestamp."""
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the object from the database."""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """Restore a soft-deleted object by clearing deleted_at."""
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])

    @property
    def is_deleted(self):
        """Check if object is soft-deleted."""
        return self.deleted_at is not None


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """The standard base class for all domain models.

    Provides:
    - id: UUID primary key (globally unique, non-guessable)
    - created_at: When the record was created
    - updated_at: When the record was last modified
    - deleted_at: Soft delete timestamp (None if active)
    - objects: Manager that excludes deleted records
    - all_objects: Manager that includes all records

    Usage:
        class Customer(BaseModel):
            name = models.CharField(max_length=100)

        # Create
        customer = Customer.objects.create(name="Acme")
        customer.id  # UUID like '550e8400-e29b-41d4-a716-446655440000'

        # Soft delete (sets deleted_at, does NOT remove row)
        customer.delete()

        # Restore
        customer.restore()

        # Check status
        customer.is_deleted  # True/False

        # Query only active
        Customer.objects.all()  # Excludes deleted

        # Query all including deleted
        Customer.all_objects.all()  # Includes deleted

        # Hard delete (permanent, use sparingly)
        customer.hard_delete()

    If you need a model without UUID (rare), use plain models.Model.
    If you need a model without soft-delete (rare), don't use django-basemodels.
    """

    class Meta:
        abstract = True
