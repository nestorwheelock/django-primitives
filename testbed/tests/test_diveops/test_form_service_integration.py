"""Tests for form-to-service integration.

These tests verify that DiveOps forms call services instead of
emitting audit events directly.

Per CLAUDE.md: All writes MUST go through service functions.
Per DiveOps ARCHITECTURE.md: Forms call services, services emit audit.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone

from django_basemodels.models import BaseModel

from primitives_testbed.diveops.forms import DiverForm, DiverCertificationForm
from primitives_testbed.diveops.models import DiverCertification, DiverProfile


# =============================================================================
# Diver Service Tests
# =============================================================================


@pytest.mark.django_db
class TestCreateDiverService:
    """Tests for create_diver service function."""

    def test_create_diver_service_exists(self):
        """create_diver function must exist in services."""
        from primitives_testbed.diveops.services import create_diver

        assert callable(create_diver)

    def test_create_diver_creates_person_and_profile(self, user, padi_agency):
        """create_diver creates Person and DiverProfile."""
        from primitives_testbed.diveops.services import create_diver

        diver = create_diver(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            total_dives=50,
            created_by=user,
        )

        assert diver is not None
        assert isinstance(diver, DiverProfile)
        assert diver.person.first_name == "John"
        assert diver.person.last_name == "Doe"
        assert diver.person.email == "john@example.com"
        assert diver.total_dives == 50

    def test_create_diver_emits_audit_event(self, user, padi_agency):
        """create_diver emits DIVER_CREATED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.services import create_diver

        initial_count = AuditLog.objects.count()

        diver = create_diver(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            total_dives=25,
            created_by=user,
        )

        # Check audit log was created
        assert AuditLog.objects.count() == initial_count + 1
        log = AuditLog.objects.order_by("-created_at").first()
        assert log.action == "diver_created"  # Matches Actions.DIVER_CREATED
        assert log.actor_user_id == user.pk  # AuditLog stores actor_user FK


