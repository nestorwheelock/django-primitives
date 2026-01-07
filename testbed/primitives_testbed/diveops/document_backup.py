"""Document backup service for exporting virtual folder structure as filesystem archive or S3."""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from django.conf import settings
from django.utils import timezone

from django_documents.models import Document, DocumentFolder


# S3 client singleton
_s3_client = None


def get_s3_client():
    """Get or create S3 client (lazy initialization)."""
    global _s3_client
    if _s3_client is None:
        try:
            import boto3
            _s3_client = boto3.client(
                's3',
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
                endpoint_url=getattr(settings, 'AWS_S3_ENDPOINT_URL', None),  # For S3-compatible services
            )
        except ImportError:
            raise ImportError("boto3 is required for S3 sync. Install with: pip install boto3")
    return _s3_client


def sync_to_s3(
    bucket: str,
    prefix: str = "document-backup/",
    include_trash: bool = False,
    folder_ids: list[str] | None = None,
    document_ids: list[str] | None = None,
    delete_removed: bool = False,
) -> dict:
    """
    Sync the virtual folder structure to an S3 bucket.

    Args:
        bucket: S3 bucket name.
        prefix: Prefix for all objects (like a folder path).
        include_trash: Whether to include Trash folder contents.
        folder_ids: List of specific folder UUIDs to include.
        document_ids: List of specific document UUIDs to include.
        delete_removed: If True, delete S3 objects not in current selection.

    Returns:
        Statistics about the sync operation.
    """
    s3 = get_s3_client()

    stats = {
        "uploaded": 0,
        "skipped": 0,
        "deleted": 0,
        "errors": 0,
        "total_size": 0,
    }

    # Normalize prefix
    if prefix and not prefix.endswith('/'):
        prefix = prefix + '/'

    # Track uploaded keys for deletion detection
    uploaded_keys = set()

    # Get documents to sync
    if folder_ids or document_ids:
        documents = _get_selection_documents(folder_ids or [], document_ids or [], include_trash)
    else:
        documents = Document.objects.filter(deleted_at__isnull=True)
        if not include_trash:
            documents = documents.exclude(folder__slug="trash", folder__parent__isnull=True)

    # Upload each document
    for doc in documents:
        try:
            if not doc.file or not os.path.exists(doc.file.path):
                stats["errors"] += 1
                continue

            # Build the S3 key (preserving folder structure)
            s3_key = _build_s3_key(doc, prefix)
            uploaded_keys.add(s3_key)

            # Check if file needs upload (by comparing ETags/checksums)
            needs_upload = True
            try:
                head = s3.head_object(Bucket=bucket, Key=s3_key)
                existing_size = head.get('ContentLength', 0)
                if existing_size == doc.file_size:
                    # Size matches, check ETag if we have checksum
                    if doc.checksum:
                        etag = head.get('ETag', '').strip('"')
                        if etag == doc.checksum:
                            needs_upload = False
                            stats["skipped"] += 1
            except s3.exceptions.ClientError:
                pass  # Object doesn't exist, needs upload

            if needs_upload:
                # Upload with metadata
                extra_args = {
                    'ContentType': doc.content_type or 'application/octet-stream',
                    'Metadata': {
                        'document-id': str(doc.pk),
                        'original-filename': doc.filename,
                        'document-type': doc.document_type or '',
                    }
                }
                s3.upload_file(doc.file.path, bucket, s3_key, ExtraArgs=extra_args)
                stats["uploaded"] += 1
                stats["total_size"] += doc.file_size or 0

        except Exception as e:
            stats["errors"] += 1

    # Delete removed files if requested
    if delete_removed:
        try:
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    if obj['Key'] not in uploaded_keys:
                        s3.delete_object(Bucket=bucket, Key=obj['Key'])
                        stats["deleted"] += 1
        except Exception as e:
            stats["errors"] += 1

    return stats


def _build_s3_key(doc: Document, prefix: str) -> str:
    """Build the S3 key for a document, preserving folder structure."""
    path_parts = [prefix.rstrip('/')]

    if doc.folder:
        # Walk up the folder hierarchy
        folder_parts = []
        current = doc.folder
        while current is not None:
            folder_parts.insert(0, sanitize_filename(current.name))
            current = current.parent
        path_parts.extend(folder_parts)
    else:
        path_parts.append("_unfiled")

    path_parts.append(sanitize_filename(doc.filename))
    return '/'.join(path_parts)


