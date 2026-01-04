"""Tests for certification-related selectors."""

from datetime import date, timedelta

import pytest
from django.db import models

from primitives_testbed.diveops.models import (
    CertificationLevel,
    DiverCertification,
    TripRequirement,
)


@pytest.mark.django_db
class TestGetDiverWithCertifications:
    """Tests for get_diver_with_certifications selector."""

    @pytest.fixture
    def setup_certifications(self, diver_profile):
        """Set up test certification data."""
        from django_parties.models import Organization

        padi = Organization.objects.create(name="PADI", org_type="other")
        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)

        DiverCertification.objects.create(
            diver=diver_profile, level=ow, agency=padi,
            certification_number="OW1", certified_on=date.today() - timedelta(days=365)
        )
        DiverCertification.objects.create(
            diver=diver_profile, level=aow, agency=padi,
            certification_number="AOW1", certified_on=date.today() - timedelta(days=180)
        )

        return {"padi": padi, "ow": ow, "aow": aow}

    def test_returns_diver_with_certifications(self, diver_profile, setup_certifications):
        """Selector returns diver with certifications prefetched."""
        from primitives_testbed.diveops.selectors import get_diver_with_certifications

        diver = get_diver_with_certifications(diver_profile.pk)

        assert diver is not None
        assert diver.pk == diver_profile.pk
        assert diver.certifications.count() == 2

    def test_certifications_ordered_by_rank_desc(self, diver_profile, setup_certifications):
        """Certifications are ordered by rank (highest first)."""
        from primitives_testbed.diveops.selectors import get_diver_with_certifications

        diver = get_diver_with_certifications(diver_profile.pk)
        certs = list(diver.certifications.all())

        # AOW (rank 3) should come before OW (rank 2)
        assert certs[0].level.code == "aow"
        assert certs[1].level.code == "ow"

    def test_avoids_n_plus_1(self, diver_profile, setup_certifications, django_assert_num_queries):
        """Selector avoids N+1 queries."""
        from primitives_testbed.diveops.selectors import get_diver_with_certifications

        # Should be 2 queries: diver + certifications (with level/agency)
        with django_assert_num_queries(2):
            diver = get_diver_with_certifications(diver_profile.pk)
            for cert in diver.certifications.all():
                _ = cert.level.name
                _ = cert.agency.name

    def test_returns_none_for_invalid_id(self):
        """Selector returns None for invalid diver ID."""
        from primitives_testbed.diveops.selectors import get_diver_with_certifications
        import uuid

        diver = get_diver_with_certifications(uuid.uuid4())
        assert diver is None


@pytest.mark.django_db
class TestGetTripWithRequirements:
    """Tests for get_trip_with_requirements selector."""

    @pytest.fixture
    def setup_requirements(self, dive_trip):
        """Set up test requirement data."""
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)

        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="certification",
            certification_level=aow,
            is_mandatory=True,
        )
        TripRequirement.objects.create(
            trip=dive_trip,
            requirement_type="experience",
            min_dives=50,
            is_mandatory=True,
        )

        return {"aow": aow}

    def test_returns_trip_with_requirements(self, dive_trip, setup_requirements):
        """Selector returns trip with requirements prefetched."""
        from primitives_testbed.diveops.selectors import get_trip_with_requirements

        trip = get_trip_with_requirements(dive_trip.pk)

        assert trip is not None
        assert trip.pk == dive_trip.pk
        assert trip.requirements.count() == 2

    def test_requirements_ordered_by_type(self, dive_trip, setup_requirements):
        """Requirements are ordered by type."""
        from primitives_testbed.diveops.selectors import get_trip_with_requirements

        trip = get_trip_with_requirements(dive_trip.pk)
        reqs = list(trip.requirements.all())

        # certification comes before experience alphabetically
        assert reqs[0].requirement_type == "certification"
        assert reqs[1].requirement_type == "experience"

    def test_avoids_n_plus_1(self, dive_trip, setup_requirements, django_assert_num_queries):
        """Selector avoids N+1 queries."""
        from primitives_testbed.diveops.selectors import get_trip_with_requirements

        # Should be 2 queries: trip + requirements (with certification_level)
        with django_assert_num_queries(2):
            trip = get_trip_with_requirements(dive_trip.pk)
            for req in trip.requirements.all():
                if req.certification_level:
                    _ = req.certification_level.name

    def test_returns_none_for_invalid_id(self):
        """Selector returns None for invalid trip ID."""
        from primitives_testbed.diveops.selectors import get_trip_with_requirements
        import uuid

        trip = get_trip_with_requirements(uuid.uuid4())
        assert trip is None


