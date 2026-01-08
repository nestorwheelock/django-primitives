"""Document services for attachment and verification."""

import hashlib
import os
from typing import Union, Optional, Any, Literal, TYPE_CHECKING
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from django_documents.models import (
    Document,
    DocumentFolder,
    FolderPermission,
    PermissionLevel,
    DocumentAccessLog,
    AccessAction,
)
from django_documents.exceptions import ChecksumMismatchError, DocumentNotFoundError, FolderNotEmpty

if TYPE_CHECKING:
    from django_documents.models import DocumentVersion


def compute_sha256(file_obj) -> str:
    """
    Compute SHA-256 checksum of a file.

    Streams the file in chunks to handle large files without OOM.
    Resets file position to start after reading.

    Args:
        file_obj: File-like object to hash.

    Returns:
        Hexadecimal string of the SHA-256 hash (64 characters).
    """
    sha256_hash = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(8192), b""):
        sha256_hash.update(chunk)
    file_obj.seek(0)
    return sha256_hash.hexdigest()


def content_addressed_path(sha256: str, original_filename: str) -> str:
    """
    Return relative blob_path for filesystem backend.

    Layout: documents/sha256/<aa>/<bb>/<fullhash>/<original_filename>

    Args:
        sha256: SHA-256 hex digest (64 characters).
        original_filename: Original filename to preserve.

    Returns:
        Relative path (no leading /) for storage under MEDIA_ROOT.
    """
    return f"documents/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}/{original_filename}"


def verify_blob(version: "DocumentVersion") -> Literal["ok", "missing", "corrupt"]:
    """
    Check filesystem blob integrity.

    Args:
        version: DocumentVersion instance to verify.

    Returns:
        - "ok": file exists and sha256 matches
        - "missing": file not found
        - "corrupt": file exists but hash mismatch
    """
    full_path = os.path.join(settings.MEDIA_ROOT, version.blob_path)

    if not os.path.exists(full_path):
        return "missing"

    # Compute actual hash
    sha256_hash = hashlib.sha256()
    with open(full_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    actual_hash = sha256_hash.hexdigest()

    if actual_hash != version.sha256:
        return "corrupt"

    return "ok"


def compute_file_checksum(file) -> str:
    """
    Compute SHA-256 checksum of a file.

    Args:
        file: File-like object to hash.

    Returns:
        Hexadecimal string of the SHA-256 hash.
    """
    sha256_hash = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(8192), b""):
        sha256_hash.update(chunk)
    file.seek(0)
    return sha256_hash.hexdigest()


@transaction.atomic
def attach_document(
    target,
    file,
    document_type: str,
    uploaded_by=None,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    description: str = '',
    retention_days: Optional[int] = None,
    retention_policy: str = 'standard',
    metadata: Optional[dict] = None,
    folder: Optional[DocumentFolder] = None,
) -> Document:
    """
    Attach a document to a target object.

    Creates a Document record with computed checksum and file metadata.

    Args:
        target: The object to attach the document to (via GenericFK).
        file: Uploaded file object.
        document_type: Classification of the document (e.g., 'invoice_pdf').
        uploaded_by: User who uploaded the document (optional).
        filename: Override filename (defaults to file.name).
        content_type: Override MIME type (defaults to file.content_type).
        description: Optional description of the document.
        retention_days: Number of days to retain (None = forever).
        retention_policy: Retention policy classification.
        metadata: Additional metadata dictionary.
        folder: Optional folder to place the document in.

    Returns:
        The created Document instance.

    Usage:
        doc = attach_document(
            target=my_invoice,
            file=uploaded_file,
            document_type='invoice_pdf',
            uploaded_by=request.user,
        )
    """
    # Get file metadata
    actual_filename = filename or getattr(file, 'name', 'unknown')
    actual_content_type = content_type or getattr(file, 'content_type', 'application/octet-stream')

    # Read file content to compute checksum and size
    file.seek(0)
    file_content = file.read()
    file_size = len(file_content)
    checksum = hashlib.sha256(file_content).hexdigest()
    file.seek(0)

    # Build metadata
    doc_metadata = metadata.copy() if metadata else {}
    if uploaded_by:
        doc_metadata['uploaded_by_id'] = uploaded_by.pk

    # Create document
    doc = Document.objects.create(
        target=target,
        file=file,
        filename=actual_filename,
        content_type=actual_content_type,
        file_size=file_size,
        checksum=checksum,
        document_type=document_type,
        description=description,
        retention_days=retention_days,
        retention_policy=retention_policy,
        metadata=doc_metadata,
        folder=folder,
    )

    return doc


