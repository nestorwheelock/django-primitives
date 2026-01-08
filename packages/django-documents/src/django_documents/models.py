"""Document model for file attachments."""

import hashlib
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel

from .exceptions import ImmutableChecksumError


class DocumentCategory(models.TextChoices):
    """Categories for document/media classification."""
    DOCUMENT = "document", "Document"
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"
    AUDIO = "audio", "Audio"
    OTHER = "other", "Other"


class AccessAction(models.TextChoices):
    """Actions that can be logged for document access."""
    VIEW = "view", "Viewed metadata"
    DOWNLOAD = "download", "Downloaded file"
    PREVIEW = "preview", "Previewed file"
    UPLOAD = "upload", "Uploaded file"
    EDIT = "edit", "Edited metadata"
    MOVE = "move", "Moved to folder"
    DELETE = "delete", "Deleted"


class PermissionLevel(models.IntegerChoices):
    """Permission levels - higher includes all lower."""
    VIEW = 10, "View"           # Can see folder and document metadata
    DOWNLOAD = 20, "Download"   # Can download documents
    UPLOAD = 30, "Upload"       # Can add documents to folder
    EDIT = 40, "Edit"           # Can rename/move/delete documents
    MANAGE = 50, "Manage"       # Can manage folder and permissions


class DocumentFolder(BaseModel):
    """
    Hierarchical folder structure with materialized path.

    Uses materialized path pattern for efficient ancestor/descendant queries.
    Path format: /<id1>/<id2>/<id3>/ where each ID is a folder in the hierarchy.
    """

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True, default="")

    # Hierarchy
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    # Materialized path for efficient queries (e.g., "/uuid1/uuid2/uuid3/")
    path = models.CharField(max_length=1000, db_index=True)
    depth = models.PositiveIntegerField(default=0)

    # Ownership (optional - for multi-tenant)
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    owner_id = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        app_label = "django_documents"
        ordering = ["path", "name"]
        unique_together = [["parent", "slug"]]
        indexes = [
            models.Index(fields=["path"]),
            models.Index(fields=["parent", "name"]),
            models.Index(fields=["owner_content_type", "owner_id"]),
        ]
        constraints = [
            # Root folders have null parent and depth 0
            # Child folders have non-null parent and depth > 0
            models.CheckConstraint(
                condition=(
                    models.Q(parent__isnull=True, depth=0) |
                    models.Q(parent__isnull=False, depth__gt=0)
                ),
                name="folder_depth_consistency",
            ),
        ]

    def __str__(self):
        return self.name


class FolderPermission(BaseModel):
    """
    Per-folder ACL with user or group grants.

    Permission levels are hierarchical - higher levels include all lower.
    Permissions can inherit to child folders via the `inherited` flag.
    """

    folder = models.ForeignKey(
        DocumentFolder,
        on_delete=models.CASCADE,
        related_name="permissions",
    )

    # Grantee (user or group via GenericFK)
    grantee_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
    )
    grantee_id = models.CharField(max_length=255)

    # Permission level
    level = models.PositiveSmallIntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW,
    )

    # Inheritance control
    inherited = models.BooleanField(
        default=True,
        help_text="If True, applies to all subfolders",
    )

    class Meta:
        app_label = "django_documents"
        unique_together = [["folder", "grantee_content_type", "grantee_id"]]
        indexes = [
            models.Index(fields=["folder", "level"]),
            models.Index(fields=["grantee_content_type", "grantee_id"]),
        ]

    def __str__(self):
        return f"{self.get_level_display()} on {self.folder.name}"


