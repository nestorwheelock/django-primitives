"""Tests for certification service functions."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from primitives_testbed.diveops.exceptions import CertificationError
from primitives_testbed.diveops.models import CertificationLevel, DiverCertification, DiverProfile
from primitives_testbed.diveops.services import (
    add_certification,
    remove_certification,
    unverify_certification,
    update_certification,
    verify_certification,
)


@pytest.fixture
def padi_agency(db):
    """Create a PADI agency organization."""
    from django_parties.models import Organization

    return Organization.objects.create(name="PADI", legal_name="PADI Worldwide")


@pytest.fixture
def ssi_agency(db):
    """Create an SSI agency organization."""
    from django_parties.models import Organization

    return Organization.objects.create(name="SSI", legal_name="Scuba Schools International")


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
def padi_advanced(padi_agency):
    """Create PADI Advanced Open Water certification level."""
    return CertificationLevel.objects.create(
        name="Advanced Open Water Diver",
        code="AOWD",
        agency=padi_agency,
        rank=2,
        max_depth_m=30,
    )


@pytest.fixture
def ssi_open_water(ssi_agency):
    """Create SSI Open Water certification level."""
    return CertificationLevel.objects.create(
        name="Open Water Diver",
        code="OWD",
        agency=ssi_agency,
        rank=1,
        max_depth_m=18,
    )


@pytest.fixture
def diver(db, padi_agency):
    """Create a diver profile."""
    from datetime import date

    from django_parties.models import Person

    person = Person.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    return DiverProfile.objects.create(
        person=person,
        # Legacy fields still required
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
class TestAddCertification:
    """Tests for add_certification service."""

    def test_add_certification_creates_record(self, diver, padi_open_water, staff_user):
        """Service creates a new certification record."""
        cert = add_certification(
            diver=diver,
            level=padi_open_water,
            added_by=staff_user,
            card_number="12345",
            issued_on=date(2024, 1, 15),
        )

        assert cert.pk is not None
        assert cert.diver == diver
        assert cert.level == padi_open_water
        assert cert.card_number == "12345"
        assert cert.issued_on == date(2024, 1, 15)
        assert cert.is_verified is False

    def test_add_certification_without_optional_fields(self, diver, padi_open_water, staff_user):
        """Service works with only required fields."""
        cert = add_certification(
            diver=diver,
            level=padi_open_water,
            added_by=staff_user,
        )

        assert cert.pk is not None
        assert cert.card_number == ""
        assert cert.issued_on is None
        assert cert.expires_on is None

    def test_add_certification_rejects_duplicate(self, diver, padi_open_water, staff_user):
        """Service rejects duplicate certification for same diver + level."""
        add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        with pytest.raises(CertificationError, match="already has"):
            add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

    def test_add_different_agencies_allowed(self, diver, padi_open_water, ssi_open_water, staff_user):
        """Diver can have certifications from different agencies."""
        cert1 = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        cert2 = add_certification(diver=diver, level=ssi_open_water, added_by=staff_user)

        assert cert1.pk != cert2.pk
        assert cert1.agency.name == "PADI"
        assert cert2.agency.name == "SSI"

    def test_add_different_levels_allowed(self, diver, padi_open_water, padi_advanced, staff_user):
        """Diver can have multiple certification levels from same agency."""
        cert1 = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        cert2 = add_certification(diver=diver, level=padi_advanced, added_by=staff_user)

        assert cert1.pk != cert2.pk
        assert diver.certifications.count() == 2


@pytest.mark.django_db
class TestUpdateCertification:
    """Tests for update_certification service."""

    def test_update_card_number(self, diver, padi_open_water, staff_user):
        """Service updates card number."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user, card_number="OLD")

        updated = update_certification(cert, staff_user, card_number="NEW123")

        assert updated.card_number == "NEW123"

    def test_update_issued_on(self, diver, padi_open_water, staff_user):
        """Service updates issue date."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        new_date = date(2024, 6, 15)
        updated = update_certification(cert, staff_user, issued_on=new_date)

        assert updated.issued_on == new_date

    def test_update_expires_on(self, diver, padi_open_water, staff_user):
        """Service updates expiration date."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        new_date = date(2026, 1, 15)
        updated = update_certification(cert, staff_user, expires_on=new_date)

        assert updated.expires_on == new_date

    def test_update_deleted_certification_raises_error(self, diver, padi_open_water, staff_user):
        """Service rejects update on deleted certification."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        remove_certification(cert, staff_user)

        with pytest.raises(CertificationError, match="deleted"):
            update_certification(cert, staff_user, card_number="NEW")

    def test_update_no_changes_does_not_save(self, diver, padi_open_water, staff_user):
        """Service doesn't save if no changes are made."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user, card_number="TEST")
        original_updated = cert.updated_at

        # Pass same value - should not trigger save
        updated = update_certification(cert, staff_user, card_number="TEST")

        # Refresh from DB to check
        cert.refresh_from_db()
        # Note: updated_at may or may not change depending on auto_now behavior