def verify_document_integrity(document: Union[Document, int]) -> bool:
    """
    Verify the integrity of a document by checking its checksum.

    Args:
        document: Document instance or document ID.

    Returns:
        True if the checksum matches.

    Raises:
        DocumentNotFoundError: If document ID doesn't exist.
        ChecksumMismatchError: If checksum doesn't match file content.
    """
    # Get document if ID was passed (supports int, str, or UUID)
    if not isinstance(document, Document):
        try:
            document = Document.objects.get(pk=document)
        except Document.DoesNotExist:
            raise DocumentNotFoundError(f"Document with ID {document} not found")

    # Verify checksum
    if not document.verify_checksum():
        raise ChecksumMismatchError(
            f"Checksum mismatch for document {document.pk}: "
            f"stored={document.checksum}, computed={document.compute_checksum()}"
        )

    return True


# =============================================================================
# Folder Operations
# =============================================================================


@transaction.atomic
def create_folder(
    *,
    name: str,
    parent: Optional[DocumentFolder] = None,
    slug: Optional[str] = None,
    description: str = "",
    owner=None,
    actor=None,
) -> DocumentFolder:
    """
    Create a folder with materialized path.

    Args:
        name: Folder name.
        parent: Parent folder (None for root).
        slug: URL-safe slug (auto-generated from name if not provided).
        description: Optional description.
        owner: Optional owner object (via GenericFK).
        actor: User performing the action (for audit).

    Returns:
        Created DocumentFolder instance.
    """
    from django.contrib.contenttypes.models import ContentType

    # Auto-generate slug if not provided
    folder_slug = slug or slugify(name)

    # Calculate depth and path
    if parent is None:
        depth = 0
        # Path will be set after save (needs PK)
        path = ""
    else:
        depth = parent.depth + 1
        path = parent.path  # Will append this folder's ID after save

    # Handle owner GenericFK
    owner_ct = None
    owner_id = ""
    if owner is not None:
        owner_ct = ContentType.objects.get_for_model(owner)
        owner_id = str(owner.pk)

    # Create folder
    folder = DocumentFolder.objects.create(
        name=name,
        slug=folder_slug,
        description=description,
        parent=parent,
        depth=depth,
        path=path,
        owner_content_type=owner_ct,
        owner_id=owner_id,
    )

    # Now set the path with the folder's ID
    if parent is None:
        folder.path = f"/{folder.pk}/"
    else:
        folder.path = f"{parent.path}{folder.pk}/"
    folder.save(update_fields=["path"])

    return folder


def get_or_create_folder_path(
    path: str,
    owner=None,
    actor=None,
) -> DocumentFolder:
    """
    Get or create a folder hierarchy from a path string.

    Creates all necessary parent folders if they don't exist.

    Args:
        path: Folder path like "Medical/Medical Questionnaires".
        owner: Optional owner object for new folders.
        actor: User performing the action (for audit).

    Returns:
        The leaf DocumentFolder instance.

    Usage:
        folder = get_or_create_folder_path("Medical/Medical Questionnaires")
    """
    from django.db import IntegrityError

    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise ValueError("Path cannot be empty")

    parent = None
    for part in parts:
        slug = slugify(part)
        # Try to find existing folder (including any with same parent/slug)
        folder = DocumentFolder.objects.filter(
            slug=slug,
            parent=parent,
        ).first()

        if folder is None:
            # Try to create the folder, handle race condition
            try:
                folder = create_folder(
                    name=part,
                    parent=parent,
                    slug=slug,
                    owner=owner,
                    actor=actor,
                )
            except IntegrityError:
                # Another process created it, fetch it
                folder = DocumentFolder.objects.get(
                    slug=slug,
                    parent=parent,
                )

        parent = folder

    return folder


