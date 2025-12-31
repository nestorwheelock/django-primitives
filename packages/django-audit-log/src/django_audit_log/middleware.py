"""Middleware for capturing request context.

Optional middleware that captures request metadata (IP, user agent, request ID)
and makes it available to audit log calls via thread-local storage.

Usage in settings.py:

    MIDDLEWARE = [
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django_audit_log.middleware.AuditContextMiddleware',  # After auth
        ...
    ]

Then in your code, the request context is automatically captured:

    from django_audit_log import log
    log(action='create', obj=instance, actor=request.user)
    # IP and user agent captured automatically from thread-local

Or access context directly:

    from django_audit_log.middleware import get_current_request
    request = get_current_request()
"""
import threading
import uuid

_thread_locals = threading.local()


def get_current_request():
    """Get the current request from thread-local storage."""
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    """Get the current user from thread-local storage."""
    return getattr(_thread_locals, 'user', None)


def get_request_id():
    """Get the current request ID from thread-local storage."""
    return getattr(_thread_locals, 'request_id', None)


def set_request_context(request=None, user=None, request_id=None):
    """Set request context in thread-local storage."""
    _thread_locals.request = request
    _thread_locals.user = user
    _thread_locals.request_id = request_id


def clear_request_context():
    """Clear request context from thread-local storage."""
    _thread_locals.request = None
    _thread_locals.user = None
    _thread_locals.request_id = None


class AuditContextMiddleware:
    """Middleware to capture request context for audit logging.

    Captures:
    - The HTTP request object
    - The authenticated user (if any)
    - A unique request ID for correlation

    This context is stored in thread-local storage and can be accessed
    via get_current_request(), get_current_user(), get_request_id().
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate request ID if not already present
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        if not request_id:
            request_id = str(uuid.uuid4())[:8]

        # Store request ID on request for easy access
        request.audit_request_id = request_id

        # Get user if authenticated
        user = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user

        # Set thread-local context
        set_request_context(
            request=request,
            user=user,
            request_id=request_id,
        )

        try:
            response = self.get_response(request)
        finally:
            # Always clear context after request
            clear_request_context()

        return response
