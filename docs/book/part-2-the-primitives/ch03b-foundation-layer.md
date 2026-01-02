# Chapter 3b: The Foundation Layer

> "Every great building rests on foundations nobody sees."

---

Before you build business primitives, you need the infrastructure that makes them work. The Foundation layer provides four packages that every other primitive depends on: base models, singleton configuration, module organization, and layer boundaries.

These aren't exciting. They don't solve business problems directly. But without them, every primitive would reinvent the same patterns—UUID primary keys, timestamp fields, configuration management, import boundaries—and get them wrong in different ways.

The Foundation layer is where you pay the boring tax once, so you never pay it again.

## The Four Foundation Packages

| Package | Purpose |
|---------|---------|
| django-basemodels | Common model patterns: UUIDs, timestamps, soft delete |
| django-singleton | Configuration that exists exactly once |
| django-modules | Organize related models into discoverable units |
| django-layers | Enforce import boundaries between packages |

Every primitive in this book inherits from these foundations. Understanding them explains why the business primitives look the way they do.

---

## django-basemodels: The Patterns You Always Need

Every business model needs the same things:

- A primary key that doesn't leak information
- Timestamps for when it was created and modified
- Soft delete so nothing truly disappears
- Audit fields for who did what

Writing these patterns into every model is tedious and error-prone. Forgetting one field in one model creates inconsistency that haunts you during audits.

### UUIDModel

The simplest base: a UUID primary key instead of auto-incrementing integers.

```python
import uuid
from django.db import models


class UUIDModel(models.Model):
    """Base model with UUID primary key."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    class Meta:
        abstract = True
```

**Why UUIDs matter:**

1. **No information leakage.** Sequential IDs reveal how many records exist. `/users/1` through `/users/47` tells attackers there are 47 users. `/users/a1b2c3d4-...` reveals nothing.

2. **No collision on merge.** When you merge databases—after an acquisition, after a disaster recovery—sequential IDs collide. UUIDs don't.

3. **Client-side generation.** You can create the ID before the record exists, enabling optimistic UI patterns and offline-first applications.

4. **Distributed systems.** No coordination required. Any node can generate IDs independently.

### TimestampedModel

Add creation and modification timestamps:

```python
class TimestampedModel(UUIDModel):
    """Base model with UUID and timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

These are system timestamps—when the database recorded the event, not when it happened in the real world. Chapter 5 (Time) explains why this distinction matters.

### SoftDeleteModel

Nothing should truly disappear:

```python
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that excludes soft-deleted records by default."""

    def delete(self):
        """Soft delete all records in queryset."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Actually delete records. Use with extreme caution."""
        return super().delete()

    def alive(self):
        """Only non-deleted records."""
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        """Only soft-deleted records."""
        return self.filter(deleted_at__isnull=False)

    def with_deleted(self):
        """All records, including soft-deleted."""
        return self.all()


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted records by default."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteModel(TimestampedModel):
    """Base model with soft delete support."""

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Escape hatch when you need everything

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at', 'updated_at'])

    def hard_delete(self, *args, **kwargs):
        """Actually delete this record. Use with extreme caution."""
        super().delete(*args, **kwargs)

    def restore(self):
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.save(update_fields=['deleted_at', 'updated_at'])

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    class Meta:
        abstract = True
```

**Why soft delete:**

1. **Audit trails need history.** You can't audit what you deleted.

2. **Recovery is possible.** Accidental deletions can be undone.

3. **References don't break.** Foreign keys to deleted records still resolve.

4. **Compliance requires it.** Many regulations require retaining records for years.

### AuditedModel

Track who made changes:

```python
from django.conf import settings