@pytest.mark.django_db
class TestListCertificationLevels:
    """Tests for list_certification_levels selector."""

    @pytest.fixture
    def setup_levels(self):
        """Set up test certification levels."""
        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)
        dm = CertificationLevel.objects.create(code="dm", name="Divemaster", rank=5, is_active=False)

        return {"ow": ow, "aow": aow, "dm": dm}

    def test_returns_active_levels_by_default(self, setup_levels):
        """Selector returns only active levels by default."""
        from primitives_testbed.diveops.selectors import list_certification_levels

        levels = list_certification_levels()

        assert len(levels) == 2
        assert all(level.is_active for level in levels)

    def test_returns_all_levels_when_active_only_false(self, setup_levels):
        """Selector returns all levels when active_only=False."""
        from primitives_testbed.diveops.selectors import list_certification_levels

        levels = list_certification_levels(active_only=False)

        assert len(levels) == 3

    def test_levels_ordered_by_rank(self, setup_levels):
        """Levels are ordered by rank ascending."""
        from primitives_testbed.diveops.selectors import list_certification_levels

        levels = list_certification_levels(active_only=False)

        assert levels[0].code == "ow"  # rank 2
        assert levels[1].code == "aow"  # rank 3
        assert levels[2].code == "dm"  # rank 5


@pytest.mark.django_db
class TestGetDiverHighestCertification:
    """Tests for get_diver_highest_certification selector."""

    @pytest.fixture
    def setup_multiple_certs(self, diver_profile):
        """Set up diver with multiple certifications."""
        from django_parties.models import Organization

        padi = Organization.objects.create(name="PADI", org_type="other")
        ow = CertificationLevel.objects.create(code="ow", name="Open Water", rank=2)
        aow = CertificationLevel.objects.create(code="aow", name="Advanced Open Water", rank=3)
        dm = CertificationLevel.objects.create(code="dm", name="Divemaster", rank=5)

        DiverCertification.objects.create(
            diver=diver_profile, level=ow, agency=padi,
            certification_number="OW1", certified_on=date.today() - timedelta(days=365)
        )
        DiverCertification.objects.create(
            diver=diver_profile, level=aow, agency=padi,
            certification_number="AOW1", certified_on=date.today() - timedelta(days=180)
        )

        return {"padi": padi, "ow": ow, "aow": aow, "dm": dm}

    def test_returns_highest_certification(self, diver_profile, setup_multiple_certs):
        """Selector returns highest (by rank) certification."""
        from primitives_testbed.diveops.selectors import get_diver_highest_certification

        highest = get_diver_highest_certification(diver_profile)

        assert highest is not None
        assert highest.level.code == "aow"  # rank 3 is highest

    def test_excludes_expired_certifications(self, diver_profile, setup_multiple_certs):
        """Selector excludes expired certifications."""
        from primitives_testbed.diveops.selectors import get_diver_highest_certification
        from django_parties.models import Organization

        padi = setup_multiple_certs["padi"]
        dm = setup_multiple_certs["dm"]

        # Add expired DM certification
        DiverCertification.objects.create(
            diver=diver_profile, level=dm, agency=padi,
            certification_number="DM1",
            certified_on=date.today() - timedelta(days=730),
            expires_on=date.today() - timedelta(days=30),  # Expired
        )

        highest = get_diver_highest_certification(diver_profile)

        # Should still be AOW, not expired DM
        assert highest.level.code == "aow"

    def test_returns_none_for_no_certifications(self, person2):
        """Selector returns None when diver has no certifications."""
        from primitives_testbed.diveops.selectors import get_diver_highest_certification
        from primitives_testbed.diveops.models import DiverProfile

        diver = DiverProfile.objects.create(
            person=person2,
            certification_level="ow",
            certification_agency="PADI",
            certification_date=date.today(),
            total_dives=0,
        )

        highest = get_diver_highest_certification(diver)

        assert highest is None
