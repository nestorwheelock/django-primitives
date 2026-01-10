"""Tests for BaseModel migration.

These tests verify that all DiveOps models properly inherit from
django_basemodels.BaseModel and do not duplicate base functionality.

Per CLAUDE.md: All domain models MUST inherit from BaseModel.
Per DiveOps ARCHITECTURE.md: No local soft delete implementations.
"""

import uuid

import pytest
from django.utils import timezone

from django_basemodels.models import BaseModel, SoftDeleteManager


# =============================================================================
# BaseModel Inheritance Tests
# =============================================================================


@pytest.mark.django_db
class TestBaseModelInheritance:
    """Verify all models inherit from django_basemodels.BaseModel."""

    def test_certification_level_inherits_basemodel(self):
        """CertificationLevel must inherit from BaseModel."""
        from primitives_testbed.diveops.models import CertificationLevel

        assert issubclass(CertificationLevel, BaseModel), (
            "CertificationLevel must inherit from django_basemodels.BaseModel"
        )

    def test_diver_certification_inherits_basemodel(self):
        """DiverCertification must inherit from BaseModel."""
        from primitives_testbed.diveops.models import DiverCertification

        assert issubclass(DiverCertification, BaseModel), (
            "DiverCertification must inherit from django_basemodels.BaseModel"
        )

    def test_trip_requirement_inherits_basemodel(self):
        """ExcursionRequirement must inherit from BaseModel."""
        from primitives_testbed.diveops.models import ExcursionRequirement

        assert issubclass(ExcursionRequirement, BaseModel), (
            "ExcursionRequirement must inherit from django_basemodels.BaseModel"
        )

    def test_diver_profile_inherits_basemodel(self):
        """DiverProfile must inherit from BaseModel."""
        from primitives_testbed.diveops.models import DiverProfile

        assert issubclass(DiverProfile, BaseModel), (
            "DiverProfile must inherit from django_basemodels.BaseModel"
        )

    def test_dive_site_inherits_basemodel(self):
        """DiveSite must inherit from BaseModel."""
        from primitives_testbed.diveops.models import DiveSite

        assert issubclass(DiveSite, BaseModel), (
            "DiveSite must inherit from django_basemodels.BaseModel"
        )

    def test_dive_trip_inherits_basemodel(self):
        """Excursion must inherit from BaseModel."""
        from primitives_testbed.diveops.models import Excursion

        assert issubclass(Excursion, BaseModel), (
            "Excursion must inherit from django_basemodels.BaseModel"
        )

    def test_booking_inherits_basemodel(self):
        """Booking must inherit from BaseModel."""
        from primitives_testbed.diveops.models import Booking

        assert issubclass(Booking, BaseModel), (
            "Booking must inherit from django_basemodels.BaseModel"
        )

    def test_trip_roster_inherits_basemodel(self):
        """ExcursionRoster must inherit from BaseModel."""
        from primitives_testbed.diveops.models import ExcursionRoster

        assert issubclass(ExcursionRoster, BaseModel), (
            "ExcursionRoster must inherit from django_basemodels.BaseModel"
        )


# =============================================================================
# No Local SoftDeleteManager Tests
# =============================================================================


@pytest.mark.django_db
class TestNoLocalSoftDeleteManager:
    """Verify local SoftDeleteManager is not defined in models.py."""

    def test_no_local_soft_delete_manager_class(self):
        """models.py must not define its own SoftDeleteManager."""
        import primitives_testbed.diveops.models as models_module

        # Check that SoftDeleteManager is not defined locally
        # It should be imported from django_basemodels if needed
        if hasattr(models_module, "SoftDeleteManager"):
            # If it exists, it must be the one from django_basemodels
            assert models_module.SoftDeleteManager is SoftDeleteManager, (
                "SoftDeleteManager must be from django_basemodels, not locally defined"
            )


