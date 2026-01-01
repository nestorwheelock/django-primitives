# Prompt: Rebuild django-documents

## Instruction

Create a Django package called `django-documents` that provides document attachment and storage functionality with integrity verification and retention policies.

## Package Purpose

Provide file attachment capabilities for any model:
- Attach documents to any model via GenericForeignKey
- SHA-256 checksum for integrity verification
- Retention policies with expiration dates
- Metadata storage with JSONField

## Dependencies

- Django >= 4.2
- django.contrib.contenttypes

## File Structure

```
packages/django-documents/
├── pyproject.toml
├── README.md
├── src/django_documents/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_document.py
    ├── test_services.py
    ├── test_retention.py
    └── test_integration.py
```

## Exceptions Specification

### exceptions.py

```python
class DocumentError(Exception):
    """Base exception for document errors."""
    pass

class ChecksumMismatchError(DocumentError):
    """Raised when checksum verification fails."""
    pass

class DocumentNotFoundError(DocumentError):
    """Raised when document cannot be found."""
    pass

class RetentionViolationError(DocumentError):
    """Raised when attempting to delete a document under retention."""
    pass

class StorageError(DocumentError):
    """Raised when storage operations fail."""
    pass
```

## Model Specification

### Document Model

```python
import hashlib
import uuid
from datetime import timedelta
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone

class DocumentQuerySet(models.QuerySet):
    def for_target(self, target):
        """Return documents for a specific target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk)
        )

    def expired(self):
        """Return expired documents."""
        return self.filter(
            expires_at__isnull=False,
            expires_at__lt=timezone.now()
        )

    def not_expired(self):
        """Return non-expired documents."""
        return self.filter(
            models.Q(expires_at__isnull=True) |
            models.Q(expires_at__gte=timezone.now())
        )


class Document(models.Model):
    # Target via GenericFK
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=255)  # CharField for UUID support
    target = GenericForeignKey('target_content_type', 'target_id')

    # File storage
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)  # MIME type
    file_size = models.PositiveBigIntegerField(default=0)

    # Document classification
    document_type = models.CharField(max_length=50)
    description = models.TextField(blank=True, default='')

    # Integrity
    checksum = models.CharField(max_length=64, blank=True, default='')  # SHA-256

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Retention
    retention_days = models.PositiveIntegerField(null=True, blank=True)
    retention_policy = models.CharField(max_length=50, default='standard')
    expires_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DocumentQuerySet.as_manager()

    class Meta:
        app_label = 'django_documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['document_type']),
            models.Index(fields=['checksum']),
        ]

    def save(self, *args, **kwargs):
        self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def compute_checksum(self) -> str:
        """Compute SHA-256 checksum of the file."""
        sha256 = hashlib.sha256()
        self.file.seek(0)
        for chunk in iter(lambda: self.file.read(8192), b''):
            sha256.update(chunk)
        self.file.seek(0)
        return sha256.hexdigest()

    def verify_checksum(self) -> bool:
        """Verify stored checksum matches file content."""
        if not self.checksum:
            return False
        return self.compute_checksum() == self.checksum

    @property
    def is_expired(self) -> bool:
        """Check if document has expired."""
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    @property
    def under_retention(self) -> bool:
        """Check if document is under retention."""
        if self.retention_days is None:
            return True  # Keep forever
        return timezone.now() < self.created_at + timedelta(days=self.retention_days)

    @property
    def retention_ends_at(self):
        """Calculate when retention ends."""
        if self.retention_days is None:
            return None
        return self.created_at + timedelta(days=self.retention_days)
```

## Service Functions

### services.py

