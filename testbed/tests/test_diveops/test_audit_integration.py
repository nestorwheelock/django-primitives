"""Tests for audit logging integration in diveops.

These tests verify that the audit adapter is called correctly during
certification operations. We mock at the django_audit_log boundary,
not at the adapter level, to ensure the full integration works.
"""

from datetime import date
from unittest.mock import patch

import pytest

from primitives_testbed.diveops.audit import Actions
from primitives_testbed.diveops.models import CertificationLevel, DiverCertification, DiverProfile
from primitives_testbed.diveops.services import (
    add_certification,
    remove_certification,
    unverify_certification,
    update_certification,
    verify_certification,
)


# Patch path is where the function is imported, not where it's defined
AUDIT_LOG_PATCH = "primitives_testbed.diveops.audit.audit_log"


@pytest.fixture
def padi_agency(db):
    """Create a PADI agency organization."""
    from django_parties.models import Organization

    return Organization.objects.create(name="PADI", legal_name="PADI Worldwide")


@pytest.fixture
def padi_open_water(padi_agency):
    """Create PADI Open Water certification level."""
    return CertificationLevel.objects.create(
        name="Open Water Diver",
        code="OWD",
        agency=padi_agency,
        rank=1,
        max_depth_m=18,
    )


@pytest.fixture
def diver(db, padi_agency):
    """Create a diver profile."""
    from django_parties.models import Person

    person = Person.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    return DiverProfile.objects.create(
        person=person,
        certification_level="ow",
        certification_agency=padi_agency,
        certification_number="LEGACY123",
        certification_date=date(2020, 1, 1),
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass",
        is_staff=True,
    )


@pytest.mark.django_db
class TestVerifyCertificationAudit:
    """Tests for audit logging during certification verification."""

    def test_verify_certification_logs_audit_event(self, diver, padi_open_water, staff_user):
        """verify_certification() logs an audit event via django_audit_log."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        with patch(AUDIT_LOG_PATCH) as mock_log:
            verify_certification(cert, staff_user)

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == Actions.CERTIFICATION_VERIFIED
            assert call_kwargs["obj"] == cert
            assert call_kwargs["actor"] == staff_user
            assert "level_id" in call_kwargs["metadata"]
            assert "agency_id" in call_kwargs["metadata"]

    def test_verify_audit_includes_correct_metadata(self, diver, padi_open_water, staff_user):
        """Verify audit event metadata includes agency and level info."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        with patch(AUDIT_LOG_PATCH) as mock_log:
            verify_certification(cert, staff_user)

            metadata = mock_log.call_args.kwargs["metadata"]
            assert metadata["agency_name"] == "PADI"
            assert metadata["level_name"] == "Open Water Diver"
            assert metadata["diver_id"] == str(diver.pk)


@pytest.mark.django_db
class TestUnverifyCertificationAudit:
    """Tests for audit logging during certification unverification."""

    def test_unverify_certification_logs_audit_event(self, diver, padi_open_water, staff_user):
        """unverify_certification() logs an audit event via django_audit_log."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        verify_certification(cert, staff_user)

        with patch(AUDIT_LOG_PATCH) as mock_log:
            unverify_certification(cert, staff_user)

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == Actions.CERTIFICATION_UNVERIFIED
            assert call_kwargs["obj"] == cert
            assert call_kwargs["actor"] == staff_user


@pytest.mark.django_db
class TestAddCertificationAudit:
    """Tests for audit logging when adding certifications."""

    def test_add_certification_logs_audit_event(self, diver, padi_open_water, staff_user):
        """add_certification() logs an audit event via django_audit_log."""
        with patch(AUDIT_LOG_PATCH) as mock_log:
            cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == Actions.CERTIFICATION_ADDED
            assert call_kwargs["obj"] == cert
            assert call_kwargs["actor"] == staff_user


@pytest.mark.django_db
class TestUpdateCertificationAudit:
    """Tests for audit logging when updating certifications."""

    def test_update_certification_logs_audit_event_with_changes(self, diver, padi_open_water, staff_user):
        """update_certification() logs an audit event with field changes."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user, card_number="OLD")

        with patch(AUDIT_LOG_PATCH) as mock_log:
            update_certification(cert, staff_user, card_number="NEW123")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == Actions.CERTIFICATION_UPDATED
            assert call_kwargs["obj"] == cert
            assert call_kwargs["actor"] == staff_user
            assert call_kwargs["changes"]["card_number"]["old"] == "OLD"
            assert call_kwargs["changes"]["card_number"]["new"] == "NEW123"

    def test_update_no_changes_does_not_log(self, diver, padi_open_water, staff_user):
        """update_certification() does not log if no changes are made."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user, card_number="SAME")

        with patch(AUDIT_LOG_PATCH) as mock_log:
            # Pass same value - should not trigger audit
            update_certification(cert, staff_user, card_number="SAME")

            mock_log.assert_not_called()


@pytest.mark.django_db
class TestRemoveCertificationAudit:
    """Tests for audit logging when removing certifications."""

    def test_remove_certification_logs_audit_event(self, diver, padi_open_water, staff_user):
        """remove_certification() logs an audit event via django_audit_log."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        with patch(AUDIT_LOG_PATCH) as mock_log:
            remove_certification(cert, staff_user)

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == Actions.CERTIFICATION_REMOVED
            assert call_kwargs["obj"] == cert
            assert call_kwargs["actor"] == staff_user


