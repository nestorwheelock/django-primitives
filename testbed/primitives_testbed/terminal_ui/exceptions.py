"""Custom exceptions for terminal UI."""


class TerminalUIError(Exception):
    """Base exception for terminal UI errors."""

    pass


class EntityNotFoundError(TerminalUIError):
    """Entity not found."""

    pass


class WorkflowError(TerminalUIError):
    """Workflow execution error."""

    pass