def _get_selection_documents(folder_ids: list, document_ids: list, include_trash: bool):
    """Get documents based on folder and document selection."""
    from django.db.models import Q

    doc_pks = set()

    # Get documents from selected folders (recursively)
    if folder_ids:
        folders = DocumentFolder.objects.filter(pk__in=folder_ids, deleted_at__isnull=True)
        if not include_trash:
            folders = folders.exclude(slug="trash")

        for folder in folders:
            _collect_folder_docs(folder, doc_pks, include_trash)

    # Add individually selected documents
    if document_ids:
        doc_pks.update(document_ids)

    return Document.objects.filter(pk__in=doc_pks, deleted_at__isnull=True)


def _collect_folder_docs(folder: DocumentFolder, doc_pks: set, include_trash: bool):
    """Recursively collect document PKs from a folder."""
    for doc in folder.documents.filter(deleted_at__isnull=True):
        doc_pks.add(doc.pk)

    children = folder.children.filter(deleted_at__isnull=True)
    if not include_trash:
        children = children.exclude(slug="trash")

    for child in children:
        _collect_folder_docs(child, doc_pks, include_trash)


def download_from_s3(
    bucket: str,
    prefix: str = "document-backup/",
    output_path: str | None = None,
) -> str:
    """
    Download documents from S3 to a local ZIP archive.

    Args:
        bucket: S3 bucket name.
        prefix: Prefix to download from.
        output_path: Path for the output ZIP file.

    Returns:
        Path to the created ZIP archive.
    """
    s3 = get_s3_client()

    temp_dir = tempfile.mkdtemp(prefix="s3_download_")
    download_root = os.path.join(temp_dir, "documents")
    os.makedirs(download_root)

    stats = {"downloaded": 0, "errors": 0}

    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                # Remove prefix to get relative path
                rel_path = key[len(prefix):].lstrip('/')
                if not rel_path:
                    continue

                local_path = os.path.join(download_root, rel_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                try:
                    s3.download_file(bucket, key, local_path)
                    stats["downloaded"] += 1
                except Exception:
                    stats["errors"] += 1

    except Exception as e:
        raise RuntimeError(f"Failed to list S3 objects: {e}")

    # Create ZIP archive
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(tempfile.gettempdir(), f"s3_backup_{timestamp}.zip")

    with ZipFile(output_path, "w", ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(download_root):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)

    shutil.rmtree(temp_dir)
    return output_path


def build_folder_path(folder: DocumentFolder) -> str:
    """Build the full path for a folder by walking up the parent chain."""
    parts = []
    current = folder
    while current is not None:
        # Sanitize folder name for filesystem
        safe_name = sanitize_filename(current.name)
        parts.insert(0, safe_name)
        current = current.parent
    return os.path.join(*parts) if parts else ""


def sanitize_filename(name: str) -> str:
    """Sanitize a filename for safe filesystem use."""
    # Replace problematic characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        name = name.replace(char, '_')
    # Remove leading/trailing spaces and dots
    name = name.strip(' .')
    # Limit length
    if len(name) > 200:
        name = name[:200]
    return name or "unnamed"


def backup_documents(
    output_path: str | None = None,
    include_trash: bool = False,
    folder_id: str | None = None,
    include_metadata: bool = True,
    folder_ids: list[str] | None = None,
    document_ids: list[str] | None = None,
) -> str:
    """
    Export the virtual folder structure as a filesystem archive.

    Args:
        output_path: Path to write the ZIP file. If None, uses temp directory.
        include_trash: Whether to include Trash folder contents.
        folder_id: If provided, only backup this folder and its contents (legacy).
        include_metadata: If True, include a manifest.json with document metadata.
        folder_ids: List of specific folder UUIDs to include (with contents).
        document_ids: List of specific document UUIDs to include.

    Returns:
        Path to the created ZIP archive.
    """
    # Create temp directory for building the archive
    temp_dir = tempfile.mkdtemp(prefix="document_backup_")
    backup_root = os.path.join(temp_dir, "documents")
    os.makedirs(backup_root)

    # Track statistics
    stats = {
        "folders_created": 0,
        "documents_copied": 0,
        "documents_missing": 0,
        "total_size": 0,
    }

    # Metadata for manifest
    manifest = {
        "backup_date": timezone.now().isoformat(),
        "include_trash": include_trash,
        "selection_mode": "custom" if (folder_ids or document_ids) else "all",
        "folders": [],
        "documents": [],
    }

    # Mode 1: Specific selection of folders and/or documents
    if folder_ids or document_ids:
        _backup_selection(
            backup_root, stats, manifest,
            folder_ids=folder_ids or [],
            document_ids=document_ids or [],
            include_trash=include_trash,
        )
    # Mode 2: Single folder (legacy)
    elif folder_id:
        root_folders = DocumentFolder.objects.filter(pk=folder_id, deleted_at__isnull=True)
        for root_folder in root_folders:
            _process_folder(root_folder, backup_root, stats, manifest, include_trash)
    # Mode 3: Everything
    else:
        root_folders = DocumentFolder.objects.filter(parent__isnull=True, deleted_at__isnull=True)
        if not include_trash:
            root_folders = root_folders.exclude(slug="trash")

        for root_folder in root_folders:
            _process_folder(root_folder, backup_root, stats, manifest, include_trash)

        # Handle documents without folders (orphans)
        orphan_docs = Document.objects.filter(folder__isnull=True, deleted_at__isnull=True)
        if orphan_docs.exists():
            orphan_dir = os.path.join(backup_root, "_unfiled")
            os.makedirs(orphan_dir, exist_ok=True)
            stats["folders_created"] += 1
            manifest["folders"].append({
                "id": None,
                "name": "_unfiled",
                "path": "_unfiled",
                "description": "Documents without folder assignment",
            })

            for doc in orphan_docs:
                _copy_document(doc, orphan_dir, stats, manifest)

    # Write manifest if requested
    if include_metadata:
        import json
        manifest["statistics"] = stats
        manifest_path = os.path.join(backup_root, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

    # Create ZIP archive
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(tempfile.gettempdir(), f"document_backup_{timestamp}.zip")

    with ZipFile(output_path, "w", ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(backup_root):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)

    # Cleanup temp directory
    shutil.rmtree(temp_dir)

    return output_path


def _backup_selection(
    backup_root: str,
    stats: dict,
    manifest: dict,
    folder_ids: list[str],
    document_ids: list[str],
    include_trash: bool,
):
    """Backup a specific selection of folders and documents."""
    # Track which documents are already included via folder selection
    included_doc_ids = set()

    # Process selected folders (with their full contents)
    if folder_ids:
        folders = DocumentFolder.objects.filter(pk__in=folder_ids, deleted_at__isnull=True)
        if not include_trash:
            folders = folders.exclude(slug="trash")

        for folder in folders:
            # Build the full path for this folder
            folder_path_parts = []
            current = folder
            while current is not None:
                folder_path_parts.insert(0, sanitize_filename(current.name))
                current = current.parent

            # Create the folder structure
            current_path = backup_root
            for part in folder_path_parts:
                current_path = os.path.join(current_path, part)
                if not os.path.exists(current_path):
                    os.makedirs(current_path)
                    stats["folders_created"] += 1

            # Add folder to manifest
            rel_path = os.path.relpath(current_path, backup_root)
            manifest["folders"].append({
                "id": str(folder.pk),
                "name": folder.name,
                "path": rel_path,
                "description": folder.description or "",
            })

            # Copy all documents in this folder (recursively)
            _copy_folder_contents(folder, current_path, stats, manifest, included_doc_ids, include_trash)

    # Process individually selected documents (not already included via folders)
    if document_ids:
        docs = Document.objects.filter(pk__in=document_ids, deleted_at__isnull=True)
        docs = docs.exclude(pk__in=included_doc_ids)

        for doc in docs:
            # Determine the target path
            if doc.folder:
                # Build folder path for this document
                folder_path_parts = []
                current = doc.folder
                while current is not None:
                    folder_path_parts.insert(0, sanitize_filename(current.name))
                    current = current.parent

                current_path = backup_root
                for part in folder_path_parts:
                    current_path = os.path.join(current_path, part)
                    if not os.path.exists(current_path):
                        os.makedirs(current_path)
                        stats["folders_created"] += 1
            else:
                # Orphan document - put in _selected folder
                current_path = os.path.join(backup_root, "_selected")
                if not os.path.exists(current_path):
                    os.makedirs(current_path)
                    stats["folders_created"] += 1

            _copy_document(doc, current_path, stats, manifest)


def _copy_folder_contents(
    folder: DocumentFolder,
    target_path: str,
    stats: dict,
    manifest: dict,
    included_doc_ids: set,
    include_trash: bool,
):
    """Copy all documents in a folder and recurse into subfolders."""
    # Copy documents
    for doc in folder.documents.filter(deleted_at__isnull=True):
        _copy_document(doc, target_path, stats, manifest)
        included_doc_ids.add(doc.pk)

    # Recurse into subfolders
    children = folder.children.filter(deleted_at__isnull=True)
    if not include_trash:
        children = children.exclude(slug="trash")

    for child in children:
        child_path = os.path.join(target_path, sanitize_filename(child.name))
        if not os.path.exists(child_path):
            os.makedirs(child_path)
            stats["folders_created"] += 1

        rel_path = os.path.relpath(child_path, os.path.dirname(os.path.dirname(target_path)))
        manifest["folders"].append({
            "id": str(child.pk),
            "name": child.name,
            "path": rel_path,
            "description": child.description or "",
        })

        _copy_folder_contents(child, child_path, stats, manifest, included_doc_ids, include_trash)


def _process_folder(
    folder: DocumentFolder,
    parent_path: str,
    stats: dict,
    manifest: dict,
    include_trash: bool,
):
    """Recursively process a folder and its contents."""
    # Build folder path
    folder_name = sanitize_filename(folder.name)
    folder_path = os.path.join(parent_path, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    stats["folders_created"] += 1

    # Get relative path from backup root
    rel_path = os.path.relpath(folder_path, os.path.dirname(parent_path))

    manifest["folders"].append({
        "id": str(folder.pk),
        "name": folder.name,
        "path": rel_path,
        "description": folder.description or "",
        "slug": folder.slug or "",
    })

    # Copy documents in this folder
    for doc in folder.documents.filter(deleted_at__isnull=True):
        _copy_document(doc, folder_path, stats, manifest)

    # Process child folders
    children = folder.children.filter(deleted_at__isnull=True)
    if not include_trash:
        children = children.exclude(slug="trash")

    for child in children:
        _process_folder(child, folder_path, stats, manifest, include_trash)


def _copy_document(doc: Document, target_dir: str, stats: dict, manifest: dict):
    """Copy a document file to the target directory."""
    if not doc.file:
        stats["documents_missing"] += 1
        return

    try:
        source_path = doc.file.path
        if not os.path.exists(source_path):
            stats["documents_missing"] += 1
            return

        # Use original filename, handle duplicates
        target_filename = sanitize_filename(doc.filename)
        target_path = os.path.join(target_dir, target_filename)

        # Handle duplicate filenames
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_filename)
            counter = 1
            while os.path.exists(target_path):
                target_filename = f"{base}_{counter}{ext}"
                target_path = os.path.join(target_dir, target_filename)
                counter += 1

        # Copy the file
        shutil.copy2(source_path, target_path)
        stats["documents_copied"] += 1
        stats["total_size"] += os.path.getsize(target_path)

        # Add to manifest
        rel_path = os.path.relpath(target_path, os.path.dirname(os.path.dirname(target_dir)))
        manifest["documents"].append({
            "id": str(doc.pk),
            "filename": doc.filename,
            "path": rel_path,
            "document_type": doc.document_type,
            "content_type": doc.content_type,
            "size": doc.file_size,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "checksum": doc.checksum,
        })

    except Exception as e:
        stats["documents_missing"] += 1


def get_backup_stats() -> dict:
    """Get statistics about what would be backed up."""
    total_docs = Document.objects.filter(deleted_at__isnull=True).count()
    trash_docs = Document.objects.filter(
        folder__slug="trash",
        folder__parent__isnull=True,
        deleted_at__isnull=True,
    ).count()
    orphan_docs = Document.objects.filter(folder__isnull=True, deleted_at__isnull=True).count()
    total_folders = DocumentFolder.objects.filter(deleted_at__isnull=True).count()

    # Calculate total size
    total_size = 0
    for doc in Document.objects.filter(deleted_at__isnull=True):
        if doc.file and doc.file_size:
            total_size += doc.file_size

    return {
        "total_documents": total_docs,
        "trash_documents": trash_docs,
        "orphan_documents": orphan_docs,
        "total_folders": total_folders,
        "estimated_size": total_size,
    }
