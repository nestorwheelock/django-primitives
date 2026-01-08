"""Tests for entitlement services."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from primitives_testbed.diveops.entitlements.models import EntitlementGrant
from primitives_testbed.diveops.entitlements.services import (
    grant_entitlements,
    revoke_entitlements,
    user_has_entitlement,
    user_has_all_entitlements,
    get_user_entitlements,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestGrantEntitlements:
    """Tests for grant_entitlements service."""

    def test_grant_single_entitlement(self, user):
        """Can grant a single entitlement to a user."""
        grants = grant_entitlements(user, ["content:test"])

        assert len(grants) == 1
        assert grants[0].user == user
        assert grants[0].code == "content:test"
        assert grants[0].source_type == "manual"

    def test_grant_multiple_entitlements(self, user):
        """Can grant multiple entitlements at once."""
        grants = grant_entitlements(user, ["code:a", "code:b", "code:c"])

        assert len(grants) == 3
        codes = {g.code for g in grants}
        assert codes == {"code:a", "code:b", "code:c"}

    def test_grant_is_idempotent(self, user):
        """Granting same entitlement twice doesn't create duplicate."""
        grants1 = grant_entitlements(user, ["content:test"], source_id="order-1")
        grants2 = grant_entitlements(user, ["content:test"], source_id="order-1")

        assert len(grants1) == 1
        assert len(grants2) == 0  # Second call returns empty (already exists)
        assert EntitlementGrant.objects.filter(user=user, code="content:test").count() == 1

    def test_grant_with_source_tracking(self, user):
        """Grants include source tracking for audit."""
        grants = grant_entitlements(
            user,
            ["content:test"],
            source_type="invoice",
            source_id="order-123",
        )

        assert grants[0].source_type == "invoice"
        assert grants[0].source_id == "order-123"

    def test_grant_with_validity_period(self, user):
        """Can grant entitlements with start and end dates."""
        starts = timezone.now()
        ends = starts + timedelta(days=30)

        grants = grant_entitlements(
            user,
            ["content:test"],
            starts_at=starts,
            ends_at=ends,
        )

        assert grants[0].starts_at == starts
        assert grants[0].ends_at == ends


@pytest.mark.django_db
class TestRevokeEntitlements:
    """Tests for revoke_entitlements service."""

    def test_revoke_entitlement(self, user):
        """Can revoke an entitlement."""
        grant_entitlements(user, ["content:test"])
        assert user_has_entitlement(user, "content:test")

        count = revoke_entitlements(user, ["content:test"])

        assert count == 1
        assert not user_has_entitlement(user, "content:test")

    def test_revoke_by_source(self, user):
        """Can revoke only entitlements from a specific source."""
        grant_entitlements(user, ["content:a"], source_id="order-1")
        grant_entitlements(user, ["content:b"], source_id="order-2")

        count = revoke_entitlements(user, ["content:a", "content:b"], source_id="order-1")

        assert count == 1
        assert not user_has_entitlement(user, "content:a")
        assert user_has_entitlement(user, "content:b")


@pytest.mark.django_db
class TestUserHasEntitlement:
    """Tests for user_has_entitlement service."""

    def test_user_has_granted_entitlement(self, user):
        """Returns True when user has the entitlement."""
        grant_entitlements(user, ["content:test"])

        assert user_has_entitlement(user, "content:test") is True

    def test_user_lacks_entitlement(self, user):
        """Returns False when user doesn't have the entitlement."""
        assert user_has_entitlement(user, "content:test") is False

    def test_anonymous_user_lacks_entitlement(self):
        """Returns False for anonymous/None user."""
        assert user_has_entitlement(None, "content:test") is False

    def test_expired_entitlement_not_active(self, user):
        """Expired entitlement returns False."""
        past = timezone.now() - timedelta(days=10)
        grant_entitlements(user, ["content:test"], ends_at=past)

        assert user_has_entitlement(user, "content:test") is False

    def test_future_entitlement_not_active(self, user):
        """Future entitlement (not yet started) returns False."""
        future = timezone.now() + timedelta(days=10)
        grant_entitlements(user, ["content:test"], starts_at=future)

        assert user_has_entitlement(user, "content:test") is False


@pytest.mark.django_db
class TestUserHasAllEntitlements:
    """Tests for user_has_all_entitlements service."""

    def test_user_has_all(self, user):
        """Returns True when user has all required entitlements."""
        grant_entitlements(user, ["code:a", "code:b", "code:c"])

        assert user_has_all_entitlements(user, ["code:a", "code:b"]) is True

    def test_user_missing_one(self, user):
        """Returns False when user is missing one entitlement."""
        grant_entitlements(user, ["code:a", "code:b"])

        assert user_has_all_entitlements(user, ["code:a", "code:b", "code:c"]) is False

    def test_empty_list_returns_true(self, user):
        """Empty requirements list returns True."""
        assert user_has_all_entitlements(user, []) is True


@pytest.mark.django_db
class TestGetUserEntitlements:
    """Tests for get_user_entitlements service."""

    def test_returns_active_codes(self, user):
        """Returns list of active entitlement codes."""
        grant_entitlements(user, ["code:a", "code:b"])

        codes = get_user_entitlements(user)

        assert set(codes) == {"code:a", "code:b"}

    def test_excludes_expired(self, user):
        """Excludes expired entitlements."""
        grant_entitlements(user, ["code:active"])
        grant_entitlements(
            user,
            ["code:expired"],
            ends_at=timezone.now() - timedelta(days=1),
        )

        codes = get_user_entitlements(user)

        assert codes == ["code:active"]

    def test_anonymous_returns_empty(self):
        """Anonymous user returns empty list."""
        assert get_user_entitlements(None) == []
