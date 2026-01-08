"""User impersonation for admin/staff users.

Allows staff users to "log in as" another user to debug issues
or see what customers see, while maintaining their admin session.

All actions during impersonation are logged to the audit log.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

logger = logging.getLogger(__name__)

IMPERSONATE_SESSION_KEY = "_impersonate_user_id"
IMPERSONATE_ORIGINAL_USER_KEY = "_impersonate_original_user_id"

User = get_user_model()


def _log_impersonation_event(event_type: str, actor, target_user, request, **extra_metadata):
    """Log impersonation events to the audit log."""
    try:
        from django_audit_log.services import log_event

        metadata = {
            "impersonated_user_id": str(target_user.pk) if target_user else None,
            "impersonated_user_email": target_user.email if target_user else None,
            "original_user_id": str(actor.pk),
            "original_user_email": actor.email,
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            **extra_metadata,
        }

        log_event(
            event_type=event_type,
            actor=actor,
            target=target_user,
            metadata=metadata,
        )
    except Exception as e:
        logger.warning(f"Failed to log impersonation event: {e}")


class ImpersonationMiddleware:
    """Middleware to swap request.user when impersonation is active.

    Logs all page views/actions during impersonation to the audit log.
    """

    # URLs to skip logging (static files, health checks, etc.)
    SKIP_LOGGING_PREFIXES = (
        "/static/",
        "/media/",
        "/health/",
        "/favicon",
        "/__debug__/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if impersonation is active
        impersonated_user_id = request.session.get(IMPERSONATE_SESSION_KEY)
        original_user_id = request.session.get(IMPERSONATE_ORIGINAL_USER_KEY)

        if impersonated_user_id and request.user.is_authenticated:
            try:
                impersonated_user = User.objects.get(pk=impersonated_user_id)
                original_user = User.objects.get(pk=original_user_id) if original_user_id else request.user
                # Store original user for reference
                request.original_user = original_user
                request.is_impersonating = True
                # Swap the user
                request.user = impersonated_user
            except User.DoesNotExist:
                # Clear invalid impersonation
                del request.session[IMPERSONATE_SESSION_KEY]
                if IMPERSONATE_ORIGINAL_USER_KEY in request.session:
                    del request.session[IMPERSONATE_ORIGINAL_USER_KEY]
                request.is_impersonating = False
        else:
            request.is_impersonating = False
            request.original_user = None

        response = self.get_response(request)

        # Log all requests during impersonation (except static files, etc.)
        if request.is_impersonating and not self._should_skip_logging(request):
            self._log_impersonated_request(request, response)

        return response

    def _should_skip_logging(self, request):
        """Check if this request should skip audit logging."""
        path = request.path
        return any(path.startswith(prefix) for prefix in self.SKIP_LOGGING_PREFIXES)

    def _log_impersonated_request(self, request, response):
        """Log a request made while impersonating."""
        try:
            from django_audit_log.services import log_event

            log_event(
                event_type="impersonation.page_view",
                actor=request.original_user,
                target=request.user,
                metadata={
                    "impersonated_user_id": str(request.user.pk),
                    "impersonated_user_email": request.user.email,
                    "original_user_id": str(request.original_user.pk),
                    "original_user_email": request.original_user.email,
                    "method": request.method,
                    "path": request.path,
                    "query_string": request.META.get("QUERY_STRING", "")[:500],
                    "status_code": response.status_code,
                    "ip_address": request.META.get("REMOTE_ADDR"),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log impersonated request: {e}")


class ImpersonateStartView(View):
    """Start impersonating a user. Staff/superusers only."""

    def post(self, request, user_id):
        # Only staff/superusers can impersonate
        if not request.user.is_staff and not request.user.is_superuser:
            return HttpResponseForbidden("Permission denied")

        # Can't impersonate while already impersonating
        if request.session.get(IMPERSONATE_SESSION_KEY):
            messages.warning(request, "Already impersonating. Stop first.")
            return redirect(request.META.get("HTTP_REFERER", "/"))

        target_user = get_object_or_404(User, pk=user_id)

        # Don't allow impersonating superusers unless you are one
        if target_user.is_superuser and not request.user.is_superuser:
            return HttpResponseForbidden("Cannot impersonate superusers")

        # Store impersonation in session
        request.session[IMPERSONATE_SESSION_KEY] = target_user.pk
        request.session[IMPERSONATE_ORIGINAL_USER_KEY] = request.user.pk

        # Log impersonation start
        _log_impersonation_event(
            event_type="impersonation.started",
            actor=request.user,
            target_user=target_user,
            request=request,
        )

        messages.success(request, f"Now viewing as {target_user.email or target_user.username}")

        # Redirect to portal dashboard
        return redirect(reverse("portal:dashboard"))


class ImpersonateStopView(View):
    """Stop impersonating and return to original user."""

    def post(self, request):
        impersonated_user_id = request.session.get(IMPERSONATE_SESSION_KEY)
        original_user_id = request.session.get(IMPERSONATE_ORIGINAL_USER_KEY)

        # Log impersonation stop before clearing session
        if impersonated_user_id and original_user_id:
            try:
                impersonated_user = User.objects.get(pk=impersonated_user_id)
                original_user = User.objects.get(pk=original_user_id)
                _log_impersonation_event(
                    event_type="impersonation.stopped",
                    actor=original_user,
                    target_user=impersonated_user,
                    request=request,
                )
            except User.DoesNotExist:
                pass

        if IMPERSONATE_SESSION_KEY in request.session:
            del request.session[IMPERSONATE_SESSION_KEY]

        if IMPERSONATE_ORIGINAL_USER_KEY in request.session:
            del request.session[IMPERSONATE_ORIGINAL_USER_KEY]

        messages.success(request, "Stopped impersonating. Back to your account.")

        # Redirect to staff portal or admin
        return redirect("/staff/diveops/")

    def get(self, request):
        # Allow GET for convenience (link in banner)
        return self.post(request)


def is_impersonating(request):
    """Check if current session is impersonating."""
    return getattr(request, "is_impersonating", False)


def get_original_user(request):
    """Get the original staff user during impersonation."""
    return getattr(request, "original_user", None)


def impersonation_context(request):
    """Context processor to add impersonation info to templates."""
    return {
        "is_impersonating": getattr(request, "is_impersonating", False),
        "original_user": getattr(request, "original_user", None),
    }
