# django-cms-core

Domain-agnostic CMS primitives for Django with publishing workflow, block-based content, and access control.

## Installation

```bash
pip install django-cms-core
```

Add to INSTALLED_APPS:

```python
INSTALLED_APPS = [
    ...
    "django_basemodels",
    "django_singleton",
    "django_cms_core",
]
```

Run migrations:

```bash
python manage.py migrate django_cms_core
```

## Quick Start

```python
from django_cms_core.services import (
    create_page,
    add_block,
    publish_page,
    check_page_access,
)
from django_cms_core.models import AccessLevel

# Create a page
page = create_page(
    slug="about-us",
    title="About Us",
    user=request.user,
    seo_description="Learn about our company",
)

# Add content blocks
add_block(page, "hero", {
    "title": "Welcome",
    "subtitle": "Learn about our story",
    "background_url": "/images/hero.jpg",
})

add_block(page, "rich_text", {
    "content": "<p>Our company was founded in 2020...</p>",
})

# Publish the page
publish_page(page, request.user)

# Check access
allowed, reason = check_page_access(page, user=request.user)
if allowed:
    snapshot = page.published_snapshot
```

## Models

| Model | Purpose |
|-------|---------|
| `ContentPage` | Page with title, slug, SEO, access control, and published snapshot |
| `ContentBlock` | Block of content belonging to a page |
| `CMSSettings` | Singleton configuration for hooks and defaults |
| `Redirect` | URL redirect mapping |

### ContentPage Fields

| Field | Description |
|-------|-------------|
| `slug` | URL-safe identifier (unique among non-deleted) |
| `title` | Display title |
| `status` | draft, published, or archived |
| `access_level` | public, authenticated, role, or entitlement |
| `required_roles` | JSON list of role slugs for role-based access |
| `required_entitlements` | JSON list for entitlement-based access |
| `seo_title` | Custom SEO title |
| `seo_description` | Meta description |
| `og_image_url` | Open Graph image URL |
| `published_snapshot` | Immutable JSON snapshot created at publish time |
| `published_at` | When the page was last published |
| `published_by` | User who published the page |

### ContentBlock Fields

| Field | Description |
|-------|-------------|
| `page` | Foreign key to ContentPage |
| `block_type` | Registry key (e.g., "rich_text", "hero") |
| `data` | JSON content data |
| `sequence` | Display order within the page |
| `is_active` | Whether block is included in published output |

## Block Registry

Blocks are registered via the `BlockRegistry` class or `@block` decorator.

### Built-in Blocks

| Block | Description | Category |
|-------|-------------|----------|
| `rich_text` | HTML content | content |
| `heading` | H1-H6 with text | content |
| `image` | Single image with caption | media |
| `image_gallery` | Multiple images | media |
| `hero` | Hero banner with CTA | layout |
| `cta` | Call to action button | content |
| `embed` | YouTube/Vimeo embed | media |
| `divider` | Visual separator | layout |

### Registering Custom Blocks

```python
from django_cms_core.registry import BlockRegistry, BlockPlugin, block

# Via class
BlockRegistry.register(BlockPlugin(
    name="testimonial",
    label="Testimonial",
    category="content",
    icon="bi-chat-quote",
    schema={
        "type": "object",
        "properties": {
            "quote": {"type": "string"},
            "author": {"type": "string"},
        },
        "required": ["quote"],
    },
    renderer=lambda data: f"<blockquote>{data['quote']}</blockquote>",
))

# Via decorator
@block(name="feature_card", label="Feature Card", category="layout")
def render_feature_card(data):
    return f"<div class='feature'><h3>{data['title']}</h3></div>"
```

### Block Validation

```python
from django_cms_core.registry import BlockRegistry

errors = BlockRegistry.validate_block("testimonial", {"author": "Jane"})
# Returns: ["'quote' is a required property"] if jsonschema installed
```

## Services

### Page Management

```python
from django_cms_core.services import (
    create_page,
    publish_page,
    unpublish_page,
    archive_page,
)

# Create a page (status defaults to draft)
page = create_page(
    slug="my-page",
    title="My Page",
    user=user,
    access_level=AccessLevel.PUBLIC,
    seo_title="My Page | Site Name",
    seo_description="Description for search engines",
)

# Publish (creates immutable snapshot)
page = publish_page(page, user)

# Unpublish (clears snapshot, returns to draft)
page = unpublish_page(page)

# Archive
page = archive_page(page)
```

### Block Management

