"""Media-related models for photo tagging and media linking."""
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone

from django_basemodels import BaseModel


# =============================================================================
# Photo Tagging
# =============================================================================


class PhotoTagQuerySet(models.QuerySet):
    """Custom queryset for PhotoTag model."""

    def for_document(self, document):
        """Return tags for a specific document."""
        return self.filter(document=document)

    def for_diver(self, diver):
        """Return tags for a specific diver."""
        return self.filter(diver=diver)


class PhotoTag(BaseModel):
    """Tag a diver in a photo.

    Links documents (photos) to divers, optionally with position
    coordinates for face-tagging functionality.

    Usage:
        PhotoTag.objects.create(
            document=photo_doc,
            diver=diver_profile,
            tagged_by=request.user,
        )

        # Get all divers tagged in a photo
        tags = PhotoTag.objects.for_document(photo)
        divers = [tag.diver for tag in tags]

        # Get all photos of a diver
        tags = PhotoTag.objects.for_diver(diver)
        photos = [tag.document for tag in tags]
    """

    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="photo_tags",
        help_text="The photo document",
    )
    diver = models.ForeignKey(
        "diveops.DiverProfile",
        on_delete=models.CASCADE,
        related_name="photo_tags",
        help_text="The diver tagged in this photo",
    )
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="photo_tags_created",
        help_text="User who created this tag",
    )

    # Optional position for face-tagging (percentages of image dimensions)
    position_x = models.FloatField(
        null=True,
        blank=True,
        help_text="X position as percentage (0-100) from left edge",
    )
    position_y = models.FloatField(
        null=True,
        blank=True,
        help_text="Y position as percentage (0-100) from top edge",
    )

    objects = PhotoTagQuerySet.as_manager()

    class Meta:
        verbose_name = "Photo Tag"
        verbose_name_plural = "Photo Tags"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document"]),
            models.Index(fields=["diver"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "diver"],
                name="phototag_unique_diver_per_photo",
            ),
        ]

    def __str__(self):
        return f"{self.diver} in {self.document.filename}"


class DiveSitePhotoTagQuerySet(models.QuerySet):
    """Custom queryset for DiveSitePhotoTag model."""

    def for_document(self, document):
        """Return tags for a specific document."""
        return self.filter(document=document)

    def for_dive_site(self, dive_site):
        """Return tags for a specific dive site."""
        return self.filter(dive_site=dive_site)


class DiveSitePhotoTag(BaseModel):
    """Tag a dive site in a photo.

    Links documents (photos) to dive sites, allowing photos to be
    associated with locations shown in them.

    Usage:
        DiveSitePhotoTag.objects.create(
            document=photo_doc,
            dive_site=dive_site,
            tagged_by=request.user,
        )

        # Get all dive sites tagged in a photo
        tags = DiveSitePhotoTag.objects.for_document(photo)
        sites = [tag.dive_site for tag in tags]

        # Get all photos of a dive site (via tags, not DiveSitePhoto)
        tags = DiveSitePhotoTag.objects.for_dive_site(site)
        photos = [tag.document for tag in tags]
    """

    document = models.ForeignKey(
        "django_documents.Document",
        on_delete=models.CASCADE,
        related_name="dive_site_tags",
        help_text="The photo document",
    )
    dive_site = models.ForeignKey(
        "diveops.DiveSite",
        on_delete=models.CASCADE,
        related_name="photo_tags",
        help_text="The dive site tagged in this photo",
    )
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dive_site_photo_tags_created",
        help_text="User who created this tag",
    )

    objects = DiveSitePhotoTagQuerySet.as_manager()

    class Meta:
        verbose_name = "Dive Site Photo Tag"
        verbose_name_plural = "Dive Site Photo Tags"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document"]),
            models.Index(fields=["dive_site"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "dive_site"],
                name="divesitephototag_unique_site_per_photo",
            ),
        ]

    def __str__(self):
        return f"{self.dive_site.name} in {self.document.filename}"


