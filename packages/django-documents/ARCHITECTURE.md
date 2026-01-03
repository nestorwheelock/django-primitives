# Architecture: django-documents

**Status:** Stable / v0.1.0

File attachment storage with checksum verification and retention policies.

---

## What This Package Is For

Answering the question: **"What files are attached to this object?"**

Use cases:
- Attaching files to any model (invoices, receipts, contracts)
- Verifying file integrity via SHA-256 checksum
- Managing document retention policies
- Tracking document expiration
- Storing file metadata (size, type, description)

---

## What This Package Is NOT For

- **Not a full DMS** - Use dedicated document management for versioning, workflows
- **Not image processing** - Use Pillow/ImageKit for thumbnails, resizing
- **Not search indexing** - Use Elasticsearch for full-text search
- **Not encryption** - Encrypt at storage layer (S3 encryption, etc.)

---

## Design Principles

1. **GenericFK attachment** - Works with any model, not just specific types
2. **Checksum immutability** - Once set, checksum cannot be modified
3. **Retention policies** - Configurable retention period per document
4. **Expiration tracking** - Documents can have explicit expiration dates
5. **Metadata flexibility** - JSONField for arbitrary metadata

---

## Data Model

```
Document
├── id (UUID, BaseModel)
├── target (GenericFK)
│   ├── target_content_type (FK → ContentType)
│   └── target_id (CharField for UUID support)
├── file (FileField)
├── filename (original name)
├── content_type (MIME type)
├── file_size (bytes)
├── document_type (classification)
├── description (optional)
├── checksum (SHA-256, immutable)
├── metadata (JSON)
├── retention_days (nullable)
├── retention_policy (standard|regulatory|legal)
├── expires_at (nullable)
├── created_at (auto)
├── updated_at (auto)
└── deleted_at (soft delete)

Retention Flow:
  Document created
       ↓
  retention_days set (e.g., 365)
       ↓
  retention_ends_at = created_at + retention_days
       ↓
  If now > retention_ends_at: safe to delete
  If retention_days is None: keep forever
```

---

## Public API

### Creating Documents

```python
from django_documents.models import Document
from django_documents.services import create_document

# Using service function (recommended)
doc = create_document(
    target=invoice,
    file=uploaded_file,
    document_type='invoice_pdf',
    description='January 2024 Invoice',
    retention_days=365 * 7,  # 7 years for financial
    retention_policy='regulatory',
)

# Direct creation
doc = Document.objects.create(
    target=invoice,
    file=uploaded_file,
    filename='invoice.pdf',
    content_type='application/pdf',
    file_size=uploaded_file.size,
    document_type='invoice_pdf',
)

# Compute and set checksum
doc.checksum = doc.compute_checksum()
doc.save()
```

### Querying Documents

```python
from django_documents.models import Document

# Get documents for a specific object
docs = Document.objects.for_target(invoice)

# Get expired documents (past expires_at)
expired = Document.objects.expired()

# Get non-expired documents
current = Document.objects.not_expired()

# Get documents safe to delete (past retention)
for doc in Document.objects.all():
    if not doc.under_retention:
        doc.delete()  # Safe to delete
```

### Verifying Integrity

```python
doc = Document.objects.get(pk=doc_id)

# Verify checksum matches file content
if doc.verify_checksum():
    print("Document is intact")
else:
    print("Document may be corrupted!")

# Check properties
print(f"Expired: {doc.is_expired}")
print(f"Under retention: {doc.under_retention}")
print(f"Retention ends: {doc.retention_ends_at}")
```

---

## Hard Rules

1. **Checksum is immutable** - Raises `ImmutableChecksumError` on modification attempt
2. **target_id is always string** - Stored as CharField for UUID support
3. **Retention policy is informational** - Enforcement is application responsibility
4. **Checksum uses SHA-256** - 64-character hex string

---

## Invariants

- Document.checksum cannot be changed after initial set (immutable)
- Document.target_id is always stored as string
- Document with `retention_days=None` is never "safe to delete"
- `under_retention=True` when `now < created_at + retention_days`
- `is_expired=True` when `expires_at IS NOT NULL AND now > expires_at`

---

## Known Gotchas

### 1. Checksum Must Be Computed After Save

**Problem:** Checksum not set on initial creation.

```python
# WRONG - file not yet available
doc = Document.objects.create(
    target=invoice,
    file=uploaded_file,
    checksum=???  # Can't compute yet!
)

# CORRECT - compute after save
doc = Document.objects.create(
    target=invoice,
    file=uploaded_file,
    filename='invoice.pdf',
    ...
)
doc.checksum = doc.compute_checksum()
doc.save()
```

### 2. Checksum Immutability

**Problem:** Trying to modify checksum after set.

```python
doc.checksum = "new_checksum_value"
doc.save()  # Raises ImmutableChecksumError!
```

**Solution:** Checksums cannot be changed. If file changes, create new document.

### 3. Retention vs Expiration

**Problem:** Confusion between the two concepts.

```python
# retention_days: how long to KEEP the document
# expires_at: when content EXPIRES (different concept)

# Example: A certification document
doc = Document.objects.create(
    retention_days=365 * 10,  # Keep for 10 years
    expires_at=date_when_cert_expires,  # Cert expires in 1 year
)

# is_expired: True when certification is no longer valid
# under_retention: True when we must keep the record
```

### 4. File Size Not Auto-Computed

**Problem:** file_size is 0 if not explicitly set.

```python
# WRONG - file_size will be 0
doc = Document.objects.create(
    file=uploaded_file,
    ...
)

# CORRECT - set file_size explicitly
doc = Document.objects.create(
    file=uploaded_file,
    file_size=uploaded_file.size,
    ...
)
```

---

## Recommended Usage

### 1. Use Service for Creation

```python
from django_documents.services import create_document

# Service handles checksum, file_size, etc.
doc = create_document(
    target=invoice,
    file=uploaded_file,
    document_type='invoice_pdf',
)
```

### 2. Classify with document_type

```python
# Define document types for your domain
DOCUMENT_TYPES = [
    'invoice_pdf',
    'receipt_image',
    'contract_signed',
    'id_photo',
    'prescription_scan',
]

# Query by type
invoices = Document.objects.filter(document_type='invoice_pdf')
```

### 3. Implement Cleanup Job

```python
from django.utils import timezone

def cleanup_expired_documents():
    """Delete documents past retention period."""
    for doc in Document.objects.all():
        if not doc.under_retention:
            # Past retention, safe to delete
            doc.file.delete()  # Delete file from storage
            doc.delete()       # Delete record
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- Document model with GenericFK target
- SHA-256 checksum with immutability
- Retention policy support
- Expiration tracking
- Custom queryset methods
