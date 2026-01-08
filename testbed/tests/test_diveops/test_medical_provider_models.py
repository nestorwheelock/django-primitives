"""Tests for Medical Provider models.

TDD: These tests are written FIRST, before the implementation.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError


@pytest.mark.django_db
class TestMedicalProviderProfile:
    """Tests for MedicalProviderProfile model."""

    def test_profile_creation(self, medical_provider_org):
        """Profile can be created with required fields."""
        from primitives_testbed.diveops.models import MedicalProviderProfile

        profile = MedicalProviderProfile.objects.create(
            organization=medical_provider_org,
            provider_type="clinic",
        )
        assert profile.pk is not None
        assert profile.organization == medical_provider_org
        assert profile.provider_type == "clinic"

    def test_profile_default_values(self, medical_provider_org):
        """Profile has expected default values."""
        from primitives_testbed.diveops.models import MedicalProviderProfile

        profile = MedicalProviderProfile.objects.create(
            organization=medical_provider_org,
            provider_type="clinic",
        )
        assert profile.has_hyperbaric_chamber is False
        assert profile.accepts_divers is True
        assert profile.accepts_emergencies is False
        assert profile.is_dan_affiliated is False
        assert profile.languages == []
        assert profile.certifications == []
        assert profile.is_active is True
        assert profile.sort_order == 0

    def test_profile_with_all_fields(self, medical_provider_org):
        """Profile with all optional fields populated."""
        from primitives_testbed.diveops.models import MedicalProviderProfile

        profile = MedicalProviderProfile.objects.create(
            organization=medical_provider_org,
            provider_type="hospital",
            has_hyperbaric_chamber=True,
            hyperbaric_details="Multi-place chamber, rated to 6 ATA",
            accepts_divers=True,
            accepts_emergencies=True,
            is_dan_affiliated=True,
            languages=["English", "Spanish", "French"],
            certifications=["DAN Diving Medicine", "UHMS Hyperbaric Medicine"],
            after_hours_phone="+52 987 872 9400",
            notes="24/7 emergency services available",
            sort_order=1,
        )
        assert profile.has_hyperbaric_chamber is True
        assert "Multi-place" in profile.hyperbaric_details
        assert profile.languages == ["English", "Spanish", "French"]
        assert len(profile.certifications) == 2

    def test_profile_one_to_one_with_organization(self, medical_provider_org):
        """Only one profile per organization."""
        from primitives_testbed.diveops.models import MedicalProviderProfile

        MedicalProviderProfile.objects.create(
            organization=medical_provider_org,
            provider_type="clinic",
        )

        with pytest.raises(IntegrityError):
            MedicalProviderProfile.objects.create(
                organization=medical_provider_org,
                provider_type="hospital",
            )

    def test_profile_str_representation(self, medical_provider_org):
        """Profile string representation includes org name."""
        from primitives_testbed.diveops.models import MedicalProviderProfile

        profile = MedicalProviderProfile.objects.create(
            organization=medical_provider_org,
            provider_type="clinic",
        )
        assert medical_provider_org.name in str(profile)

    def test_provider_type_choices(self, medical_provider_org):
        """Provider type accepts valid choices."""
        from primitives_testbed.diveops.models import MedicalProviderProfile

        valid_types = ["clinic", "hospital", "urgent_care", "chamber", "physician"]
        for provider_type in valid_types:
            profile = MedicalProviderProfile(
                organization=medical_provider_org,
                provider_type=provider_type,
            )
            profile.full_clean()


@pytest.mark.django_db
class TestMedicalProviderLocation:
    """Tests for MedicalProviderLocation model."""

    def test_location_creation(self, medical_provider_profile):
        """Location can be created with required fields."""
        from primitives_testbed.diveops.models import MedicalProviderLocation

        location = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Av. 20 Sur entre Calle 1 Sur",
            city="Cozumel",
            country="Mexico",
            hours_text="Mon-Fri: 8:00 AM - 6:00 PM",
        )
        assert location.pk is not None
        assert location.profile == medical_provider_profile
        assert location.city == "Cozumel"

    def test_location_with_coordinates(self, medical_provider_profile):
        """Location stores lat/lng coordinates."""
        from primitives_testbed.diveops.models import MedicalProviderLocation

        location = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Calle 5 Sur #21",
            city="Cozumel",
            country="Mexico",
            hours_text="24/7",
            latitude=Decimal("20.508900"),
            longitude=Decimal("-86.949400"),
        )
        assert location.latitude == Decimal("20.508900")
        assert location.longitude == Decimal("-86.949400")

    def test_location_multiple_per_profile(self, medical_provider_profile):
        """Profile can have multiple locations."""
        from primitives_testbed.diveops.models import MedicalProviderLocation

        loc1 = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            name="Main Office",
            address_line1="Address 1",
            city="Cozumel",
            country="Mexico",
            hours_text="Mon-Fri 9-5",
            is_primary=True,
        )
        loc2 = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            name="Chamber Facility",
            address_line1="Address 2",
            city="Cozumel",
            country="Mexico",
            hours_text="24/7",
            is_primary=False,
        )
        assert medical_provider_profile.locations.count() == 2
        assert loc1.is_primary is True
        assert loc2.is_primary is False

    def test_location_optional_fields(self, medical_provider_profile):
        """Location with optional fields."""
        from primitives_testbed.diveops.models import MedicalProviderLocation

        location = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            name="Branch Office",
            address_line1="Main Street 123",
            address_line2="Suite 456",
            city="Cozumel",
            state="Quintana Roo",
            postal_code="77600",
            country="Mexico",
            hours_text="Mon-Sat 9-6",
            is_24_7=False,
            phone="+52 987 872 1234",
            email="branch@example.com",
            sort_order=2,
        )
        assert location.address_line2 == "Suite 456"
        assert location.state == "Quintana Roo"
        assert location.postal_code == "77600"
        assert location.email == "branch@example.com"

    def test_location_is_24_7_flag(self, medical_provider_profile):
        """Location 24/7 flag works."""
        from primitives_testbed.diveops.models import MedicalProviderLocation

        location = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Emergency Center",
            city="Cozumel",
            country="Mexico",
            hours_text="24/7 Emergency Services",
            is_24_7=True,
        )
        assert location.is_24_7 is True

    def test_location_ordering(self, medical_provider_profile):
        """Locations are ordered by sort_order then created_at."""
        from primitives_testbed.diveops.models import MedicalProviderLocation

        loc3 = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Third",
            city="Cozumel",
            country="Mexico",
            hours_text="Hours",
            sort_order=3,
        )
        loc1 = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="First",
            city="Cozumel",
            country="Mexico",
            hours_text="Hours",
            sort_order=1,
        )
        loc2 = MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Second",
            city="Cozumel",
            country="Mexico",
            hours_text="Hours",
            sort_order=2,
        )
        locations = list(medical_provider_profile.locations.all())
        assert locations[0].address_line1 == "First"
        assert locations[1].address_line1 == "Second"
        assert locations[2].address_line1 == "Third"


@pytest.mark.django_db
class TestMedicalProviderRelationship:
    """Tests for MedicalProviderRelationship model."""

    def test_relationship_creation(self, dive_shop, medical_provider_profile):
        """Relationship can be created linking dive shop to provider."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        rel = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
        )
        assert rel.pk is not None
        assert rel.dive_shop == dive_shop
        assert rel.provider == medical_provider_profile

    def test_relationship_default_values(self, dive_shop, medical_provider_profile):
        """Relationship has expected default values."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        rel = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
        )
        assert rel.is_primary is False
        assert rel.is_active is True
        assert rel.sort_order == 0
        assert rel.notes == ""

    def test_relationship_unique_dive_shop_provider(self, dive_shop, medical_provider_profile):
        """Only one relationship per dive_shop + provider combination."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
        )

        with pytest.raises(IntegrityError):
            MedicalProviderRelationship.objects.create(
                dive_shop=dive_shop,
                provider=medical_provider_profile,
            )

    def test_relationship_multiple_providers_per_shop(
        self, dive_shop, medical_provider_profile, medical_provider_profile_2
    ):
        """Dive shop can have multiple provider relationships."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        rel1 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_primary=True,
            sort_order=1,
        )
        rel2 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_primary=False,
            sort_order=2,
        )
        assert dive_shop.medical_provider_relationships.count() == 2

    def test_relationship_with_notes(self, dive_shop, medical_provider_profile):
        """Relationship can have notes."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        rel = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            notes="Preferred for complex medical histories",
        )
        assert "complex medical histories" in rel.notes

    def test_relationship_ordering(self, dive_shop, medical_provider_profile, medical_provider_profile_2):
        """Relationships are ordered by sort_order then created_at."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        rel2 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            sort_order=2,
        )
        rel1 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            sort_order=1,
        )
        rels = list(dive_shop.medical_provider_relationships.all())
        assert rels[0] == rel1
        assert rels[1] == rel2

    def test_relationship_inactive_excluded_by_default(
        self, dive_shop, medical_provider_profile, medical_provider_profile_2
    ):
        """Inactive relationships are not excluded by default (soft delete via BaseModel)."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        rel1 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_active=True,
        )
        rel2 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_active=False,  # Inactive but not deleted
        )
        # Both should be visible (is_active is a flag, not a manager filter)
        assert MedicalProviderRelationship.objects.count() == 2


