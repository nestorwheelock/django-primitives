"""Custom exceptions for django-worklog."""


class WorklogError(Exception):
    """Base exception for worklog errors."""
    pass


class NoActiveSession(WorklogError):
    """Raised when stop_session called with no active session."""

    def __init__(self, user):
        self.user = user
        super().__init__(f"No active session for user '{user}'")


class SessionAlreadyStopped(WorklogError):
    """Raised when attempting to stop an already-stopped session."""

    def __init__(self, session_id):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' is already stopped")


class InvalidContext(WorklogError):
    """Raised when context is invalid or None."""

    def __init__(self, reason: str = "Context cannot be None"):
        self.reason = reason
        super().__init__(reason)