@transaction.atomic
def move_folder(
    *,
    folder: DocumentFolder,
    new_parent: Optional[DocumentFolder],
    actor=None,
) -> DocumentFolder:
    """
    Move a folder to a new parent.

    Updates the folder's path and depth, and all descendant paths.

    Args:
        folder: Folder to move.
        new_parent: New parent folder (None to move to root).
        actor: User performing the action (for audit).

    Returns:
        Updated DocumentFolder instance.
    """
    old_path = folder.path

    # Calculate new depth and path
    if new_parent is None:
        new_depth = 0
        new_path = f"/{folder.pk}/"
    else:
        new_depth = new_parent.depth + 1
        new_path = f"{new_parent.path}{folder.pk}/"

    depth_delta = new_depth - folder.depth

    # Update this folder
    folder.parent = new_parent
    folder.depth = new_depth
    folder.path = new_path
    folder.save(update_fields=["parent", "depth", "path", "updated_at"])

    # Update all descendants
    # Find all folders whose path starts with old_path
    descendants = DocumentFolder.objects.filter(path__startswith=old_path).exclude(pk=folder.pk)

    for descendant in descendants:
        # Replace old path prefix with new path prefix
        descendant.path = descendant.path.replace(old_path, new_path, 1)
        descendant.depth = descendant.depth + depth_delta
        descendant.save(update_fields=["path", "depth", "updated_at"])

    return folder


@transaction.atomic
def delete_folder(
    *,
    folder: DocumentFolder,
    actor=None,
    recursive: bool = False,
) -> None:
    """
    Delete a folder.

    Args:
        folder: Folder to delete.
        actor: User performing the action (for audit).
        recursive: If True, delete all contents recursively.
                   If False, raise FolderNotEmpty if folder has children.

    Raises:
        FolderNotEmpty: If folder has children and recursive=False.
    """
    # Check for children
    child_count = folder.children.count()

    if child_count > 0 and not recursive:
        raise FolderNotEmpty(folder.pk, child_count)

    if recursive:
        # Delete all descendants (children will cascade to their children)
        # Using path prefix query for efficiency
        DocumentFolder.objects.filter(path__startswith=folder.path).delete()
    else:
        # Just delete this folder (already confirmed no children)
        folder.delete()


# =============================================================================
# Permission Operations
# =============================================================================


def _parse_path_to_ids(path: str) -> list:
    """
    Parse a materialized path into a list of folder IDs.

    Args:
        path: Materialized path like "/uuid1/uuid2/uuid3/"

    Returns:
        List of folder IDs.
    """
    # Path format: /id1/id2/id3/
    parts = path.strip("/").split("/")
    return [p for p in parts if p]


@transaction.atomic
def grant_folder_permission(
    *,
    folder: DocumentFolder,
    grantee,
    level: PermissionLevel,
    inherited: bool = True,
    actor=None,
) -> FolderPermission:
    """
    Grant permission to a user or group on a folder.

    Args:
        folder: Folder to grant permission on.
        grantee: User or Group to grant permission to.
        level: Permission level to grant.
        inherited: If True, permission applies to all subfolders.
        actor: User performing the action (for audit).

    Returns:
        Created FolderPermission instance.
    """
    from django.contrib.contenttypes.models import ContentType

    grantee_ct = ContentType.objects.get_for_model(grantee)

    perm = FolderPermission.objects.create(
        folder=folder,
        grantee_content_type=grantee_ct,
        grantee_id=str(grantee.pk),
        level=level,
        inherited=inherited,
    )

    return perm