class AuditedModel(SoftDeleteModel):
    """Base model with full audit support."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(class)s_created',
        null=True, blank=True
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(class)s_updated',
        null=True, blank=True
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(class)s_deleted',
        null=True, blank=True
    )

    class Meta:
        abstract = True
```

**The inheritance hierarchy:**

```
UUIDModel
    └── TimestampedModel
            └── SoftDeleteModel
                    └── AuditedModel
```

Pick the level you need. Most business models use `SoftDeleteModel` or `AuditedModel`. Internal system models might use `TimestampedModel`. Truly ephemeral data might use `UUIDModel`.

---

## django-singleton: Configuration That Exists Once

Some things should exist exactly once: site settings, feature flags, rate limits, the current billing plan. These are configurations, not collections.

The naive approach is a regular model with business logic ensuring only one record exists. This fails under concurrent access—two requests can each check "does a record exist?" and both create one.

### The Singleton Pattern

```python
from django.db import models
from django.core.cache import cache


class SingletonModel(models.Model):
    """A model that can only have one instance."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Force the primary key to always be 1
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalidate cache on save
        cache.delete(self._cache_key())

    def delete(self, *args, **kwargs):
        # Prevent deletion
        raise ValueError("Singleton instances cannot be deleted")

    @classmethod
    def _cache_key(cls):
        return f'singleton_{cls.__name__}'

    @classmethod
    def load(cls):
        """Load the singleton instance, creating if necessary."""
        cache_key = cls._cache_key()
        instance = cache.get(cache_key)

        if instance is None:
            instance, _ = cls.objects.get_or_create(pk=1)
            cache.set(cache_key, instance, timeout=3600)

        return instance
```

### Usage Example

```python
class SiteSettings(SingletonModel):
    """Global site configuration."""

    site_name = models.CharField(max_length=255, default="My Site")
    maintenance_mode = models.BooleanField(default=False)
    max_upload_size_mb = models.IntegerField(default=10)
    feature_new_checkout = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"


# Usage
settings = SiteSettings.load()
if settings.maintenance_mode:
    return HttpResponse("Site under maintenance", status=503)
```

### Why Not Django Settings?

Django's `settings.py` requires a restart to change. Singleton models can be changed at runtime through the admin interface or API calls.

Use Django settings for:
- Database connections
- Secret keys
- Installed apps
- Middleware configuration

Use singleton models for:
- Feature flags
- Rate limits
- Display text
- Business rules that change without deployments

---

## django-modules: Organizing Related Models

As your application grows, you'll have dozens of models. Some belong together—they share concepts, they reference each other, they're maintained by the same team. Modules make these relationships explicit.

### The Module Registry

```python
from django.apps import apps


class ModuleRegistry:
    """Registry of all application modules."""

    _modules = {}

    @classmethod
    def register(cls, name, models, description=""):
        """Register a module with its models."""
        cls._modules[name] = {
            'models': models,
            'description': description,
        }

    @classmethod
    def get_module(cls, name):
        """Get a registered module by name."""
        return cls._modules.get(name)

    @classmethod
    def all_modules(cls):
        """Get all registered modules."""
        return dict(cls._modules)

    @classmethod
    def models_for_module(cls, name):
        """Get all models in a module."""
        module = cls.get_module(name)
        if module:
            return [apps.get_model(m) for m in module['models']]
        return []


# Registration in apps.py
class IdentityConfig(AppConfig):
    name = 'django_parties'

    def ready(self):
        ModuleRegistry.register(
            'identity',
            models=[
                'django_parties.Party',
                'django_parties.Person',
                'django_parties.Organization',
                'django_rbac.Role',
                'django_rbac.Permission',
            ],
            description='Identity and access control primitives'
        )
```

### Why Modules Matter

1. **Documentation.** "What models are involved in identity?" has a clear answer.

2. **Permissions.** Grant access to entire modules, not individual models.

3. **Export/Import.** Dump and restore related data together.

4. **Testing.** Test modules in isolation with clear boundaries.

5. **Onboarding.** New developers understand the system structure.

---

## django-layers: Enforcing Boundaries

The most important foundation package prevents you from making architectural mistakes. Layers define what can import what.

### The Dependency Rule

From the project's CLAUDE.md:

> **Dependency Rule:** Never import from a higher layer. Foundation has no dependencies. Each layer only imports from layers below it.

This isn't a suggestion. It's enforced by code.

### Layer Configuration

```yaml
# layers.yaml
layers:
  - name: foundation
    packages:
      - django_basemodels
      - django_singleton
      - django_modules
      - django_layers
    allowed_imports: []  # Foundation imports nothing from our code

  - name: identity
    packages:
      - django_parties
      - django_rbac
    allowed_imports:
      - foundation

  - name: infrastructure
    packages:
      - django_decisioning
      - django_audit_log
    allowed_imports:
      - foundation
      - identity

  - name: domain
    packages:
      - django_catalog
      - django_encounters
      - django_worklog
      - django_geo
      - django_ledger
    allowed_imports:
      - foundation
      - identity
      - infrastructure

  - name: content
    packages:
      - django_documents
      - django_notes
      - django_agreements
    allowed_imports:
      - foundation
      - identity
      - infrastructure
      - domain

  - name: value_objects
    packages:
      - django_money
      - django_sequence
    allowed_imports:
      - foundation  # Value objects are mostly standalone
