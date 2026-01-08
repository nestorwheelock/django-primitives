"""Tests for CMS entitlement-based access control."""

import pytest
from django.contrib.auth import get_user_model

from django_cms_core.models import ContentPage, CMSSettings, AccessLevel, PageStatus
from django_cms_core.services import create_page, check_page_access

from primitives_testbed.diveops.entitlements.services import grant_entitlements
from primitives_testbed.diveops.entitlements.cms_checker import cms_entitlement_checker

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def cms_settings(db):
    """Configure CMS settings with entitlement checker."""
    settings = CMSSettings.get_instance()
    settings.entitlement_checker_path = (
        "primitives_testbed.diveops.entitlements.cms_checker.cms_entitlement_checker"
    )
    settings.save()
    return settings


@pytest.fixture
def public_page(user, db):
    """Create a public CMS page."""
    return create_page(
        slug="public-page",
        title="Public Page",
        user=user,
        access_level=AccessLevel.PUBLIC,
    )


@pytest.fixture
def authenticated_page(user, db):
    """Create an authenticated-only CMS page."""
    return create_page(
        slug="auth-page",
        title="Authenticated Page",
        user=user,
        access_level=AccessLevel.AUTHENTICATED,
    )


@pytest.fixture
def entitlement_page(user, db):
    """Create an entitlement-gated CMS page."""
    return create_page(
        slug="premium-page",
        title="Premium Page",
        user=user,
        access_level=AccessLevel.ENTITLEMENT,
        required_entitlements=["content:premium"],
    )


@pytest.mark.django_db
class TestCMSEntitlementChecker:
    """Tests for cms_entitlement_checker function."""

    def test_user_with_entitlement_passes(self, user):
        """User with required entitlement passes check."""
        grant_entitlements(user, ["content:premium"])

        result = cms_entitlement_checker(user, ["content:premium"])

        assert result is True

    def test_user_without_entitlement_fails(self, user):
        """User without required entitlement fails check."""
        result = cms_entitlement_checker(user, ["content:premium"])

        assert result is False

    def test_empty_requirements_passes(self, user):
        """Empty requirements list always passes."""
        result = cms_entitlement_checker(user, [])

        assert result is True

    def test_handles_string_input(self, user):
        """Can handle single string instead of list."""
        grant_entitlements(user, ["content:premium"])

        result = cms_entitlement_checker(user, "content:premium")

        assert result is True


@pytest.mark.django_db
class TestCMSPageAccessControl:
    """Tests for CMS page access control with entitlements."""

    def test_public_page_accessible_to_anonymous(self, public_page):
        """Public pages are accessible without login."""
        allowed, reason = check_page_access(public_page, user=None)

        assert allowed is True
        assert reason == ""

    def test_authenticated_page_requires_login(self, authenticated_page):
        """Authenticated pages require login."""
        allowed, reason = check_page_access(authenticated_page, user=None)

        assert allowed is False
        assert "Authentication required" in reason

    def test_authenticated_page_accessible_to_logged_in(self, authenticated_page, user):
        """Authenticated pages accessible to logged-in users."""
        allowed, reason = check_page_access(authenticated_page, user=user)

        assert allowed is True

    def test_entitlement_page_denied_without_entitlement(
        self, entitlement_page, user, cms_settings
    ):
        """Entitlement pages denied without the entitlement."""
        allowed, reason = check_page_access(entitlement_page, user=user)

        assert allowed is False
        assert "Entitlement check failed" in reason

    def test_entitlement_page_accessible_with_entitlement(
        self, entitlement_page, user, cms_settings
    ):
        """Entitlement pages accessible with the required entitlement."""
        grant_entitlements(user, ["content:premium"])

        allowed, reason = check_page_access(entitlement_page, user=user)

        assert allowed is True

    def test_superuser_bypasses_entitlement_check(
        self, entitlement_page, db, cms_settings
    ):
        """Superusers bypass entitlement checks."""
        superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass",
        )

        allowed, reason = check_page_access(entitlement_page, user=superuser)

        assert allowed is True
