"""Template tags for diveops app."""

from django import template

register = template.Library()

# Map size names to MediaRendition roles
SIZE_TO_ROLE = {
    "thumb": "thumb",
    "small": "small",
    "medium": "medium",
    "large": "large",
    "xlarge": "xlarge",
}


@register.simple_tag
def thumbnail_url(document, size="medium"):
    """Get the thumbnail URL for a document.

    Uses MediaRendition from django-documents if available,
    falls back to original file URL.

    Usage:
        {% load diveops_tags %}
        {% thumbnail_url doc "small" as thumb_url %}
        {% if thumb_url %}
            <img src="{{ thumb_url }}" alt="">
        {% endif %}

    Or directly:
        <img src="{% thumbnail_url doc 'medium' %}" alt="">
    """
    if not document:
        return ""

    # Try to get rendition from MediaAsset
    role = SIZE_TO_ROLE.get(size, "medium")

    try:
        # Check if document has a MediaAsset with renditions
        if hasattr(document, "media_asset"):
            asset = document.media_asset
            rendition = asset.renditions.filter(role=role).first()
            if rendition and rendition.file:
                return rendition.file.url
    except Exception:
        pass

    # Fallback: return original file URL if it's small enough
    # or if no rendition exists
    if document.file:
        return document.file.url

    return ""


@register.filter
def has_thumbnail(document):
    """Check if a document can have a thumbnail.

    Usage:
        {% if doc|has_thumbnail %}
            <img src="{% thumbnail_url doc 'small' %}">
        {% endif %}
    """
    if not document:
        return False
    if not hasattr(document, "category"):
        return False
    return document.category == "image" and document.file
