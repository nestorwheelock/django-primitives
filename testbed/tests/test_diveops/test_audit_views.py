"""Tests for audit log staff views."""

import pytest
from django.urls import reverse

from django_audit_log.models import AuditLog


@pytest.mark.django_db
class TestAuditLogListView:
    """Tests for the audit log list view in staff portal."""

    def test_audit_log_view_requires_staff(self, client):
        """Audit log view requires staff authentication."""
        url = reverse("diveops:audit-log")
        response = client.get(url)
        # Should redirect to login
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_audit_log_view_accessible_to_staff(self, staff_client):
        """Staff users can access the audit log view."""
        url = reverse("diveops:audit-log")
        response = staff_client.get(url)
        assert response.status_code == 200

    def test_audit_log_view_displays_entries(self, staff_client, staff_user):
        """Audit log view displays log entries."""
        # Create some audit entries
        AuditLog.objects.create(
            action="certification_added",
            model_label="diveops.divercertification",
            object_id="test-123",
            object_repr="Test Diver - Open Water",
            actor_user=staff_user,
            actor_display=staff_user.email,
        )
        AuditLog.objects.create(
            action="certification_verified",
            model_label="diveops.divercertification",
            object_id="test-456",
            object_repr="Another Diver - Advanced",
            actor_user=staff_user,
            actor_display=staff_user.email,
        )

        url = reverse("diveops:audit-log")
        response = staff_client.get(url)

        assert response.status_code == 200
        assert b"certification_added" in response.content
        assert b"certification_verified" in response.content
        assert b"Test Diver - Open Water" in response.content

    def test_audit_log_view_shows_newest_first(self, staff_client, staff_user):
        """Audit log entries are ordered newest first."""
        # Create entries
        entry1 = AuditLog.objects.create(
            action="first_action",
            model_label="test.model",
            object_id="1",
            object_repr="First Entry",
            actor_display="user",
        )
        entry2 = AuditLog.objects.create(
            action="second_action",
            model_label="test.model",
            object_id="2",
            object_repr="Second Entry",
            actor_display="user",
        )

        url = reverse("diveops:audit-log")
        response = staff_client.get(url)

        content = response.content.decode()
        # Second entry should appear before first (newest first)
        assert content.index("second_action") < content.index("first_action")

    def test_audit_log_view_paginates(self, staff_client, staff_user):
        """Audit log view paginates results."""
        # Create more than one page of entries
        for i in range(30):
            AuditLog.objects.create(
                action=f"action_{i}",
                model_label="test.model",
                object_id=str(i),
                object_repr=f"Entry {i}",
                actor_display="user",
            )

        url = reverse("diveops:audit-log")
        response = staff_client.get(url)

        assert response.status_code == 200
        # Should have pagination
        assert b"page" in response.content.lower() or response.context.get("is_paginated")

    def test_audit_log_in_navigation(self, staff_client):
        """Audit log link appears in staff navigation."""
        # Access any staff page
        url = reverse("diveops:diver-list")
        response = staff_client.get(url)

        assert response.status_code == 200
        # Navigation should include audit log link
        assert b"Audit Log" in response.content
        assert b"audit-log" in response.content or b"audit" in response.content.lower()
