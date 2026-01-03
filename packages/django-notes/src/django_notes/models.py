"""Note and Tag models for attachable notes and tagging."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_basemodels import BaseModel


class NoteQuerySet(models.QuerySet):
    """Custom queryset for Note model."""

    def for_target(self, target):
        """Return notes attached to the given target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk),
        )

    def by_visibility(self, visibility):
        """Return notes with the specified visibility."""
        return self.filter(visibility=visibility)

    def public(self):
        """Return only public notes."""
        return self.filter(visibility='public')

    def by_author(self, author):
        """Return notes by the specified author."""
        return self.filter(author=author)


class Note(BaseModel):
    """
    Note attachment model.

    Attaches notes/comments to any model via GenericForeignKey.
    Supports visibility levels and author tracking.

    Usage:
        from django_notes.models import Note

        # Add a note
        note = Note.objects.create(
            target=my_project,
            content="Important update about this project.",
            author=request.user,
            visibility='internal',
        )

        # Query notes
        notes = Note.objects.for_target(my_project)
    """

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Public'
        INTERNAL = 'internal', 'Internal'
        PRIVATE = 'private', 'Private'

    # GenericFK to target object - CharField for UUID support
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Content type of the target object",
    )
    target_id = models.CharField(
        max_length=255,
        help_text="ID of the target object (CharField for UUID support)",
    )
    target = GenericForeignKey('target_content_type', 'target_id')

    # Note content
    content = models.TextField(
        help_text="Note content",
    )

    # Author - nullable for system-generated notes
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes',
        help_text="User who created the note",
    )

    # Visibility
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.INTERNAL,
        help_text="Note visibility level",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata",
    )

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    objects = NoteQuerySet.as_manager()

    class Meta:
        app_label = 'django_notes'
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['visibility']),
            models.Index(fields=['author']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Ensure target_id is always stored as string."""
        if self.target_id is not None:
            self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Note: {preview}"


class Tag(BaseModel):
    """
    Tag model for categorization.

    Usage:
        tag = Tag.objects.create(
            name="Urgent",
            slug="urgent",
            color="#FF0000",
        )
    """

    name = models.CharField(
        max_length=50,
        help_text="Tag display name",
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-friendly tag identifier",
    )
    color = models.CharField(
        max_length=7,
        default='#808080',
        help_text="Hex color code (e.g., #FF0000)",
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text="Optional description of the tag",
    )

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    class Meta:
        app_label = 'django_notes'
        ordering = ['name']

    def __str__(self):
        return self.name


class ObjectTagQuerySet(models.QuerySet):
    """Custom queryset for ObjectTag model."""

    def for_target(self, target):
        """Return tags attached to the given target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk),
        )

    def with_tag(self, tag):
        """Return object tags with the specified tag."""
        if isinstance(tag, str):
            return self.filter(tag__slug=tag)
        return self.filter(tag=tag)


class ObjectTag(BaseModel):
    """
    GenericFK-based many-to-many tagging.

    Allows tagging any object with any tag.

    Usage:
        ObjectTag.objects.create(
            target=my_project,
            tag=urgent_tag,
        )

        # Query tags for an object
        tags = ObjectTag.objects.for_target(my_project)
    """

    # GenericFK to target object - CharField for UUID support
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Content type of the target object",
    )
    target_id = models.CharField(
        max_length=255,
        help_text="ID of the target object (CharField for UUID support)",
    )
    target = GenericForeignKey('target_content_type', 'target_id')

    # Tag reference
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name='object_tags',
        help_text="The tag applied to the object",
    )

    # Who tagged it
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tags_created',
        help_text="User who applied the tag",
    )

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    objects = ObjectTagQuerySet.as_manager()

    class Meta:
        app_label = 'django_notes'
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['tag']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['target_content_type', 'target_id', 'tag'],
                name='objecttag_unique_per_target',
            ),
        ]

    def save(self, *args, **kwargs):
        """Ensure target_id is always stored as string."""
        if self.target_id is not None:
            self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tag.name} on {self.target_content_type.model}:{self.target_id}"
