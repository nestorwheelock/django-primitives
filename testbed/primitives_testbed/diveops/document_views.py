"""Document management views for diveops staff portal."""

import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from django_portal_ui.mixins import StaffPortalMixin

from django_documents.models import (
    AccessAction,
    Document,
    DocumentAccessLog,
    DocumentContent,
    DocumentFolder,
    ExtractionStatus,
    FolderPermission,
    PermissionLevel,
)
from django_documents.extraction import can_extract, process_document_extraction
from django_documents.services import (
    attach_document,
    create_folder,
    delete_folder,
    grant_folder_permission,
    log_access,
    move_document,
)
from django_documents.exceptions import FolderNotEmpty

from .document_forms import (
    DocumentFolderForm,
    DocumentLegalHoldForm,
    DocumentLegalHoldReleaseForm,
    DocumentMoveForm,
    DocumentRetentionPolicyForm,
    DocumentUploadForm,
    FolderPermissionForm,
)
from .models import DocumentLegalHold, DocumentRetentionPolicy


# =============================================================================
# Browser / Navigation Views
# =============================================================================


class DocumentBrowserView(StaffPortalMixin, TemplateView):
    """Root view showing all root folders and documents without folders."""

    template_name = "diveops/staff/document_browser.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Documents"
        context["root_folders"] = DocumentFolder.objects.filter(parent__isnull=True).order_by("name")
        context["orphan_documents"] = Document.objects.filter(folder__isnull=True).order_by("-created_at")[:20]
        return context


class FolderDetailView(StaffPortalMixin, DetailView):
    """Show folder contents (subfolders + documents)."""

    model = DocumentFolder
    template_name = "diveops/staff/folder_detail.html"
    context_object_name = "folder"

    # Valid sort fields and their display names
    SORT_OPTIONS = {
        "name": "Name (A-Z)",
        "-name": "Name (Z-A)",
        "created_at": "Oldest First",
        "-created_at": "Newest First",
        "category": "Category",
        "-category": "Category (Z-A)",
        "file_size": "Size (Smallest)",
        "-file_size": "Size (Largest)",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        folder = self.object

        # Get sort and view preferences from query params
        sort = self.request.GET.get("sort", "-created_at")
        view = self.request.GET.get("view", "list")

        # Validate sort field
        if sort not in self.SORT_OPTIONS:
            sort = "-created_at"

        # Map sort field to actual model field
        sort_field = sort
        if sort in ("name", "-name"):
            sort_field = sort.replace("name", "filename")

        # Get sorted documents
        documents = folder.documents.all()
        try:
            documents = documents.order_by(sort_field)
        except Exception:
            documents = documents.order_by("-created_at")

        context["page_title"] = folder.name
        context["subfolders"] = folder.children.order_by("name")
        context["documents"] = documents
        context["breadcrumbs"] = self._build_breadcrumbs(folder)
        context["is_trash"] = folder.slug == "trash" and folder.parent is None
        context["sort"] = sort
        context["sort_display"] = self.SORT_OPTIONS.get(sort, "Newest First")
        context["view"] = view
        return context

    def _build_breadcrumbs(self, folder):
        """Build breadcrumb trail from root to current folder."""
        breadcrumbs = []
        current = folder
        while current is not None:
            breadcrumbs.insert(0, current)
            current = current.parent
        return breadcrumbs


# =============================================================================
# Folder CRUD Views
# =============================================================================


class FolderCreateView(StaffPortalMixin, FormView):
    """Create a new folder (root or nested)."""

    template_name = "diveops/staff/folder_form.html"
    form_class = DocumentFolderForm

    def get_parent_folder(self):
        """Get parent folder from URL if creating subfolder."""
        parent_pk = self.kwargs.get("parent_pk")
        if parent_pk:
            return get_object_or_404(DocumentFolder, pk=parent_pk)
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.get_parent_folder()
        if parent:
            context["page_title"] = f"Create Subfolder in {parent.name}"
            context["parent_folder"] = parent
        else:
            context["page_title"] = "Create Folder"
        context["is_create"] = True
        return context

    def form_valid(self, form):
        parent = self.get_parent_folder()
        folder = create_folder(
            name=form.cleaned_data["name"],
            description=form.cleaned_data.get("description", ""),
            parent=parent,
            actor=self.request.user,
        )
        messages.success(self.request, f"Folder '{folder.name}' created successfully.")
        return redirect("diveops:folder-detail", pk=folder.pk)


class FolderUpdateView(StaffPortalMixin, UpdateView):
    """Edit folder name/description."""

    model = DocumentFolder
    form_class = DocumentFolderForm
    template_name = "diveops/staff/folder_form.html"
    context_object_name = "folder"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit {self.object.name}"
        context["is_create"] = False
        return context

    def get_success_url(self):
        messages.success(self.request, f"Folder '{self.object.name}' updated successfully.")
        return reverse("diveops:folder-detail", kwargs={"pk": self.object.pk})


class FolderDeleteView(StaffPortalMixin, DeleteView):
    """Delete a folder (must be empty)."""

    model = DocumentFolder
    template_name = "diveops/staff/folder_confirm_delete.html"
    context_object_name = "folder"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.name}"
        context["has_children"] = self.object.children.exists()
        context["has_documents"] = self.object.documents.exists()
        return context

    def form_valid(self, form):
        folder = self.object
        folder_name = folder.name
        parent_pk = folder.parent_id

        try:
            delete_folder(folder=folder, actor=self.request.user, recursive=False)
            messages.success(self.request, f"Folder '{folder_name}' deleted successfully.")
        except FolderNotEmpty:
            messages.error(self.request, f"Cannot delete folder '{folder_name}': it contains subfolders or documents.")
            return redirect("diveops:folder-detail", pk=folder.pk)

        if parent_pk:
            return redirect("diveops:folder-detail", pk=parent_pk)
        return redirect("diveops:document-browser")


# =============================================================================
# Document Operations Views
# =============================================================================


