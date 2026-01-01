# Prompt: Rebuild django-notes

## Instruction

Create a Django package called `django-notes` that provides notes and tagging primitives for attaching comments and tags to any model.

## Package Purpose

Provide notes and tagging capabilities for any model:
- `Note` - Attach notes/comments with visibility control
- `Tag` - Reusable tags with colors and descriptions
- `ObjectTag` - Apply tags to any object via GenericForeignKey
- QuerySet methods for filtering

## Dependencies

- Django >= 4.2
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-notes/
├── pyproject.toml
├── README.md
├── src/django_notes/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_note.py
    └── test_tag.py
```

## Models Specification

### Note Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Visibility(models.TextChoices):
    PUBLIC = 'public', 'Public'
    INTERNAL = 'internal', 'Internal'
    PRIVATE = 'private', 'Private'


class NoteQuerySet(models.QuerySet):
    def for_target(self, target):
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk)
        )

    def by_visibility(self, visibility):
        return self.filter(visibility=visibility)

    def public(self):
        return self.filter(visibility='public')

    def by_author(self, author):
        return self.filter(author=author)


class Note(models.Model):
    # Target via GenericFK
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Content
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notes'
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.INTERNAL
    )

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoteQuerySet.as_manager()

    class Meta:
        app_label = 'django_notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['visibility']),
            models.Index(fields=['author']),
        ]

    def save(self, *args, **kwargs):
        self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        preview = self.content[:50]
        if len(self.content) > 50:
            preview += '...'
        return f"Note: {preview}"
```

### Tag Model

```python
class Tag(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#808080')  # Hex color
    description = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'django_notes'
        ordering = ['name']

    def __str__(self):
        return self.name
```

### ObjectTag Model

```python
class ObjectTagQuerySet(models.QuerySet):
    def for_target(self, target):
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk)
        )

    def with_tag(self, tag):
        if isinstance(tag, str):
            return self.filter(tag__slug=tag)
        return self.filter(tag=tag)


class ObjectTag(models.Model):
    # Target via GenericFK
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='object_tags')
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tags_created'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    objects = ObjectTagQuerySet.as_manager()

    class Meta:
        app_label = 'django_notes'
        unique_together = ['target_content_type', 'target_id', 'tag']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['tag']),
        ]

    def save(self, *args, **kwargs):
        self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tag.name} on {self.target_content_type.model}:{self.target_id}"
```

## Test Models

### tests/models.py

```python
from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

class Task(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    class Meta:
        app_label = 'tests'
```

## Test Cases (37 tests)

### TestNoteModel (11 tests)
1. `test_note_has_target_generic_fk` - GenericFK works
2. `test_note_target_id_is_charfield` - UUID support
3. `test_note_has_content_field` - Content stored
4. `test_note_has_author_fk` - Author FK works
5. `test_note_author_is_nullable` - System notes allowed
6. `test_note_has_visibility_field` - Visibility stored
7. `test_note_visibility_defaults_to_internal` - Default 'internal'
8. `test_note_visibility_choices` - All choices work
9. `test_note_has_timestamps` - created_at, updated_at
10. `test_note_has_metadata_json_field` - JSONField works
11. `test_note_metadata_defaults_to_empty_dict` - Default {}

### TestNoteQuerySet (4 tests)
1. `test_for_target_returns_notes_for_object` - Filters by target
2. `test_by_visibility_filters_notes` - Filters by visibility
3. `test_public_queryset_method` - public() shortcut
4. `test_by_author_filters_notes` - Filters by author

### TestTagModel (9 tests)
1. `test_tag_has_name_field` - Name stored
2. `test_tag_has_slug_field` - Slug stored
3. `test_tag_slug_is_unique` - Unique constraint
4. `test_tag_has_color_field` - Color stored
5. `test_tag_color_defaults_to_gray` - Default #808080
6. `test_tag_has_description_field` - Description stored
7. `test_tag_description_is_optional` - Default ''
8. `test_tag_has_timestamps` - created_at, updated_at
9. `test_tag_str_representation` - Returns name

### TestObjectTagModel (9 tests)
1. `test_object_tag_has_target_generic_fk` - GenericFK works
2. `test_object_tag_target_id_is_charfield` - UUID support
3. `test_object_tag_has_tag_fk` - Tag FK works
4. `test_object_tag_has_tagged_by` - tagged_by FK works
5. `test_object_tag_tagged_by_is_nullable` - System tags allowed
6. `test_object_tag_has_created_at` - Timestamp exists
7. `test_object_tag_unique_constraint` - No duplicate tags
8. `test_different_tags_on_same_object` - Multiple tags allowed
9. `test_same_tag_on_different_objects` - Same tag reusable

### TestObjectTagQuerySet (4 tests)
1. `test_for_target_returns_tags_for_object` - Filters by target
2. `test_with_tag_filters_by_tag_object` - Filters by Tag instance
3. `test_with_tag_filters_by_slug` - Filters by slug string
4. `test_chained_queries` - Methods chainable

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = ['Note', 'Tag', 'ObjectTag']

def __getattr__(name):
    if name == 'Note':
        from .models import Note
        return Note
    if name == 'Tag':
        from .models import Tag
        return Tag
    if name == 'ObjectTag':
        from .models import ObjectTag
        return ObjectTag
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **GenericForeignKey**: Attach notes/tags to any model
2. **Visibility Control**: public, internal, private notes
3. **Reusable Tags**: Tag model shared across all objects
4. **Unique Constraint**: Same tag only once per object
5. **Author Tracking**: Optional author for user attribution

## Usage Examples

```python
# Create a note
from django_notes.models import Note

note = Note.objects.create(
    target=my_project,
    content="Customer requested rush delivery.",
    author=request.user,
    visibility='internal',
)

# Query notes
notes = Note.objects.for_target(my_project)
public_notes = Note.objects.public()
user_notes = Note.objects.by_author(request.user)

# Create and apply tags
from django_notes.models import Tag, ObjectTag

urgent = Tag.objects.create(name="Urgent", slug="urgent", color="#FF0000")

ObjectTag.objects.create(
    target=my_invoice,
    tag=urgent,
    tagged_by=request.user,
)

# Query tags
tags = ObjectTag.objects.for_target(my_invoice)
urgent_items = ObjectTag.objects.with_tag("urgent")
```

## Acceptance Criteria

- [ ] Note model with visibility and author
- [ ] Tag model with slug, color, description
- [ ] ObjectTag model with unique constraint
- [ ] NoteQuerySet with for_target, by_visibility, public, by_author
- [ ] ObjectTagQuerySet with for_target, with_tag
- [ ] All 37 tests passing
- [ ] README with usage examples
