# django-rbac

Role-based access control with hierarchy enforcement for Django.

## Overview

django-rbac provides a complete RBAC system with:
- **Roles** with configurable hierarchy levels (10-100)
- **Hierarchy enforcement** - users can only manage users below their level
- **Module permissions** - control access to application modules
- **View protection** - decorators and mixins for function and class-based views

## Key Principle

**Users can only manage users with LOWER hierarchy levels.**

This is enforced at the model level and prevents privilege escalation.

## Hierarchy Levels

| Level | Role Example | Description |
|-------|--------------|-------------|
| 100 | Superuser | System admin (automatic for is_superuser) |
| 80 | Administrator | Full system access |
| 60 | Manager | Team leads, can manage staff |
| 40 | Professional | Licensed professionals |
| 30 | Technician | Support staff |
| 20 | Staff | Front desk, basic access |
| 10 | Customer | End users, minimal access |

## Installation

```bash
pip install django-rbac
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_rbac',
]
```

## Setup

### 1. Add RBACUserMixin to your User model

```python
from django.contrib.auth.models import AbstractUser
from django_rbac.mixins import RBACUserMixin

class User(RBACUserMixin, AbstractUser):
    pass
```

### 2. Run migrations

```bash
python manage.py migrate django_rbac
```

### 3. Create Roles

```python
from django.contrib.auth.models import Group
from django_rbac.models import Role

# Create a Django Group first (for permission management)
group = Group.objects.create(name='Staff')

# Create the Role with hierarchy level
role = Role.objects.create(
    name='Staff',
    slug='staff',
    hierarchy_level=20,
    group=group,
)

# Add permissions via the group
group.permissions.add(practice_view_permission)
```

### 4. Assign Roles to Users

```python
from django_rbac.models import UserRole

UserRole.objects.create(
    user=user,
    role=role,
    assigned_by=admin_user,  # Optional: track who assigned
    is_primary=True,         # Optional: mark as primary role
)
```

## Usage

### Check Hierarchy Level

```python
# Get user's highest hierarchy level
level = user.hierarchy_level  # 60 for manager

# Superuser always has level 100
superuser.hierarchy_level  # 100
```

### Check Management Permission

```python
# Can manager manage staff?
manager.can_manage_user(staff)  # True (60 > 20)

# Can staff manage manager?
staff.can_manage_user(manager)  # False (20 < 60)

# Same level cannot manage each other
manager1.can_manage_user(manager2)  # False (60 == 60)
```

### Get Manageable Roles

```python
# What roles can manager assign?
roles = manager.get_manageable_roles()
# Returns: Staff (20), Customer (10) - all below level 60
```

### Check Module Permissions

```python
# Does user have permission for module.action?
user.has_module_permission('practice', 'view')  # True/False
user.has_module_permission('accounting', 'manage')  # True/False

# Superuser always has all permissions
superuser.has_module_permission('anything', 'any')  # True
```

### Protect Function-Based Views

```python
from django_rbac.decorators import require_permission, requires_hierarchy_level

@require_permission('practice', 'manage')
def staff_create(request):
    # Only users with practice.manage permission
    ...

@requires_hierarchy_level(60)  # Manager or higher
def approve_leave(request):
    # Only users with level >= 60
    ...
```

### Protect Class-Based Views

```python
from django_rbac.views import (
    ModulePermissionMixin,
    HierarchyPermissionMixin,
    CombinedPermissionMixin,
    HierarchyLevelMixin,
)

# Require module permission
class StaffListView(ModulePermissionMixin, ListView):
    required_module = 'practice'
    required_action = 'view'
    model = StaffProfile

# Require hierarchy check
class StaffEditView(HierarchyPermissionMixin, UpdateView):
    model = StaffProfile

    def get_target_user(self):
        return self.get_object().user

# Require both
class StaffDeleteView(CombinedPermissionMixin, DeleteView):
    required_module = 'practice'
    required_action = 'delete'
    model = StaffProfile

    def get_target_user(self):
        return self.get_object().user

# Require minimum level
class SystemSettings(HierarchyLevelMixin, UpdateView):
    required_level = 80  # Administrator or higher
    model = Settings
```

## Models Reference

### Role

| Field | Type | Description |
|-------|------|-------------|
| name | CharField | Role name (unique) |
| slug | SlugField | URL-safe identifier (unique) |
| description | TextField | Optional description |
| hierarchy_level | IntegerField | Authority level 10-100 (default: 20) |
| is_active | BooleanField | Active status (default: True) |
| group | OneToOneField | Link to Django Group for permissions |

### UserRole

| Field | Type | Description |
|-------|------|-------------|
| user | ForeignKey | The user being assigned |
| role | ForeignKey | The role being assigned |
| assigned_by | ForeignKey | User who assigned (optional) |
| assigned_at | DateTimeField | When assigned (auto) |
| is_primary | BooleanField | Primary role flag (default: False) |

## Architecture Principles

This package follows CONTRACT Rule 2:

> "Users can only manage users with LOWER hierarchy levels."

**Prohibitions:**
- No escalation via convenience flags
- All escalation requires explicit role assignment
- No "is_superuser" shortcuts that bypass hierarchy (except for level 100)

## License

Proprietary - All rights reserved.