class DocumentAccessLog(models.Model):
    """
    Immutable audit log for document access.

    Records all document access events for compliance and auditing.
    Preserves document filename as a snapshot in case document is deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    document = models.ForeignKey(
        "Document",
        on_delete=models.SET_NULL,
        null=True,
        related_name="access_logs",
    )

    # Track specific version accessed (for downloads)
    version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )

    # Snapshot of filename at time of access
    document_filename = models.CharField(max_length=255)

    action = models.CharField(max_length=20, choices=AccessAction.choices)

    # Actor (null for anonymous access)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    # Timestamp
    accessed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "django_documents"
        ordering = ["-accessed_at"]
        indexes = [
            models.Index(fields=["document", "accessed_at"]),
            models.Index(fields=["actor", "accessed_at"]),
            models.Index(fields=["action", "accessed_at"]),
        ]

    def save(self, *args, **kwargs):
        # Immutable after creation
        if self.pk and DocumentAccessLog.objects.filter(pk=self.pk).exists():
            raise ValueError("DocumentAccessLog records are immutable")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action} on {self.document_filename} at {self.accessed_at}"


class DocumentVersion(BaseModel):
    """
    Immutable file version record.

    Document metadata (folder/target/title/etc.) lives on Document.
    The actual file blob reference and integrity fields live here.
    """

    document = models.ForeignKey(
        "Document",
        on_delete=models.CASCADE,
        related_name="versions",
    )

    # Blob reference (filesystem backend initially)
    storage_backend = models.CharField(max_length=50, default="filesystem")
    blob_path = models.CharField(
        max_length=1000,
        db_index=True,
        help_text="Relative path under MEDIA_ROOT",
    )

    # Integrity + file metadata snapshot
    sha256 = models.CharField(max_length=64, db_index=True)
    size_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=255, blank=True)
    original_filename = models.CharField(max_length=255)

    # Optional per-version metadata (OCR text, extracted fields, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        app_label = "django_documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document", "created_at"]),
            models.Index(fields=["sha256"]),
            models.Index(fields=["blob_path"]),
        ]
        constraints = [
            # Dedupe safety within backend (same blob may be reused by multiple versions)
            models.UniqueConstraint(
                fields=["storage_backend", "sha256", "blob_path"],
                name="uniq_blob_identity",
            )
        ]

    def save(self, *args, **kwargs):
        # Immutable after creation
        if self.pk and DocumentVersion.objects.filter(pk=self.pk).exists():
            raise ValueError("DocumentVersion records are immutable")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Version {self.pk} of {self.original_filename}"


class DocumentQuerySet(models.QuerySet):
    """Custom queryset for Document model."""

    def for_target(self, target):
        """Return documents attached to the given target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk),
        )

    def expired(self):
        """Return documents that have passed their expiration date."""
        return self.filter(
            expires_at__isnull=False,
            expires_at__lt=timezone.now(),
        )

    def not_expired(self):
        """Return documents that are not expired (or have no expiration)."""
        return self.filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=timezone.now())
        )


