# Architecture: django-singleton

**Status:** Stable / v0.1.0

Singleton pattern for Django settings/configuration models.

---

## What This Package Is For

Answering the question: **"Where do I store application settings that aren't in environment variables?"**

Use cases:
- Application-wide settings (site name, contact email)
- Runtime configuration (feature toggles, thresholds)
- Admin-editable settings
- Settings that need to be stored in database

---

## What This Package Is NOT For

- **Not environment config** - Use env vars for secrets, deployment config
- **Not per-user settings** - Use User profile model for that
- **Not per-org settings** - Use django-modules for org-specific config
- **Not feature flags** - Use django-modules for feature toggles

---

## Design Principles

1. **Single row enforcement** - Always pk=1, enforced on save
2. **No deletion** - Raises error on delete attempt
3. **Thread-safe creation** - Handles race conditions on get_instance()
4. **Corruption detection** - Raises error if multiple rows exist
5. **Simple API** - Just get_instance() for access

---

## Data Model

```
SingletonModel (Abstract)
├── pk = 1 (always)
└── Your custom fields...

MySettings (Example)
├── pk = 1
├── site_name
├── contact_email
├── maintenance_mode
└── ...

Invariants:
  - Only one row ever exists (pk=1)
  - Cannot delete the row
  - Cannot create pk != 1
```

---

## Public API

### Defining a Singleton

```python
from django_singleton.models import SingletonModel
from django.db import models

class SiteSettings(SingletonModel):
    """Site-wide configuration."""

    site_name = models.CharField(max_length=100, default='My Site')
    contact_email = models.EmailField(default='admin@example.com')
    maintenance_mode = models.BooleanField(default=False)
    max_upload_mb = models.IntegerField(default=10)

    class Meta:
        verbose_name = 'Site Settings'
```

### Accessing the Singleton

```python
from myapp.models import SiteSettings

# Get (or create) the singleton
settings = SiteSettings.get_instance()

# Use the settings
print(settings.site_name)
if settings.maintenance_mode:
    return HttpResponse("Site under maintenance")

# Update settings
settings.max_upload_mb = 50
settings.save()
```

### In Views and Templates

```python
# views.py
def home(request):
    settings = SiteSettings.get_instance()
    return render(request, 'home.html', {
        'site_name': settings.site_name,
    })

# template
<title>{{ site_name }}</title>
```

---

## Hard Rules

1. **pk is always 1** - Enforced in save(), cannot override
2. **No deletion** - Raises `SingletonDeletionError` on delete()
3. **No multiple rows** - Raises `SingletonViolationError` if extras exist
4. **get_instance() is safe** - Handles race conditions

---

## Invariants

- SingletonModel descendants always have pk=1
- Only one row exists in the table
- delete() always raises SingletonDeletionError
- save() enforces pk=1 regardless of what you set
- get_instance() never returns None (creates if missing)

---

## Known Gotchas

### 1. Cannot Delete

**Problem:** Trying to delete singleton.

```python
settings = SiteSettings.get_instance()
settings.delete()
# Raises: SingletonDeletionError("Cannot delete singleton SiteSettings")
```

**Solution:** Clear fields instead of deleting:

```python
settings.reset_to_defaults()  # If you implement this method
# Or manually:
settings.field1 = 'default1'
settings.save()
```

### 2. Multiple Rows Corruption

**Problem:** Fixtures or raw SQL created extra rows.

```python
# If someone ran: INSERT INTO myapp_sitesettings (id, ...) VALUES (2, ...)

settings = SiteSettings.get_instance()
settings.save()
# Raises: SingletonViolationError("Multiple rows exist...")
```

**Solution:** Delete extra rows:

```python
SiteSettings.objects.exclude(pk=1).delete()
```

### 3. Race Condition Handling

**Problem:** Two requests creating simultaneously.

```python
# Request 1: get_instance() → get_or_create → creating...
# Request 2: get_instance() → get_or_create → IntegrityError!

# This is handled automatically:
# Request 2 catches IntegrityError and retries with objects.get()
```

### 4. Not Using get_instance()

**Problem:** Direct model access bypasses safety.

```python
# WRONG - might create duplicate or miss existing
settings = SiteSettings()
settings.save()

# CORRECT - always use get_instance()
settings = SiteSettings.get_instance()
```

### 5. No Caching by Default

**Problem:** Every access hits database.

```python
# Each call hits the database
settings1 = SiteSettings.get_instance()
settings2 = SiteSettings.get_instance()
# Two queries!
```

**Solution:** Cache in view or use select_related:

```python
# Cache per request
class SettingsMiddleware:
    def __call__(self, request):
        request.site_settings = SiteSettings.get_instance()
        return self.get_response(request)
```

---

## Recommended Usage

### 1. Use for Admin-Editable Settings

```python
# admin.py
from django.contrib import admin
from myapp.models import SiteSettings

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Only allow if none exists
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False  # Never allow delete
```

### 2. Add Defaults

```python
class SiteSettings(SingletonModel):
    site_name = models.CharField(max_length=100, default='My Site')
    contact_email = models.EmailField(default='admin@example.com')

    def reset_to_defaults(self):
        """Reset all fields to defaults."""
        self.site_name = 'My Site'
        self.contact_email = 'admin@example.com'
        self.save()
```

### 3. Use Context Processor

```python
# context_processors.py
def site_settings(request):
    from myapp.models import SiteSettings
    return {'site_settings': SiteSettings.get_instance()}

# settings.py
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            'myapp.context_processors.site_settings',
        ],
    },
}]

# Any template
{{ site_settings.site_name }}
```

### 4. Create via Migration

```python
def create_initial_settings(apps, schema_editor):
    SiteSettings = apps.get_model('myapp', 'SiteSettings')
    SiteSettings.objects.get_or_create(pk=1, defaults={
        'site_name': 'My Application',
        'contact_email': 'support@example.com',
    })

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(create_initial_settings),
    ]
```

---

## Dependencies

None. This is a standalone Django model mixin.

---

## Changelog

### v0.1.0 (2024-12-30)
- Initial release
- SingletonModel abstract base class
- get_instance() with race condition handling
- SingletonDeletionError on delete attempts
- SingletonViolationError on multiple row detection