# =============================================================================
# Media Link (Generic Linking with Provenance)
# =============================================================================


class MediaLinkSource(models.TextChoices):
    """How a media link was created."""
    DIRECT = "direct", "Direct"
    DERIVED_FROM_EXCURSION = "derived_from_excursion", "From Excursion"


class MediaLinkQuerySet(models.QuerySet):
    """Custom queryset for MediaLink model."""

    def for_media_asset(self, media_asset):
        """Return links for a specific media asset."""
        return self.filter(media_asset=media_asset)

    def direct(self):
        """Return only direct links (not derived)."""
        return self.filter(link_source=MediaLinkSource.DIRECT)

    def derived(self):
        """Return only derived links."""
        return self.filter(link_source=MediaLinkSource.DERIVED_FROM_EXCURSION)

    def for_target(self, target):
        """Return links to a specific target object."""
        ct = ContentType.objects.get_for_model(target)
        return self.filter(content_type=ct, object_id=str(target.pk))


class MediaLink(BaseModel):
    """Link a MediaAsset to any entity via GenericFK.

    IMPORTANT: Both direct and derived links can coexist for the same target.
    This allows a user to directly link a photo to a diver, AND that same
    photo can also have derived links from excursion tagging.

    The UniqueConstraint includes link_source and source_excursion to allow:
    - One direct link per (media_asset, target)
    - One derived link per (media_asset, target, source_excursion)

    Usage:
        from django.contrib.contenttypes.models import ContentType

        # Direct link
        MediaLink.objects.create(
            media_asset=asset,
            content_type=ContentType.objects.get_for_model(DiverProfile),
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DIRECT,
            linked_by=user,
        )

        # Derived link from excursion
        MediaLink.objects.create(
            media_asset=asset,
            content_type=ContentType.objects.get_for_model(DiverProfile),
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion,
            linked_by=user,
        )
    """

    media_asset = models.ForeignKey(
        "django_documents.MediaAsset",
        on_delete=models.CASCADE,
        related_name="links",
        help_text="The media asset being linked",
    )

    # GenericFK to target entity
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Content type of the target entity",
    )
    object_id = models.CharField(
        max_length=255,
        help_text="ID of the target entity (CharField for UUID support)",
    )
    target = GenericForeignKey("content_type", "object_id")

    # Provenance tracking
    link_source = models.CharField(
        max_length=30,
        choices=MediaLinkSource.choices,
        default=MediaLinkSource.DIRECT,
        help_text="How this link was created (direct or derived from excursion)",
    )
    source_excursion = models.ForeignKey(
        "diveops.Excursion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_media_links",
        help_text="Set when link_source=derived_from_excursion",
    )

    # Who created this link
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_links_created",
        help_text="User who created this link",
    )

    objects = MediaLinkQuerySet.as_manager()

    class Meta:
        verbose_name = "Media Link"
        verbose_name_plural = "Media Links"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["media_asset"]),
            models.Index(fields=["link_source"]),
            models.Index(fields=["source_excursion"]),
        ]
        constraints = [
            # Direct links: unique per (media_asset, target) when source=direct
            # (Partial constraint because source_excursion is NULL for direct links)
            models.UniqueConstraint(
                fields=["media_asset", "content_type", "object_id"],
                condition=Q(link_source="direct"),
                name="medialink_unique_direct",
            ),
            # Derived links: unique per (media_asset, target, source_excursion)
            models.UniqueConstraint(
                fields=["media_asset", "content_type", "object_id", "source_excursion"],
                condition=Q(link_source="derived_from_excursion"),
                name="medialink_unique_derived",
            ),
            # Derived links must have source_excursion set
            models.CheckConstraint(
                condition=(
                    Q(link_source="direct") |
                    Q(link_source="derived_from_excursion", source_excursion__isnull=False)
                ),
                name="medialink_derived_requires_source_excursion",
            ),
        ]

    def __str__(self):
        return f"{self.media_asset} → {self.content_type.model}:{self.object_id}"
