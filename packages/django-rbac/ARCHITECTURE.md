# Architecture: django-rbac

**Status:** Stable / v0.1.0

Role-based access control with hierarchy enforcement for Django applications.

---

## What This Package Is For

Answering the question: **"Can this user manage that user?"**

Use cases:
- Custom roles with configurable permissions
- Hierarchy-based user management (managers manage staff, not peers)
- Time-boxed role assignments with effective dating
- Role assignment audit trail (who assigned whom)
- Integration with Django's Group/Permission system

---

## What This Package Is NOT For

- **Not row-level permissions** - Use django-guardian for object permissions
- **Not organizational hierarchy** - Use django-parties for org structure
- **Not a replacement for is_superuser** - Superuser bypasses all checks
- **Not multi-tenancy isolation** - Roles are global, not per-tenant

---

## Design Principles

1. **Hierarchy enforcement** - Users can only manage users with LOWER hierarchy levels
2. **No escalation via shortcuts** - No "is_superuser" flags that bypass hierarchy
3. **Roles linked to Groups** - Permissions managed via Django's built-in Group system
4. **Effective dating** - Role assignments have validity windows (valid_from/valid_to)
5. **Soft delete with dating** - Revoke by setting valid_to, don't delete

---

## Data Model

```
Role                                   UserRole
├── id (UUID, BaseModel)               ├── id (UUID, BaseModel)
├── name (unique)                      ├── user (FK → AUTH_USER_MODEL)
├── slug (unique)                      ├── role (FK → Role)
├── description                        ├── assigned_by (FK → User)
├── hierarchy_level (10-100)           ├── assigned_at (auto)
├── is_active (bool)                   ├── is_primary (bool)
├── group (OneToOne → Group)           ├── valid_from (datetime)
├── created_at (auto)                  ├── valid_to (nullable)
├── updated_at (auto)                  ├── created_at (auto)
└── deleted_at (soft delete)           ├── updated_at (auto)
                                       └── deleted_at (soft delete)

Hierarchy Level Guide:
| Level | Role            | Can Manage       |
|-------|-----------------|------------------|
| 100   | Superuser       | All (90 and below) |
| 80    | Administrator   | 70 and below     |
| 60    | Manager         | 50 and below     |
| 40    | Professional    | 30 and below     |
| 30    | Technician      | 20 and below     |
| 20    | Staff           | 10 and below     |
| 10    | Customer        | None             |
```

---

## Public API

### Creating Roles

```python
from django.contrib.auth.models import Group
from django_rbac import Role

# Create Django Group first
group = Group.objects.create(name='Practice Manager')

# Create Role linked to Group
role = Role.objects.create(
    name='Practice Manager',
    slug='practice-manager',
    hierarchy_level=60,
    group=group,
)

# Add permissions via the linked group
from django.contrib.auth.models import Permission
perm = Permission.objects.get(codename='view_patient')
role.group.permissions.add(perm)
```

### Assigning Roles to Users

```python
from django_rbac import UserRole

# Assign role with effective dating
UserRole.objects.create(
    user=staff_member,
    role=staff_role,
    assigned_by=manager,
    is_primary=True,
    valid_from=timezone.now(),
    # valid_to=None means indefinite
)

# Revoke by setting valid_to
user_role.valid_to = timezone.now()
user_role.save()
```

### Querying Roles

```python
# Get currently valid roles for a user
current_roles = UserRole.objects.current().filter(user=user)

# Get roles valid at a specific point in time
past_roles = UserRole.objects.as_of(some_date).filter(user=user)

# Get user's highest role level
from django.db.models import Max
max_level = UserRole.objects.current().filter(
    user=user
).aggregate(max=Max('role__hierarchy_level'))['max'] or 0
```

### Hierarchy Enforcement

```python
def can_manage(manager_user, target_user):
    """Check if manager can manage target based on hierarchy."""
    manager_level = UserRole.objects.current().filter(
        user=manager_user
    ).aggregate(max=Max('role__hierarchy_level'))['max'] or 0

    target_level = UserRole.objects.current().filter(
        user=target_user
    ).aggregate(max=Max('role__hierarchy_level'))['max'] or 0

    return manager_level > target_level
```

