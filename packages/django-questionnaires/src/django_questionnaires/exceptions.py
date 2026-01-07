"""Exceptions for django-questionnaires."""


class QuestionnaireError(Exception):
    """Base exception for questionnaire operations."""

    pass


class DefinitionNotFoundError(QuestionnaireError):
    """Raised when a questionnaire definition is not found."""

    pass


class DefinitionNotPublishedError(QuestionnaireError):
    """Raised when trying to create an instance from unpublished definition."""

    pass


class DefinitionAlreadyPublishedError(QuestionnaireError):
    """Raised when trying to modify a published definition."""

    pass


class InstanceNotFoundError(QuestionnaireError):
    """Raised when a questionnaire instance is not found."""

    pass


class InstanceAlreadyCompletedError(QuestionnaireError):
    """Raised when trying to submit to an already completed instance."""

    pass


class InstanceExpiredError(QuestionnaireError):
    """Raised when trying to submit to an expired instance."""

    pass


class InvalidResponseError(QuestionnaireError):
    """Raised when a response fails validation."""

    pass


class MissingRequiredResponseError(QuestionnaireError):
    """Raised when required questions are not answered."""

    pass


class InstanceNotFlaggedError(QuestionnaireError):
    """Raised when trying to clear an instance that is not flagged."""

    pass