```

### The Layer Checker

```python
import ast
import sys
from pathlib import Path
import yaml


def load_layer_config(path='layers.yaml'):
    """Load layer configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_layer_for_package(package_name, config):
    """Find which layer a package belongs to."""
    for layer in config['layers']:
        if package_name in layer['packages']:
            return layer['name']
    return None


def get_allowed_imports(layer_name, config):
    """Get list of packages this layer can import from."""
    allowed_packages = set()
    for layer in config['layers']:
        if layer['name'] == layer_name:
            for allowed_layer in layer['allowed_imports']:
                for l in config['layers']:
                    if l['name'] == allowed_layer:
                        allowed_packages.update(l['packages'])
            break
    return allowed_packages


def check_imports(file_path, config):
    """Check if a file's imports violate layer boundaries."""
    violations = []

    with open(file_path) as f:
        tree = ast.parse(f.read())

    # Determine which package this file belongs to
    package_name = None
    for part in Path(file_path).parts:
        if part.startswith('django_'):
            package_name = part
            break

    if not package_name:
        return violations

    current_layer = get_layer_for_package(package_name, config)
    if not current_layer:
        return violations

    allowed = get_allowed_imports(current_layer, config)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_pkg = alias.name.split('.')[0]
                if imported_pkg.startswith('django_'):
                    if imported_pkg not in allowed and imported_pkg != package_name:
                        violations.append({
                            'file': file_path,
                            'line': node.lineno,
                            'import': alias.name,
                            'message': f'{package_name} cannot import from {imported_pkg}'
                        })

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_pkg = node.module.split('.')[0]
                if imported_pkg.startswith('django_'):
                    if imported_pkg not in allowed and imported_pkg != package_name:
                        violations.append({
                            'file': file_path,
                            'line': node.lineno,
                            'import': node.module,
                            'message': f'{package_name} cannot import from {imported_pkg}'
                        })

    return violations


def check_all_layers(packages_dir='packages', config_path='layers.yaml'):
    """Check all packages for layer violations."""
    config = load_layer_config(config_path)
    all_violations = []

    for py_file in Path(packages_dir).rglob('*.py'):
        violations = check_imports(str(py_file), config)
        all_violations.extend(violations)

    return all_violations


if __name__ == '__main__':
    violations = check_all_layers()
    if violations:
        print("Layer violations found:")
        for v in violations:
            print(f"  {v['file']}:{v['line']} - {v['message']}")
        sys.exit(1)
    else:
        print("No layer violations found.")
        sys.exit(0)
```

### Running the Check

```bash
# Check layer boundaries
python -m django_layers check

# In CI/CD pipeline
python -m django_layers check || exit 1
```

### Why Layers Matter

Without enforced boundaries:

1. **Circular dependencies emerge.** Identity imports from Ledger imports from Identity.

2. **Changes cascade.** Modifying a low-level package breaks everything above.

3. **Testing becomes impossible.** You can't test Identity without also loading Ledger, Catalog, and everything else.

4. **Mental models break.** Developers can't reason about the system in pieces.

With enforced boundaries:

1. **Clear dependencies.** You know exactly what each package needs.

2. **Isolated testing.** Test each layer independently.

3. **Safe refactoring.** Changes in higher layers can't break lower layers.

4. **Understandable architecture.** New developers grasp the structure quickly.

---

## Relationship to Django Built-ins

The Foundation layer doesn't replace Django's built-in apps. It extends them.

### What Django Provides

| Django App | Purpose |
|------------|---------|
| django.contrib.auth | User model, authentication, basic permissions |
| django.contrib.contenttypes | Generic foreign keys, model metadata |
| django.contrib.sessions | Session management |
| django.contrib.admin | Admin interface |

### What Foundation Adds

| Foundation Package | Extends Django How |
|-------------------|-------------------|
| django-basemodels | Provides abstract base classes that Django models inherit from |
| django-singleton | Provides a pattern Django doesn't have natively |
| django-modules | Organizes Django apps into logical groupings |
| django-layers | Enforces import rules between Django apps |

### The Integration Points

```python
# django-basemodels uses Django's model system
from django.db import models

class UUIDModel(models.Model):  # Inherits from Django
    ...

