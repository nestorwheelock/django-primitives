"""Services for django-cms-core.

Domain-agnostic service functions for managing content pages, blocks,
and publishing workflow.
"""

import hashlib
import json
from typing import Any

from django.db import models, transaction
from django.utils import timezone

from .models import (
    ContentPage,
    ContentBlock,
    PageStatus,
    AccessLevel,
)
from .registry import BlockRegistry


def create_page(
    slug: str,
    title: str,
    user: Any,
    status: str = PageStatus.DRAFT,
    access_level: str = AccessLevel.PUBLIC,
    required_roles: list[str] | None = None,
    required_entitlements: list[str] | None = None,
    seo_title: str = "",
    seo_description: str = "",
    og_image_url: str = "",
    canonical_url: str = "",
    robots: str = "index, follow",
    template_key: str = "default",
    metadata: dict | None = None,
    sort_order: int = 0,
    is_indexable: bool = True,
) -> ContentPage:
    """Create a new content page.

    Args:
        slug: URL-safe identifier
        title: Display title
        user: User creating the page (for audit)
        status: Page status (default: draft)
        access_level: Access control level (default: public)
        required_roles: Role slugs for role-based access
        required_entitlements: Entitlement codes for entitlement access
        seo_title: Custom SEO title
        seo_description: Meta description
        og_image_url: Open Graph image URL
        canonical_url: Canonical URL
        robots: Robots meta tag
        template_key: Template hint
        metadata: Custom metadata
        sort_order: Display order
        is_indexable: Include in sitemaps

    Returns:
        The created ContentPage
    """
    return ContentPage.objects.create(
        slug=slug,
        title=title,
        status=status,
        access_level=access_level,
        required_roles=required_roles or [],
        required_entitlements=required_entitlements or [],
        seo_title=seo_title,
        seo_description=seo_description,
        og_image_url=og_image_url,
        canonical_url=canonical_url,
        robots=robots,
        template_key=template_key,
        metadata=metadata or {},
        sort_order=sort_order,
        is_indexable=is_indexable,
    )


def add_block(
    page: ContentPage,
    block_type: str,
    data: dict,
    sequence: int | None = None,
) -> ContentBlock:
    """Add a content block to a page.

    Args:
        page: The parent page
        block_type: Block type identifier (registry key)
        data: Block content data
        sequence: Optional explicit sequence (auto-assigned if not provided)

    Returns:
        The created ContentBlock
    """
    with transaction.atomic():
        if sequence is None:
            # Auto-assign sequence based on existing blocks
            # Use all_objects to bypass soft-delete filter, then filter manually
            max_seq = ContentBlock.all_objects.filter(
                page=page,
                deleted_at__isnull=True,
            ).aggregate(max_seq=models.Max("sequence"))["max_seq"]
            # Use explicit None check since max_seq=0 is falsy but valid
            sequence = 0 if max_seq is None else max_seq + 1

        return ContentBlock.objects.create(
            page=page,
            block_type=block_type,
            data=data,
            sequence=sequence,
        )



def update_block(
    block: ContentBlock,
    data: dict | None = None,
    sequence: int | None = None,
    is_active: bool | None = None,
) -> ContentBlock:
    """Update a content block.

    Args:
        block: The block to update
        data: New data (if provided)
        sequence: New sequence (if provided)
        is_active: New is_active state (if provided)

    Returns:
        The updated ContentBlock
    """
    if data is not None:
        block.data = data
    if sequence is not None:
        block.sequence = sequence
    if is_active is not None:
        block.is_active = is_active

    block.save()
    return block


def reorder_blocks(page: ContentPage, block_ids: list[str]) -> None:
    """Reorder blocks based on provided ID order.

    Args:
        page: The page whose blocks to reorder
        block_ids: List of block IDs in desired order
    """
    with transaction.atomic():
        for idx, block_id in enumerate(block_ids):
            ContentBlock.objects.filter(
                page=page,
                id=block_id,
                deleted_at__isnull=True,
            ).update(sequence=idx)


def delete_block(block: ContentBlock) -> None:
    """Soft-delete a content block.

    Args:
        block: The block to delete
    """
    block.delete()


def publish_page(page: ContentPage, user: Any) -> ContentPage:
    """Publish a content page.

    Creates an immutable snapshot of the page and its blocks,
    sets status to published, and records publish metadata.

    Args:
        page: The page to publish
        user: User performing the publish

    Returns:
        The published ContentPage
    """
    with transaction.atomic():
        # Lock the page for update
        page = ContentPage.objects.select_for_update().get(pk=page.pk)

        # Get active blocks ordered by sequence
        blocks = list(
            page.blocks.filter(
                deleted_at__isnull=True,
                is_active=True,
            ).order_by("sequence")
        )

        # Build snapshot
        now = timezone.now()
        snapshot = {
            "version": 1,
            "published_at": now.isoformat(),
            "published_by_id": str(user.id),
            "meta": {
                "title": page.title,
                "slug": page.slug,
                "path": f"/{page.slug}/",
                "seo_title": page.seo_title,
                "seo_description": page.seo_description,
                "og_image_url": page.og_image_url,
                "robots": page.robots,
            },
            "access_control": {
                "level": page.access_level,
                "required_roles": page.required_roles,
                "required_entitlements": page.required_entitlements,
            },
            "blocks": [
                {
                    "id": str(b.id),
                    "type": b.block_type,
                    "sequence": b.sequence,
                    "data": b.data,
                }
                for b in blocks
            ],
        }

        # Add checksum
        snapshot_json = json.dumps(snapshot, sort_keys=True, default=str)
        snapshot["checksum"] = hashlib.sha256(snapshot_json.encode()).hexdigest()

        # Update page
        page.status = PageStatus.PUBLISHED
        page.published_snapshot = snapshot
        page.published_at = now
        page.published_by = user
        page.save()

        return page