```python
from django_cms_core.services import (
    add_block,
    update_block,
    reorder_blocks,
    delete_block,
)

# Add blocks (sequence auto-assigned if not provided)
block1 = add_block(page, "heading", {"text": "Welcome", "level": 1})
block2 = add_block(page, "rich_text", {"content": "<p>Hello</p>"})

# Update a block
update_block(block1, data={"text": "New Title", "level": 1})

# Reorder blocks by ID
reorder_blocks(page, [str(block2.id), str(block1.id)])

# Soft-delete a block
delete_block(block1)
```

### Access Control

```python
from django_cms_core.services import check_page_access
from django_cms_core.models import AccessLevel

# Public pages - anyone can access
page.access_level = AccessLevel.PUBLIC
allowed, reason = check_page_access(page, user=None)  # True, ""

# Authenticated - must be logged in
page.access_level = AccessLevel.AUTHENTICATED
allowed, reason = check_page_access(page, user=None)  # False, "Authentication required"

# Role-based - must have required role
page.access_level = AccessLevel.ROLE
page.required_roles = ["staff"]
allowed, reason = check_page_access(page, user=staff_user)  # True if user.is_staff

# Entitlement-based - uses configured hook
page.access_level = AccessLevel.ENTITLEMENT
page.required_entitlements = ["premium_access"]
# Requires entitlement_checker_path configured in CMSSettings
```

### API Helpers

```python
from django_cms_core.services import get_published_page, list_published_pages

# Get single published page by slug
snapshot = get_published_page("about-us")

# List all published pages
pages = list_published_pages()
```

## Access Control Configuration

### Role-Based Access

Built-in role mapping:
- `"staff"` maps to `user.is_staff`
- Superusers bypass all role checks

### Entitlement-Based Access

Configure an entitlement checker hook in CMSSettings:

```python
from django_cms_core.models import CMSSettings

settings = CMSSettings.get_instance()
settings.entitlement_checker_path = "myapp.auth.check_entitlement"
settings.save()
```

Create the checker function:

```python
# myapp/auth.py
def check_entitlement(user, entitlements, page):
    """Return True if user has any of the required entitlements."""
    user_entitlements = get_user_entitlements(user)  # Your logic
    return bool(set(entitlements) & set(user_entitlements))
```

**Fail-secure behavior:**
- No hook configured: access denied
- Hook raises exception: access denied (logged)
- Superusers bypass entitlement checks

## Published Snapshot

When a page is published, an immutable JSON snapshot is created:

```json
{
  "version": 1,
  "published_at": "2025-01-08T10:00:00Z",
  "published_by_id": "uuid",
  "meta": {
    "title": "About Us",
    "slug": "about-us",
    "path": "/about-us/",
    "seo_title": "About Us | Company",
    "seo_description": "Learn about our company",
    "og_image_url": "/media/images/about.jpg",
    "robots": "index, follow"
  },
  "access_control": {
    "level": "public",
    "required_roles": [],
    "required_entitlements": []
  },
  "blocks": [
    {"id": "uuid", "type": "hero", "sequence": 0, "data": {...}},
    {"id": "uuid", "type": "rich_text", "sequence": 1, "data": {...}}
  ],
  "checksum": "sha256..."
}
```

The snapshot is frozen at publish time. Editing the page or blocks does not affect the published snapshot until you publish again.

## CMSSettings

Singleton configuration model:

```python
from django_cms_core.models import CMSSettings

settings = CMSSettings.get_instance()

# Configure hooks
settings.media_url_resolver_path = "myapp.media.resolve_url"
settings.entitlement_checker_path = "myapp.auth.check_entitlement"

# Default SEO
settings.default_seo_title_suffix = " | My Site"
settings.default_og_image_url = "/images/default-og.jpg"

# Navigation data
settings.nav_json = [
    {"label": "Home", "url": "/"},
    {"label": "About", "url": "/about/"},
]

# API caching
settings.api_cache_ttl_seconds = 300

settings.save()
```

## Redirects

```python
from django_cms_core.models import Redirect

# Create a redirect
Redirect.objects.create(
    from_path="/old-page/",
    to_path="/new-page/",
    is_permanent=True,  # 301 vs 302
)
```

## Django Admin

The package includes Django admin configuration with:
- ContentPage admin with inline blocks
- Collapsible fieldsets for SEO, access control, publishing
- Soft-delete aware querysets
- CMSSettings singleton admin (prevents multiple instances)

## Dependencies

- Django >= 4.2
- django-basemodels (UUID, timestamps, soft delete)
- django-singleton (CMSSettings singleton)
- jsonschema (optional, for block validation)

## License

MIT
