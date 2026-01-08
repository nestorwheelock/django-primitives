"""Exceptions for django-cms-core."""


class CMSError(Exception):
    """Base exception for CMS errors."""
    pass


class PageNotFoundError(CMSError):
    """Raised when a page is not found."""
    pass


class PageNotPublishedError(CMSError):
    """Raised when trying to access unpublished page via public API."""
    pass


class PageAlreadyPublishedError(CMSError):
    """Raised when trying to publish an already published page."""
    pass


class BlockTypeNotFoundError(CMSError):
    """Raised when a block type is not registered."""
    pass


class BlockValidationError(CMSError):
    """Raised when block data fails validation."""
    pass


class AccessDeniedError(CMSError):
    """Raised when user doesn't have access to a page."""
    pass


class InvalidStateTransitionError(CMSError):
    """Raised when an invalid state transition is attempted."""
    pass
