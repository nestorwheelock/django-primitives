# Chapter 11d: Notes

> "The context that explains everything."

---

Every business record needs context. Why was this order cancelled? What did the customer say on the phone? What's the history of this account? Notes capture the human context that structured data can't.

The Notes primitive provides threaded, searchable, attributable notes that attach to any record in your system.

## The Problem Notes Solve

Note-taking fails in predictable ways:

**Scattered context.** Customer history lives in emails, CRM notes, support tickets, and someone's memory. Reconstructing the full picture requires archaeology.

**Unstructured data.** A text field called "notes" becomes a dumping ground. Critical information is buried in walls of text.

**Missing attribution.** "Customer complained about shipping" - who wrote this? When? Was it before or after we fixed the shipping issue?

**No threading.** Notes are flat. You can't see conversations, follow-ups, or the chain of events.

**Lost history.** When notes can be edited or deleted, the historical record is corrupted.

## The Note Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_basemodels.models import SoftDeleteModel


class Note(SoftDeleteModel):
    """A note attached to any model with threading support."""

    # What this note is attached to
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Note content
    content = models.TextField()

    # Optional structured data
    NOTE_TYPES = [
        ('general', 'General Note'),
        ('call', 'Phone Call'),
        ('meeting', 'Meeting'),
        ('email', 'Email Summary'),
        ('task', 'Task'),
        ('followup', 'Follow-up'),
        ('warning', 'Warning'),
        ('resolution', 'Resolution'),
    ]
    note_type = models.CharField(max_length=50, choices=NOTE_TYPES, default='general')

    # Priority/visibility
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    is_pinned = models.BooleanField(default=False)
    is_internal = models.BooleanField(default=True)  # Not visible to customers

    # Authorship (immutable)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='notes_created'
    )

    # Threading
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='replies'
    )

    # Timestamps (from SoftDeleteModel: created_at, updated_at)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id', '-created_at']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['note_type']),
        ]

    @property
    def is_reply(self):
        return self.parent is not None

    @property
    def thread_root(self):
        """Get the root note of this thread."""
        current = self
        while current.parent:
            current = current.parent
        return current

    @property
    def thread(self):
        """Get all notes in this thread."""
        root = self.thread_root
        return Note.objects.filter(
            models.Q(pk=root.pk) | models.Q(parent=root)
        ).order_by('created_at')

    @property
    def reply_count(self):
        return self.replies.count()

    def add_reply(self, content, created_by, **kwargs):
        """Add a reply to this note."""
        return Note.objects.create(
            target_content_type=self.target_content_type,
            target_id=self.target_id,
            content=content,
            created_by=created_by,
            parent=self,
            note_type=kwargs.get('note_type', 'general'),
            is_internal=kwargs.get('is_internal', self.is_internal),
        )

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.created_by}: {preview}"
```

## Note QuerySet

```python
class NoteQuerySet(models.QuerySet):
    """QuerySet with note-specific filters."""

    def for_target(self, target):
        """Notes for a specific target object."""
        ct = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=ct,
            target_id=str(target.pk)
        )

    def root_notes(self):
        """Only top-level notes (not replies)."""
        return self.filter(parent__isnull=True)

    def by_type(self, note_type):
        """Filter by note type."""
        return self.filter(note_type=note_type)

    def internal(self):
        """Only internal notes."""
        return self.filter(is_internal=True)

    def external(self):
        """Only external/customer-visible notes."""
        return self.filter(is_internal=False)

    def pinned(self):
        """Only pinned notes."""
        return self.filter(is_pinned=True)

    def by_author(self, user):
        """Notes by a specific author."""
        return self.filter(created_by=user)

    def search(self, query):
        """Full-text search in note content."""
        return self.filter(content__icontains=query)

    def recent(self, days=30):
        """Notes from the last N days."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
```

## Mentions and Notifications

```python
import re


class NoteMention(models.Model):
    """Track @mentions in notes."""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='mentions')
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='note_mentions'
    )
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['note', 'mentioned_user']


def extract_mentions(content):
    """Extract @username mentions from content."""
    pattern = r'@(\w+)'
    return re.findall(pattern, content)


def process_mentions(note):
    """Create NoteMention records for all @mentions in a note."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    usernames = extract_mentions(note.content)

    for username in usernames:
        try:
            user = User.objects.get(username=username)
            NoteMention.objects.get_or_create(
                note=note,
                mentioned_user=user
            )
        except User.DoesNotExist:
            pass
