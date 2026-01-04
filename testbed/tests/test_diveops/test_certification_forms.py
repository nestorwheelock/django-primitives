"""Tests for certification model forms."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from primitives_testbed.diveops.models import CertificationLevel, DiverCertification


@pytest.mark.django_db
class TestCertificationLevelForm:
    """Tests for CertificationLevelForm."""

    @pytest.fixture
    def padi_agency(self):
        from django_parties.models import Organization
        return Organization.objects.create(
            name="PADI",
            org_type="other",
        )

    def test_form_exists(self):
        """CertificationLevelForm can be imported."""
        from primitives_testbed.diveops.forms import CertificationLevelForm
        assert CertificationLevelForm is not None

    def test_form_valid_data(self, padi_agency):
        """Form accepts valid certification level data."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "agency": padi_agency.pk,
            "code": "ow",
            "name": "Open Water Diver",
            "rank": 2,
            "description": "Basic scuba certification",
            "is_active": True,
        })

        assert form.is_valid(), form.errors
        level = form.save()
        assert level.pk is not None
        assert level.code == "ow"
        assert level.agency == padi_agency

    def test_form_requires_agency(self, padi_agency):
        """Form requires agency field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "code": "ow",
            "name": "Open Water Diver",
            "rank": 2,
        })

        assert not form.is_valid()
        assert "agency" in form.errors

    def test_form_requires_code(self, padi_agency):
        """Form requires code field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "agency": padi_agency.pk,
            "name": "Open Water Diver",
            "rank": 2,
        })

        assert not form.is_valid()
        assert "code" in form.errors

    def test_form_requires_name(self, padi_agency):
        """Form requires name field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "agency": padi_agency.pk,
            "code": "ow",
            "rank": 2,
        })

        assert not form.is_valid()
        assert "name" in form.errors

    def test_form_requires_rank(self, padi_agency):
        """Form requires rank field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "agency": padi_agency.pk,
            "code": "ow",
            "name": "Open Water Diver",
        })

        assert not form.is_valid()
        assert "rank" in form.errors


@pytest.mark.django_db
class TestDiverCertificationForm:
    """Tests for DiverCertificationForm."""

    @pytest.fixture
    def padi_agency(self):
        from django_parties.models import Organization
        return Organization.objects.create(
            name="PADI",
            org_type="other",
        )

    @pytest.fixture
    def certification_level(self, padi_agency):
        # CertificationLevel now requires agency
        return CertificationLevel.objects.create(
            agency=padi_agency,
            code="ow",
            name="Open Water Diver",
            rank=2,
        )

    def test_form_exists(self):
        """DiverCertificationForm can be imported."""
        from primitives_testbed.diveops.forms import DiverCertificationForm
        assert DiverCertificationForm is not None

    def test_form_valid_data(self, diver_profile, certification_level):
        """Form accepts valid certification data."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        # Agency is derived from level.agency - not a separate field
        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": certification_level.pk,
            "card_number": "OW12345",
            "issued_on": date.today() - timedelta(days=365),
        })

        assert form.is_valid(), form.errors
        cert = form.save()
        assert cert.pk is not None
        # Agency should be derived from level
        assert cert.agency == certification_level.agency

    def test_form_with_expiration(self, diver_profile, certification_level):
        """Form accepts optional expiration date."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": certification_level.pk,
            "card_number": "OW12345",
            "issued_on": date.today() - timedelta(days=365),
            "expires_on": date.today() + timedelta(days=365),
        })

        assert form.is_valid(), form.errors

    def test_form_validates_expires_after_issued(self, diver_profile, certification_level):
        """Form validates that expires_on is after issued_on."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": certification_level.pk,
            "card_number": "OW12345",
            "issued_on": date.today(),
            "expires_on": date.today() - timedelta(days=1),  # Before issued_on
        })

        assert not form.is_valid()
        # Should have error about expiration date


@pytest.mark.django_db
class TestExcursionRequirementForm:
    """Tests for ExcursionRequirementForm."""

    @pytest.fixture
    def padi_agency(self):
        from django_parties.models import Organization
        return Organization.objects.create(
            name="PADI",
            org_type="other",
        )

    @pytest.fixture
    def certification_level(self, padi_agency):
        # CertificationLevel now requires agency
        return CertificationLevel.objects.create(
            agency=padi_agency,
            code="aow",
            name="Advanced Open Water",
            rank=3,
        )

    def test_form_exists(self):
        """ExcursionRequirementForm can be imported."""
        from primitives_testbed.diveops.forms import ExcursionRequirementForm
        assert ExcursionRequirementForm is not None

    def test_form_valid_certification_requirement(self, dive_trip, certification_level):
        """Form accepts valid certification requirement."""
        from primitives_testbed.diveops.forms import ExcursionRequirementForm

        form = ExcursionRequirementForm(data={
            "excursion": dive_trip.pk,
            "requirement_type": "certification",
            "certification_level": certification_level.pk,
            "is_mandatory": True,
        })

        assert form.is_valid(), form.errors
        req = form.save()
        assert req.pk is not None

    def test_form_valid_experience_requirement(self, dive_trip):
        """Form accepts valid experience requirement."""
        from primitives_testbed.diveops.forms import ExcursionRequirementForm

        form = ExcursionRequirementForm(data={
            "excursion": dive_trip.pk,
            "requirement_type": "experience",
            "min_dives": 50,
            "is_mandatory": True,
        })

        assert form.is_valid(), form.errors

    def test_form_validates_cert_level_for_cert_type(self, dive_trip):
        """Form requires certification_level when type is certification."""
        from primitives_testbed.diveops.forms import ExcursionRequirementForm

        form = ExcursionRequirementForm(data={
            "excursion": dive_trip.pk,
            "requirement_type": "certification",
            # Missing certification_level
            "is_mandatory": True,
        })

        assert not form.is_valid()
        # Should have error about missing certification level
