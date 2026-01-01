# django-documents

Document attachment and storage primitives for Django applications.

## Features

- **Document Model**: Attach documents to any model via GenericFK
- **Checksum Validation**: SHA-256 checksums for integrity verification
- **Retention Policies**: Configure document lifecycle and expiration
- **Storage Abstraction**: Pluggable storage backends (local, S3, etc.)
- **Immutability**: Documents are append-only once created

## Installation

```bash
pip install django-documents
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django.contrib.contenttypes',
    'django_documents',
]
```

Run migrations:

```bash
python manage.py migrate django_documents
```

## Usage

### Attaching Documents

```python
from django_documents.models import Document
from django_documents.services import attach_document

# Attach a document to any model
doc = attach_document(
    target=my_invoice,
    file=uploaded_file,
    document_type='invoice_pdf',
    uploaded_by=request.user,
)

# Verify integrity
if doc.verify_checksum():
    print("Document integrity verified")
```

### Querying Documents

```python
from django_documents.models import Document

# Get all documents for an object
docs = Document.objects.for_target(my_invoice)

# Filter by document type
pdfs = Document.objects.for_target(my_invoice).filter(document_type='invoice_pdf')
```

### Retention Policies

```python
from django_documents.models import Document

# Set retention period
doc = Document.objects.create(
    target=my_record,
    file=uploaded_file,
    retention_days=365 * 7,  # 7 year retention
    retention_policy='regulatory',
)

# Find expired documents
expired = Document.objects.expired()
```

## Configuration

```python
# settings.py

# Default storage backend
DOCUMENTS_STORAGE_BACKEND = 'django.core.files.storage.FileSystemStorage'

# Default retention (days, None = forever)
DOCUMENTS_DEFAULT_RETENTION_DAYS = None

# Checksum algorithm
DOCUMENTS_CHECKSUM_ALGORITHM = 'sha256'
```

## License

MIT