def get_effective_permission(user, folder: DocumentFolder) -> Optional[PermissionLevel]:
    """
    Get user's effective permission for a folder.

    Checks folder and all ancestors, returns highest level.
    Only considers inherited permissions from ancestors.

    Args:
        user: User to check permission for.
        folder: Folder to check permission on.

    Returns:
        Highest PermissionLevel the user has, or None if no permission.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q

    # Get all ancestor folder IDs from materialized path
    ancestor_ids = _parse_path_to_ids(folder.path)

    user_ct = ContentType.objects.get_for_model(user)

    # Get all permissions for user on folder or ancestors
    permissions = FolderPermission.objects.filter(
        folder_id__in=ancestor_ids,
        grantee_content_type=user_ct,
        grantee_id=str(user.pk),
    ).filter(
        # Only inherited permissions from ancestors, or direct on this folder
        Q(folder=folder) | Q(inherited=True)
    )

    if not permissions.exists():
        return None

    # Return highest level
    max_level = max(p.level for p in permissions)
    return PermissionLevel(max_level)


def check_permission(
    user,
    folder: DocumentFolder,
    required_level: PermissionLevel,
) -> bool:
    """
    Check if user has required permission level on a folder.

    Permission levels are hierarchical - higher levels include all lower.

    Args:
        user: User to check permission for.
        folder: Folder to check permission on.
        required_level: Minimum permission level required.

    Returns:
        True if user has required level or higher, False otherwise.
    """
    effective = get_effective_permission(user, folder)

    if effective is None:
        return False

    # Higher levels include all lower
    return effective >= required_level


def get_accessible_folders(
    user,
    min_level: PermissionLevel = PermissionLevel.VIEW,
) -> "models.QuerySet[DocumentFolder]":
    """
    Get all folders user can access at minimum permission level.

    Args:
        user: User to check access for.
        min_level: Minimum permission level required.

    Returns:
        QuerySet of accessible DocumentFolder instances.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import models

    user_ct = ContentType.objects.get_for_model(user)

    # Get folders where user has direct permission at min_level or higher
    folder_ids = FolderPermission.objects.filter(
        grantee_content_type=user_ct,
        grantee_id=str(user.pk),
        level__gte=min_level,
    ).values_list("folder_id", flat=True)

    return DocumentFolder.objects.filter(pk__in=folder_ids)


# =============================================================================
# Access Logging Operations
# =============================================================================


def log_access(
    *,
    document: Document,
    action: AccessAction,
    actor=None,
    version: "DocumentVersion" = None,
    ip_address: Optional[str] = None,
    user_agent: str = "",
    request=None,
) -> DocumentAccessLog:
    """
    Log a document access event.

    Creates an immutable audit log entry for the access.

    Args:
        document: Document being accessed.
        action: Type of access (view, download, etc.).
        actor: User performing the action (None for anonymous).
        version: Specific DocumentVersion being accessed (for downloads).
        ip_address: IP address of the request.
        user_agent: User agent string.
        request: Django request object (alternative to ip_address/user_agent).

    Returns:
        Created DocumentAccessLog instance.
    """
    # Extract IP and user agent from request if provided
    if request is not None:
        if ip_address is None:
            ip_address = _get_client_ip(request)
        if not user_agent:
            user_agent = request.META.get("HTTP_USER_AGENT", "")

    log = DocumentAccessLog.objects.create(
        document=document,
        version=version,
        document_filename=document.filename,
        action=action,
        actor=actor,
        ip_address=ip_address,
        user_agent=user_agent or "",
    )

    return log


def _get_client_ip(request) -> Optional[str]:
    """
    Extract client IP address from request.

    Handles X-Forwarded-For header for proxied requests.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# =============================================================================
# Document Operations
# =============================================================================


@transaction.atomic
def move_document(
    *,
    document: Document,
    destination: Optional[DocumentFolder],
    actor=None,
) -> Document:
    """
    Move a document to a different folder.

    NOTE: This does NOT move the blob on disk - blobs are content-addressed
    and immutable. Only updates the Document.folder FK.

    Args:
        document: Document to move.
        destination: Destination folder (None to move to root/no folder).
        actor: User performing the action (for audit).

    Returns:
        Updated Document instance.
    """
    document.folder = destination
    document.save(update_fields=["folder", "updated_at"])
    return document
