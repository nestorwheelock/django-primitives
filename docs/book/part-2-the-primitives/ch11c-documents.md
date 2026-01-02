# Chapter 11c: Documents

> "The paper trail that proves everything."

---

Business runs on documents. Contracts. Invoices. Receipts. Reports. Policies. Forms. Every significant business action either produces a document or requires one as input.

The Documents primitive captures document storage, versioning, and lifecycle with the precision that compliance, audit, and collaboration require.

## The Problem Documents Solve

Document management fails in predictable ways:

**Lost files.** Documents stored in email attachments, local folders, or random cloud drives can't be found when needed.

**No versioning.** "Final_v2_FINAL_revised.pdf" is not version control. When disputes arise, which version was signed?

**Missing metadata.** A PDF file named "contract.pdf" tells you nothing. When was it created? By whom? For what purpose? Is it still valid?

**Broken links.** Documents referenced by transactions become inaccessible when storage systems change.

**No retention policy.** How long must you keep this document? When can you delete it? Without policy, you either keep everything forever or delete things you shouldn't.

## The Document Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_basemodels.models import SoftDeleteModel
import hashlib
import uuid


def document_upload_path(instance, filename):
    """Generate upload path: documents/{year}/{month}/{uuid}/{filename}"""
    from django.utils import timezone
    now = timezone.now()
    return f"documents/{now.year}/{now.month:02d}/{instance.id}/{filename}"


class Document(SoftDeleteModel):
    """A managed document with versioning and metadata."""

    # Unique identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Document metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    DOCUMENT_TYPES = [
        ('contract', 'Contract'),
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('report', 'Report'),
        ('policy', 'Policy'),
        ('form', 'Form'),
        ('correspondence', 'Correspondence'),
        ('certificate', 'Certificate'),
        ('license', 'License'),
        ('other', 'Other'),
    ]
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='other')

    # File storage
    file = models.FileField(upload_to=document_upload_path)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=64)  # SHA-256

    # Link to any model
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    related_id = models.CharField(max_length=255, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_id')

    # Authorship
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('superseded', 'Superseded'),
        ('archived', 'Archived'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Versioning
    version = models.PositiveIntegerField(default=1)
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='newer_versions'
    )

    # Validity
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)

    # Retention
    retention_years = models.PositiveIntegerField(default=7)
    can_delete_after = models.DateField(null=True, blank=True)

    # Security
    is_confidential = models.BooleanField(default=False)
    access_level = models.CharField(max_length=50, default='internal')

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['document_type', 'status']),
            models.Index(fields=['related_content_type', 'related_id']),
            models.Index(fields=['file_hash']),
        ]

    def save(self, *args, **kwargs):
        # Calculate file hash if file is new
        if self.file and not self.file_hash:
            self.file_hash = self._calculate_hash()

        # Set file metadata
        if self.file:
            self.file_name = self.file.name.split('/')[-1]
            self.file_size = self.file.size

        super().save(*args, **kwargs)

    def _calculate_hash(self):
        """Calculate SHA-256 hash of file content."""
        sha256 = hashlib.sha256()
        for chunk in self.file.chunks():
            sha256.update(chunk)
        return sha256.hexdigest()

    def verify_integrity(self):
        """Verify file hasn't been modified."""
        current_hash = self._calculate_hash()
        return current_hash == self.file_hash

    def create_new_version(self, new_file, uploaded_by, **kwargs):
        """Create a new version of this document."""
        new_doc = Document.objects.create(
            title=self.title,
            description=kwargs.get('description', self.description),
            document_type=self.document_type,
            file=new_file,
            mime_type=kwargs.get('mime_type', self.mime_type),
            related_content_type=self.related_content_type,
            related_id=self.related_id,
            uploaded_by=uploaded_by,
            version=self.version + 1,
            previous_version=self,
            retention_years=self.retention_years,
            is_confidential=self.is_confidential,
            access_level=self.access_level,
        )

        # Mark this version as superseded
        self.status = 'superseded'
        self.save()

        return new_doc

    @property
    def is_expired(self):
        if self.expiration_date:
            from django.utils import timezone
            return self.expiration_date < timezone.now().date()
        return False

    @property
    def version_history(self):
        """Get all versions of this document."""
        versions = [self]
        current = self.previous_version
        while current:
            versions.append(current)
            current = current.previous_version
        return versions

    def __str__(self):
        return f"{self.title} (v{self.version})"
```

## Document Collections

Group related documents:

```python
class DocumentCollection(SoftDeleteModel):
    """A folder or collection of related documents."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children'
    )

    # Link to any model
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    owner_id = models.CharField(max_length=255, blank=True)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    documents = models.ManyToManyField(Document, blank=True, related_name='collections')

    class Meta:
        ordering = ['name']

    @property
    def path(self):
        """Full path from root."""
        parts = [self.name]
        current = self.parent
        while current:
            parts.insert(0, current.name)
            current = current.parent
        return '/'.join(parts)

    @property
    def all_documents(self):
        """All documents including from child collections."""
        docs = list(self.documents.all())
        for child in self.children.all():
            docs.extend(child.all_documents)
        return docs
```

## Document Requirements

Define what documents are required:

```python
class DocumentRequirement(models.Model):
    """Definition of a required document."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=50)

    # What this applies to
    applies_to_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    is_required = models.BooleanField(default=True)
    expires_after_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']


class DocumentCompliance(models.Model):
    """Track document compliance for an entity."""

    requirement = models.ForeignKey(DocumentRequirement, on_delete=models.CASCADE)

    # What entity this is for
    entity_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    entity_id = models.CharField(max_length=255)
    entity = GenericForeignKey('entity_content_type', 'entity_id')

    # The document that satisfies the requirement
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('compliant', 'Compliant'),
        ('expired', 'Expired'),
        ('missing', 'Missing'),
    ], default='pending')

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        unique_together = ['requirement', 'entity_content_type', 'entity_id']
```

## Document Access Control

```python
class DocumentAccess(models.Model):
    """Access permissions for a document."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_grants')

    # Who has access
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    role = models.CharField(max_length=100, blank=True)  # For role-based access

    # What access
    can_view = models.BooleanField(default=True)
    can_download = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_share = models.BooleanField(default=False)

    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_grants_given'
    )
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['document', 'user']
```

## Why This Matters Later

The Documents primitive connects to:

- **Identity** (Chapter 4): Documents have owners and access lists.
- **Agreements** (Chapter 6): Contracts are documents.
- **Audit** (Chapter 11): Document access is logged.
- **Workflow** (Chapter 9): Documents flow through approval processes.

Document management seems simple until you need to:
- Prove what version of a contract was signed
- Demonstrate compliance with retention policies
- Control who can see confidential documents
- Track every access to sensitive files

The Documents primitive handles the complexity so your application doesn't have to reinvent it.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-documents | `docs/prompts/django-documents.md` | ~30 tests |

### Using the Prompt

```bash
cat docs/prompts/django-documents.md | claude

# Request: "Implement Document model with version history,
# GenericFK for attaching to any model, and file metadata.
# Add DocumentCollection for folder hierarchy."
```

### Key Constraints

- **Immutable versions**: DocumentVersion records cannot be modified
- **Content hash**: SHA-256 of file content for integrity verification
- **Soft delete**: Documents are never hard deleted
- **GenericFK attachment**: Documents attach to any model

If Claude allows editing document versions or skips content hashing, that's a constraint violation.

---

*Status: Draft*
