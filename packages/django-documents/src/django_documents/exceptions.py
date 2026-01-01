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
