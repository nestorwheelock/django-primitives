"""Custom template filters for diveops app."""

import re
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()


@register.filter
def simple_markdown(text):
    """
    Convert simple markdown-style formatting to HTML.

    Supports:
    - **text** -> <strong>text</strong>
    """
    if not text:
        return ""

    # Escape HTML first for safety
    text = escape(str(text))

    # Convert **text** to <strong>text</strong>
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)

    # Preserve newlines
    text = text.replace('\n', '<br>\n')

    return mark_safe(text)


@register.filter
def render_content(text):
    """
    Render content that may be HTML or Markdown.

    If the content contains HTML tags (like <p>, <h2>, <div>), it's returned as-is.
    Otherwise, it's converted from Markdown to HTML.

    This allows supporting both HTML output from AI and legacy markdown content.
    """
    if not text:
        return ""

    text = str(text).strip()

    # Check if content already contains HTML block tags
    html_pattern = r'<(p|div|h[1-6]|ol|ul|li|strong|em|table|tr|td|th|br|hr)\b[^>]*>'
    if re.search(html_pattern, text, re.IGNORECASE):
        # Content is already HTML, return as-is (marked safe)
        return mark_safe(text)

    # Content is markdown, convert to HTML
    try:
        import markdown
        html = markdown.markdown(
            text,
            extensions=['tables', 'nl2br', 'sane_lists'],
            output_format='html5'
        )
        return mark_safe(html)
    except ImportError:
        # Fallback: basic markdown conversion if markdown library not installed
        # Escape for safety first
        text = escape(text)

        # Headers: ## Header -> <h2>Header</h2>
        text = re.sub(r'^### (.+)$', r'<h3 class="font-semibold mt-4 mb-2">\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2 class="font-bold text-lg mt-6 mb-2">\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1 class="font-bold text-xl mt-6 mb-3">\1</h1>', text, flags=re.MULTILINE)

        # Bold: **text** -> <strong>text</strong>
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)

        # Italic: *text* -> <em>text</em>
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)

        # Numbered lists: 1. item -> <li>item</li>
        # Simple conversion - wrap consecutive numbered items in <ol>
        lines = text.split('\n')
        result = []
        in_list = False
        for line in lines:
            numbered = re.match(r'^\d+\.\s+(.+)$', line)
            if numbered:
                if not in_list:
                    result.append('<ol class="list-decimal ml-6 space-y-1">')
                    in_list = True
                result.append(f'<li>{numbered.group(1)}</li>')
            else:
                if in_list:
                    result.append('</ol>')
                    in_list = False
                result.append(line)
        if in_list:
            result.append('</ol>')
        text = '\n'.join(result)

        # Paragraphs: double newlines become paragraph breaks
        text = re.sub(r'\n\n+', '</p><p class="mb-4">', text)
        text = f'<p class="mb-4">{text}</p>'

        # Clean up empty paragraphs
        text = re.sub(r'<p class="mb-4"></p>', '', text)

        # Single newlines to <br> (except around block elements)
        text = re.sub(r'(?<!</p>)\n(?!<)', '<br>\n', text)

        return mark_safe(text)


@register.filter
def youtube_embed_url(url):
    """
    Convert a YouTube URL to an embed URL.

    Handles various YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtu.be/VIDEO_ID?si=TRACKING_PARAM
    - https://www.youtube.com/watch?v=VIDEO_ID&other_params

    Returns the embed URL: https://www.youtube.com/embed/VIDEO_ID
    """
    if not url:
        return ""

    url = str(url).strip()

    # Pattern for youtu.be short links (with or without parameters)
    short_pattern = r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)"

    # Pattern for youtube.com/watch?v= links
    watch_pattern = r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"

    # Pattern for already-embedded URLs
    embed_pattern = r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)"

    # Try short URL first (youtu.be)
    match = re.search(short_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"

    # Try watch URL
    match = re.search(watch_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"

    # Already an embed URL
    match = re.search(embed_pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"

    # Return as-is if we can't parse it
    return url


@register.filter
def get_item(collection, key):
    """
    Get an item from a dictionary or list using a variable key/index.

    Usage in template:
        {{ my_dict|get_item:key_variable }}
        {{ my_list|get_item:index }}

    Handles both string and integer keys for dicts, and integer indices for lists.
    """
    if collection is None:
        return None
    try:
        # Try dictionary-style access first
        return collection.get(key)
    except (AttributeError, TypeError):
        pass
    try:
        # Try list-style index access
        return collection[int(key)]
    except (IndexError, ValueError, TypeError, KeyError):
        return None


@register.filter
def in_list(value, lst):
    """
    Check if a value is in a list.

    Usage in template:
        {% if choice|in_list:my_list %}checked{% endif %}

    Returns True if value is in the list, False otherwise.
    """
    if lst is None:
        return False
    try:
        return value in lst
    except TypeError:
        return False


@register.simple_tag
def pref_checked(existing_prefs, key, choice):
    """
    Check if a choice is selected in existing preferences.

    Usage: {% pref_checked existing_prefs defn.key choice as is_checked %}
    """
    if not existing_prefs:
        return False
    values = existing_prefs.get(key)
    if values is None:
        return False
    if isinstance(values, list):
        return choice in values
    return values == choice


@register.filter
def pref_field_name(key):
    """
    Convert a preference definition key to a form field name.

    Replaces dots with underscores to create valid HTML field names.
    Usage: name="pref_{{ defn.key|pref_field_name }}"
    """
    if not key:
        return ""
    return str(key).replace(".", "_")


@register.filter
def class_name(obj):
    """
    Return the class name of an object.

    Usage: {{ object|class_name }}
    Returns: "MyModel" for a MyModel instance
    """
    if obj is None:
        return ""
    return obj.__class__.__name__
