"""Document services for attachment and verification."""

import hashlib
from typing import Union, Optional, Any
from django.db import transaction

from django_documents.models import Document
from django_documents.exceptions import ChecksumMismatchError, DocumentNotFoundError


def compute_file_checksum(file) -> str:
    """
    Compute SHA-256 checksum of a file.

    Args:
        file: File-like object to hash.

    Returns:
        Hexadecimal string of the SHA-256 hash.
    """
    sha256_hash = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(8192), b""):
        sha256_hash.update(chunk)
    file.seek(0)
    return sha256_hash.hexdigest()


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

    Creates a Document record with computed checksum and file metadata.

    Args:
        target: The object to attach the document to (via GenericFK).
        file: Uploaded file object.
        document_type: Classification of the document (e.g., 'invoice_pdf').
        uploaded_by: User who uploaded the document (optional).
        filename: Override filename (defaults to file.name).
        content_type: Override MIME type (defaults to file.content_type).
        description: Optional description of the document.
        retention_days: Number of days to retain (None = forever).
        retention_policy: Retention policy classification.
        metadata: Additional metadata dictionary.

    Returns:
        The created Document instance.

    Usage:
        doc = attach_document(
            target=my_invoice,
            file=uploaded_file,
            document_type='invoice_pdf',
            uploaded_by=request.user,
        )
    """
    # Get file metadata
    actual_filename = filename or getattr(file, 'name', 'unknown')
    actual_content_type = content_type or getattr(file, 'content_type', 'application/octet-stream')

    # Read file content to compute checksum and size
    file.seek(0)
    file_content = file.read()
    file_size = len(file_content)
    checksum = hashlib.sha256(file_content).hexdigest()
    file.seek(0)

    # Build metadata
    doc_metadata = metadata.copy() if metadata else {}
    if uploaded_by:
        doc_metadata['uploaded_by_id'] = uploaded_by.pk

    # Create document
    doc = Document.objects.create(
        target=target,
        file=file,
        filename=actual_filename,
        content_type=actual_content_type,
        file_size=file_size,
        checksum=checksum,
        document_type=document_type,
        description=description,
        retention_days=retention_days,
        retention_policy=retention_policy,
        metadata=doc_metadata,
    )

    return doc


def verify_document_integrity(document: Union[Document, int]) -> bool:
    """
    Verify the integrity of a document by checking its checksum.

    Args:
        document: Document instance or document ID.

    Returns:
        True if the checksum matches.

    Raises:
        DocumentNotFoundError: If document ID doesn't exist.
        ChecksumMismatchError: If checksum doesn't match file content.
    """
    # Get document if ID was passed
    if isinstance(document, int):
        try:
            document = Document.objects.get(pk=document)
        except Document.DoesNotExist:
            raise DocumentNotFoundError(f"Document with ID {document} not found")

    # Verify checksum
    if not document.verify_checksum():
        raise ChecksumMismatchError(
            f"Checksum mismatch for document {document.pk}: "
            f"stored={document.checksum}, computed={document.compute_checksum()}"
        )

    return True
