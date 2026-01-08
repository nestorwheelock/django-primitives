"""Media processing services for images and videos."""
import logging
from io import BytesIO
from typing import BinaryIO

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction

from .models import (
    Document,
    MediaAsset,
    MediaRendition,
    Attachment,
    MediaKind,
    MediaProcessingStatus,
    RenditionRole,
    AttachmentPurpose,
)

logger = logging.getLogger(__name__)

# Rendition size configurations
RENDITION_SIZES = {
    RenditionRole.THUMB: 150,
    RenditionRole.SMALL: 320,
    RenditionRole.MEDIUM: 640,
    RenditionRole.LARGE: 1280,
}

DEFAULT_RENDITION_ROLES = [RenditionRole.THUMB, RenditionRole.SMALL, RenditionRole.MEDIUM]


def extract_dimensions(file_obj: BinaryIO) -> tuple[int | None, int | None]:
    """
    Extract width and height from an image file.

    Args:
        file_obj: File-like object containing image data

    Returns:
        Tuple of (width, height) or (None, None) if extraction fails
    """
    try:
        from PIL import Image

        file_obj.seek(0)
        img = Image.open(file_obj)
        width, height = img.size
        file_obj.seek(0)
        return width, height
    except Exception as e:
        logger.warning(f"Failed to extract dimensions: {e}")
        file_obj.seek(0)
        return None, None


def process_image_upload(document: Document) -> MediaAsset:
    """
    Process an uploaded image document and create MediaAsset.

    Creates a MediaAsset for the document with extracted dimensions.
    If MediaAsset already exists, returns the existing one.

    Args:
        document: Document containing the image file

    Returns:
        MediaAsset instance
    """
    # Return existing if already processed
    try:
        return document.media_asset
    except MediaAsset.DoesNotExist:
        pass

    # Try to extract dimensions
    width, height = None, None
    status = MediaProcessingStatus.PENDING

    try:
        document.file.seek(0)
        width, height = extract_dimensions(document.file)
        if width and height:
            status = MediaProcessingStatus.COMPLETED
        else:
            status = MediaProcessingStatus.FAILED
    except Exception as e:
        logger.error(f"Failed to process image {document.pk}: {e}")
        status = MediaProcessingStatus.FAILED

    asset = MediaAsset.objects.create(
        document=document,
        kind=MediaKind.IMAGE,
        width=width,
        height=height,
        status=status,
    )

    return asset


def generate_renditions(
    media_asset: MediaAsset,
    roles: list[str] | None = None,
) -> list[MediaRendition]:
    """
    Generate renditions (resized versions) for a MediaAsset.

    Args:
        media_asset: MediaAsset to generate renditions for
        roles: List of RenditionRole values. Defaults to thumb, small, medium.

    Returns:
        List of created MediaRendition instances
    """
    from PIL import Image

    if roles is None:
        roles = DEFAULT_RENDITION_ROLES

    renditions = []
    document = media_asset.document

    try:
        document.file.seek(0)
        original_img = Image.open(document.file)
        original_img = original_img.convert("RGB")  # Ensure RGB for JPEG output
    except Exception as e:
        logger.error(f"Failed to open image for renditions: {e}")
        return renditions

    original_width = media_asset.width or original_img.width
    original_height = media_asset.height or original_img.height

    for role in roles:
        # Skip if rendition already exists
        if media_asset.renditions.filter(role=role).exists():
            existing = media_asset.renditions.get(role=role)
            renditions.append(existing)
            continue

        # Get target size for this role
        target_size = RENDITION_SIZES.get(role)
        if target_size is None:
            continue

        # Skip if original is smaller than target
        if original_width <= target_size and original_height <= target_size:
            continue

        # Calculate new dimensions maintaining aspect ratio
        if original_width > original_height:
            new_width = target_size
            new_height = int(original_height * (target_size / original_width))
        else:
            new_height = target_size
            new_width = int(original_width * (target_size / original_height))

        # Resize image
        try:
            resized = original_img.copy()
            resized.thumbnail((new_width, new_height), Image.LANCZOS)

            # Save to buffer
            buffer = BytesIO()
            resized.save(buffer, format="JPEG", quality=85, optimize=True)
            file_size = buffer.tell()  # Get size before seeking back
            buffer.seek(0)

            # Create rendition
            filename = f"{document.filename.rsplit('.', 1)[0]}_{role}.jpg"
            content_file = ContentFile(buffer.read(), name=filename)

            rendition = MediaRendition.objects.create(
                media_asset=media_asset,
                role=role,
                file=content_file,
                width=resized.width,
                height=resized.height,
                file_size=file_size,
                format="jpeg",
            )
            renditions.append(rendition)

        except Exception as e:
            logger.error(f"Failed to generate {role} rendition: {e}")
            continue

    return renditions


def attach_media(
    document: Document,
    target,
    purpose: str,
    caption: str = "",
    sort_order: int = 0,
    alt_text: str = "",
    attached_by=None,
) -> Attachment:
    """
    Attach a document to a target entity.

    Args:
        document: Document to attach
        target: Target model instance (any Django model)
        purpose: AttachmentPurpose value
        caption: Optional caption
        sort_order: Sort order for ordering in galleries
        alt_text: Alt text for accessibility
        attached_by: User who created the attachment

    Returns:
        Attachment instance (created or existing)
    """
    content_type = ContentType.objects.get_for_model(target)
    object_id = str(target.pk)

    # Return existing if already attached with same purpose
    existing = Attachment.objects.filter(
        document=document,
        content_type=content_type,
        object_id=object_id,
        purpose=purpose,
    ).first()

    if existing:
        return existing

    return Attachment.objects.create(
        document=document,
        content_type=content_type,
        object_id=object_id,
        purpose=purpose,
        caption=caption,
        sort_order=sort_order,
        alt_text=alt_text,
        attached_by=attached_by,
    )


def get_attachments(target, purpose: str | None = None):
    """
    Get all attachments for a target entity.

    Args:
        target: Target model instance
        purpose: Optional AttachmentPurpose to filter by

    Returns:
        QuerySet of Attachment instances
    """
    content_type = ContentType.objects.get_for_model(target)
    object_id = str(target.pk)

    qs = Attachment.objects.filter(
        content_type=content_type,
        object_id=object_id,
    )

    if purpose is not None:
        qs = qs.filter(purpose=purpose)

    return qs.order_by("purpose", "sort_order", "created_at")


@transaction.atomic
def reorder_attachments(target, purpose: str, ordered_ids: list) -> None:
    """
    Reorder attachments by setting sort_order based on list position.

    Args:
        target: Target model instance
        purpose: AttachmentPurpose to reorder
        ordered_ids: List of Attachment PKs in desired order
    """
    content_type = ContentType.objects.get_for_model(target)
    object_id = str(target.pk)

    for index, attachment_id in enumerate(ordered_ids):
        Attachment.objects.filter(
            pk=attachment_id,
            content_type=content_type,
            object_id=object_id,
            purpose=purpose,
        ).update(sort_order=index)


@transaction.atomic
def set_primary_attachment(attachment: Attachment) -> None:
    """
    Set an attachment as primary, clearing other primaries.

    Only clears primaries for the same target and purpose.

    Args:
        attachment: Attachment to set as primary
    """
    # Clear other primaries for same target and purpose
    Attachment.objects.filter(
        content_type=attachment.content_type,
        object_id=attachment.object_id,
        purpose=attachment.purpose,
        is_primary=True,
    ).exclude(pk=attachment.pk).update(is_primary=False)

    # Set this one as primary
    attachment.is_primary = True
    attachment.save(update_fields=["is_primary", "updated_at"])
