"""Exceptions for django-documents."""


class DocumentError(Exception):
    """Base exception for document errors."""
    pass


class ChecksumMismatchError(DocumentError):
    """Raised when document checksum verification fails."""
    pass


class DocumentNotFoundError(DocumentError):
    """Raised when a document cannot be found."""
    pass


class RetentionViolationError(DocumentError):
    """Raised when attempting to delete a document under retention."""
    pass


class StorageError(DocumentError):
    """Raised when storage operations fail."""
    pass


class ImmutableChecksumError(DocumentError):
    """Raised when attempting to modify a document's checksum after it's set."""

    def __init__(self, document_id):
        self.document_id = document_id
        super().__init__(
            f"Cannot modify checksum of document {document_id} - checksums are immutable. "
            "Checksums verify document integrity and cannot be changed once set."
        )