@pytest.mark.django_db
class TestUpdateDiverService:
    """Tests for update_diver service function."""

    def test_update_diver_service_exists(self):
        """update_diver function must exist in services."""
        from primitives_testbed.diveops.services import update_diver

        assert callable(update_diver)

    def test_update_diver_updates_person_and_profile(self, diver_profile, user):
        """update_diver updates Person and DiverProfile."""
        from primitives_testbed.diveops.services import update_diver

        updated = update_diver(
            diver=diver_profile,
            first_name="Updated",
            last_name="Name",
            email="updated@example.com",
            total_dives=100,
            updated_by=user,
        )

        diver_profile.refresh_from_db()
        diver_profile.person.refresh_from_db()

        assert diver_profile.person.first_name == "Updated"
        assert diver_profile.person.last_name == "Name"
        assert diver_profile.person.email == "updated@example.com"
        assert diver_profile.total_dives == 100

    def test_update_diver_emits_audit_event(self, diver_profile, user):
        """update_diver emits DIVER_UPDATED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.services import update_diver

        initial_count = AuditLog.objects.count()

        update_diver(
            diver=diver_profile,
            first_name="Changed",
            updated_by=user,
        )

        assert AuditLog.objects.count() == initial_count + 1
        log = AuditLog.objects.order_by("-created_at").first()
        assert log.action == "diver_updated"  # Matches Actions.DIVER_UPDATED


# =============================================================================
# Form-to-Service Integration Tests
# =============================================================================


@pytest.mark.django_db
class TestDiverFormCallsServices:
    """Verify DiverForm.save() calls service functions, not audit directly."""

    def test_diver_form_save_does_not_import_audit_directly(self, user, padi_agency):
        """DiverForm.save() must not import log_certification_event directly."""
        import inspect

        # Get the source code of DiverForm.save
        source = inspect.getsource(DiverForm.save)

        # It should NOT contain direct log_certification_event import/call
        # (It should delegate to add_certification service which handles audit)
        assert "from .audit import" not in source or "log_certification_event" not in source.split("from .audit import")[1].split("\n")[0], \
            "DiverForm.save() should not import log_certification_event directly"

    def test_diver_form_imports_services(self, user, padi_agency):
        """DiverForm.save() must import service functions."""
        import inspect

        source = inspect.getsource(DiverForm.save)

        # Should import from services
        assert "from .services import" in source, \
            "DiverForm.save() should import from services"
        assert "create_diver" in source, \
            "DiverForm.save() should use create_diver service"
        assert "update_diver" in source, \
            "DiverForm.save() should use update_diver service"

    def test_diver_form_save_creates_diver_with_audit(self, user, padi_agency):
        """DiverForm.save() creates diver and audit event via service."""
        from django_audit_log.models import AuditLog

        initial_count = AuditLog.objects.count()

        form = DiverForm(data={
            "first_name": "Form",
            "last_name": "Test",
            "email": "formtest@example.com",
            "total_dives": 10,
        })

        assert form.is_valid(), form.errors
        diver = form.save(actor=user)

        # Verify diver created
        assert diver is not None
        assert diver.person.first_name == "Form"

        # Verify audit event emitted (by service)
        assert AuditLog.objects.count() > initial_count


@pytest.mark.django_db
class TestDiverCertificationFormCallsServices:
    """Verify DiverCertificationForm.save() calls service functions."""

    def test_certification_form_save_does_not_import_audit_directly(self):
        """DiverCertificationForm.save() must not import log_certification_event."""
        import inspect

        source = inspect.getsource(DiverCertificationForm.save)

        # After refactor, should not contain direct audit import
        assert "from .audit import" not in source or "log_certification_event" not in source.split("from .audit import")[1].split("\n")[0], \
            "DiverCertificationForm.save() should not import log_certification_event directly"

    def test_certification_form_imports_services(self):
        """DiverCertificationForm.save() must import service functions."""
        import inspect

        source = inspect.getsource(DiverCertificationForm.save)

        # Should import from services
        assert "from .services import" in source, \
            "DiverCertificationForm.save() should import from services"
        assert "add_certification" in source, \
            "DiverCertificationForm.save() should use add_certification service"
        assert "update_certification" in source, \
            "DiverCertificationForm.save() should use update_certification service"

    def test_certification_form_save_creates_cert_with_audit(
        self, diver_profile, padi_open_water, user
    ):
        """DiverCertificationForm.save() creates cert and audit event via service."""
        from django_audit_log.models import AuditLog

        initial_count = AuditLog.objects.count()

        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": padi_open_water.pk,
            "card_number": "FORM-001",
        })

        assert form.is_valid(), form.errors
        cert = form.save(actor=user)

        # Verify cert created
        assert cert is not None
        assert cert.card_number == "FORM-001"

        # Verify audit event emitted (by service)
        assert AuditLog.objects.count() > initial_count


# =============================================================================
# Audit Event Origin Tests
# =============================================================================


@pytest.mark.django_db
class TestAuditEventsFromServicesOnly:
    """Verify audit events originate from services, not forms."""

    def test_certification_audit_from_service_has_correct_source(
        self, diver_profile, padi_open_water, user
    ):
        """Certification audit events must come from service layer."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.services import add_certification

        # Call service directly
        cert = add_certification(
            diver=diver_profile,
            level=padi_open_water,
            added_by=user,
            card_number="SVC-001",
        )

        # Verify audit was created
        log = AuditLog.objects.order_by("-created_at").first()
        assert log.action == "certification_added"  # Matches Actions.CERTIFICATION_ADDED
        assert log.actor_user_id == user.pk  # AuditLog stores actor_user FK

    def test_diver_audit_from_service_has_correct_source(self, user, padi_agency):
        """Diver audit events must come from service layer."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.services import create_diver

        diver = create_diver(
            first_name="Service",
            last_name="Test",
            email="svc@example.com",
            total_dives=0,
            created_by=user,
        )

        log = AuditLog.objects.order_by("-created_at").first()
        assert log.action == "diver_created"  # Matches Actions.DIVER_CREATED
        assert log.actor_user_id == user.pk
