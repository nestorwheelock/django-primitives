"""Built-in block types for django-cms-core.

Provides standard content blocks that can be used out of the box.
Import this module to register the built-in blocks.
"""

from .registry import block


@block(
    name="rich_text",
    label="Rich Text",
    category="content",
    icon="bi-text-paragraph",
    schema={
        "type": "object",
        "properties": {
            "content": {"type": "string"},
        },
    },
)
def render_rich_text(data: dict) -> str:
    """Render rich text content (HTML passthrough)."""
    return data.get("content", "")


@block(
    name="heading",
    label="Heading",
    category="content",
    icon="bi-type-h1",
    schema={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "level": {"type": "integer", "minimum": 1, "maximum": 6},
        },
        "required": ["text"],
    },
)
def render_heading(data: dict) -> str:
    """Render a heading (H1-H6)."""
    level = data.get("level", 2)
    text = data.get("text", "")
    return f"<h{level}>{text}</h{level}>"


@block(
    name="image",
    label="Image",
    category="media",
    icon="bi-image",
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "alt": {"type": "string"},
            "caption": {"type": "string"},
        },
        "required": ["url"],
    },
)
def render_image(data: dict) -> str:
    """Render a single image with optional caption."""
    url = data.get("url", "")
    alt = data.get("alt", "")
    caption = data.get("caption", "")

    img = f'<img src="{url}" alt="{alt}">'
    if caption:
        return f"<figure>{img}<figcaption>{caption}</figcaption></figure>"
    return img


@block(
    name="image_gallery",
    label="Image Gallery",
    category="media",
    icon="bi-images",
    schema={
        "type": "object",
        "properties": {
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "alt": {"type": "string"},
                        "caption": {"type": "string"},
                    },
                    "required": ["url"],
                },
            },
            "columns": {"type": "integer", "minimum": 1, "maximum": 6},
        },
    },
)
def render_image_gallery(data: dict) -> str:
    """Render a gallery of images."""
    images = data.get("images", [])
    columns = data.get("columns", 3)

    items = []
    for img in images:
        url = img.get("url", "")
        alt = img.get("alt", "")
        items.append(f'<img src="{url}" alt="{alt}">')

    return f'<div class="gallery columns-{columns}">{"".join(items)}</div>'


@block(
    name="hero",
    label="Hero Banner",
    category="layout",
    icon="bi-card-image",
    schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "background_url": {"type": "string"},
            "cta_text": {"type": "string"},
            "cta_url": {"type": "string"},
        },
    },
)
def render_hero(data: dict) -> str:
    """Render a hero banner section."""
    title = data.get("title", "")
    subtitle = data.get("subtitle", "")
    bg_url = data.get("background_url", "")
    cta_text = data.get("cta_text", "")
    cta_url = data.get("cta_url", "")

    style = f'background-image: url({bg_url});' if bg_url else ""
    cta = f'<a href="{cta_url}" class="cta-button">{cta_text}</a>' if cta_text else ""

    return f'''
<section class="hero" style="{style}">
    <h1>{title}</h1>
    {f'<p>{subtitle}</p>' if subtitle else ''}
    {cta}
</section>
'''.strip()


@block(
    name="cta",
    label="Call to Action",
    category="content",
    icon="bi-arrow-right-circle",
    schema={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "url": {"type": "string"},
            "style": {"type": "string", "enum": ["primary", "secondary", "outline"]},
        },
        "required": ["text", "url"],
    },
)
def render_cta(data: dict) -> str:
    """Render a call-to-action button."""
    text = data.get("text", "")
    url = data.get("url", "#")
    style = data.get("style", "primary")

    return f'<a href="{url}" class="cta cta-{style}">{text}</a>'


@block(
    name="embed",
    label="Embed",
    category="media",
    icon="bi-youtube",
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "provider": {"type": "string", "enum": ["youtube", "vimeo", "other"]},
            "aspect_ratio": {"type": "string"},
        },
        "required": ["url"],
    },
)
def render_embed(data: dict) -> str:
    """Render an embed (YouTube, Vimeo, etc.)."""
    url = data.get("url", "")
    aspect_ratio = data.get("aspect_ratio", "16-9")

    return f'''
<div class="embed-container aspect-{aspect_ratio}">
    <iframe src="{url}" frameborder="0" allowfullscreen></iframe>
</div>
'''.strip()


@block(
    name="divider",
    label="Divider",
    category="layout",
    icon="bi-dash-lg",
    schema={
        "type": "object",
        "properties": {
            "style": {"type": "string", "enum": ["solid", "dashed", "dotted", "none"]},
            "spacing": {"type": "string", "enum": ["small", "medium", "large"]},
        },
    },
)
def render_divider(data: dict) -> str:
    """Render a visual divider/separator."""
    style = data.get("style", "solid")
    spacing = data.get("spacing", "medium")

    return f'<hr class="divider divider-{style} spacing-{spacing}">'
