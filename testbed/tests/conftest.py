"""Pytest configuration for primitives testbed integration tests."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    user, _ = User.objects.get_or_create(
        username="test_admin",
        defaults={
            "email": "admin@test.local",
            "is_staff": True,
            "is_superuser": True,
        }
    )
    user.set_password("testpass123")
    user.save()
    return user


@pytest.fixture
def regular_user(db):
    """Create a regular user for testing."""
    user, _ = User.objects.get_or_create(
        username="test_user",
        defaults={
            "email": "user@test.local",
        }
    )
    user.set_password("testpass123")
    user.save()
    return user


@pytest.fixture
def seeded_database(db):
    """Seed the database with sample data from all scenarios."""
    from primitives_testbed.scenarios import seed_all
    results = seed_all()
    return results