class Document(BaseModel):
    """
    Document attachment model with checksum verification.

    Attaches documents to any model via GenericForeignKey.
    Stores file metadata and SHA-256 checksum for integrity verification.

    Usage:
        from django_documents.models import Document

        # Attach a document
        doc = Document.objects.create(
            target=my_invoice,
            file=uploaded_file,
            filename="invoice.pdf",
            content_type="application/pdf",
            document_type="invoice_pdf",
        )

        # Query documents for an object
        docs = Document.objects.for_target(my_invoice)

        # Verify integrity
        if doc.verify_checksum():
            print("Document is intact")
    """

    # GenericFK to target object - CharField for UUID support
    # Made nullable to support dual mode (folder-only documents)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Content type of the target object",
    )
    target_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="ID of the target object (CharField for UUID support)",
    )
    target = GenericForeignKey('target_content_type', 'target_id')

    # Folder placement (optional - for dual mode)
    folder = models.ForeignKey(
        DocumentFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        help_text="Folder containing this document (optional)",
    )

    # Media category
    category = models.CharField(
        max_length=20,
        choices=DocumentCategory.choices,
        default=DocumentCategory.DOCUMENT,
        help_text="Document/media category for filtering",
    )

    # File storage
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/',
        help_text="The uploaded file",
    )

    # File metadata
    filename = models.CharField(
        max_length=255,
        help_text="Original filename",
    )
    content_type = models.CharField(
        max_length=100,
        help_text="MIME content type (e.g., application/pdf)",
    )
    file_size = models.PositiveBigIntegerField(
        default=0,
        help_text="File size in bytes",
    )

    # Document classification
    document_type = models.CharField(
        max_length=50,
        help_text="Document classification (e.g., invoice_pdf, receipt_image)",
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text="Optional description of the document",
    )

    # Integrity verification
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="SHA-256 checksum for integrity verification",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (page count, author, etc.)",
    )

    # Retention policy
    retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of days to retain document (None = forever)",
    )
    retention_policy = models.CharField(
        max_length=50,
        default='standard',
        help_text="Retention policy classification (standard, regulatory, legal, etc.)",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Explicit expiration date (None = never expires)",
    )

    # Versioning support
    current_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Current version of this document (new uploads use DocumentVersion)",
    )

    # BaseModel provides: id (UUID), created_at, updated_at, deleted_at

    objects = DocumentQuerySet.as_manager()

    class Meta:
        app_label = 'django_documents'
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['document_type']),
            models.Index(fields=['checksum']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """Ensure target_id is string and enforce checksum immutability."""
        # Enforce checksum immutability - once set, cannot be changed
        if not self._state.adding:
            # Get original checksum from database
            original = Document.objects.filter(pk=self.pk).values_list('checksum', flat=True).first()
            if original and original != self.checksum:
                raise ImmutableChecksumError(self.pk)

        # String coercion for GenericFK ID
        if self.target_id is not None:
            self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.filename} ({self.document_type})"

    def compute_checksum(self) -> str:
        """
        Compute SHA-256 checksum of the file.

        Returns:
            Hexadecimal string of the SHA-256 hash.
        """
        sha256_hash = hashlib.sha256()
        self.file.seek(0)
        for chunk in iter(lambda: self.file.read(8192), b""):
            sha256_hash.update(chunk)
        self.file.seek(0)
        return sha256_hash.hexdigest()

    def verify_checksum(self) -> bool:
        """
        Verify the stored checksum matches the file content.

        Returns:
            True if checksum matches, False otherwise.
        """
        if not self.checksum:
            return False
        return self.compute_checksum() == self.checksum

    @property
    def is_expired(self) -> bool:
        """
        Check if the document has expired.

        Returns:
            True if expires_at is set and in the past, False otherwise.
        """
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def under_retention(self) -> bool:
        """
        Check if the document is still under retention.

        Returns:
            True if document must be retained, False if it can be deleted.
        """
        if self.retention_days is None:
            return True  # Keep forever
        retention_end = self.created_at + timedelta(days=self.retention_days)
        return timezone.now() < retention_end

    @property
    def retention_ends_at(self):
        """
        Calculate when the retention period ends.

        Returns:
            DateTime when retention ends, or None if retention_days is None.
        """
        if self.retention_days is None:
            return None
        return self.created_at + timedelta(days=self.retention_days)


class MediaKind(models.TextChoices):
    """Types of media assets."""
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"


class MediaProcessingStatus(models.TextChoices):
    """Status of media processing pipeline."""
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class RenditionRole(models.TextChoices):
    """Standard rendition sizes/roles."""
    THUMB = "thumb", "Thumbnail (150px)"
    SMALL = "small", "Small (320px)"
    MEDIUM = "medium", "Medium (640px)"
    LARGE = "large", "Large (1280px)"
    POSTER = "poster", "Video Poster"


class AttachmentPurpose(models.TextChoices):
    """Purpose of attachment to an entity."""
    GALLERY = "gallery", "Gallery"
    AVATAR = "avatar", "Avatar"
    COVER = "cover", "Cover Image"
    HERO = "hero", "Hero Image"
    CERTIFICATE = "certificate", "Certificate"
    EVIDENCE = "evidence", "Evidence"
    MARKETING = "marketing", "Marketing"