@pytest.mark.django_db
class TestMedicalProviderQuerysets:
    """Tests for custom querysets and managers."""

    def test_get_active_providers_for_dive_shop(
        self, dive_shop, medical_provider_profile, medical_provider_profile_2
    ):
        """Can query active providers for a dive shop."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_active=True,
        )
        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_active=False,
        )

        active_rels = MedicalProviderRelationship.objects.filter(
            dive_shop=dive_shop,
            is_active=True,
        )
        assert active_rels.count() == 1
        assert active_rels.first().provider == medical_provider_profile


# Fixtures for medical provider tests


@pytest.fixture
def medical_provider_org(db):
    """Create a medical provider organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Cozumel Medical Center",
        org_type="clinic",
    )


@pytest.fixture
def medical_provider_org_2(db):
    """Create a second medical provider organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Costamed Hospital Cozumel",
        org_type="hospital",
    )


@pytest.fixture
def medical_provider_profile(db, medical_provider_org):
    """Create a medical provider profile."""
    from primitives_testbed.diveops.models import MedicalProviderProfile

    return MedicalProviderProfile.objects.create(
        organization=medical_provider_org,
        provider_type="clinic",
        accepts_divers=True,
        languages=["English", "Spanish"],
    )


@pytest.fixture
def medical_provider_profile_2(db, medical_provider_org_2):
    """Create a second medical provider profile."""
    from primitives_testbed.diveops.models import MedicalProviderProfile

    return MedicalProviderProfile.objects.create(
        organization=medical_provider_org_2,
        provider_type="hospital",
        has_hyperbaric_chamber=True,
        accepts_emergencies=True,
        languages=["English", "Spanish"],
    )
