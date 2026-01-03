"""RBAC scenario: Roles, UserRoles with hierarchy and effective dating."""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group as DjangoGroup
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_rbac.models import Role, UserRole


User = get_user_model()


def seed():
    """Create sample RBAC data."""
    count = 0

    # Create Django groups for roles
    admin_group, _ = DjangoGroup.objects.get_or_create(name="Administrators")
    manager_group, _ = DjangoGroup.objects.get_or_create(name="Managers")
    staff_group, _ = DjangoGroup.objects.get_or_create(name="Staff")
    customer_group, _ = DjangoGroup.objects.get_or_create(name="Customers")
    count += 4

    # Create roles with hierarchy levels
    admin_role, created = Role.objects.get_or_create(
        slug="administrator",
        defaults={
            "name": "Administrator",
            "hierarchy_level": 80,
            "group": admin_group,
            "description": "Full system access"
        }
    )
    if created:
        count += 1

    manager_role, created = Role.objects.get_or_create(
        slug="manager",
        defaults={
            "name": "Manager",
            "hierarchy_level": 60,
            "group": manager_group,
            "description": "Team management access"
        }
    )
    if created:
        count += 1

    staff_role, created = Role.objects.get_or_create(
        slug="staff",
        defaults={
            "name": "Staff",
            "hierarchy_level": 20,
            "group": staff_group,
            "description": "Basic staff access"
        }
    )
    if created:
        count += 1

    customer_role, created = Role.objects.get_or_create(
        slug="customer",
        defaults={
            "name": "Customer",
            "hierarchy_level": 10,
            "group": customer_group,
            "description": "Customer access"
        }
    )
    if created:
        count += 1

    # Create test users
    admin_user, created = User.objects.get_or_create(
        username="admin_testbed",
        defaults={
            "email": "admin@testbed.local",
            "first_name": "Admin",
            "last_name": "User",
        }
    )
    if created:
        admin_user.set_password("testbed123")
        admin_user.save()
        count += 1

    manager_user, created = User.objects.get_or_create(
        username="manager_testbed",
        defaults={
            "email": "manager@testbed.local",
            "first_name": "Manager",
            "last_name": "User",
        }
    )
    if created:
        manager_user.set_password("testbed123")
        manager_user.save()
        count += 1

    staff_user, created = User.objects.get_or_create(
        username="staff_testbed",
        defaults={
            "email": "staff@testbed.local",
            "first_name": "Staff",
            "last_name": "User",
        }
    )
    if created:
        staff_user.set_password("testbed123")
        staff_user.save()
        count += 1

    # Assign roles
    UserRole.objects.get_or_create(
        user=admin_user,
        role=admin_role,
        defaults={"is_primary": True}
    )
    UserRole.objects.get_or_create(
        user=manager_user,
        role=manager_role,
        defaults={"is_primary": True, "assigned_by": admin_user}
    )
    UserRole.objects.get_or_create(
        user=staff_user,
        role=staff_role,
        defaults={"is_primary": True, "assigned_by": manager_user}
    )
    count += 3

    # Create an expired role assignment for testing
    now = timezone.now()
    past_start = now - datetime.timedelta(days=60)
    past_end = now - datetime.timedelta(days=30)

    UserRole.objects.get_or_create(
        user=staff_user,
        role=manager_role,
        valid_from=past_start,
        valid_to=past_end,
        defaults={"assigned_by": admin_user}
    )
    count += 1

    return count


def verify():
    """Verify RBAC constraints with negative writes."""
    results = []

    # Test 1: Role hierarchy_level must be in range 10-100
    group = DjangoGroup.objects.first()
    if group:
        # Test below minimum
        try:
            with transaction.atomic():
                Role.objects.create(
                    name="Invalid Low",
                    slug="invalid-low",
                    hierarchy_level=5,  # Below 10
                    group=group,
                )
            results.append(("role_hierarchy_level_range (below 10)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("role_hierarchy_level_range (below 10)", True, "Correctly rejected"))

        # Test above maximum
        try:
            with transaction.atomic():
                Role.objects.create(
                    name="Invalid High",
                    slug="invalid-high",
                    hierarchy_level=150,  # Above 100
                    group=group,
                )
            results.append(("role_hierarchy_level_range (above 100)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("role_hierarchy_level_range (above 100)", True, "Correctly rejected"))
    else:
        results.append(("role_hierarchy_level_range", None, "Skipped - no test data"))

    # Test 2: UserRole valid_to must be after valid_from
    user = User.objects.filter(username="staff_testbed").first()
    role = Role.objects.filter(slug="customer").first()
    if user and role:
        try:
            with transaction.atomic():
                now = timezone.now()
                UserRole.objects.create(
                    user=user,
                    role=role,
                    valid_from=now,
                    valid_to=now - datetime.timedelta(days=1),  # Before valid_from
                )
            results.append(("userrole_valid_to_after_valid_from", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("userrole_valid_to_after_valid_from", True, "Correctly rejected"))
    else:
        results.append(("userrole_valid_to_after_valid_from", None, "Skipped - no test data"))

    # Test 3: Verify hierarchy enforcement in Python (can_manage_user)
    admin = User.objects.filter(username="admin_testbed").first()
    staff = User.objects.filter(username="staff_testbed").first()
    if admin and staff:
        # Admin (level 80) should be able to manage staff (level 20)
        can_manage = admin.can_manage_user(staff)
        if can_manage:
            results.append(("hierarchy_can_manage (admin->staff)", True, "Admin can manage staff"))
        else:
            results.append(("hierarchy_can_manage (admin->staff)", False, "Admin should manage staff"))

        # Staff should NOT be able to manage admin
        cannot_manage = not staff.can_manage_user(admin)
        if cannot_manage:
            results.append(("hierarchy_can_manage (staff->admin)", True, "Staff cannot manage admin"))
        else:
            results.append(("hierarchy_can_manage (staff->admin)", False, "Staff should not manage admin"))
    else:
        results.append(("hierarchy_can_manage", None, "Skipped - no test data"))

    return results