# django-singleton uses Django's cache framework
from django.core.cache import cache

# AuditedModel references Django's user model
from django.conf import settings

class AuditedModel(SoftDeleteModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Uses Django's user model setting
        ...
    )
```

### AUTH_USER_MODEL Integration

Every primitive that tracks "who did this" references Django's user model through `settings.AUTH_USER_MODEL`. This works whether you use Django's default `User`, a custom user model, or a third-party authentication system.

```python
# In settings.py
AUTH_USER_MODEL = 'myapp.CustomUser'

# In primitives
from django.conf import settings

class Decision(models.Model):
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
```

The primitives don't care what your user model looks like. They just need something to point to.

---

## Installation and Setup

### 1. Install the Foundation Packages

```bash
pip install django-basemodels django-singleton django-modules django-layers
```

Or in development:

```bash
pip install -e packages/django-basemodels
pip install -e packages/django-singleton
pip install -e packages/django-modules
pip install -e packages/django-layers
```

### 2. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # Django built-ins first
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Foundation layer
    'django_basemodels',
    'django_singleton',
    'django_modules',
    'django_layers',

    # Your other primitives and apps...
]
```

### 3. Create layers.yaml

```yaml
# layers.yaml in project root
layers:
  - name: foundation
    packages:
      - django_basemodels
      - django_singleton
      - django_modules
      - django_layers
    allowed_imports: []

  # Add other layers as you add packages...
```

### 4. Add Layer Check to CI

```yaml
# .github/workflows/ci.yml
- name: Check layer boundaries
  run: python -m django_layers check
```

---

## Why This Matters Later

The Foundation layer is invisible in working applications. You don't think about UUID primary keys when you're querying invoices. You don't think about soft delete when you're displaying a customer list. The foundation just works.

That invisibility is the point.

Every primitive in Part II inherits from these base classes. Every primitive respects layer boundaries. Every primitive can be tested in isolation because the architecture is clean.

When you see `class Invoice(SoftDeleteModel)` in Chapter 8, you know:
- It has a UUID primary key
- It has created_at and updated_at timestamps
- Calling delete() sets deleted_at instead of removing the row
- Default queries exclude soft-deleted records
- You can access deleted records through `all_objects`

You know all of this because the Foundation layer defined it once, correctly.

The boring foundations enable the interesting business logic. Build them right, and you never think about them again.

---

## How to Rebuild These Primitives

The Foundation packages can be rebuilt from scratch using constrained prompts. Each package has a detailed specification in `docs/prompts/`:

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-basemodels | `docs/prompts/django-basemodels.md` | 30 tests |
| django-singleton | `docs/prompts/django-singleton.md` | ~15 tests |
| django-modules | `docs/prompts/django-modules.md` | ~20 tests |
| django-layers | `docs/prompts/django-layers.md` | ~25 tests |

### Using the Prompts

Each prompt file contains:

1. **Instruction** - What to build and why
2. **File Structure** - Exact directory layout
3. **Models Specification** - Fields, methods, behaviors
4. **Test Cases** - Numbered tests to implement first (TDD)
5. **Known Gotchas** - Common mistakes to avoid
6. **Acceptance Criteria** - Definition of done

### Example Workflow

To rebuild `django-basemodels`:

```bash
# Step 1: Give Claude the prompt
cat docs/prompts/django-basemodels.md | claude

# Step 2: Request TDD approach
"Start with the TimeStampedModel tests. Write failing tests first,
then implement minimal code to pass."

# Step 3: Verify constraints
# - Abstract models only (no migrations)
# - SoftDeleteManager is default manager
# - QuerySet.delete() gotcha is documented
```

### Key Constraint

The prompts enforce the **NO DATABASE MIGRATIONS** rule for abstract base models. If Claude generates migration files for these packages, that's a constraint violation—abstract models don't create tables.

---

## References

- Django Model documentation: https://docs.djangoproject.com/en/stable/topics/db/models/
- Django abstract base classes: https://docs.djangoproject.com/en/stable/topics/db/models/#abstract-base-classes
- UUID specification: RFC 4122
- The Singleton Pattern: Gamma, Helm, Johnson, Vlissides. *Design Patterns*. Addison-Wesley, 1994.
- Hexagonal Architecture: Cockburn, Alistair. "Hexagonal Architecture." 2005.
- Clean Architecture: Martin, Robert C. *Clean Architecture*. Prentice Hall, 2017.

---

*Status: Draft*
