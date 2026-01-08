"""Tests for T-003: Agreement Creation on Booking.

This module tests that bookings can be governed by legal terms via
django_agreements integration.

Requirements:
- book_excursion() optionally creates a waiver/cancellation Agreement
- Agreement is linked via Booking.waiver_agreement FK
- Agreement terms are stored immutably
- Agreement lifecycle is auditable
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-003: Agreement Creation on Booking Tests
# =============================================================================


@pytest.mark.django_db
class TestBookingAgreementCreation:
    """Test: book_excursion() creates agreement when requested."""

    def test_booking_without_agreement_has_null_fk(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Default booking has null waiver_agreement."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_t003", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive T003",
            slug="test-dive-t003",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        assert booking.waiver_agreement is None

    def test_booking_with_agreement_creates_agreement(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """book_excursion with create_agreement=True creates Agreement."""
        from django_agreements.models import Agreement

        from primitives_testbed.diveops.cancellation_policy import (
            DEFAULT_CANCELLATION_POLICY,
        )
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_agr", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Agreement",
            slug="test-dive-agreement",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        initial_agreement_count = Agreement.objects.count()

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )

        assert booking.waiver_agreement is not None
        assert Agreement.objects.count() == initial_agreement_count + 1
        assert booking.waiver_agreement.scope_type == "booking_waiver"

    def test_agreement_links_correct_parties(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Agreement party_a is diver, party_b is dive_shop."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_party", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Party",
            slug="test-dive-party",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )

        agreement = booking.waiver_agreement
        # party_a is the diver's person
        assert str(agreement.party_a_id) == str(diver_profile.person.pk)
        # party_b is the dive shop organization
        assert str(agreement.party_b_id) == str(dive_shop.pk)


@pytest.mark.django_db
class TestAgreementTermsImmutability:
    """Test: Agreement terms are stored immutably."""

    def test_agreement_stores_cancellation_policy_terms(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Agreement terms contain cancellation policy."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_terms", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Terms",
            slug="test-dive-terms",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )

        terms = booking.waiver_agreement.terms
        assert "cancellation_policy" in terms
        assert "version" in terms["cancellation_policy"]
        assert "tiers" in terms["cancellation_policy"]

    def test_agreement_terms_include_booking_reference(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Agreement terms include booking_id for reference."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_ref", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Ref",
            slug="test-dive-ref",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )

        terms = booking.waiver_agreement.terms
        assert "booking_id" in terms
        assert terms["booking_id"] == str(booking.pk)

    def test_agreement_has_version_record(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Agreement has immutable AgreementVersion record."""
        from django_agreements.models import AgreementVersion

        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_vers", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Version",
            slug="test-dive-version",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )

        agreement = booking.waiver_agreement
        versions = AgreementVersion.objects.filter(agreement=agreement)
        assert versions.count() == 1
        assert versions.first().version == 1
        assert versions.first().terms == agreement.terms


@pytest.mark.django_db
class TestAgreementCustomPolicy:
    """Test: Custom cancellation policy can be provided."""

    def test_custom_cancellation_policy_stored(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Custom policy is stored in agreement terms."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_cust", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Custom",
            slug="test-dive-custom",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        custom_policy = {
            "version": 1,
            "tiers": [
                {"hours_before": 72, "refund_percent": 100},
                {"hours_before": 0, "refund_percent": 0},
            ],
        }

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
            cancellation_policy=custom_policy,
        )

        terms = booking.waiver_agreement.terms
        assert terms["cancellation_policy"]["tiers"][0]["hours_before"] == 72

    def test_invalid_policy_raises_error(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Invalid cancellation policy raises ValueError."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_inv", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Invalid",
            slug="test-dive-invalid",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        invalid_policy = {"tiers": []}  # Missing version, empty tiers

        with pytest.raises(ValueError, match="cancellation.*policy"):
            book_excursion(
                excursion=excursion,
                diver=diver_profile,
                booked_by=user,
                skip_eligibility_check=True,
                create_agreement=True,
                cancellation_policy=invalid_policy,
            )


@pytest.mark.django_db
class TestAgreementAuditEvents:
    """Test: Agreement lifecycle emits audit events."""

    def test_agreement_creation_emits_audit_event(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Creating agreement emits audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.audit import Actions
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow_audit", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive Audit",
            slug="test-dive-audit",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),
            currency="USD",
            created_by=user,
        )

        initial_count = AuditLog.objects.count()

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
            create_agreement=True,
        )

        # Should have at least 2 audit events: booking_created + agreement_created
        assert AuditLog.objects.count() >= initial_count + 2

        # Find agreement audit event
        agreement_events = AuditLog.objects.filter(
            action=Actions.AGREEMENT_CREATED
        )
        assert agreement_events.exists()


@pytest.mark.django_db
class TestBookingModelAgreementFK:
    """Test: Booking model has waiver_agreement FK."""

    def test_booking_has_waiver_agreement_field(self, db):
        """Booking model has waiver_agreement FK to Agreement."""
        from primitives_testbed.diveops.models import Booking

        field = Booking._meta.get_field("waiver_agreement")
        assert field is not None
        assert field.get_internal_type() == "ForeignKey"
        assert field.null is True
        assert field.blank is True
