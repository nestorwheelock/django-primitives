"""Tests for certification recommendation logic.

Tests cover:
- get_recommended_certifications: Suggest next certifications based on progression and preferences
- Progression recommendations (next level in path)
- Specialty recommendations (based on diving interests)
"""

import pytest
from datetime import date, timedelta
from django_parties.models import Organization, Person

from ..models import PreferenceDefinition, PartyPreference, ValueType, Sensitivity
from ..selectors import get_recommended_certifications
from ...models import CertificationLevel, DiverCertification, DiverProfile


@pytest.fixture
def padi_agency(db):
    """Create PADI certification agency."""
    return Organization.objects.create(
        name="PADI",
    )


@pytest.fixture
def certification_levels(padi_agency, db):
    """Create standard PADI certification levels."""
    levels = {}

    # Core progression path
    levels["sd"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="sd",
        name="Scuba Diver",
        rank=1,
        max_depth_m=12,
    )
    levels["ow"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="ow",
        name="Open Water Diver",
        rank=2,
        max_depth_m=18,
    )
    levels["aow"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="aow",
        name="Advanced Open Water Diver",
        rank=3,
        max_depth_m=30,
    )
    levels["rescue"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="rescue",
        name="Rescue Diver",
        rank=4,
        max_depth_m=30,
    )
    levels["dm"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="dm",
        name="Divemaster",
        rank=5,
        max_depth_m=40,
    )

    # Specialty courses (rank=10+ indicates specialty, not progression)
    levels["ppb"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="ppb",
        name="Peak Performance Buoyancy",
        rank=10,
        description="Master your buoyancy control",
    )
    levels["deep"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="deep",
        name="Deep Diver",
        rank=10,
        max_depth_m=40,
        description="Learn to dive safely to 40m",
    )
    levels["wreck"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="wreck",
        name="Wreck Diver",
        rank=10,
        description="Explore sunken ships and structures",
    )
    levels["night"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="night",
        name="Night Diver",
        rank=10,
        description="Dive after dark",
    )
    levels["nitrox"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="nitrox",
        name="Enriched Air (Nitrox) Diver",
        rank=10,
        description="Extend bottom times with enriched air",
    )
    levels["photo"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="photo",
        name="Underwater Photographer",
        rank=10,
        description="Capture the underwater world",
    )
    levels["cavern"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="cavern",
        name="Cavern Diver",
        rank=11,
        description="Explore cavern environments safely",
    )

    return levels


@pytest.fixture
def person(db):
    """Create a test person."""
    return Person.objects.create(
        first_name="Test",
        last_name="Diver",
        email="test@example.com",
    )


@pytest.fixture
def diver(person, db):
    """Create a test diver profile."""
    return DiverProfile.objects.create(person=person)


@pytest.fixture
def preference_definitions(db):
    """Create preference definitions for interests."""
    defs = {}
    defs["interests"] = PreferenceDefinition.objects.create(
        key="diving.interests",
        label="Diving Interests",
        category="diving",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["Reef/coral", "Wrecks", "Cenotes", "Caves", "Night diving", "Macro photography", "Wide-angle photography"],
        sensitivity=Sensitivity.PUBLIC,
    )
    defs["likes_photography"] = PreferenceDefinition.objects.create(
        key="diving.likes_photography",
        label="Likes Photography",
        category="diving",
        value_type=ValueType.BOOL,
        sensitivity=Sensitivity.PUBLIC,
    )
    defs["depth_comfort"] = PreferenceDefinition.objects.create(
        key="diving.depth_comfort",
        label="Depth Comfort",
        category="diving",
        value_type=ValueType.CHOICE,
        choices_json=["Shallow (< 18m)", "Recreational (18-30m)", "Deep recreational (30-40m)", "Technical (40m+)"],
        sensitivity=Sensitivity.PUBLIC,
    )
    return defs


