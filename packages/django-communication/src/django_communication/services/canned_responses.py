"""Canned response services for listing, rendering, and managing snippets."""

import logging
import re
from typing import Any

from django.conf import settings
from django.db.models import Q, QuerySet
from django.template import Context, Template
from django.utils.module_loading import import_string

from ..models.canned_response import CannedResponse, ResponseChannel, Visibility

logger = logging.getLogger(__name__)

# Regex to extract {{ variable_name }} from template text
VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}")


def extract_variables(body: str) -> set[str]:
    """Extract variable names from a canned response body.

    Args:
        body: Template text with {{ variable }} placeholders

    Returns:
        Set of variable names found in the body

    Example:
        >>> extract_variables("Hello {{ first_name }}, your trip on {{ trip_date }}!")
        {'first_name', 'trip_date'}
    """
    return set(VARIABLE_PATTERN.findall(body))


def render_canned_response(
    canned_response: CannedResponse,
    context: dict[str, Any],
) -> str:
    """Render a canned response with variable substitution.

    Uses Django template engine with a restricted context.
    Missing variables are rendered as empty strings.

    Args:
        canned_response: The canned response to render
        context: Dictionary of variable values

    Returns:
        Rendered text with variables substituted

    Example:
        >>> render_canned_response(response, {"first_name": "John"})
        "Hello John, welcome to our dive shop!"
    """
    try:
        template = Template(canned_response.body)
        rendered = template.render(Context(context))
        return rendered
    except Exception as e:
        logger.warning(
            "Error rendering canned response %s: %s",
            canned_response.pk,
            e,
        )
        # Fallback: return body with empty substitutions
        return VARIABLE_PATTERN.sub("", canned_response.body)


def get_context_for_conversation(
    conversation=None,
    actor=None,
    recipient=None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Build context for rendering canned responses.

    Calls all configured context providers and merges results.
    Later providers override earlier ones.

    Context providers are configured in settings:
        COMMUNICATION_CANNED_CONTEXT_PROVIDERS = [
            "myapp.context.get_diver_context",
            "myapp.context.get_booking_context",
        ]

    Each provider receives (conversation, actor, recipient, extra)
    and returns a dict of variables.

    Args:
        conversation: Optional Conversation instance
        actor: The person inserting the canned response (staff)
        recipient: The person receiving the message (customer)
        extra: Additional context from caller

    Returns:
        Merged context dictionary
    """
    context = {}

    # Get configured providers
    provider_paths = getattr(
        settings,
        "COMMUNICATION_CANNED_CONTEXT_PROVIDERS",
        [],
    )

    for path in provider_paths:
        try:
            provider = import_string(path)
            provider_context = provider(
                conversation=conversation,
                actor=actor,
                recipient=recipient,
                extra=extra or {},
            )
            if provider_context:
                context.update(provider_context)
        except Exception as e:
            logger.warning("Error calling context provider %s: %s", path, e)

    # Add extra context last (highest priority)
    if extra:
        context.update(extra)

    return context


def list_canned_responses(
    *,
    actor,
    org=None,
    channel: str | None = None,
    language: str | None = None,
    q: str | None = None,
    tags: list[str] | None = None,
) -> QuerySet[CannedResponse]:
    """List canned responses available to an actor.

    Filters by visibility rules:
    - Private: only creator can see
    - Org: members of owner_party can see
    - Public: all users can see

    Args:
        actor: Person requesting the list
        org: Optional Party to filter by organization
        channel: Optional channel filter (includes 'any' responses)
        language: Optional language filter
        q: Optional search query (searches title and body)
        tags: Optional list of tag names to filter by

    Returns:
        QuerySet of accessible, active canned responses
    """
    qs = CannedResponse.objects.filter(is_active=True)

    # Visibility filtering
    visibility_filter = Q(visibility=Visibility.PUBLIC)

    if actor:
        # Creator can always see their private responses
        visibility_filter |= Q(visibility=Visibility.PRIVATE, created_by=actor)

        # Org responses - for now, if no owner_party, visible to all org members
        if org:
            visibility_filter |= Q(visibility=Visibility.ORG, owner_party=org)
        else:
            # If no org specified, include org responses without owner_party
            visibility_filter |= Q(visibility=Visibility.ORG, owner_party__isnull=True)

    qs = qs.filter(visibility_filter)

    # Channel filtering - include channel match OR 'any'
    if channel:
        qs = qs.filter(Q(channel=channel) | Q(channel=ResponseChannel.ANY))

    # Language filtering
    if language:
        qs = qs.filter(Q(language=language) | Q(language=""))

    # Search query
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))

    # Tag filtering
    if tags:
        qs = qs.filter(tags__name__in=tags).distinct()

    return qs.order_by("title")


def get_canned_response(pk) -> CannedResponse | None:
    """Get a single canned response by primary key.

    Args:
        pk: Primary key of the canned response

    Returns:
        CannedResponse instance or None if not found
    """
    try:
        return CannedResponse.objects.get(pk=pk)
    except CannedResponse.DoesNotExist:
        return None


def create_canned_response(
    *,
    title: str,
    body: str,
    created_by,
    channel: str = ResponseChannel.ANY,
    language: str = "",
    visibility: str = Visibility.ORG,
    owner_party=None,
    tags: list[str] | None = None,
) -> CannedResponse:
    """Create a new canned response.

    Args:
        title: Short label for picker UI
        body: Message content with {{ variable }} placeholders
        created_by: Person creating the response
        channel: Channel constraint (default: any)
        language: Language code (default: all languages)
        visibility: Visibility scope (default: org)
        owner_party: Optional Party for org-scoped responses
        tags: Optional list of tag names to add

    Returns:
        Created CannedResponse instance
    """
    from ..models import CannedResponseTag

    response = CannedResponse.objects.create(
        title=title,
        body=body,
        created_by=created_by,
        channel=channel,
        language=language,
        visibility=visibility,
        owner_party=owner_party,
    )

    if tags:
        for tag_name in tags:
            tag, _ = CannedResponseTag.objects.get_or_create(name=tag_name)
            response.tags.add(tag)

    return response


def can_use_canned_response(actor, canned_response: CannedResponse) -> bool:
    """Check if an actor can use a canned response.

    Args:
        actor: Person attempting to use the response
        canned_response: The response to check

    Returns:
        True if actor has permission to use the response
    """
    if not canned_response.is_active:
        return False

    if canned_response.visibility == Visibility.PUBLIC:
        return True

    if canned_response.visibility == Visibility.PRIVATE:
        return canned_response.created_by == actor

    if canned_response.visibility == Visibility.ORG:
        # TODO: Check org membership when party membership is available
        # For now, org responses without owner_party are accessible to all
        if canned_response.owner_party is None:
            return True
        # Would check: actor is member of canned_response.owner_party
        return True

    return False


def can_edit_canned_response(actor, canned_response: CannedResponse) -> bool:
    """Check if an actor can edit a canned response.

    Args:
        actor: Person attempting to edit the response
        canned_response: The response to check

    Returns:
        True if actor has permission to edit the response
    """
    # Creator can always edit
    if canned_response.created_by == actor:
        return True

    # TODO: Check admin/role permissions when available
    return False


def deactivate_canned_response(pk) -> bool:
    """Deactivate a canned response (soft disable).

    Args:
        pk: Primary key of the canned response

    Returns:
        True if successfully deactivated, False if not found
    """
    try:
        response = CannedResponse.objects.get(pk=pk)
        response.is_active = False
        response.save(update_fields=["is_active", "updated_at"])
        return True
    except CannedResponse.DoesNotExist:
        return False
