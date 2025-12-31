"""Pytest configuration for django-worklog tests."""

import pytest


@pytest.fixture
def user(db, django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user(
        username="testuser",
        password="testpass123",
    )


@pytest.fixture
def other_user(db, django_user_model):
    """Create another test user for multi-user tests."""
    return django_user_model.objects.create_user(
        username="otheruser",
        password="testpass123",
    )
