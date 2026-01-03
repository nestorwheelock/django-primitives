# Architecture: django-notes

**Status:** Stable / v0.1.0

Notes and tagging for any Django model via GenericForeignKey.

---

## What This Package Is For

Answering the question: **"What notes and tags are attached to this object?"**

Use cases:
- Adding comments/notes to any model
- Tagging objects for categorization
- Visibility-controlled notes (public, internal, private)
- Author tracking on notes
- Querying by tag across models

---

## What This Package Is NOT For

- **Not a full CMS** - Use Wagtail for content management
- **Not a discussion forum** - Use Django-machina for threaded discussions
- **Not activity feeds** - Use django-activity-stream for feeds
- **Not rich text** - Content is plain text, use TinyMCE for WYSIWYG

---

## Design Principles

1. **GenericFK attachment** - Works with any model, not just specific types
2. **Visibility levels** - Notes can be public, internal, or private
3. **Author tracking** - Notes track who created them
4. **Simple tagging** - Tags are reusable across objects
5. **Unique tag assignment** - Same tag can't be applied twice to same object

---

## Data Model

```
Note                                   Tag
├── id (UUID, BaseModel)               ├── id (UUID, BaseModel)
├── target (GenericFK)                 ├── name
│   ├── target_content_type            ├── slug (unique)
│   └── target_id (CharField)          ├── color (hex)
├── content (text)                     ├── description
├── author (FK → User, nullable)       └── BaseModel fields
├── visibility (public|internal|private)
├── metadata (JSON)
└── BaseModel fields

ObjectTag (Many-to-Many via GenericFK)
├── id (UUID, BaseModel)
├── target (GenericFK)
│   ├── target_content_type
│   └── target_id (CharField)
├── tag (FK → Tag)
├── tagged_by (FK → User, nullable)
└── BaseModel fields

Constraints:
  - One ObjectTag per (target, tag) - no duplicate tags
  - Tag.slug is globally unique
```

---

## Public API

### Creating Notes

```python
from django_notes.models import Note

# Add a note to any object
note = Note.objects.create(
    target=my_project,  # Any model
    content="Important update about this project.",
    author=request.user,
    visibility='internal',  # or 'public', 'private'
)

# System-generated note (no author)
system_note = Note.objects.create(
    target=my_project,
    content="Automated status change recorded.",
    visibility='internal',
)
```

### Querying Notes

```python
from django_notes.models import Note

# Get all notes for an object
notes = Note.objects.for_target(my_project)

# Filter by visibility
public_notes = Note.objects.for_target(my_project).public()
internal = Note.objects.for_target(my_project).by_visibility('internal')

# Filter by author
my_notes = Note.objects.by_author(request.user)
```

### Creating and Using Tags

```python
from django_notes.models import Tag, ObjectTag

# Create tags
urgent = Tag.objects.create(
    name='Urgent',
    slug='urgent',
    color='#FF0000',
)

# Apply tag to object
ObjectTag.objects.create(
    target=my_project,
    tag=urgent,
    tagged_by=request.user,
)

# Query tags for an object
tags = ObjectTag.objects.for_target(my_project)

# Find all objects with a specific tag
tagged_objects = ObjectTag.objects.with_tag('urgent')
```

---

## Hard Rules

1. **Tag.slug is unique** - No duplicate tag slugs
2. **One tag per target** - UniqueConstraint on (target, tag)
3. **target_id is string** - Stored as CharField for UUID support
4. **Visibility choices** - Only 'public', 'internal', 'private' allowed

---

## Invariants

- Tag.slug is globally unique
- ObjectTag(target, tag) is unique per combination
- Note.target_id is always stored as string
- ObjectTag.target_id is always stored as string
- Note.visibility is always one of: 'public', 'internal', 'private'

---

## Known Gotchas

### 1. Duplicate Tag Application

**Problem:** Trying to apply same tag twice.

```python
ObjectTag.objects.create(target=project, tag=urgent)
ObjectTag.objects.create(target=project, tag=urgent)
# IntegrityError: unique constraint "objecttag_unique_per_target"
```

**Solution:** Use get_or_create:

```python
tag_assignment, created = ObjectTag.objects.get_or_create(
    target_content_type=ContentType.objects.get_for_model(project),
    target_id=str(project.pk),
    tag=urgent,
    defaults={'tagged_by': user}
)
```

### 2. Querying with GenericFK

**Problem:** Can't use direct FK queries.

```python
# WRONG - GenericFK doesn't support this
notes = Note.objects.filter(target=my_project)

# CORRECT - use for_target() queryset method
notes = Note.objects.for_target(my_project)
```

### 3. Visibility Enforcement

**Problem:** Visibility is metadata, not access control.

```python
# Visibility doesn't prevent access - it's a classification
private_notes = Note.objects.filter(visibility='private')
# Anyone with model access can query this!

# Enforce in views:
def get_notes(request, obj):
    notes = Note.objects.for_target(obj)
    if not request.user.is_staff:
        notes = notes.exclude(visibility='private')
    return notes
```

### 4. Cascading Deletes

**Problem:** Deleting tag removes all ObjectTags.

```python
urgent_tag.delete()
# All ObjectTag entries for 'urgent' are deleted (CASCADE)
```

---

## Recommended Usage

### 1. Use for_target() Method

```python
# RECOMMENDED
notes = Note.objects.for_target(my_object)

# AVOID - verbose and error-prone
from django.contrib.contenttypes.models import ContentType
notes = Note.objects.filter(
    target_content_type=ContentType.objects.get_for_model(my_object),
    target_id=str(my_object.pk),
)
```

### 2. Define Standard Tags in Migrations

```python
def create_tags(apps, schema_editor):
    Tag = apps.get_model('django_notes', 'Tag')
    tags = [
        ('urgent', 'Urgent', '#FF0000'),
        ('review', 'Needs Review', '#FFAA00'),
        ('approved', 'Approved', '#00FF00'),
    ]
    for slug, name, color in tags:
        Tag.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'color': color}
        )
```

### 3. Add Notes in Service Layer

```python
def update_project_status(project, new_status, user, note_text=None):
    """Update status and optionally add a note."""
    old_status = project.status
    project.status = new_status
    project.save()

    if note_text:
        Note.objects.create(
            target=project,
            content=note_text,
            author=user,
            visibility='internal',
            metadata={'old_status': old_status, 'new_status': new_status},
        )
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Note model with GenericFK target
- Visibility levels (public, internal, private)
- Tag model with slug and color
- ObjectTag for GenericFK-based tagging
- Custom querysets with for_target() method