def unpublish_page(page: ContentPage) -> ContentPage:
    """Unpublish a page, returning it to draft status.

    Args:
        page: The page to unpublish

    Returns:
        The unpublished ContentPage
    """
    page.status = PageStatus.DRAFT
    page.published_snapshot = None
    page.published_at = None
    page.save()
    return page


def archive_page(page: ContentPage) -> ContentPage:
    """Archive a page.

    Args:
        page: The page to archive

    Returns:
        The archived ContentPage
    """
    page.status = PageStatus.ARCHIVED
    page.save()
    return page


def validate_page_blocks(page: ContentPage) -> list[str]:
    """Validate all blocks on a page.

    Checks that each block has a registered type and valid data.

    Args:
        page: The page to validate

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []

    blocks = page.blocks.filter(deleted_at__isnull=True, is_active=True)
    for block in blocks:
        block_errors = BlockRegistry.validate_block(block.block_type, block.data)
        for error in block_errors:
            errors.append(f"Block {block.id} ({block.block_type}): {error}")

    return errors


def check_page_access(page: ContentPage, user: Any = None) -> tuple[bool, str]:
    """Check if a user has access to a page.

    Implements access control based on page's access_level:
    - PUBLIC: Anyone can access
    - AUTHENTICATED: Must be logged in
    - ROLE: Must have one of the required roles (staff or superuser)
    - ENTITLEMENT: Must pass entitlement check (via hook)

    Fail-secure: If entitlement hook is not configured or raises,
    access is denied.

    Args:
        page: The page to check access for
        user: The user requesting access (None = anonymous)

    Returns:
        Tuple of (allowed: bool, reason: str)
        If allowed, reason is empty string.
        If denied, reason explains why.
    """
    # Check if page is deleted
    if page.deleted_at is not None:
        return False, "Page is deleted"

    access_level = page.access_level

    # PUBLIC: Allow everyone
    if access_level == AccessLevel.PUBLIC:
        return True, ""

    # Check if user is authenticated
    is_authenticated = user is not None and getattr(user, "is_authenticated", False)

    # AUTHENTICATED: Must be logged in
    if access_level == AccessLevel.AUTHENTICATED:
        if is_authenticated:
            return True, ""
        return False, "Authentication required"

    # ROLE: Must have required role (or be superuser)
    if access_level == AccessLevel.ROLE:
        if not is_authenticated:
            return False, "Authentication required for role-based access"

        # Superusers bypass role checks
        if getattr(user, "is_superuser", False):
            return True, ""

        required_roles = page.required_roles or []

        # Check if user has any of the required roles
        # Built-in role: "staff" maps to is_staff
        user_roles = set()
        if getattr(user, "is_staff", False):
            user_roles.add("staff")

        # Check for match
        if user_roles.intersection(set(required_roles)):
            return True, ""

        return False, f"Required role not found: {required_roles}"

    # ENTITLEMENT: Must pass entitlement check
    if access_level == AccessLevel.ENTITLEMENT:
        if not is_authenticated:
            return False, "Authentication required for entitlement-based access"

        # Superusers bypass entitlement checks
        if getattr(user, "is_superuser", False):
            return True, ""

        # Load entitlement checker from settings
        from .models import CMSSettings

        settings = CMSSettings.get_instance()
        checker_path = settings.entitlement_checker_path

        if not checker_path:
            # Fail-secure: no checker configured = deny
            return False, "Entitlement check not configured"

        try:
            # Import the checker function
            import importlib

            module_path, func_name = checker_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            checker = getattr(module, func_name)

            # Call the checker
            required_entitlements = page.required_entitlements or []
            if checker(user, required_entitlements, page):
                return True, ""
            return False, f"Entitlement check failed: {required_entitlements}"

        except Exception as e:
            # Fail-secure: any error = deny
            return False, f"Entitlement check error: {str(e)}"

    # Unknown access level (shouldn't happen)
    return False, f"Unknown access level: {access_level}"


def get_published_page(slug: str, user: Any = None) -> dict | None:
    """Get a published page's snapshot by slug.

    Args:
        slug: The page slug
        user: Optional user for access control (not implemented yet)

    Returns:
        The page's published snapshot, or None if not found/not published
    """
    try:
        page = ContentPage.objects.get(
            slug=slug,
            status=PageStatus.PUBLISHED,
            deleted_at__isnull=True,
        )
        return page.published_snapshot
    except ContentPage.DoesNotExist:
        return None


def list_published_pages(user: Any = None) -> list[dict]:
    """List all published pages.

    Args:
        user: Optional user for access control (not implemented yet)

    Returns:
        List of published page snapshots
    """
    pages = ContentPage.objects.filter(
        status=PageStatus.PUBLISHED,
        deleted_at__isnull=True,
    ).order_by("sort_order", "title")

    return [page.published_snapshot for page in pages if page.published_snapshot]
