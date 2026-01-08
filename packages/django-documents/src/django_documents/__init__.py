"""Django documents - Document attachment and storage primitives."""

__version__ = "0.1.0"

__all__ = [
    "Document",
    "DocumentVersion",
    "DocumentFolder",
    "FolderPermission",
    "DocumentAccessLog",
    "DocumentContent",
    "ExtractionStatus",
    "PermissionLevel",
    "AccessAction",
    # Media models
    "MediaAsset",
    "MediaRendition",
    "Attachment",
    "MediaKind",
    "MediaProcessingStatus",
    "RenditionRole",
    "AttachmentPurpose",
]


def __getattr__(name):
    """Lazy imports to prevent AppRegistryNotReady errors."""
    if name in (
        "Document",
        "DocumentVersion",
        "DocumentFolder",
        "FolderPermission",
        "DocumentAccessLog",
        "DocumentContent",
        "ExtractionStatus",
        "PermissionLevel",
        "AccessAction",
        "MediaAsset",
        "MediaRendition",
        "Attachment",
        "MediaKind",
        "MediaProcessingStatus",
        "RenditionRole",
        "AttachmentPurpose",
    ):
        from .models import (
            Document,
            DocumentVersion,
            DocumentFolder,
            FolderPermission,
            DocumentAccessLog,
            DocumentContent,
            ExtractionStatus,
            PermissionLevel,
            AccessAction,
            MediaAsset,
            MediaRendition,
            Attachment,
            MediaKind,
            MediaProcessingStatus,
            RenditionRole,
            AttachmentPurpose,
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
