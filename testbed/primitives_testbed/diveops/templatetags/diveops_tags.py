"""Template tags for diveops app."""

from django import template

from ..thumbnails import get_thumbnail_url

register = template.Library()


@register.simple_tag
def thumbnail_url(document, size="medium"):
    """Get the thumbnail URL for a document.

    Usage:
        {% load diveops_tags %}
        {% thumbnail_url doc "small" as thumb_url %}
        {% if thumb_url %}
            <img src="{{ thumb_url }}" alt="">
        {% endif %}

    Or directly:
        <img src="{% thumbnail_url doc 'medium' %}" alt="">
    """
    return get_thumbnail_url(document, size) or ""


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