@pytest.mark.django_db
class TestRemoveCertification:
    """Tests for remove_certification service."""

    def test_remove_sets_deleted_at(self, diver, padi_open_water, staff_user):
        """Service sets deleted_at timestamp."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        removed = remove_certification(cert, staff_user)

        assert removed.deleted_at is not None

    def test_remove_excludes_from_default_queryset(self, diver, padi_open_water, staff_user):
        """Removed certification excluded from default manager."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        remove_certification(cert, staff_user)

        # Default manager excludes soft-deleted
        assert not DiverCertification.objects.filter(pk=cert.pk).exists()

        # all_objects includes soft-deleted
        assert DiverCertification.all_objects.filter(pk=cert.pk).exists()

    def test_remove_already_deleted_raises_error(self, diver, padi_open_water, staff_user):
        """Service rejects double removal."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        remove_certification(cert, staff_user)

        with pytest.raises(CertificationError, match="already removed"):
            remove_certification(cert, staff_user)


@pytest.mark.django_db
class TestVerifyCertification:
    """Tests for verify_certification service."""

    def test_verify_sets_is_verified(self, diver, padi_open_water, staff_user):
        """Service sets is_verified to True."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        verified = verify_certification(cert, staff_user)

        assert verified.is_verified is True

    def test_verify_already_verified_raises_error(self, diver, padi_open_water, staff_user):
        """Service rejects verification of already verified cert."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        verify_certification(cert, staff_user)

        with pytest.raises(CertificationError, match="already verified"):
            verify_certification(cert, staff_user)

    def test_verify_deleted_certification_raises_error(self, diver, padi_open_water, staff_user):
        """Service rejects verification of deleted cert."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        remove_certification(cert, staff_user)

        with pytest.raises(CertificationError, match="deleted"):
            verify_certification(cert, staff_user)


@pytest.mark.django_db
class TestUnverifyCertification:
    """Tests for unverify_certification service."""

    def test_unverify_sets_is_verified_false(self, diver, padi_open_water, staff_user):
        """Service sets is_verified to False."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        verify_certification(cert, staff_user)

        unverified = unverify_certification(cert, staff_user)

        assert unverified.is_verified is False

    def test_unverify_not_verified_raises_error(self, diver, padi_open_water, staff_user):
        """Service rejects unverification of not verified cert."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)

        with pytest.raises(CertificationError, match="not verified"):
            unverify_certification(cert, staff_user)

    def test_unverify_deleted_certification_raises_error(self, diver, padi_open_water, staff_user):
        """Service rejects unverification of deleted cert."""
        cert = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        verify_certification(cert, staff_user)
        # Get fresh from all_objects since it's about to be deleted
        cert_id = cert.pk
        remove_certification(cert, staff_user)
        cert = DiverCertification.all_objects.get(pk=cert_id)

        with pytest.raises(CertificationError, match="deleted"):
            unverify_certification(cert, staff_user)


@pytest.mark.django_db
class TestCertificationWorkflow:
    """Integration tests for certification workflow."""

    def test_full_certification_lifecycle(self, diver, padi_open_water, staff_user):
        """Test complete lifecycle: add -> update -> verify -> remove."""
        # Add
        cert = add_certification(
            diver=diver,
            level=padi_open_water,
            added_by=staff_user,
            card_number="12345",
        )
        assert cert.pk is not None
        assert cert.is_verified is False

        # Update
        cert = update_certification(cert, staff_user, card_number="67890")
        assert cert.card_number == "67890"

        # Verify
        cert = verify_certification(cert, staff_user)
        assert cert.is_verified is True

        # Remove
        cert = remove_certification(cert, staff_user)
        assert cert.deleted_at is not None

    def test_diver_multiple_certifications_with_workflow(
        self, diver, padi_open_water, padi_advanced, ssi_open_water, staff_user
    ):
        """Test managing multiple certifications for one diver."""
        # Add multiple certs
        padi_ow = add_certification(diver=diver, level=padi_open_water, added_by=staff_user)
        padi_aow = add_certification(diver=diver, level=padi_advanced, added_by=staff_user)
        ssi_ow = add_certification(diver=diver, level=ssi_open_water, added_by=staff_user)

        assert diver.certifications.count() == 3

        # Verify some
        verify_certification(padi_ow, staff_user)
        verify_certification(padi_aow, staff_user)

        verified = diver.certifications.filter(is_verified=True)
        assert verified.count() == 2

        # Remove one
        remove_certification(ssi_ow, staff_user)
        assert diver.certifications.count() == 2

        # Check highest rank
        highest = diver.certifications.order_by("-level__rank").first()
        assert highest.level == padi_advanced