@pytest.mark.django_db
class TestGetRecommendedCertifications:
    """Tests for get_recommended_certifications selector."""

    def test_returns_list_of_recommendations(
        self, diver, certification_levels, preference_definitions
    ):
        """Returns a list of recommendation dicts."""
        recommendations = get_recommended_certifications(diver)

        assert isinstance(recommendations, list)

    def test_recommends_ow_for_uncertified_diver(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Open Water for diver with no certifications."""
        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "ow" in codes

    def test_recommends_aow_for_ow_diver(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Advanced Open Water for Open Water diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "aow" in codes

    def test_recommends_rescue_for_aow_diver(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Rescue Diver for Advanced Open Water diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["aow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "rescue" in codes

    def test_recommends_dm_for_rescue_diver(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Divemaster for Rescue Diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["rescue"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "dm" in codes

    def test_recommends_ppb_for_new_ow_diver(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Peak Performance Buoyancy as common specialty for OW divers."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "ppb" in codes

    def test_recommends_wreck_for_wreck_interest(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Wreck Diver specialty based on wreck diving interest."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        # Set wreck interest preference
        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["interests"],
            value_json=["Wrecks"],
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "wreck" in codes

    def test_recommends_night_for_night_interest(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Night Diver specialty based on night diving interest."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["interests"],
            value_json=["Night diving"],
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "night" in codes

    def test_recommends_photo_for_photography_interest(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Underwater Photographer based on photography preference."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["likes_photography"],
            value_bool=True,
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "photo" in codes

    def test_recommends_cavern_for_cenote_interest(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Cavern Diver based on cenote diving interest."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["aow"],  # AOW required for cavern
            issued_on=date.today() - timedelta(days=30),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["interests"],
            value_json=["Cenotes", "Caves"],
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "cavern" in codes

    def test_recommends_deep_for_depth_comfort(
        self, diver, certification_levels, preference_definitions
    ):
        """Recommends Deep Diver based on depth comfort preference."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["aow"],
            issued_on=date.today() - timedelta(days=30),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["depth_comfort"],
            value_text="Deep recreational (30-40m)",
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "deep" in codes

    def test_excludes_already_held_certifications(
        self, diver, certification_levels, preference_definitions
    ):
        """Does not recommend certifications the diver already has."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=60),
        )
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ppb"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        codes = [r["level"].code for r in recommendations]
        assert "ow" not in codes
        assert "ppb" not in codes

    def test_includes_reason_for_recommendation(
        self, diver, certification_levels, preference_definitions
    ):
        """Each recommendation includes a reason string."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        for rec in recommendations:
            assert "reason" in rec
            assert isinstance(rec["reason"], str)
            assert len(rec["reason"]) > 0

    def test_includes_priority_score(
        self, diver, certification_levels, preference_definitions
    ):
        """Each recommendation includes a priority score."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        for rec in recommendations:
            assert "priority" in rec
            assert isinstance(rec["priority"], int)

    def test_progression_has_higher_priority_than_specialty(
        self, diver, certification_levels, preference_definitions
    ):
        """Next level in progression path has higher priority than specialties."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        # Find AOW (progression) and PPB (specialty)
        aow_rec = next((r for r in recommendations if r["level"].code == "aow"), None)
        ppb_rec = next((r for r in recommendations if r["level"].code == "ppb"), None)

        assert aow_rec is not None
        assert ppb_rec is not None
        assert aow_rec["priority"] > ppb_rec["priority"]

    def test_respects_limit_parameter(
        self, diver, certification_levels, preference_definitions
    ):
        """Limits number of recommendations returned."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver, limit=2)

        assert len(recommendations) <= 2

    def test_returns_empty_for_divemaster(
        self, diver, certification_levels, preference_definitions
    ):
        """Returns only specialties for Divemaster (no higher progression)."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["dm"],
            issued_on=date.today() - timedelta(days=30),
        )

        recommendations = get_recommended_certifications(diver)

        # Should only have specialties, no progression path beyond DM
        codes = [r["level"].code for r in recommendations]
        assert "dm" not in codes
        # Progression path levels (sd, ow, aow, rescue) should not appear
        for code in ["sd", "ow", "aow", "rescue"]:
            assert code not in codes
