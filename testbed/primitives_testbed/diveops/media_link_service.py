"""Media linking service with excursion cascading.

This module provides service functions for linking MediaAssets to entities
using the MediaLink model with provenance tracking.

Key features:
- link_media_to_excursion: Creates direct link + cascades to divers/site
- unlink_media_from_excursion: Removes links with optional cascade
- link_media_direct: Creates direct link to any entity
- Query helpers for virtual folders (by excursion, diver, site, date, unused)
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from django_documents.models import MediaAsset

from .models import MediaLink, MediaLinkSource, Excursion, DiverProfile, DiveSite


@transaction.atomic
def link_media_to_excursion(
    media_asset: MediaAsset,
    excursion: Excursion,
    linked_by=None,
    cascade: bool = True,
) -> MediaLink:
    """Link media to excursion and optionally cascade to divers/sites.

    Args:
        media_asset: The MediaAsset to link
        excursion: The Excursion to link to
        linked_by: Optional user who created the link
        cascade: If True, also create derived links to divers and dive site

    Returns:
        The MediaLink for the excursion (direct link)
    """
    # Pre-fetch ContentTypes once
    excursion_ct = ContentType.objects.get_for_model(Excursion)
    diver_ct = ContentType.objects.get_for_model(DiverProfile)
    site_ct = ContentType.objects.get_for_model(DiveSite)

    # Create direct link to excursion
    exc_link, created = MediaLink.objects.get_or_create(
        media_asset=media_asset,
        content_type=excursion_ct,
        object_id=str(excursion.pk),
        link_source=MediaLinkSource.DIRECT,
        defaults={"linked_by": linked_by, "source_excursion": None},
    )

    if cascade:
        # Cascade to dive site(s)
        if excursion.dive_site_id:
            MediaLink.objects.get_or_create(
                media_asset=media_asset,
                content_type=site_ct,
                object_id=str(excursion.dive_site_id),
                link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
                source_excursion=excursion,
                defaults={"linked_by": linked_by},
            )

        # Cascade to divers (prefer roster, fallback to bookings)
        diver_ids = list(excursion.roster.values_list('diver_id', flat=True))
        if not diver_ids:
            # Fallback to confirmed/checked-in bookings
            diver_ids = list(
                excursion.bookings.filter(
                    status__in=['confirmed', 'checked_in']
                ).values_list('diver_id', flat=True)
            )

        for diver_id in diver_ids:
            MediaLink.objects.get_or_create(
                media_asset=media_asset,
                content_type=diver_ct,
                object_id=str(diver_id),
                link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
                source_excursion=excursion,
                defaults={"linked_by": linked_by},
            )

    # Set captured_at if not set
    if not media_asset.captured_at and excursion.departure_time:
        media_asset.captured_at = excursion.departure_time
        media_asset.save(update_fields=["captured_at", "updated_at"])

    return exc_link


@transaction.atomic
def unlink_media_from_excursion(
    media_asset: MediaAsset,
    excursion: Excursion,
    cascade_derived: bool = True,
) -> int:
    """Remove excursion link and optionally cascade derived links.

    Args:
        media_asset: The MediaAsset to unlink
        excursion: The Excursion to unlink from
        cascade_derived: If True, also delete derived links from this excursion

    Returns:
        Number of links deleted
    """
    excursion_ct = ContentType.objects.get_for_model(Excursion)
    deleted_count = 0

    # Delete direct excursion link
    deleted, _ = MediaLink.objects.filter(
        media_asset=media_asset,
        content_type=excursion_ct,
        object_id=str(excursion.pk),
        link_source=MediaLinkSource.DIRECT,
    ).delete()
    deleted_count += deleted

    # Cascade delete derived links
    if cascade_derived:
        deleted, _ = MediaLink.objects.filter(
            media_asset=media_asset,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion,
        ).delete()
        deleted_count += deleted

    return deleted_count


def link_media_direct(media_asset: MediaAsset, target, linked_by=None) -> MediaLink:
    """Create a direct link to any entity.

    Args:
        media_asset: The MediaAsset to link
        target: The target entity (DiverProfile, DiveSite, etc.)
        linked_by: Optional user who created the link

    Returns:
        The created or existing MediaLink
    """
    ct = ContentType.objects.get_for_model(target)
    link, _ = MediaLink.objects.get_or_create(
        media_asset=media_asset,
        content_type=ct,
        object_id=str(target.pk),
        link_source=MediaLinkSource.DIRECT,
        defaults={"linked_by": linked_by, "source_excursion": None},
    )
    return link


def unlink_media_direct(media_asset: MediaAsset, target) -> int:
    """Remove a direct link to an entity.

    Args:
        media_asset: The MediaAsset to unlink
        target: The target entity

    Returns:
        Number of links deleted (0 or 1)
    """
    ct = ContentType.objects.get_for_model(target)
    deleted, _ = MediaLink.objects.filter(
        media_asset=media_asset,
        content_type=ct,
        object_id=str(target.pk),
        link_source=MediaLinkSource.DIRECT,
    ).delete()
    return deleted


# =============================================================================
# Query helpers for virtual folders
# =============================================================================


def get_media_by_excursion(excursion: Excursion) -> QuerySet:
    """Get media linked to excursion (direct links only).

    Args:
        excursion: The Excursion to get media for

    Returns:
        QuerySet of MediaAsset objects
    """
    ct = ContentType.objects.get_for_model(Excursion)
    return MediaAsset.objects.filter(
        links__content_type=ct,
        links__object_id=str(excursion.pk),
        links__link_source=MediaLinkSource.DIRECT,
        document__deleted_at__isnull=True,
    ).distinct()


def get_media_by_diver(diver: DiverProfile) -> QuerySet:
    """Get media linked to diver (direct or derived).

    Args:
        diver: The DiverProfile to get media for

    Returns:
        QuerySet of MediaAsset objects
    """
    ct = ContentType.objects.get_for_model(diver)
    return MediaAsset.objects.filter(
        links__content_type=ct,
        links__object_id=str(diver.pk),
        document__deleted_at__isnull=True,
    ).distinct()


def get_media_by_dive_site(dive_site: DiveSite) -> QuerySet:
    """Get media linked to dive site (direct or derived).

    Args:
        dive_site: The DiveSite to get media for

    Returns:
        QuerySet of MediaAsset objects
    """
    ct = ContentType.objects.get_for_model(dive_site)
    return MediaAsset.objects.filter(
        links__content_type=ct,
        links__object_id=str(dive_site.pk),
        document__deleted_at__isnull=True,
    ).distinct()


def get_media_by_date(date) -> QuerySet:
    """Get media for a captured_at date.

    Args:
        date: The date to filter by (datetime.date)

    Returns:
        QuerySet of MediaAsset objects
    """
    return MediaAsset.objects.filter(
        captured_at__date=date,
        document__deleted_at__isnull=True,
    )


def get_unused_media() -> QuerySet:
    """Get media with no links.

    Returns:
        QuerySet of MediaAsset objects that have no links
    """
    return MediaAsset.objects.filter(
        links__isnull=True,
        document__deleted_at__isnull=True,
    )
