"""Document model for file attachments."""

import hashlib
from datetime import timedelta
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from django_basemodels import BaseModel


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
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Content type of the target object",
    )
    target_id = models.CharField(
        max_length=255,
        help_text="ID of the target object (CharField for UUID support)",
    )
    target = GenericForeignKey('target_content_type', 'target_id')

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
        """Ensure target_id is always stored as string."""
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