```python
import hashlib
from typing import Optional, Union
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import Document
from .exceptions import ChecksumMismatchError, DocumentNotFoundError

def compute_file_checksum(file) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(8192), b''):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


@transaction.atomic
def attach_document(
    target,
    file,
    document_type: str,
    uploaded_by=None,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    description: str = '',
    retention_days: Optional[int] = None,
    retention_policy: str = 'standard',
    metadata: Optional[dict] = None,
) -> Document:
    """
    Attach a document to a target object.

    Args:
        target: Object to attach document to
        file: File object to attach
        document_type: Classification (e.g., 'invoice_pdf')
        uploaded_by: User who uploaded (optional)
        filename: Override filename (defaults to file.name)
        content_type: Override MIME type
        description: Optional description
        retention_days: Days to retain (None = forever)
        retention_policy: Policy classification
        metadata: Additional metadata dict

    Returns:
        Created Document instance
    """
    # Extract file info
    _filename = filename or getattr(file, 'name', 'unknown')
    _content_type = content_type or getattr(file, 'content_type', 'application/octet-stream')

    # Read content for checksum and size
    file.seek(0)
    content = file.read()
    file_size = len(content)
    file.seek(0)

    # Compute checksum
    checksum = compute_file_checksum(file)

    # Build metadata
    _metadata = dict(metadata) if metadata else {}
    if uploaded_by:
        _metadata['uploaded_by_id'] = uploaded_by.pk

    # Create document
    document = Document.objects.create(
        target=target,
        file=file,
        filename=_filename,
        content_type=_content_type,
        file_size=file_size,
        document_type=document_type,
        description=description,
        checksum=checksum,
        metadata=_metadata,
        retention_days=retention_days,
        retention_policy=retention_policy,
    )

    return document


def verify_document_integrity(document: Union[Document, int]) -> bool:
    """
    Verify document integrity by checking checksum.

    Args:
        document: Document instance or document ID

    Returns:
        True if checksum matches

    Raises:
        DocumentNotFoundError: If document ID doesn't exist
        ChecksumMismatchError: If checksum doesn't match
    """
    if isinstance(document, int):
        try:
            document = Document.objects.get(pk=document)
        except Document.DoesNotExist:
            raise DocumentNotFoundError(f"Document with ID {document} not found")

    if not document.verify_checksum():
        stored = document.checksum
        computed = document.compute_checksum()
        raise ChecksumMismatchError(
            f"Checksum mismatch: stored={stored}, computed={computed}"
        )

    return True
```

## Test Models

### tests/models.py

```python
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

class Invoice(models.Model):
    number = models.CharField(max_length=50)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)

    class Meta:
        app_label = 'tests'
```

## Test Cases (56 tests)

### TestDocumentModel (13 tests)
1. `test_document_has_target_generic_fk` - GenericFK works
2. `test_document_target_uses_charfield_for_id` - UUID support
3. `test_document_has_file_field` - File stored
4. `test_document_has_filename` - Filename stored
5. `test_document_has_content_type` - MIME type stored
6. `test_document_has_document_type` - Classification stored
7. `test_document_has_file_size` - Size tracked
8. `test_document_has_checksum` - SHA-256 field
9. `test_document_has_timestamps` - created_at, updated_at
10. `test_document_can_have_description` - Description stored
11. `test_document_description_is_optional` - Defaults to ''
12. `test_document_has_metadata_json_field` - JSONField works
13. `test_document_metadata_defaults_to_empty_dict` - Default {}

### TestDocumentQuerySet (2 tests)
1. `test_for_target_returns_documents_for_object` - Filters by target
2. `test_for_target_with_document_type_filter` - Chainable

### TestDocumentChecksum (3 tests)
1. `test_compute_checksum_returns_sha256` - Correct hash
2. `test_verify_checksum_returns_true_for_valid` - True for match
3. `test_verify_checksum_returns_false_for_invalid` - False for mismatch