class ExtractionStatus(models.TextChoices):
    """Status of text extraction processing."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"  # Not extractable (binary files, etc.)


class DocumentContent(BaseModel):
    """
    Extracted text content from documents for search and AI processing.

    Stores the full extracted text from PDFs, images (via OCR), and text files.
    This enables full-text search across document contents and provides the
    foundation for AI-powered features like summarization and entity extraction.

    Inherits from BaseModel: id (UUID), created_at, updated_at, deleted_at.
    """

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="content",
        help_text="The document this content was extracted from",
    )

    # Extraction status
    status = models.CharField(
        max_length=20,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.PENDING,
        help_text="Status of text extraction",
    )

    # Extracted content
    extracted_text = models.TextField(
        blank=True,
        default="",
        help_text="Full text extracted from the document",
    )

    # Extraction metadata
    extraction_method = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Method used for extraction (pdf_text, ocr, direct_read, etc.)",
    )
    page_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of pages processed (for PDFs)",
    )
    word_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Approximate word count of extracted text",
    )
    language = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Detected language code (e.g., 'en', 'es')",
    )

    # Processing timestamps
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When extraction was completed",
    )
    processing_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time taken to extract content in milliseconds",
    )

    # Error tracking
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if extraction failed",
    )

    # Future AI processing fields (placeholders for Phase 2)
    summary = models.TextField(
        blank=True,
        default="",
        help_text="AI-generated summary of the document",
    )
    entities = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extracted entities (names, dates, amounts, etc.)",
    )
    ai_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="AI model used for processing (e.g., 'claude-3-haiku')",
    )
    ai_processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When AI processing was completed",
    )

    class Meta:
        app_label = "django_documents"
        verbose_name = "Document Content"
        verbose_name_plural = "Document Contents"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["extraction_method"]),
        ]

    def __str__(self):
        return f"Content for {self.document.filename} ({self.status})"

    @property
    def has_text(self) -> bool:
        """Check if document has extracted text."""
        return bool(self.extracted_text.strip())

    @property
    def is_searchable(self) -> bool:
        """Check if document content is searchable."""
        return self.status == ExtractionStatus.COMPLETED and self.has_text


class MediaAsset(BaseModel):
    """
    Media-specific metadata overlay for Documents containing images or videos.

    This is a 1:1 extension of Document that adds media-specific fields like
    dimensions, EXIF data, and processing status. The actual file is stored
    in the related Document.

    Usage:
        from django_documents.models import Document, MediaAsset, MediaKind

        # Create document first
        doc = Document.objects.create(
            file=uploaded_image,
            filename="photo.jpg",
            content_type="image/jpeg",
            document_type="photo",
            category="image",
        )

        # Add media asset metadata
        asset = MediaAsset.objects.create(
            document=doc,
            kind=MediaKind.IMAGE,
            width=1920,
            height=1080,
        )
    """

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="media_asset",
        help_text="The document containing the media file",
    )

    kind = models.CharField(
        max_length=10,
        choices=MediaKind.choices,
        help_text="Type of media (image or video)",
    )

    status = models.CharField(
        max_length=20,
        choices=MediaProcessingStatus.choices,
        default=MediaProcessingStatus.PENDING,
        help_text="Processing status",
    )

    # Dimensions
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Width in pixels",
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Height in pixels",
    )

    # Video-specific
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Duration in seconds (video only)",
    )

    # EXIF/metadata
    taken_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the photo/video was taken (from EXIF)",
    )
    camera_make = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Camera manufacturer (from EXIF)",
    )
    camera_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Camera model (from EXIF)",
    )

    # GPS coordinates
    gps_latitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS latitude (from EXIF)",
    )
    gps_longitude = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS longitude (from EXIF)",
    )

    # Accessibility
    alt_text = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Alt text for accessibility",
    )

    # User-settable metadata (vs EXIF-extracted)
    captured_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="User-settable capture date (vs EXIF taken_at)",
    )

    # Visibility control
    visibility = models.CharField(
        max_length=20,
        choices=[
            ("private", "Private"),       # Staff only
            ("internal", "Internal"),     # Divers can see their own
            ("public", "Public"),         # Website/marketing use
        ],
        default="private",
        db_index=True,
        help_text="Visibility level for this media",
    )

    class Meta:
        app_label = "django_documents"
        verbose_name = "Media Asset"
        verbose_name_plural = "Media Assets"
        indexes = [
            models.Index(fields=["kind"]),
            models.Index(fields=["status"]),
            models.Index(fields=["taken_at"]),
        ]

    def __str__(self):
        return f"MediaAsset for {self.document.filename}"

    @property
    def aspect_ratio(self) -> float | None:
        """Calculate aspect ratio (width/height)."""
        if self.width and self.height:
            return self.width / self.height
        return None

    @property
    def is_landscape(self) -> bool | None:
        """Check if media is landscape orientation."""
        if self.width and self.height:
            return self.width > self.height
        return None

    @property
    def is_portrait(self) -> bool | None:
        """Check if media is portrait orientation."""
        if self.width and self.height:
            return self.height > self.width
        return None


class MediaRendition(BaseModel):
    """
    Generated rendition (thumbnail, resized version) of a MediaAsset.

    Each MediaAsset can have multiple renditions at different sizes/roles.
    Renditions are generated server-side using Pillow for images and
    ffmpeg for video posters.

    Usage:
        from django_documents.models import MediaRendition, RenditionRole

        # Generate thumbnail
        rendition = MediaRendition.objects.create(
            media_asset=asset,
            role=RenditionRole.THUMB,
            file=thumb_file,
            width=150,
            height=84,
            file_size=12345,
        )
    """

    media_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name="renditions",
        help_text="The media asset this rendition belongs to",
    )

    role = models.CharField(
        max_length=20,
        choices=RenditionRole.choices,
        help_text="Role/size of this rendition",
    )

    file = models.FileField(
        upload_to="documents/renditions/%Y/%m/%d/",
        help_text="The generated rendition file",
    )

    # Rendition dimensions
    width = models.PositiveIntegerField(
        help_text="Width in pixels",
    )
    height = models.PositiveIntegerField(
        help_text="Height in pixels",
    )
    file_size = models.PositiveBigIntegerField(
        help_text="File size in bytes",
    )

    format = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Output format (jpeg, webp, png)",
    )

    class Meta:
        app_label = "django_documents"
        verbose_name = "Media Rendition"
        verbose_name_plural = "Media Renditions"
        unique_together = [["media_asset", "role"]]
        indexes = [
            models.Index(fields=["media_asset", "role"]),
        ]

    def __str__(self):
        return f"{self.get_role_display()} for {self.media_asset.document.filename}"


class Attachment(BaseModel):
    """
    Generic association between a Document and any entity.

    Attachments allow a single Document to be attached to multiple entities
    with different purposes (gallery, avatar, cover, etc.) and ordering.

    Usage:
        from django.contrib.contenttypes.models import ContentType
        from django_documents.models import Attachment, AttachmentPurpose

        # Attach document to a dive site as gallery image
        ct = ContentType.objects.get_for_model(DiveSite)
        attachment = Attachment.objects.create(
            document=doc,
            content_type=ct,
            object_id=str(dive_site.pk),
            purpose=AttachmentPurpose.GALLERY,
            sort_order=1,
        )
    """

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="attachments",
        help_text="The document being attached",
    )

    # GenericFK to target entity
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Content type of the target entity",
    )
    object_id = models.CharField(
        max_length=255,
        help_text="ID of the target entity",
    )
    content_object = GenericForeignKey("content_type", "object_id")

    purpose = models.CharField(
        max_length=20,
        choices=AttachmentPurpose.choices,
        help_text="Purpose of this attachment",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Sort order for galleries",
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Is this the primary attachment for this purpose",
    )

    caption = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Caption for the attachment",
    )

    alt_text = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Alt text for accessibility",
    )

    attached_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who created this attachment",
    )

    class Meta:
        app_label = "django_documents"
        verbose_name = "Attachment"
        verbose_name_plural = "Attachments"
        ordering = ["purpose", "sort_order", "created_at"]
        unique_together = [["document", "content_type", "object_id", "purpose"]]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["purpose", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.document.filename} attached as {self.get_purpose_display()}"
