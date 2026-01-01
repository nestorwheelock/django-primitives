# django-notes

Notes and tagging primitives for Django applications.

## Features

- **Note Model**: Attach notes to any model via GenericFK
- **Tag System**: Flexible tagging with colors and slugs
- **ObjectTag**: GenericFK-based many-to-many tagging
- **Visibility Controls**: Public, private, and internal notes

## Installation

```bash
pip install django-notes
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django.contrib.contenttypes',
    'django_notes',
]
```

Run migrations:

```bash
python manage.py migrate django_notes
```

## Usage

### Adding Notes

```python
from django_notes.models import Note

# Add a note to any object
note = Note.objects.create(
    target=my_invoice,
    content="Customer requested rush delivery.",
    visibility='internal',
    author=request.user,
)
```

### Tagging Objects

```python
from django_notes.models import Tag, ObjectTag

# Create a tag
urgent = Tag.objects.create(
    name="Urgent",
    slug="urgent",
    color="#FF0000",
)

# Tag an object
ObjectTag.objects.create(
    target=my_invoice,
    tag=urgent,
)

# Query tags for an object
tags = ObjectTag.objects.for_target(my_invoice)
```

### Querying Notes

```python
from django_notes.models import Note

# Get all notes for an object
notes = Note.objects.for_target(my_invoice)

# Filter by visibility
internal_notes = notes.filter(visibility='internal')
```

## License

MIT