---

## Hard Rules

1. **Hierarchy level range** - Must be 10-100 (enforced by DB constraint)
2. **No self-escalation** - Users cannot assign themselves higher roles
3. **Manage down only** - Users can only manage users with LOWER levels
4. **Group required** - Every Role must link to a Django Group
5. **Unique role names** - name and slug are both unique

---

## Invariants

- `hierarchy_level` is always in range [10, 100]
- Every Role has exactly one linked Group (OneToOne)
- For currently valid UserRole: `valid_from <= now()` and (`valid_to IS NULL` or `valid_to > now()`)
- User's effective level is the MAX of their currently valid roles
- Role.name and Role.slug are globally unique

---

## Known Gotchas

### 1. Hierarchy Level Direction

**Problem:** Confusion about which direction is "higher".

```python
# WRONG mental model: "Level 10 is highest"
# CORRECT: Higher number = more authority

# Manager (60) can manage Staff (20)
# Staff (20) CANNOT manage Manager (60)
```

### 2. Forgetting to Create Group First

**Problem:** Creating Role without linked Group.

```python
# WRONG - no Group
role = Role.objects.create(name='Manager', hierarchy_level=60)
# Error: group is required!

# CORRECT - Group first
group = Group.objects.create(name='Manager')
role = Role.objects.create(name='Manager', group=group, hierarchy_level=60)
```

### 3. Not Using current() for Validity Checks

**Problem:** Querying all UserRoles instead of currently valid ones.

```python
# WRONG - includes expired and future assignments
roles = UserRole.objects.filter(user=user)

# CORRECT - only currently valid
roles = UserRole.objects.current().filter(user=user)
```

### 4. Revocation vs Deletion

**Problem:** Hard-deleting UserRole instead of revoking.

```python
# WRONG - loses audit trail
user_role.delete()

# CORRECT - preserves history
user_role.valid_to = timezone.now()
user_role.save()
```

### 5. Soft Delete Interaction

**Problem:** Soft-deleted roles appearing in queries.

```python
# Default manager excludes deleted
roles = Role.objects.filter(is_active=True)  # Excludes soft-deleted

# To include deleted (for admin views)
all_roles = Role.all_objects.all()
```

---

## Recommended Usage

### 1. Define Standard Roles at Setup

```python
def create_standard_roles():
    """Create standard roles for the application."""
    role_defs = [
        ('Administrator', 'administrator', 80),
        ('Manager', 'manager', 60),
        ('Professional', 'professional', 40),
        ('Staff', 'staff', 20),
        ('Customer', 'customer', 10),
    ]

    for name, slug, level in role_defs:
        group, _ = Group.objects.get_or_create(name=name)
        Role.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'hierarchy_level': level, 'group': group}
        )
```

### 2. Use Decorators for View Protection

```python
from functools import wraps
from django.http import HttpResponseForbidden

def require_role_level(min_level):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_level = get_user_max_level(request.user)
            if user_level < min_level:
                return HttpResponseForbidden("Insufficient role level")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

@require_role_level(60)  # Manager or higher
def manage_staff(request):
    ...
```

### 3. Use Primary Role for Display

```python
def get_user_primary_role(user):
    """Get user's primary role for display."""
    primary = UserRole.objects.current().filter(
        user=user, is_primary=True
    ).select_related('role').first()

    if primary:
        return primary.role

    # Fallback to highest level role
    highest = UserRole.objects.current().filter(
        user=user
    ).select_related('role').order_by('-role__hierarchy_level').first()

    return highest.role if highest else None
```

---

## Dependencies

- Django >= 4.2
- django-basemodels (for UUID PK, soft delete)

---

## Changelog

### v0.1.0 (2024-12-31)
- Initial release
- Role model with hierarchy levels (10-100)
- UserRole with effective dating (valid_from/valid_to)
- Integration with Django Group for permissions
- Custom manager with as_of() and current() methods
