"""Tests for Medical Provider services.

TDD: These tests are written FIRST, before the implementation.
"""

from decimal import Decimal

import pytest


@pytest.mark.django_db
class TestGetRecommendedProviders:
    """Tests for get_recommended_providers function."""

    def test_returns_active_providers_for_dive_shop(
        self, dive_shop, medical_provider_profile, medical_provider_profile_2
    ):
        """Returns only active provider relationships."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship
        from primitives_testbed.diveops.medical.provider_service import get_recommended_providers

        # Create active relationship
        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_active=True,
            sort_order=1,
        )
        # Create inactive relationship
        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_active=False,
            sort_order=2,
        )

        providers = get_recommended_providers(dive_shop)

        assert len(providers) == 1
        assert providers[0].provider == medical_provider_profile

    def test_returns_ordered_by_sort_order(
        self, dive_shop, medical_provider_profile, medical_provider_profile_2
    ):
        """Providers are ordered by sort_order."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship
        from primitives_testbed.diveops.medical.provider_service import get_recommended_providers

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_active=True,
            sort_order=2,
        )
        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_active=True,
            sort_order=1,
        )

        providers = get_recommended_providers(dive_shop)

        assert len(providers) == 2
        assert providers[0].provider == medical_provider_profile
        assert providers[1].provider == medical_provider_profile_2

    def test_prefetches_locations(self, dive_shop, medical_provider_profile):
        """Provider locations are prefetched efficiently."""
        from primitives_testbed.diveops.models import (
            MedicalProviderLocation,
            MedicalProviderRelationship,
        )
        from primitives_testbed.diveops.medical.provider_service import get_recommended_providers

        # Add locations
        MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Address 1",
            city="Cozumel",
            country="Mexico",
            hours_text="Mon-Fri",
        )
        MedicalProviderLocation.objects.create(
            profile=medical_provider_profile,
            address_line1="Address 2",
            city="Cozumel",
            country="Mexico",
            hours_text="24/7",
        )

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_active=True,
        )

        providers = get_recommended_providers(dive_shop)

        # Access locations without additional queries
        assert providers[0].provider.locations.count() == 2

    def test_returns_empty_list_when_no_providers(self, dive_shop):
        """Returns empty list when dive shop has no providers."""
        from primitives_testbed.diveops.medical.provider_service import get_recommended_providers

        providers = get_recommended_providers(dive_shop)

        assert list(providers) == []

    def test_filters_soft_deleted_providers(
        self, dive_shop, medical_provider_profile, medical_provider_profile_2
    ):
        """Excludes soft-deleted provider profiles."""
        from django.utils import timezone
        from primitives_testbed.diveops.models import MedicalProviderRelationship
        from primitives_testbed.diveops.medical.provider_service import get_recommended_providers

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_active=True,
        )
        rel2 = MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_active=True,
        )
        # Soft-delete the second provider profile
        medical_provider_profile_2.deleted_at = timezone.now()
        medical_provider_profile_2.save()

        providers = get_recommended_providers(dive_shop)

        assert len(providers) == 1
        assert providers[0].provider == medical_provider_profile


@pytest.mark.django_db
class TestGetPrimaryProvider:
    """Tests for get_primary_provider function."""

    def test_returns_primary_provider(self, dive_shop, medical_provider_profile, medical_provider_profile_2):
        """Returns the provider marked as primary."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship
        from primitives_testbed.diveops.medical.provider_service import get_primary_provider

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_primary=False,
            is_active=True,
        )
        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile_2,
            is_primary=True,
            is_active=True,
        )

        primary = get_primary_provider(dive_shop)

        assert primary == medical_provider_profile_2

    def test_returns_none_when_no_primary(self, dive_shop, medical_provider_profile):
        """Returns None when no provider is marked as primary."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship
        from primitives_testbed.diveops.medical.provider_service import get_primary_provider

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_primary=False,
            is_active=True,
        )

        primary = get_primary_provider(dive_shop)

        assert primary is None

    def test_returns_none_when_no_providers(self, dive_shop):
        """Returns None when dive shop has no providers."""
        from primitives_testbed.diveops.medical.provider_service import get_primary_provider

        primary = get_primary_provider(dive_shop)

        assert primary is None

    def test_ignores_inactive_primary(self, dive_shop, medical_provider_profile):
        """Ignores primary providers that are inactive."""
        from primitives_testbed.diveops.models import MedicalProviderRelationship
        from primitives_testbed.diveops.medical.provider_service import get_primary_provider

        MedicalProviderRelationship.objects.create(
            dive_shop=dive_shop,
            provider=medical_provider_profile,
            is_primary=True,
            is_active=False,  # Inactive
        )

        primary = get_primary_provider(dive_shop)

        assert primary is None


@pytest.mark.django_db
class TestGetMedicalInstructions:
    """Tests for get_medical_instructions function."""

    def test_returns_default_instructions(self):
        """Returns default medical clearance instructions."""
        from primitives_testbed.diveops.medical.provider_service import get_medical_instructions

        instructions = get_medical_instructions()

        assert "title" in instructions
        assert "intro" in instructions
        assert "steps" in instructions
        assert len(instructions["steps"]) > 0

    def test_instructions_contain_required_sections(self):
        """Instructions contain all required sections."""
        from primitives_testbed.diveops.medical.provider_service import get_medical_instructions

        instructions = get_medical_instructions()

        assert "physician" in instructions["title"].lower() or "clearance" in instructions["title"].lower()
        assert isinstance(instructions["steps"], list)


# Fixtures for medical provider tests (copied from test_medical_provider_models.py)


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
