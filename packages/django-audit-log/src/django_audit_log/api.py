"""Public API for audit logging.

This is the primary interface for applications. Import and use these functions:

    from django_audit_log import log, log_event

    # Log a model operation
    log(action='create', obj=my_instance, actor=request.user, request=request)

    # Log a non-model event (login, permission denied, etc.)
    log_event(action='login', actor=user, metadata={'method': 'oauth'})
"""
from .models import AuditLog


def _get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request):
    """Extract user agent from request."""
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def _get_actor_display(actor):
    """Get display string for actor."""
    if not actor:
        return ''
    if hasattr(actor, 'email') and actor.email:
        return actor.email
    if hasattr(actor, 'username') and actor.username:
        return actor.username
    return str(actor)


def log(
    action,
    obj=None,
    obj_label=None,
    obj_id=None,
    obj_repr=None,
    actor=None,
    actor_display=None,
    request=None,
    changes=None,
    metadata=None,
    sensitivity='normal',
    is_system=False,
    request_id=None,
    trace_id=None,
):
    """Log an audit event for a model operation.

    Args:
        action: Action type (create, update, delete, view, etc.)
        obj: Model instance (optional, extracts label/id/repr automatically)
        obj_label: Model label in app.model format (if obj not provided)
        obj_id: Object primary key (if obj not provided)
        obj_repr: Object string representation (if obj not provided)
        actor: User who performed the action (optional)
        actor_display: Actor display name (defaults to user email/username)
        request: HTTP request (for IP, user agent extraction)
        changes: Dict of field changes: {"field": {"old": x, "new": y}}
        metadata: Additional context as dict
        sensitivity: normal, high, or critical
        is_system: True if action performed by system
        request_id: Request correlation ID
        trace_id: Distributed trace ID

    Returns:
        AuditLog instance
    """
    # Extract model info from obj if provided
    if obj is not None:
        obj_label = f'{obj._meta.app_label}.{obj._meta.model_name}'
        obj_id = str(obj.pk) if obj.pk else ''
        obj_repr = str(obj)[:200] if obj_repr is None else obj_repr

    # Build actor display
    if actor_display is None:
        actor_display = _get_actor_display(actor)

    return AuditLog.objects.create(
        action=action,
        model_label=obj_label or '',
        object_id=str(obj_id) if obj_id else '',
        object_repr=obj_repr[:200] if obj_repr else '',
        actor_user=actor,
        actor_display=actor_display[:200] if actor_display else '',
        changes=changes or {},
        metadata=metadata or {},
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        request_id=request_id or '',
        trace_id=trace_id or '',
        sensitivity=sensitivity,
        is_system=is_system,
    )


def log_event(
    action,
    actor=None,
    actor_display=None,
    request=None,
    metadata=None,
    sensitivity='normal',
    is_system=False,
    request_id=None,
    trace_id=None,
):
    """Log a non-model event (login, permission denied, WAF block, etc.).

    Args:
        action: Event type (login, logout, permission_denied, etc.)
        actor: User who triggered the event (optional)
        actor_display: Actor display name (defaults to user email/username)
        request: HTTP request (for IP, user agent extraction)
        metadata: Additional context as dict
        sensitivity: normal, high, or critical
        is_system: True if event triggered by system
        request_id: Request correlation ID
        trace_id: Distributed trace ID

    Returns:
        AuditLog instance
    """
    if actor_display is None:
        actor_display = _get_actor_display(actor)

    return AuditLog.objects.create(
        action=action,
        actor_user=actor,
        actor_display=actor_display[:200] if actor_display else '',
        metadata=metadata or {},
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        request_id=request_id or '',
        trace_id=trace_id or '',
        sensitivity=sensitivity,
        is_system=is_system,
    )
