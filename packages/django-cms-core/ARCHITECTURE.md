# Architecture: django-cms-core

**Status:** Alpha / v0.1.0

Domain-agnostic CMS primitives for Django with publishing workflow, block-based content, and access control.

---

## What This Package Is For

Answering the question: **"How do I manage content pages with publishing workflow and access control?"**

Use cases:
- Marketing pages with draft/publish workflow
- Documentation sites with role-based access
- Gated content requiring entitlements
- Block-based page builders
- Multi-tenant content management

---

## What This Package Is NOT For

- **Not a form builder** - Use Django forms or frontend builders
- **Not a page tree/hierarchy** - Flat pages only (v1.0)
- **Not a media manager** - Use django-documents for assets
- **Not a WYSIWYG editor** - Use frontend libraries for editing
- **Not a template engine** - Use Django templates for rendering

---

## Design Principles

1. **Domain-agnostic** - Works for any content type, not tied to specific use case
2. **Immutable snapshots** - Published content is frozen at publish time
3. **Block-based** - Content is composed of typed blocks
4. **Pluggable registry** - Custom blocks can be registered by apps
5. **Fail-secure access** - Unknown access levels or missing hooks deny access
6. **Soft-delete everywhere** - All records use soft delete for audit trail

---

## Data Model

```
ContentPage (BaseModel)
├── id (UUID, PK)
├── slug (unique among non-deleted)
├── title
├── status (draft | published | archived)
├── access_level (public | authenticated | role | entitlement)
├── required_roles (JSON list)
├── required_entitlements (JSON list)
├── seo_* fields
├── published_snapshot (immutable JSON)
├── published_at, published_by
├── template_key, metadata
└── BaseModel fields (created_at, updated_at, deleted_at)

ContentBlock (BaseModel)
├── id (UUID, PK)
├── page (FK to ContentPage)
├── block_type (registry key)
├── data (JSON)
├── sequence
├── is_active
└── BaseModel fields

CMSSettings (SingletonModel)
├── site_name
├── hook paths (media_url_resolver, entitlement_checker)
├── default SEO settings
├── nav_json, footer_json
├── api_cache_ttl_seconds
└── metadata

Redirect (BaseModel)
├── from_path (unique among non-deleted)
├── to_path
├── is_permanent (301 vs 302)
└── BaseModel fields
```

---

## Block Registry

Blocks are registered via the `BlockRegistry` class or `@block` decorator:

```python
from django_cms_core.registry import BlockRegistry, BlockPlugin, block

# Via class
BlockRegistry.register(BlockPlugin(
    name="custom_block",
    label="Custom Block",
    schema={"type": "object", ...},
    renderer=my_render_function,
))

# Via decorator
@block(name="quote", label="Quote")
def render_quote(data):
    return f"<blockquote>{data.get('text')}</blockquote>"
```

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

---

## Published Snapshot Structure

When a page is published, an immutable snapshot is created:

```json
{
  "version": 1,
  "published_at": "2025-01-08T10:00:00Z",
  "published_by_id": "uuid",
  "meta": {
    "title": "About Us",
    "slug": "about-us",
    "path": "/about-us/",
    "seo_title": "...",
    "seo_description": "...",
    "og_image_url": "...",
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

---

## Access Control

Access is checked via `check_page_access(page, user)`:

| Level | Behavior |
|-------|----------|
| `PUBLIC` | Anyone can access |
| `AUTHENTICATED` | Must be logged in |
| `ROLE` | Must have required role (staff, superuser, or custom) |
| `ENTITLEMENT` | Must pass entitlement check via configured hook |

### Entitlement Hook

Configure in `CMSSettings.entitlement_checker_path`:

```python
# myapp/auth.py
def check_entitlement(user, entitlements, page):
    """Return True if user has any of the required entitlements."""
    user_entitlements = get_user_entitlements(user)
    return bool(set(entitlements) & set(user_entitlements))

# settings
CMSSettings.entitlement_checker_path = "myapp.auth.check_entitlement"
```

**Fail-secure behavior:**
- No hook configured → deny access
- Hook raises exception → log error, deny access
- Superusers bypass all access checks

---

## Hard Rules

1. **Published snapshots are immutable** - Never modify after publish
2. **Slug unique among non-deleted** - Partial unique constraint
3. **Superusers bypass all access checks** - Built-in override
4. **Entitlement checks fail-secure** - Missing hook = deny
5. **Soft delete everywhere** - No hard deletes by default

---

## Invariants

- `ContentPage.slug` is unique among non-deleted pages
- `ContentPage.published_snapshot` is only set when status is PUBLISHED
- `ContentBlock.sequence` determines block order within a page
- `CMSSettings` is a singleton (pk=1)
- `Redirect.from_path` is unique among non-deleted redirects

---

## Known Gotchas

### 1. Block Type Not Registered

**Problem:** Creating blocks with unregistered types.

```python
# Import blocks module to register built-in types
from django_cms_core import blocks  # noqa: F401

# Or register custom blocks
from django_cms_core.registry import BlockRegistry, BlockPlugin
BlockRegistry.register(BlockPlugin(name="my_block", label="My Block"))
```

### 2. Access Check Returns Tuple

**Problem:** Forgetting to unpack the tuple.

```python
# WRONG
if check_page_access(page, user):  # Always truthy!

# CORRECT
allowed, reason = check_page_access(page, user)
if allowed:
    ...
```

### 3. Snapshot Not Updated After Page Edit

**Problem:** Expecting live updates to published content.

```python
# After editing page or blocks, must republish
page.title = "New Title"
page.save()
publish_page(page, user)  # Creates new snapshot
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (UUID, timestamps, soft delete)
- django-singleton (CMSSettings singleton)
- jsonschema (optional, for block validation)

---

## Changelog

### v0.1.0 (2025-01-08)
- Initial release
- ContentPage with draft/published/archived workflow
- ContentBlock with registry-based types
- 8 built-in block types
- Access control (public, authenticated, role, entitlement)
- Immutable published snapshots
- CMSSettings singleton
- Redirect model
- Django admin integration
