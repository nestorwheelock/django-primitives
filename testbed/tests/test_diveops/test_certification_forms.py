"""Tests for certification model forms."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from primitives_testbed.diveops.models import CertificationLevel, DiverCertification


@pytest.mark.django_db
class TestCertificationLevelForm:
    """Tests for CertificationLevelForm."""

    def test_form_exists(self):
        """CertificationLevelForm can be imported."""
        from primitives_testbed.diveops.forms import CertificationLevelForm
        assert CertificationLevelForm is not None

    def test_form_valid_data(self):
        """Form accepts valid certification level data."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
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

    def test_form_requires_code(self):
        """Form requires code field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "name": "Open Water Diver",
            "rank": 2,
        })

        assert not form.is_valid()
        assert "code" in form.errors

    def test_form_requires_name(self):
        """Form requires name field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "code": "ow",
            "rank": 2,
        })

        assert not form.is_valid()
        assert "name" in form.errors

    def test_form_requires_rank(self):
        """Form requires rank field."""
        from primitives_testbed.diveops.forms import CertificationLevelForm

        form = CertificationLevelForm(data={
            "code": "ow",
            "name": "Open Water Diver",
        })

        assert not form.is_valid()
        assert "rank" in form.errors


@pytest.mark.django_db
class TestDiverCertificationForm:
    """Tests for DiverCertificationForm."""

    @pytest.fixture
    def certification_level(self):
        return CertificationLevel.objects.create(
            code="ow",
            name="Open Water Diver",
            rank=2,
        )

    @pytest.fixture
    def padi_agency(self):
        from django_parties.models import Organization
        return Organization.objects.create(
            name="PADI",
            org_type="other",
        )

    def test_form_exists(self):
        """DiverCertificationForm can be imported."""
        from primitives_testbed.diveops.forms import DiverCertificationForm
        assert DiverCertificationForm is not None

    def test_form_valid_data(self, diver_profile, certification_level, padi_agency):
        """Form accepts valid certification data."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": certification_level.pk,
            "agency": padi_agency.pk,
            "certification_number": "OW12345",
            "certified_on": date.today() - timedelta(days=365),
        })

        assert form.is_valid(), form.errors
        cert = form.save()
        assert cert.pk is not None

    def test_form_with_expiration(self, diver_profile, certification_level, padi_agency):
        """Form accepts optional expiration date."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": certification_level.pk,
            "agency": padi_agency.pk,
            "certification_number": "OW12345",
            "certified_on": date.today() - timedelta(days=365),
            "expires_on": date.today() + timedelta(days=365),
        })

        assert form.is_valid(), form.errors

    def test_form_validates_expires_after_certified(
        self, diver_profile, certification_level, padi_agency
    ):
        """Form validates that expires_on is after certified_on."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form = DiverCertificationForm(data={
            "diver": diver_profile.pk,
            "level": certification_level.pk,
            "agency": padi_agency.pk,
            "certification_number": "OW12345",
            "certified_on": date.today(),
            "expires_on": date.today() - timedelta(days=1),  # Before certified_on
        })

        assert not form.is_valid()
        # Should have error about expiration date


@pytest.mark.django_db
class TestTripRequirementForm:
    """Tests for TripRequirementForm."""

    @pytest.fixture
    def certification_level(self):
        return CertificationLevel.objects.create(
            code="aow",
            name="Advanced Open Water",
            rank=3,
        )

    def test_form_exists(self):
        """TripRequirementForm can be imported."""
        from primitives_testbed.diveops.forms import TripRequirementForm
        assert TripRequirementForm is not None

    def test_form_valid_certification_requirement(self, dive_trip, certification_level):
        """Form accepts valid certification requirement."""
        from primitives_testbed.diveops.forms import TripRequirementForm

        form = TripRequirementForm(data={
            "trip": dive_trip.pk,
            "requirement_type": "certification",
            "certification_level": certification_level.pk,
            "is_mandatory": True,
        })

        assert form.is_valid(), form.errors
        req = form.save()
        assert req.pk is not None

    def test_form_valid_experience_requirement(self, dive_trip):
        """Form accepts valid experience requirement."""
        from primitives_testbed.diveops.forms import TripRequirementForm

        form = TripRequirementForm(data={
            "trip": dive_trip.pk,
            "requirement_type": "experience",
            "min_dives": 50,
            "is_mandatory": True,
        })

        assert form.is_valid(), form.errors

    def test_form_validates_cert_level_for_cert_type(self, dive_trip):
        """Form requires certification_level when type is certification."""
        from primitives_testbed.diveops.forms import TripRequirementForm

        form = TripRequirementForm(data={
            "trip": dive_trip.pk,
            "requirement_type": "certification",
            # Missing certification_level
            "is_mandatory": True,
        })

        assert not form.is_valid()
        # Should have error about missing certification level