@pytest.mark.django_db
class TestAuditAdapterActions:
    """Tests verifying stable action constants are used correctly."""

    def test_action_constants_are_stable_strings(self):
        """Action constants are stable strings per the audit contract."""
        assert Actions.CERTIFICATION_ADDED == "certification_added"
        assert Actions.CERTIFICATION_UPDATED == "certification_updated"
        assert Actions.CERTIFICATION_REMOVED == "certification_removed"
        assert Actions.CERTIFICATION_VERIFIED == "certification_verified"
        assert Actions.CERTIFICATION_UNVERIFIED == "certification_unverified"

    def test_actions_are_used_consistently(self, diver, padi_open_water, staff_user):
        """Verify all certification services use the correct action constants."""
        actions_called = []

        with patch(AUDIT_LOG_PATCH) as mock_log:
            mock_log.side_effect = lambda **kwargs: actions_called.append(kwargs["action"])

            cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
            verify_certification(cert, staff_user)
            unverify_certification(cert, staff_user)
            update_certification(cert, staff_user, card_number="NEW")
            remove_certification(cert, staff_user)

        assert actions_called == [
            Actions.CERTIFICATION_ADDED,
            Actions.CERTIFICATION_VERIFIED,
            Actions.CERTIFICATION_UNVERIFIED,
            Actions.CERTIFICATION_UPDATED,
            Actions.CERTIFICATION_REMOVED,
        ]


@pytest.mark.django_db
class TestFormAuditLogging:
    """Tests for audit logging through DiverCertificationForm (staff portal path).

    Forms now delegate to services which handle audit. These tests verify that
    audit events are created, using behavior-based assertions.
    """

    def test_form_save_logs_add_event(self, diver, padi_open_water, staff_user):
        """DiverCertificationForm.save() logs audit event when creating certification."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.forms import DiverCertificationForm

        initial_count = AuditLog.objects.count()

        form_data = {
            "diver": diver.pk,
            "level": padi_open_water.pk,
            "card_number": "FORM123",
            "issued_on": date(2024, 1, 15),
            "expires_on": "",
        }
        form = DiverCertificationForm(data=form_data)
        assert form.is_valid(), form.errors
        cert = form.save(actor=staff_user)

        # Verify audit log was created via service
        assert AuditLog.objects.count() == initial_count + 1
        log = AuditLog.objects.order_by("-created_at").first()
        assert log.action == Actions.CERTIFICATION_ADDED
        assert log.actor_user_id == staff_user.pk

    def test_form_save_logs_update_event_with_changes(self, diver, padi_open_water, staff_user):
        """DiverCertificationForm.save() logs audit event when updating certification."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.forms import DiverCertificationForm

        # Create existing certification
        cert = DiverCertification.objects.create(
            diver=diver,
            level=padi_open_water,
            card_number="OLD_NUMBER",
            issued_on=date(2024, 1, 1),
        )

        initial_count = AuditLog.objects.count()

        # Update via form
        form_data = {
            "diver": diver.pk,
            "level": padi_open_water.pk,
            "card_number": "NEW_NUMBER",
            "issued_on": date(2024, 1, 1),
            "expires_on": "",
        }
        form = DiverCertificationForm(data=form_data, instance=cert)
        assert form.is_valid(), form.errors
        updated_cert = form.save(actor=staff_user)

        # Verify audit log was created via service
        assert AuditLog.objects.count() == initial_count + 1
        log = AuditLog.objects.order_by("-created_at").first()
        assert log.action == Actions.CERTIFICATION_UPDATED
        assert log.actor_user_id == staff_user.pk
        # Changes are stored in metadata
        assert "card_number" in str(log.changes)

    def test_form_save_no_audit_when_no_changes(self, diver, padi_open_water, staff_user):
        """DiverCertificationForm.save() does not log when no changes made."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.forms import DiverCertificationForm

        # Create existing certification
        cert = DiverCertification.objects.create(
            diver=diver,
            level=padi_open_water,
            card_number="SAME",
            issued_on=date(2024, 1, 1),
        )

        initial_count = AuditLog.objects.count()

        # Submit same data
        form_data = {
            "diver": diver.pk,
            "level": padi_open_water.pk,
            "card_number": "SAME",
            "issued_on": date(2024, 1, 1),
            "expires_on": "",
        }
        form = DiverCertificationForm(data=form_data, instance=cert)
        assert form.is_valid(), form.errors
        form.save(actor=staff_user)

        # No audit log should be created (no changes)
        assert AuditLog.objects.count() == initial_count

    def test_form_save_without_actor(self, diver, padi_open_water):
        """DiverCertificationForm.save() works but actor is None in audit."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form_data = {
            "diver": diver.pk,
            "level": padi_open_water.pk,
            "card_number": "NO_ACTOR",
            "issued_on": date(2024, 1, 15),
            "expires_on": "",
        }
        form = DiverCertificationForm(data=form_data)
        assert form.is_valid(), form.errors

        with patch(AUDIT_LOG_PATCH) as mock_log:
            cert = form.save()  # No actor passed

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["actor"] is None