class DocumentDetailView(StaffPortalMixin, DetailView):
    """Show document details with versions and access log."""

    model = Document
    template_name = "diveops/staff/document_detail.html"
    context_object_name = "document"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Log the view
        log_access(
            document=self.object,
            action=AccessAction.VIEW,
            actor=request.user,
            request=request,
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc = self.object
        context["page_title"] = doc.filename
        context["versions"] = doc.versions.order_by("-created_at")[:10]

        # Combine access logs with audit log entries for unified activity view
        context["activity_log"] = self._get_activity_log(doc)

        if doc.folder:
            context["breadcrumbs"] = self._build_breadcrumbs(doc.folder)

        # Get extracted content if available
        try:
            context["content"] = doc.content
        except DocumentContent.DoesNotExist:
            context["content"] = None

        # Check if extraction is supported for this document
        context["can_extract"] = can_extract(doc.content_type)

        # Legal hold information
        context["has_legal_hold"] = DocumentLegalHold.document_has_active_hold(doc)
        context["active_holds"] = DocumentLegalHold.objects.filter(
            document=doc,
            released_at__isnull=True,
            deleted_at__isnull=True,
        ).select_related("placed_by")

        # Notes for document
        context["notes"] = self._get_document_notes(doc)

        # File metadata (EXIF, video/audio info)
        # Auto-extract metadata for images/video/audio if not already done
        metadata = doc.metadata or {}
        is_media = (
            doc.category in ("image", "video", "audio") or
            (doc.content_type and doc.content_type.startswith(("image/", "video/", "audio/")))
        )
        if is_media and "file_metadata" not in metadata:
            try:
                from .document_metadata import extract_document_metadata
                extracted = extract_document_metadata(doc)
                if extracted:
                    metadata.update(extracted)
                    doc.metadata = metadata
                    doc.save(update_fields=["metadata", "updated_at"])
            except Exception as e:
                logger.warning(f"Auto metadata extraction failed for {doc.filename}: {e}")

        if "file_metadata" in metadata:
            context["file_metadata"] = metadata.get("file_metadata", {})
            context["image_metadata"] = metadata.get("image_metadata", {})
            context["video_metadata"] = metadata.get("video_metadata", {})
            context["audio_metadata"] = metadata.get("audio_metadata", {})

        # Office document detection
        from .document_metadata import is_office_document, can_convert_to_pdf
        context["is_office_document"] = is_office_document(doc)
        context["can_convert_to_pdf"] = can_convert_to_pdf(doc)

        # Check if we have a PDF conversion available
        if context["is_office_document"]:
            pdf_version = doc.metadata.get("pdf_preview_version") if doc.metadata else None
            if pdf_version:
                context["office_preview_url"] = reverse("diveops:document-preview-pdf", kwargs={"pk": doc.pk})

        # Photo tagging (only for images)
        is_image = (
            doc.category == "image" or
            (doc.content_type and doc.content_type.startswith("image/"))
        )
        if is_image:
            from .models import PhotoTag, DiverProfile, DiveSitePhotoTag, DiveSite
            # Diver tagging
            context["photo_tags"] = PhotoTag.objects.filter(
                document=doc, deleted_at__isnull=True
            ).select_related("diver__person", "tagged_by")
            # Get divers not already tagged in this photo
            tagged_diver_ids = context["photo_tags"].values_list("diver_id", flat=True)
            context["available_divers"] = DiverProfile.objects.exclude(
                id__in=tagged_diver_ids
            ).select_related("person").order_by("person__last_name", "person__first_name")[:50]
            context["can_tag_divers"] = True

            # Dive site tagging
            context["dive_site_tags"] = DiveSitePhotoTag.objects.filter(
                document=doc, deleted_at__isnull=True
            ).select_related("dive_site", "tagged_by")
            # Get dive sites not already tagged in this photo
            tagged_site_ids = context["dive_site_tags"].values_list("dive_site_id", flat=True)
            context["available_dive_sites"] = DiveSite.objects.filter(
                deleted_at__isnull=True
            ).exclude(
                id__in=tagged_site_ids
            ).order_by("name")[:50]
            context["can_tag_dive_sites"] = True
        else:
            context["can_tag_divers"] = False
            context["can_tag_dive_sites"] = False

        return context

    def _get_activity_log(self, document):
        """Get unified activity log combining access logs and audit log entries."""
        from types import SimpleNamespace
        from django.contrib.contenttypes.models import ContentType
        from django_audit_log.models import AuditLog

        activities = []

        # Get document access log entries
        access_logs = document.access_logs.select_related("actor").order_by("-accessed_at")[:20]
        for log in access_logs:
            activities.append(SimpleNamespace(
                timestamp=log.accessed_at,
                action=log.action,
                action_display=log.get_action_display(),
                actor=log.actor,
                actor_display=log.actor.username if log.actor else "Anonymous",
                source="access",
                details=None,
            ))

        # Get audit log entries for this document
        doc_content_type = ContentType.objects.get_for_model(document)
        model_label = f"{doc_content_type.app_label}.{doc_content_type.model}"
        audit_logs = AuditLog.objects.filter(
            model_label=model_label,
            object_id=str(document.pk),
        ).select_related("actor_user").order_by("-created_at")[:20]

        for log in audit_logs:
            # Make action more readable
            action_display = log.action.replace("_", " ").title()
            details = None

            # Extract meaningful details from metadata
            if log.metadata:
                if "diver_name" in log.metadata:
                    details = log.metadata.get("diver_name")

            activities.append(SimpleNamespace(
                timestamp=log.created_at,
                action=log.action,
                action_display=action_display,
                actor=log.actor_user,
                actor_display=log.actor_display or (log.actor_user.username if log.actor_user else "System"),
                source="audit",
                details=details,
            ))

        # Sort by timestamp descending and limit to 15 most recent
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        return activities[:15]

    def _build_breadcrumbs(self, folder):
        """Build breadcrumb trail from root to folder."""
        breadcrumbs = []
        current = folder
        while current is not None:
            breadcrumbs.insert(0, current)
            current = current.parent
        return breadcrumbs

    def _get_document_notes(self, document):
        """Get notes for a document from metadata."""
        metadata = document.metadata or {}
        notes_data = metadata.get("notes", [])
        # Convert to objects for easier template access
        notes = []
        for note in notes_data:
            from types import SimpleNamespace
            from django.contrib.auth import get_user_model
            from django.utils.dateparse import parse_datetime

            User = get_user_model()
            created_by = None
            if note.get("created_by_id"):
                try:
                    created_by = User.objects.get(pk=note["created_by_id"])
                except User.DoesNotExist:
                    pass

            notes.append(SimpleNamespace(
                pk=note.get("pk"),
                text=note.get("text", ""),
                created_by=created_by,
                created_at=parse_datetime(note.get("created_at")) if note.get("created_at") else None,
            ))
        return notes


class DocumentExtractView(StaffPortalMixin, View):
    """Trigger text extraction for a document."""

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        if not can_extract(document.content_type):
            messages.error(request, f"Text extraction not supported for {document.content_type}")
            return redirect("diveops:document-detail", pk=pk)

        try:
            content = process_document_extraction(document)
            if content.status == ExtractionStatus.COMPLETED:
                messages.success(
                    request,
                    f"Text extraction complete: {content.word_count or 0} words extracted in {content.processing_time_ms}ms."
                )
            elif content.status == ExtractionStatus.FAILED:
                messages.error(request, f"Text extraction failed: {content.error_message}")
            else:
                messages.warning(request, f"Text extraction status: {content.get_status_display()}")
        except Exception as e:
            messages.error(request, f"Text extraction error: {str(e)}")

        return redirect("diveops:document-detail", pk=pk)


class DocumentUploadView(StaffPortalMixin, FormView):
    """Upload a document to a folder."""

    template_name = "diveops/staff/document_upload.html"
    form_class = DocumentUploadForm

    def get_folder(self):
        """Get target folder from URL."""
        folder_pk = self.kwargs.get("pk")
        return get_object_or_404(DocumentFolder, pk=folder_pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        folder = self.get_folder()
        context["page_title"] = f"Upload to {folder.name}"
        context["folder"] = folder
        context["breadcrumbs"] = self._build_breadcrumbs(folder)
        return context

    def _build_breadcrumbs(self, folder):
        breadcrumbs = []
        current = folder
        while current is not None:
            breadcrumbs.insert(0, current)
            current = current.parent
        return breadcrumbs

    def _get_category_from_mime(self, mime_type):
        """Determine document category from mime type."""
        if not mime_type:
            return "document"
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
        return "document"

    def form_valid(self, form):
        folder = self.get_folder()
        uploaded_file = form.cleaned_data["file"]

        # Detect mime type
        import mimetypes
        content_type = getattr(uploaded_file, "content_type", None)
        if not content_type or content_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(uploaded_file.name)
            content_type = guessed or "application/octet-stream"

        # Determine category from mime type
        category = self._get_category_from_mime(content_type)

        # Create document in folder
        doc = Document.objects.create(
            folder=folder,
            file=uploaded_file,
            filename=uploaded_file.name,
            content_type=content_type,
            document_type=content_type,
            category=category,
            file_size=uploaded_file.size,
        )

        # Log the upload
        log_access(
            document=doc,
            action=AccessAction.UPLOAD,
            actor=self.request.user,
            request=self.request,
        )

        # Auto-extract EXIF/metadata for images, video, audio
        if category in ("image", "video", "audio"):
            try:
                from .document_metadata import extract_document_metadata
                extracted = extract_document_metadata(doc)
                if extracted:
                    metadata = doc.metadata or {}
                    metadata.update(extracted)
                    doc.metadata = metadata
                    doc.save(update_fields=["metadata", "updated_at"])
            except Exception as e:
                logger.warning(f"Metadata extraction failed for {doc.filename}: {e}")

        # Trigger text extraction if supported
        if can_extract(doc.content_type):
            try:
                content = process_document_extraction(doc)
                if content.status == ExtractionStatus.COMPLETED:
                    messages.info(
                        self.request,
                        f"Text extraction complete: {content.word_count or 0} words extracted."
                    )
                elif content.status == ExtractionStatus.FAILED:
                    messages.warning(
                        self.request,
                        f"Text extraction failed: {content.error_message}"
                    )
            except Exception as e:
                messages.warning(self.request, f"Text extraction error: {str(e)}")

        messages.success(self.request, f"Document '{doc.filename}' uploaded successfully.")
        return redirect("diveops:folder-detail", pk=folder.pk)


class DocumentDownloadView(StaffPortalMixin, View):
    """Download a document and log the access."""

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        # Log the download
        log_access(
            document=document,
            action=AccessAction.DOWNLOAD,
            actor=request.user,
            request=request,
        )

        # Serve the file
        if not document.file:
            raise Http404("File not found")

        file_path = document.file.path
        if not os.path.exists(file_path):
            raise Http404("File not found on disk")

        response = FileResponse(
            open(file_path, "rb"),
            as_attachment=True,
            filename=document.filename,
        )
        return response


class DocumentPreviewView(StaffPortalMixin, View):
    """Preview a document inline (for PDFs, images, etc.)."""

    # Content types that can be previewed inline
    PREVIEWABLE_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "text/plain",
        "text/html",
        "text/csv",
    }

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        # Log the preview access
        log_access(
            document=document,
            action=AccessAction.PREVIEW,
            actor=request.user,
            request=request,
        )

        # Serve the file
        if not document.file:
            raise Http404("File not found")

        file_path = document.file.path
        if not os.path.exists(file_path):
            raise Http404("File not found on disk")

        # Determine content type
        content_type = document.content_type or "application/octet-stream"

        # Check if previewable
        if content_type not in self.PREVIEWABLE_TYPES:
            # Fall back to download
            return redirect("diveops:document-download", pk=pk)

        response = FileResponse(
            open(file_path, "rb"),
            as_attachment=False,  # Display inline
            filename=document.filename,
            content_type=content_type,
        )

        # For PDFs, set proper headers for browser viewing
        if content_type == "application/pdf":
            response["Content-Disposition"] = f'inline; filename="{document.filename}"'

        return response


class DocumentMoveView(StaffPortalMixin, FormView):
    """Move a document to a different folder."""

    template_name = "diveops/staff/document_move.html"
    form_class = DocumentMoveForm

    def get_document(self):
        return get_object_or_404(Document, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        document = self.get_document()
        kwargs["exclude_folder"] = document.folder
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.get_document()
        context["page_title"] = f"Move {document.filename}"
        context["document"] = document
        return context

    def form_valid(self, form):
        document = self.get_document()
        destination = form.cleaned_data["destination"]

        # Log the move
        log_access(
            document=document,
            action=AccessAction.MOVE,
            actor=self.request.user,
            request=self.request,
        )

        # Move the document
        move_document(
            document=document,
            destination=destination,
            actor=self.request.user,
        )

        messages.success(self.request, f"Document '{document.filename}' moved to '{destination.name}'.")
        return redirect("diveops:document-detail", pk=document.pk)


class DocumentDeleteView(StaffPortalMixin, DeleteView):
    """Move a document to Trash folder."""

    model = Document
    template_name = "diveops/staff/document_confirm_delete.html"
    context_object_name = "document"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete {self.object.filename}"
        context["has_legal_hold"] = DocumentLegalHold.document_has_active_hold(self.object)
        return context

    def form_valid(self, form):
        document = self.object
        filename = document.filename
        original_folder_pk = document.folder_id if document.folder else None

        # Check for legal hold
        if DocumentLegalHold.document_has_active_hold(document):
            messages.error(
                self.request,
                f"Cannot delete '{filename}': document has an active legal hold."
            )
            return redirect("diveops:document-detail", pk=document.pk)

        # Get or create Trash folder
        trash_folder = DocumentFolder.objects.filter(
            slug="trash",
            parent__isnull=True,
        ).first()

        if not trash_folder:
            # Create Trash folder if it doesn't exist
            from django_documents.services import create_folder
            trash_folder = create_folder(
                name="Trash",
                description="Deleted documents awaiting permanent removal",
                parent=None,
                actor=self.request.user,
            )

        # Store original folder in metadata for potential restore
        metadata = document.metadata or {}
        if document.folder:
            metadata["original_folder_id"] = str(document.folder_id)
            metadata["original_folder_name"] = document.folder.name
        metadata["deleted_at"] = timezone.now().isoformat()
        metadata["deleted_by"] = self.request.user.username if self.request.user else None
        document.metadata = metadata

        # Move to Trash
        document.folder = trash_folder
        document.save(update_fields=["folder", "metadata", "updated_at"])

        # Log the delete
        log_access(
            document=document,
            action=AccessAction.DELETE,
            actor=self.request.user,
            request=self.request,
        )

        messages.success(self.request, f"Document '{filename}' moved to Trash.")

        if original_folder_pk:
            return redirect("diveops:folder-detail", pk=original_folder_pk)
        return redirect("diveops:document-browser")


class DocumentRestoreView(StaffPortalMixin, View):
    """Restore a document from Trash to its original folder."""

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        # Check if document is in Trash
        if not document.folder or document.folder.slug != "trash":
            messages.error(request, "This document is not in the Trash.")
            return redirect("diveops:document-detail", pk=pk)

        # Get original folder from metadata
        metadata = document.metadata or {}
        original_folder_id = metadata.get("original_folder_id")
        original_folder = None

        if original_folder_id:
            try:
                from uuid import UUID
                original_folder = DocumentFolder.objects.filter(pk=UUID(original_folder_id)).first()
            except (ValueError, TypeError):
                pass

        # Move document back to original folder (or root if not found)
        document.folder = original_folder

        # Clean up trash metadata
        if "original_folder_id" in metadata:
            del metadata["original_folder_id"]
        if "original_folder_name" in metadata:
            del metadata["original_folder_name"]
        if "deleted_at" in metadata:
            del metadata["deleted_at"]
        if "deleted_by" in metadata:
            del metadata["deleted_by"]
        document.metadata = metadata
        document.save(update_fields=["folder", "metadata", "updated_at"])

        # Log the restore
        log_access(
            document=document,
            action=AccessAction.VIEW,  # Using VIEW as there's no RESTORE action
            actor=request.user,
            request=request,
        )

        if original_folder:
            messages.success(request, f"Document '{document.filename}' restored to '{original_folder.name}'.")
        else:
            messages.success(request, f"Document '{document.filename}' restored (original folder not found).")

        return redirect("diveops:document-detail", pk=pk)


class DocumentPermanentDeleteView(StaffPortalMixin, DeleteView):
    """Permanently delete a document from Trash."""

    model = Document
    template_name = "diveops/staff/document_confirm_permanent_delete.html"
    context_object_name = "document"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Permanently Delete {self.object.filename}"
        context["has_legal_hold"] = DocumentLegalHold.document_has_active_hold(self.object)
        return context

    def form_valid(self, form):
        document = self.object
        filename = document.filename

        # Check if document is in Trash
        if not document.folder or document.folder.slug != "trash":
            messages.error(self.request, "Only documents in Trash can be permanently deleted.")
            return redirect("diveops:document-detail", pk=document.pk)

        # Check for legal hold
        if DocumentLegalHold.document_has_active_hold(document):
            messages.error(
                self.request,
                f"Cannot permanently delete '{filename}': document has an active legal hold."
            )
            return redirect("diveops:document-detail", pk=document.pk)

        # Log the permanent delete before deletion
        log_access(
            document=document,
            action=AccessAction.DELETE,
            actor=self.request.user,
            request=self.request,
        )

        # Actually delete the document (hard delete via BaseModel)
        document.hard_delete()
        messages.success(self.request, f"Document '{filename}' permanently deleted.")

        # Redirect to Trash folder
        trash_folder = DocumentFolder.objects.filter(slug="trash", parent__isnull=True).first()
        if trash_folder:
            return redirect("diveops:folder-detail", pk=trash_folder.pk)
        return redirect("diveops:document-browser")


class EmptyTrashView(StaffPortalMixin, View):
    """Empty all documents from Trash, respecting legal holds."""

    def post(self, request):
        trash_folder = DocumentFolder.objects.filter(slug="trash", parent__isnull=True).first()

        if not trash_folder:
            messages.error(request, "Trash folder not found.")
            return redirect("diveops:document-browser")

        # Get all documents in trash
        documents = list(Document.objects.filter(folder=trash_folder))

        deleted_count = 0
        held_count = 0
        held_docs = []

        # Process each document, checking for legal holds
        for doc in documents:
            if DocumentLegalHold.document_has_active_hold(doc):
                held_count += 1
                held_docs.append(doc.filename)
            else:
                # Log the deletion before removing
                log_access(
                    document=doc,
                    action=AccessAction.DELETE,
                    actor=request.user,
                    request=request,
                )
                doc.hard_delete()
                deleted_count += 1

        # Build appropriate message
        if deleted_count > 0 and held_count > 0:
            messages.success(
                request,
                f"Permanently deleted {deleted_count} document(s) from Trash. "
                f"Skipped {held_count} document(s) with active legal holds."
            )
        elif deleted_count > 0:
            messages.success(request, f"Permanently deleted {deleted_count} document(s) from Trash.")
        elif held_count > 0:
            messages.warning(
                request,
                f"No documents deleted. {held_count} document(s) have active legal holds."
            )
        else:
            messages.info(request, "Trash is already empty.")

        return redirect("diveops:folder-detail", pk=trash_folder.pk)


# =============================================================================
# Permission Management Views
# =============================================================================


class FolderPermissionListView(StaffPortalMixin, ListView):
    """List permissions on a folder."""

    model = FolderPermission
    template_name = "diveops/staff/folder_permissions.html"
    context_object_name = "permissions"

    def get_folder(self):
        return get_object_or_404(DocumentFolder, pk=self.kwargs["pk"])

    def get_queryset(self):
        folder = self.get_folder()
        return FolderPermission.objects.filter(folder=folder).select_related("grantee_content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        folder = self.get_folder()
        context["page_title"] = f"Permissions for {folder.name}"
        context["folder"] = folder
        context["permission_levels"] = PermissionLevel.choices
        return context


class FolderPermissionCreateView(StaffPortalMixin, FormView):
    """Grant permission on a folder."""

    template_name = "diveops/staff/folder_permission_form.html"
    form_class = FolderPermissionForm

    def get_folder(self):
        return get_object_or_404(DocumentFolder, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        folder = self.get_folder()
        context["page_title"] = f"Grant Permission on {folder.name}"
        context["folder"] = folder
        return context

    def form_valid(self, form):
        folder = self.get_folder()
        user = form.cleaned_data["user"]
        level = int(form.cleaned_data["level"])
        inherited = form.cleaned_data["inherited"]

        grant_folder_permission(
            folder=folder,
            grantee=user,
            level=PermissionLevel(level),
            inherited=inherited,
            actor=self.request.user,
        )

        messages.success(self.request, f"Permission granted to {user.username} on '{folder.name}'.")
        return redirect("diveops:folder-permissions", pk=folder.pk)


class FolderPermissionDeleteView(StaffPortalMixin, DeleteView):
    """Revoke a permission."""

    model = FolderPermission
    template_name = "diveops/staff/folder_permission_confirm_delete.html"
    context_object_name = "permission"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Revoke Permission"
        return context

    def get_success_url(self):
        folder_pk = self.object.folder_id
        messages.success(self.request, "Permission revoked successfully.")
        return reverse("diveops:folder-permissions", kwargs={"pk": folder_pk})


# =============================================================================
# Access Log Views
# =============================================================================


class DocumentAccessLogView(StaffPortalMixin, ListView):
    """View document access logs with filtering."""

    model = DocumentAccessLog
    template_name = "diveops/staff/document_access_logs.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        qs = DocumentAccessLog.objects.select_related("document", "actor").order_by("-accessed_at")

        # Filter by action
        action = self.request.GET.get("action")
        if action:
            qs = qs.filter(action=action)

        # Filter by document
        document_pk = self.request.GET.get("document")
        if document_pk:
            qs = qs.filter(document_id=document_pk)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Document Access Logs"
        context["actions"] = AccessAction.choices
        context["current_action"] = self.request.GET.get("action", "")
        return context


# =============================================================================
# Retention Policy Views
# =============================================================================


class RetentionPolicyListView(StaffPortalMixin, ListView):
    """List all document retention policies."""

    model = DocumentRetentionPolicy
    template_name = "diveops/staff/retention_policy_list.html"
    context_object_name = "policies"

    def get_queryset(self):
        return DocumentRetentionPolicy.objects.filter(deleted_at__isnull=True).order_by("document_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Document Retention Policies"
        return context


class RetentionPolicyCreateView(StaffPortalMixin, CreateView):
    """Create a new retention policy."""

    model = DocumentRetentionPolicy
    form_class = DocumentRetentionPolicyForm
    template_name = "diveops/staff/retention_policy_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Retention Policy"
        context["is_create"] = True
        return context

    def get_success_url(self):
        messages.success(self.request, f"Retention policy for '{self.object.document_type}' created.")
        return reverse("diveops:retention-policy-list")


class RetentionPolicyUpdateView(StaffPortalMixin, UpdateView):
    """Edit an existing retention policy."""

    model = DocumentRetentionPolicy
    form_class = DocumentRetentionPolicyForm
    template_name = "diveops/staff/retention_policy_form.html"
    context_object_name = "policy"

    def get_queryset(self):
        return DocumentRetentionPolicy.objects.filter(deleted_at__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Policy: {self.object.document_type}"
        context["is_create"] = False
        return context

    def get_success_url(self):
        messages.success(self.request, f"Retention policy for '{self.object.document_type}' updated.")
        return reverse("diveops:retention-policy-list")


class RetentionPolicyDeleteView(StaffPortalMixin, DeleteView):
    """Delete a retention policy."""

    model = DocumentRetentionPolicy
    template_name = "diveops/staff/retention_policy_confirm_delete.html"
    context_object_name = "policy"

    def get_queryset(self):
        return DocumentRetentionPolicy.objects.filter(deleted_at__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Delete Policy: {self.object.document_type}"
        return context

    def form_valid(self, form):
        policy = self.object
        policy_name = policy.document_type
        # Soft delete
        policy.deleted_at = timezone.now()
        policy.save(update_fields=["deleted_at", "updated_at"])
        messages.success(self.request, f"Retention policy for '{policy_name}' deleted.")
        return HttpResponseRedirect(reverse("diveops:retention-policy-list"))


# =============================================================================
# Legal Hold Views
# =============================================================================


class LegalHoldListView(StaffPortalMixin, ListView):
    """List all legal holds (active and released)."""

    model = DocumentLegalHold
    template_name = "diveops/staff/legal_hold_list.html"
    context_object_name = "holds"
    paginate_by = 50

    def get_queryset(self):
        qs = DocumentLegalHold.objects.filter(deleted_at__isnull=True).select_related(
            "document", "placed_by", "released_by"
        ).order_by("-placed_at")

        # Filter by status
        status = self.request.GET.get("status")
        if status == "active":
            qs = qs.filter(released_at__isnull=True)
        elif status == "released":
            qs = qs.filter(released_at__isnull=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Legal Holds"
        context["current_status"] = self.request.GET.get("status", "")
        context["active_count"] = DocumentLegalHold.objects.filter(
            deleted_at__isnull=True, released_at__isnull=True
        ).count()
        return context


class LegalHoldCreateView(StaffPortalMixin, FormView):
    """Place a legal hold on a document."""

    template_name = "diveops/staff/legal_hold_form.html"
    form_class = DocumentLegalHoldForm

    def get_document(self):
        return get_object_or_404(Document, pk=self.kwargs["document_pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.get_document()
        context["page_title"] = f"Place Legal Hold on {document.filename}"
        context["document"] = document
        return context

    def form_valid(self, form):
        document = self.get_document()

        hold = DocumentLegalHold.objects.create(
            document=document,
            reason=form.cleaned_data["reason"],
            reference=form.cleaned_data.get("reference", ""),
            notes=form.cleaned_data.get("notes", ""),
            placed_by=self.request.user,
        )

        messages.success(self.request, f"Legal hold placed on '{document.filename}'.")
        return redirect("diveops:document-detail", pk=document.pk)


class LegalHoldReleaseView(StaffPortalMixin, FormView):
    """Release a legal hold."""

    template_name = "diveops/staff/legal_hold_release.html"
    form_class = DocumentLegalHoldReleaseForm

    def get_hold(self):
        return get_object_or_404(
            DocumentLegalHold,
            pk=self.kwargs["pk"],
            deleted_at__isnull=True,
            released_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hold = self.get_hold()
        context["page_title"] = f"Release Legal Hold"
        context["hold"] = hold
        return context

    def form_valid(self, form):
        hold = self.get_hold()

        hold.released_at = timezone.now()
        hold.released_by = self.request.user
        hold.release_reason = form.cleaned_data["release_reason"]
        hold.save(update_fields=["released_at", "released_by", "release_reason", "updated_at"])

        messages.success(self.request, f"Legal hold released on '{hold.document.filename}'.")
        return redirect("diveops:legal-hold-list")


class LegalHoldDetailView(StaffPortalMixin, DetailView):
    """View details of a legal hold."""

    model = DocumentLegalHold
    template_name = "diveops/staff/legal_hold_detail.html"
    context_object_name = "hold"

    def get_queryset(self):
        return DocumentLegalHold.objects.filter(deleted_at__isnull=True).select_related(
            "document", "placed_by", "released_by"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Legal Hold: {self.object.reason[:50]}"
        return context


# =============================================================================
# Backup / Export Views
# =============================================================================


class DocumentBackupView(StaffPortalMixin, TemplateView):
    """View to select folders/documents for backup and download."""

    template_name = "diveops/staff/document_backup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Backup Documents"

        # Build folder tree for selection
        context["folders"] = self._build_folder_tree()

        # Get backup stats
        from .document_backup import get_backup_stats
        context["stats"] = get_backup_stats()

        return context

    def _build_folder_tree(self):
        """Build a nested folder structure for display."""
        root_folders = DocumentFolder.objects.filter(
            parent__isnull=True, deleted_at__isnull=True
        ).order_by("name")

        def build_tree(folder):
            return {
                "id": str(folder.pk),
                "name": folder.name,
                "slug": folder.slug,
                "document_count": folder.documents.filter(deleted_at__isnull=True).count(),
                "children": [build_tree(child) for child in folder.children.filter(deleted_at__isnull=True).order_by("name")],
            }

        return [build_tree(f) for f in root_folders]


class DocumentBackupDownloadView(StaffPortalMixin, View):
    """Generate and download a backup ZIP file."""

    def post(self, request):
        from .document_backup import backup_documents
        import json

        # Get selection from form
        folder_ids = request.POST.getlist("folders")
        document_ids = request.POST.getlist("documents")
        include_trash = request.POST.get("include_trash") == "on"
        backup_all = request.POST.get("backup_all") == "on"

        # If backup_all is selected, clear specific selections
        if backup_all:
            folder_ids = None
            document_ids = None

        try:
            # Generate the backup
            zip_path = backup_documents(
                folder_ids=folder_ids if folder_ids else None,
                document_ids=document_ids if document_ids else None,
                include_trash=include_trash,
            )

            # Serve the file
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"document_backup_{timestamp}.zip"

            response = FileResponse(
                open(zip_path, "rb"),
                as_attachment=True,
                filename=filename,
            )
            response["Content-Type"] = "application/zip"

            # Schedule temp file cleanup (file will be deleted when response is closed)
            import os
            import atexit
            atexit.register(lambda: os.unlink(zip_path) if os.path.exists(zip_path) else None)

            return response

        except Exception as e:
            messages.error(request, f"Backup failed: {str(e)}")
            return redirect("diveops:document-backup")


class DocumentS3SyncView(StaffPortalMixin, View):
    """Trigger S3 sync for documents."""

    def post(self, request):
        from .document_backup import sync_to_s3
        import json

        bucket = request.POST.get("s3_bucket")
        prefix = request.POST.get("s3_prefix", "document-backup/")
        folder_ids = request.POST.getlist("folders")
        document_ids = request.POST.getlist("documents")
        include_trash = request.POST.get("include_trash") == "on"
        delete_removed = request.POST.get("s3_delete") == "on"
        sync_all = request.POST.get("sync_all") == "on"

        if not bucket:
            messages.error(request, "S3 bucket name is required.")
            return redirect("diveops:document-backup")

        # If sync_all is selected, clear specific selections
        if sync_all:
            folder_ids = None
            document_ids = None

        try:
            stats = sync_to_s3(
                bucket=bucket,
                prefix=prefix,
                folder_ids=folder_ids if folder_ids else None,
                document_ids=document_ids if document_ids else None,
                include_trash=include_trash,
                delete_removed=delete_removed,
            )

            msg = f"S3 sync complete: {stats['uploaded']} uploaded, {stats['skipped']} unchanged"
            if delete_removed:
                msg += f", {stats['deleted']} deleted"
            if stats["errors"]:
                msg += f", {stats['errors']} errors"

            messages.success(request, msg)

        except ImportError:
            messages.error(request, "boto3 is required for S3 sync. Install with: pip install boto3")
        except Exception as e:
            messages.error(request, f"S3 sync failed: {str(e)}")

        return redirect("diveops:document-backup")


# =============================================================================
# Notes and Metadata Views
# =============================================================================


class DocumentAddNoteView(StaffPortalMixin, View):
    """Add a note to a document."""

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        note_text = request.POST.get("note_text", "").strip()
        if not note_text:
            messages.error(request, "Note text is required.")
            return redirect("diveops:document-detail", pk=pk)

        # Add note to document metadata
        metadata = document.metadata or {}
        notes = metadata.get("notes", [])

        import uuid

        notes.append({
            "pk": str(uuid.uuid4()),
            "text": note_text,
            "created_by_id": request.user.id if request.user.is_authenticated else None,
            "created_at": timezone.now().isoformat(),
        })

        metadata["notes"] = notes
        document.metadata = metadata
        document.save(update_fields=["metadata", "updated_at"])

        messages.success(request, "Note added successfully.")
        return redirect("diveops:document-detail", pk=pk)


class DocumentDeleteNoteView(StaffPortalMixin, View):
    """Delete a note from a document."""

    def post(self, request, pk, note_pk):
        document = get_object_or_404(Document, pk=pk)

        # Remove note from document metadata
        metadata = document.metadata or {}
        notes = metadata.get("notes", [])

        # Find and remove the note
        original_count = len(notes)
        notes = [n for n in notes if n.get("pk") != str(note_pk)]

        if len(notes) == original_count:
            messages.error(request, "Note not found.")
            return redirect("diveops:document-detail", pk=pk)

        metadata["notes"] = notes
        document.metadata = metadata
        document.save(update_fields=["metadata", "updated_at"])

        messages.success(request, "Note deleted.")
        return redirect("diveops:document-detail", pk=pk)


class DocumentExtractMetadataView(StaffPortalMixin, View):
    """Extract and store file metadata (EXIF, video/audio info)."""

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        from .document_metadata import extract_document_metadata

        try:
            extracted = extract_document_metadata(document)

            if extracted:
                # Merge with existing metadata
                metadata = document.metadata or {}
                metadata.update(extracted)
                document.metadata = metadata
                document.save(update_fields=["metadata", "updated_at"])

                messages.success(request, "Metadata extracted successfully.")
            else:
                messages.info(request, "No additional metadata found.")

        except Exception as e:
            messages.error(request, f"Metadata extraction failed: {str(e)}")

        return redirect("diveops:document-detail", pk=pk)


class DocumentConvertToPdfView(StaffPortalMixin, View):
    """Convert an office document to PDF for preview."""

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        from .document_metadata import is_office_document

        if not is_office_document(document):
            messages.error(request, "This document cannot be converted to PDF.")
            return redirect("diveops:document-detail", pk=pk)

        try:
            import subprocess
            import tempfile

            # Create temp directory for output
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert using LibreOffice
                result = subprocess.run(
                    [
                        "libreoffice",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", temp_dir,
                        document.file.path,
                    ],
                    capture_output=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    raise Exception(f"Conversion failed: {result.stderr.decode()}")

                # Find the output PDF
                pdf_files = [f for f in os.listdir(temp_dir) if f.endswith(".pdf")]
                if not pdf_files:
                    raise Exception("PDF output not found")

                pdf_path = os.path.join(temp_dir, pdf_files[0])

                # Store the PDF as a preview version
                with open(pdf_path, "rb") as f:
                    pdf_content = f.read()

                # Save PDF preview path in metadata
                preview_filename = f"preview_{document.pk}.pdf"
                preview_path = os.path.join(settings.MEDIA_ROOT, "document_previews", preview_filename)

                os.makedirs(os.path.dirname(preview_path), exist_ok=True)
                with open(preview_path, "wb") as f:
                    f.write(pdf_content)

                # Update metadata
                metadata = document.metadata or {}
                metadata["pdf_preview_version"] = preview_filename
                document.metadata = metadata
                document.save(update_fields=["metadata", "updated_at"])

                messages.success(request, "Document converted to PDF for preview.")

        except FileNotFoundError:
            messages.error(request, "LibreOffice not installed. Cannot convert to PDF.")
        except Exception as e:
            messages.error(request, f"PDF conversion failed: {str(e)}")

        return redirect("diveops:document-detail", pk=pk)


class DocumentPreviewPdfView(StaffPortalMixin, View):
    """Serve the PDF preview of an office document."""

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)

        metadata = document.metadata or {}
        preview_filename = metadata.get("pdf_preview_version")

        if not preview_filename:
            raise Http404("PDF preview not available")

        preview_path = os.path.join(settings.MEDIA_ROOT, "document_previews", preview_filename)

        if not os.path.exists(preview_path):
            raise Http404("PDF preview file not found")

        # Log the preview access
        log_access(
            document=document,
            action=AccessAction.VIEW,
            actor=request.user,
            request=request,
        )

        response = FileResponse(
            open(preview_path, "rb"),
            as_attachment=False,
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'inline; filename="preview_{document.filename}.pdf"'
        return response


# =============================================================================
# Photo Tagging Views
# =============================================================================


class PhotoTagAddView(StaffPortalMixin, View):
    """Add a diver tag to a photo."""

    def post(self, request, pk):
        from .models import PhotoTag, DiverProfile
        from .audit import Actions, log_photo_tag_event

        document = get_object_or_404(Document, pk=pk)

        # Only allow tagging on images
        if document.category != "image":
            messages.error(request, "Only images can have diver tags.")
            return redirect("diveops:document-detail", pk=pk)

        diver_id = request.POST.get("diver_id")
        if not diver_id:
            messages.error(request, "Please select a diver to tag.")
            return redirect("diveops:document-detail", pk=pk)

        diver = get_object_or_404(DiverProfile, pk=diver_id)

        # Check if tag exists (including soft-deleted)
        existing_tag = PhotoTag.all_objects.filter(document=document, diver=diver).first()

        if existing_tag:
            if existing_tag.deleted_at is None:
                # Already actively tagged
                messages.warning(request, f"{diver.person.get_full_name()} is already tagged in this photo.")
                return redirect("diveops:document-detail", pk=pk)
            else:
                # Restore soft-deleted tag
                existing_tag.deleted_at = None
                existing_tag.tagged_by = request.user
                existing_tag.save(update_fields=["deleted_at", "tagged_by", "updated_at"])
                tag = existing_tag
        else:
            # Create new tag
            tag = PhotoTag.objects.create(
                document=document,
                diver=diver,
                tagged_by=request.user,
            )

        # Audit log
        log_photo_tag_event(
            action=Actions.PHOTO_DIVER_TAGGED,
            photo_tag=tag,
            actor=request.user,
            request=request,
        )

        messages.success(request, f"Tagged {diver.person.get_full_name()} in this photo.")
        return redirect("diveops:document-detail", pk=pk)


class PhotoTagRemoveView(StaffPortalMixin, View):
    """Remove a diver tag from a photo."""

    def post(self, request, pk, tag_pk):
        from .models import PhotoTag
        from .audit import Actions, log_photo_tag_event

        document = get_object_or_404(Document, pk=pk)
        tag = get_object_or_404(PhotoTag, pk=tag_pk, document=document)

        diver_name = tag.diver.person.get_full_name()

        # Audit log before deletion
        log_photo_tag_event(
            action=Actions.PHOTO_DIVER_UNTAGGED,
            photo_tag=tag,
            actor=request.user,
            request=request,
        )

        # Soft delete the tag
        tag.delete()

        messages.success(request, f"Removed {diver_name} from this photo.")
        return redirect("diveops:document-detail", pk=pk)


# =============================================================================
# Dive Site Photo Tagging Views
# =============================================================================


class DiveSitePhotoTagAddView(StaffPortalMixin, View):
    """Add a dive site tag to a photo."""

    def post(self, request, pk):
        from .models import DiveSitePhotoTag, DiveSite

        document = get_object_or_404(Document, pk=pk)

        # Only allow tagging on images
        is_image = (
            document.category == "image"
            or (document.content_type and document.content_type.startswith("image/"))
        )
        if not is_image:
            messages.error(request, "Only images can have dive site tags.")
            return redirect("diveops:document-detail", pk=pk)

        dive_site_id = request.POST.get("dive_site_id")
        if not dive_site_id:
            messages.error(request, "Please select a dive site to tag.")
            return redirect("diveops:document-detail", pk=pk)

        dive_site = get_object_or_404(DiveSite, pk=dive_site_id, deleted_at__isnull=True)

        # Check if tag exists (including soft-deleted)
        existing_tag = DiveSitePhotoTag.all_objects.filter(
            document=document, dive_site=dive_site
        ).first()

        if existing_tag:
            if existing_tag.deleted_at is None:
                # Already actively tagged
                messages.warning(request, f"{dive_site.name} is already tagged in this photo.")
                return redirect("diveops:document-detail", pk=pk)
            else:
                # Restore soft-deleted tag
                existing_tag.deleted_at = None
                existing_tag.tagged_by = request.user
                existing_tag.save(update_fields=["deleted_at", "tagged_by", "updated_at"])
        else:
            # Create new tag
            DiveSitePhotoTag.objects.create(
                document=document,
                dive_site=dive_site,
                tagged_by=request.user,
            )

        messages.success(request, f"Tagged {dive_site.name} in this photo.")
        return redirect("diveops:document-detail", pk=pk)


class DiveSitePhotoTagRemoveView(StaffPortalMixin, View):
    """Remove a dive site tag from a photo."""

    def post(self, request, pk, tag_pk):
        from .models import DiveSitePhotoTag

        document = get_object_or_404(Document, pk=pk)
        tag = get_object_or_404(DiveSitePhotoTag, pk=tag_pk, document=document)

        site_name = tag.dive_site.name

        # Soft delete the tag
        tag.delete()

        messages.success(request, f"Removed {site_name} from this photo.")
        return redirect("diveops:document-detail", pk=pk)