### TestAttachDocument (13 tests)
1. `test_attach_document_creates_document` - Creates in DB
2. `test_attach_document_sets_target` - Target set
3. `test_attach_document_stores_file` - File stored
4. `test_attach_document_sets_filename` - Filename extracted
5. `test_attach_document_sets_content_type` - MIME type extracted
6. `test_attach_document_sets_file_size` - Size calculated
7. `test_attach_document_computes_checksum` - Checksum computed
8. `test_attach_document_sets_document_type` - Type stored
9. `test_attach_document_with_description` - Description works
10. `test_attach_document_with_retention_days` - Retention stored
11. `test_attach_document_with_retention_policy` - Policy stored
12. `test_attach_document_with_metadata` - Metadata stored
13. `test_attach_document_stores_uploader_in_metadata` - uploaded_by_id

### TestVerifyDocumentIntegrity (4 tests)
1. `test_verify_integrity_returns_true_for_valid` - True for valid
2. `test_verify_integrity_raises_for_invalid` - ChecksumMismatchError
3. `test_verify_integrity_by_document_id` - Accepts int ID
4. `test_verify_integrity_raises_for_missing_document` - DocumentNotFoundError

### TestRetentionPolicyFields (6 tests)
1. `test_document_has_retention_days_field` - Field exists
2. `test_document_retention_days_nullable` - Can be None
3. `test_document_has_retention_policy_field` - Field exists
4. `test_document_retention_policy_defaults_to_standard` - Default
5. `test_document_has_expires_at_field` - Field exists
6. `test_document_expires_at_nullable` - Can be None

### TestRetentionProperties (6 tests)
1. `test_is_expired_returns_true_for_past_date` - True for past
2. `test_is_expired_returns_false_for_future_date` - False for future
3. `test_is_expired_returns_false_when_no_expiration` - False for None
4. `test_under_retention_returns_true_during_period` - True during
5. `test_under_retention_returns_false_after_period` - False after
6. `test_under_retention_returns_true_when_no_retention` - True for None

### TestRetentionQuerySet (3 tests)
1. `test_expired_returns_expired_documents` - Filters expired
2. `test_expired_excludes_documents_without_expiration` - Excludes None
3. `test_not_expired_returns_valid_documents` - Returns valid + None

### TestIntegration (9 tests)
1. `test_invoice_document_workflow` - Complete workflow
2. `test_multi_document_attachment` - Multiple docs per target
3. `test_document_retention_lifecycle` - Different policies
4. `test_document_expiration_management` - expired/not_expired
5. `test_verify_multiple_documents` - Batch verification
6. `test_checksum_detects_tampering` - Detects changes
7. `test_checksum_computation_consistency` - Same content = same hash
8. `test_documents_attached_to_different_targets` - Multiple targets
9. `test_total_documents_count` - Cross-target counting

## __init__.py Exports

```python
__version__ = "0.1.0"

__all__ = [
    'Document',
    'attach_document',
    'verify_document_integrity',
    'DocumentError',
    'ChecksumMismatchError',
    'DocumentNotFoundError',
]

def __getattr__(name):
    if name == 'Document':
        from .models import Document
        return Document
    if name in ('attach_document', 'verify_document_integrity'):
        from .services import attach_document, verify_document_integrity
        return locals()[name]
    if name in ('DocumentError', 'ChecksumMismatchError', 'DocumentNotFoundError'):
        from .exceptions import DocumentError, ChecksumMismatchError, DocumentNotFoundError
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

## Key Behaviors

1. **GenericForeignKey**: Attach to any model
2. **SHA-256 Checksum**: Integrity verification
3. **Retention Policies**: Time-based document management
4. **Atomic Transactions**: attach_document is transactional
5. **Metadata Storage**: JSONField for extensibility

## Acceptance Criteria

- [ ] Document model with GenericFK
- [ ] SHA-256 checksum computation and verification
- [ ] attach_document service function
- [ ] verify_document_integrity service function
- [ ] Retention properties (is_expired, under_retention)
- [ ] QuerySet methods (for_target, expired, not_expired)
- [ ] All 56 tests passing
- [ ] README with usage examples