```

## Activity Timeline

Combine notes with system events:

```python
class ActivityEntry(models.Model):
    """A timeline entry (note or system event)."""

    # What this is attached to
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    ENTRY_TYPES = [
        ('note', 'Note'),
        ('status_change', 'Status Change'),
        ('assignment', 'Assignment'),
        ('creation', 'Created'),
        ('update', 'Updated'),
        ('attachment', 'Attachment Added'),
        ('email_sent', 'Email Sent'),
        ('email_received', 'Email Received'),
    ]
    entry_type = models.CharField(max_length=50, choices=ENTRY_TYPES)

    # Content
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)  # Structured data about the event

    # For note entries, link to the actual note
    note = models.ForeignKey(Note, on_delete=models.SET_NULL, null=True, blank=True)

    # Who and when
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id', '-created_at']),
        ]

    @classmethod
    def log_status_change(cls, target, old_status, new_status, actor):
        """Log a status change event."""
        ct = ContentType.objects.get_for_model(target)
        return cls.objects.create(
            target_content_type=ct,
            target_id=str(target.pk),
            entry_type='status_change',
            title=f"Status changed from {old_status} to {new_status}",
            metadata={'old_status': old_status, 'new_status': new_status},
            actor=actor
        )

    @classmethod
    def from_note(cls, note):
        """Create activity entry from a note."""
        return cls.objects.create(
            target_content_type=note.target_content_type,
            target_id=note.target_id,
            entry_type='note',
            title=f"{note.get_note_type_display()} by {note.created_by}",
            note=note,
            actor=note.created_by,
            created_at=note.created_at
        )
```

## Templates and Snippets

Pre-defined note templates:

```python
class NoteTemplate(models.Model):
    """Reusable note templates."""

    name = models.CharField(max_length=255)
    content = models.TextField()
    note_type = models.CharField(max_length=50, default='general')

    # Where this template applies
    applies_to = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    is_shared = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def render(self, context=None):
        """Render template with context variables."""
        from django.template import Template, Context
        template = Template(self.content)
        return template.render(Context(context or {}))
```

## Why This Matters Later

The Notes primitive connects to:

- **Identity** (Chapter 4): Notes are created by users, mention users.
- **Workflow** (Chapter 9): Notes explain state transitions.
- **Audit** (Chapter 11): Notes are part of the audit trail.
- **Decisions** (Chapter 10): Notes capture decision rationale.

Note-taking seems simple until you need to:
- Reconstruct the complete history of a customer relationship
- Prove what was communicated and when
- Search across all notes for mentions of a product issue
- Show a timeline of everything that happened to an account

The Notes primitive handles the complexity so your application doesn't have to reinvent it.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-notes | `docs/prompts/django-notes.md` | ~25 tests |

### Using the Prompt

```bash
cat docs/prompts/django-notes.md | claude

# Request: "Implement Note model with GenericFK target,
# visibility controls (public/private/internal),
# and @mention extraction with NoteMention records."
```

### Key Constraints

- **GenericFK target**: Notes attach to any model
- **Soft delete preservation**: Deleted notes remain for audit
- **Mention processing**: Extract @usernames and create NoteMention records
- **Thread support**: Notes can reply to other notes via parent FK

If Claude hard-deletes notes or skips mention extraction, that's a constraint violation.

---

*Status: Draft*
