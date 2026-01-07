"""Thumbnail generation service for document images.

Thumbnails are stored as proper Document objects in a folder hierarchy:
    Photos/resized/small/
    Photos/resized/medium/
    Photos/resized/large/

Each thumbnail document is linked to its original via metadata.
"""

import io
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction

from django_documents.models import Document, DocumentFolder

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Thumbnail sizes for responsive design (max width, height scales proportionally)
THUMBNAIL_SIZES = {
    "thumb": (80, 2000),     # List view icons, compact UI
    "small": (150, 2000),    # Mobile grid (2 columns ~150px each)
    "medium": (300, 2000),   # Tablet grid, desktop cards
    "large": (600, 2000),    # Preview modal, detail page
    "xlarge": (1200, 2000),  # Retina displays, full preview
}

# Default thumbnail size
DEFAULT_SIZE = "medium"

# Size recommendations by context
SIZE_RECOMMENDATIONS = {
    "list_icon": "thumb",      # Small icons in list/table views
    "mobile_grid": "small",    # 2-column mobile grid
    "tablet_grid": "medium",   # 3-4 column tablet grid
    "desktop_grid": "medium",  # 5-6 column desktop grid
    "preview": "large",        # Modal/lightbox preview
    "detail": "large",         # Document detail page
    "retina": "xlarge",        # High-DPI displays
}

# Supported image formats
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# Root folder for resized images
RESIZED_ROOT = "Photos"
RESIZED_SUBFOLDER = "resized"


def get_or_create_thumbnail_folder(size=DEFAULT_SIZE):
    """Get or create the folder for thumbnails of a given size.

    Creates hierarchy: Photos/resized/{size}/
    """
    # Get or create Photos folder (root level, depth=0)
    try:
        photos_folder = DocumentFolder.objects.get(name=RESIZED_ROOT, parent=None)
    except DocumentFolder.DoesNotExist:
        photos_folder = DocumentFolder(
            name=RESIZED_ROOT,
            parent=None,
            slug="photos",
            description="Photo library",
            depth=0,
            path="/",
        )
        photos_folder.save()
        # Update path to include the ID
        photos_folder.path = f"/{photos_folder.pk}/"
        photos_folder.save(update_fields=["path"])

    # Get or create resized subfolder (depth=1)
    try:
        resized_folder = DocumentFolder.objects.get(name=RESIZED_SUBFOLDER, parent=photos_folder)
    except DocumentFolder.DoesNotExist:
        resized_folder = DocumentFolder(
            name=RESIZED_SUBFOLDER,
            parent=photos_folder,
            slug="resized",
            description="Resized images",
            depth=1,
            path=photos_folder.path,
        )
        resized_folder.save()
        # Update path to include the ID
        resized_folder.path = f"{photos_folder.path}{resized_folder.pk}/"
        resized_folder.save(update_fields=["path"])

    # Get or create size-specific folder (depth=2)
    try:
        size_folder = DocumentFolder.objects.get(name=size, parent=resized_folder)
    except DocumentFolder.DoesNotExist:
        size_folder = DocumentFolder(
            name=size,
            parent=resized_folder,
            slug=size,
            description=f"{size.title()} thumbnails ({THUMBNAIL_SIZES[size][0]}x{THUMBNAIL_SIZES[size][1]})",
            depth=2,
            path=resized_folder.path,
        )
        size_folder.save()
        # Update path to include the ID
        size_folder.path = f"{resized_folder.path}{size_folder.pk}/"
        size_folder.save(update_fields=["path"])

    return size_folder


def get_thumbnail_document(document, size=DEFAULT_SIZE):
    """Get the thumbnail document for an original document, if it exists."""
    if size not in THUMBNAIL_SIZES:
        size = DEFAULT_SIZE

    # Look for thumbnail by checking metadata
    thumb_filename = f"thumb_{size}_{document.pk}.jpg"

    try:
        folder = get_or_create_thumbnail_folder(size)
        return Document.objects.get(
            folder=folder,
            filename=thumb_filename
        )
    except Document.DoesNotExist:
        return None


def get_thumbnail_url(document, size=DEFAULT_SIZE):
    """Get the URL for a document's thumbnail, generating if needed."""
    if not HAS_PIL:
        return None

    if not document.file:
        return None

    # Check if it's an image
    ext = Path(document.filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        return None

    # Check for existing thumbnail
    thumb_doc = get_thumbnail_document(document, size)

    if thumb_doc and thumb_doc.file:
        # Check if original is newer (regenerate if so)
        if document.updated_at and thumb_doc.created_at:
            if document.updated_at > thumb_doc.created_at:
                thumb_doc = generate_thumbnail(document, size)
        if thumb_doc and thumb_doc.file:
            return thumb_doc.file.url
    else:
        # Generate new thumbnail
        thumb_doc = generate_thumbnail(document, size)
        if thumb_doc and thumb_doc.file:
            return thumb_doc.file.url

    return None


@transaction.atomic
def generate_thumbnail(document, size=DEFAULT_SIZE):
    """Generate a thumbnail document for an image document.

    Returns the thumbnail Document object, or None on failure.
    """
    if not HAS_PIL:
        return None

    if not document.file:
        return None

    if size not in THUMBNAIL_SIZES:
        size = DEFAULT_SIZE

    try:
        orig_path = Path(document.file.path)
        if not orig_path.exists():
            return None

        dimensions = THUMBNAIL_SIZES[size]

        # Generate thumbnail image
        with Image.open(orig_path) as img:
            # Handle different image modes
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Create thumbnail maintaining aspect ratio
            img.thumbnail(dimensions, Image.Resampling.LANCZOS)

            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            buffer.seek(0)

        # Get or create thumbnail folder
        folder = get_or_create_thumbnail_folder(size)

        # Create unique filename
        thumb_filename = f"thumb_{size}_{document.pk}.jpg"

        # Delete existing thumbnail if any
        Document.objects.filter(folder=folder, filename=thumb_filename).delete()

        # Create new thumbnail document
        thumb_doc = Document.objects.create(
            filename=thumb_filename,
            document_type="image/jpeg",
            category="image",
            folder=folder,
            file_size=buffer.getbuffer().nbytes,
            metadata={
                "original_document_id": str(document.pk),
                "original_filename": document.filename,
                "thumbnail_size": size,
                "dimensions": list(dimensions),
                "is_thumbnail": True,
            }
        )

        # Save the file
        thumb_doc.file.save(thumb_filename, ContentFile(buffer.getvalue()), save=True)

        return thumb_doc

    except Exception as e:
        print(f"Thumbnail generation error for {document.pk}: {e}")
        return None


def generate_all_thumbnails(document):
    """Generate thumbnails in all sizes for a document."""
    results = {}
    for size in THUMBNAIL_SIZES:
        thumb_doc = generate_thumbnail(document, size)
        results[size] = thumb_doc is not None
    return results


def delete_thumbnails(document):
    """Delete all thumbnail documents for an original document."""
    for size in THUMBNAIL_SIZES:
        try:
            folder = get_or_create_thumbnail_folder(size)
            thumb_filename = f"thumb_{size}_{document.pk}.jpg"
            Document.objects.filter(folder=folder, filename=thumb_filename).delete()
        except Exception:
            pass


def get_original_document(thumbnail_doc):
    """Get the original document for a thumbnail document."""
    if not thumbnail_doc.metadata:
        return None

    original_id = thumbnail_doc.metadata.get("original_document_id")
    if not original_id:
        return None

    try:
        return Document.objects.get(pk=original_id)
    except Document.DoesNotExist:
        return None