# =============================================================================
# Soft Delete Behavior Tests (for models that should have it)
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteBehavior:
    """Verify soft delete works correctly via BaseModel."""

    def test_certification_level_soft_delete(self, padi_agency):
        """CertificationLevel.delete() sets deleted_at, not hard delete."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="test_sd",
            name="Test Soft Delete",
            rank=99,
        )
        pk = level.pk

        # Soft delete
        level.delete()

        # Should not exist in default queryset
        assert CertificationLevel.objects.filter(pk=pk).count() == 0

        # Should exist in all_objects
        deleted = CertificationLevel.all_objects.get(pk=pk)
        assert deleted.deleted_at is not None
        assert deleted.is_deleted is True

    def test_certification_level_restore(self, padi_agency):
        """CertificationLevel can be restored after soft delete."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="test_restore",
            name="Test Restore",
            rank=98,
        )
        pk = level.pk

        level.delete()
        assert CertificationLevel.objects.filter(pk=pk).count() == 0

        # Restore
        deleted = CertificationLevel.all_objects.get(pk=pk)
        deleted.restore()

        # Should be back in default queryset
        restored = CertificationLevel.objects.get(pk=pk)
        assert restored.deleted_at is None
        assert restored.is_deleted is False

    def test_diver_certification_soft_delete(self, diver_profile, padi_open_water):
        """DiverCertification.delete() sets deleted_at."""
        from primitives_testbed.diveops.models import DiverCertification

        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="SD123",
        )
        pk = cert.pk

        cert.delete()

        assert DiverCertification.objects.filter(pk=pk).count() == 0
        deleted = DiverCertification.all_objects.get(pk=pk)
        assert deleted.is_deleted is True

    def test_trip_requirement_soft_delete(self, dive_trip):
        """ExcursionRequirement.delete() sets deleted_at."""
        from primitives_testbed.diveops.models import ExcursionRequirement

        req = ExcursionRequirement.objects.create(
            excursion=dive_trip,
            requirement_type="gear",
            description="Test gear requirement",
        )
        pk = req.pk

        req.delete()

        assert ExcursionRequirement.objects.filter(pk=pk).count() == 0
        deleted = ExcursionRequirement.all_objects.get(pk=pk)
        assert deleted.is_deleted is True


# =============================================================================
# UUID and Timestamp Tests
# =============================================================================


@pytest.mark.django_db
class TestUUIDAndTimestamps:
    """Verify UUID and timestamp fields from BaseModel."""

    def test_certification_level_has_uuid_pk(self, padi_agency):
        """CertificationLevel.id is a UUID."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="uuid_test",
            name="UUID Test",
            rank=97,
        )
        assert isinstance(level.pk, uuid.UUID)

    def test_certification_level_has_timestamps(self, padi_agency):
        """CertificationLevel has created_at and updated_at from BaseModel."""
        from primitives_testbed.diveops.models import CertificationLevel

        before = timezone.now()
        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="ts_test",
            name="Timestamp Test",
            rank=96,
        )
        after = timezone.now()

        assert level.created_at is not None
        assert level.updated_at is not None
        assert before <= level.created_at <= after

    def test_diver_profile_has_uuid_pk(self, diver_profile):
        """DiverProfile.id is a UUID."""
        assert isinstance(diver_profile.pk, uuid.UUID)

    def test_diver_profile_has_timestamps(self, diver_profile):
        """DiverProfile has created_at and updated_at."""
        assert diver_profile.created_at is not None
        assert diver_profile.updated_at is not None

    def test_dive_trip_has_uuid_pk(self, dive_trip):
        """Excursion.id is a UUID."""
        assert isinstance(dive_trip.pk, uuid.UUID)

    def test_booking_has_uuid_pk(self, dive_trip, diver_profile, user):
        """Booking.id is a UUID."""
        from primitives_testbed.diveops.models import Booking

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            booked_by=user,
        )
        assert isinstance(booking.pk, uuid.UUID)

    def test_trip_roster_has_uuid_pk(self, dive_trip, diver_profile, user):
        """ExcursionRoster.id is a UUID."""
        from primitives_testbed.diveops.models import Booking, ExcursionRoster

        booking = Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            booked_by=user,
        )
        roster = ExcursionRoster.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            booking=booking,
            checked_in_by=user,
        )
        assert isinstance(roster.pk, uuid.UUID)


# =============================================================================
# Manager Tests
# =============================================================================


@pytest.mark.django_db
class TestManagerBehavior:
    """Verify manager behavior from BaseModel."""

    def test_objects_excludes_deleted(self, padi_agency):
        """Model.objects excludes soft-deleted records."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="mgr_test",
            name="Manager Test",
            rank=95,
        )
        pk = level.pk

        # Before delete: visible in objects
        assert CertificationLevel.objects.filter(pk=pk).exists()

        level.delete()

        # After delete: not visible in objects
        assert not CertificationLevel.objects.filter(pk=pk).exists()

    def test_all_objects_includes_deleted(self, padi_agency):
        """Model.all_objects includes soft-deleted records."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="all_mgr_test",
            name="All Manager Test",
            rank=94,
        )
        pk = level.pk

        level.delete()

        # Visible in all_objects
        assert CertificationLevel.all_objects.filter(pk=pk).exists()

    def test_with_deleted_queryset_method(self, padi_agency):
        """Model.objects.with_deleted() includes deleted records."""
        from primitives_testbed.diveops.models import CertificationLevel

        level = CertificationLevel.objects.create(
            agency=padi_agency,
            code="with_del_test",
            name="With Deleted Test",
            rank=93,
        )
        pk = level.pk

        level.delete()

        # with_deleted() should find it
        assert CertificationLevel.objects.with_deleted().filter(pk=pk).exists()
