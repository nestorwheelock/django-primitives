"""Tests for courseware recommendation logic.

Tests cover:
- get_recommended_courseware: Suggest courseware based on certification recommendations
- Entitlement checking to avoid recommending already-owned courseware
- Linking courseware to certifications via tags/metadata
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_catalog.models import CatalogItem
from django_parties.models import Organization, Person

from primitives_testbed.diveops.entitlements.models import EntitlementGrant
from primitives_testbed.pricing.models import Price
from primitives_testbed.store.models import CatalogItemEntitlement

from ..selectors import get_recommended_courseware
from ...models import CertificationLevel, DiverCertification, DiverProfile

User = get_user_model()


@pytest.fixture
def padi_agency(db):
    """Create PADI certification agency."""
    return Organization.objects.create(name="PADI")


@pytest.fixture
def certification_levels(padi_agency, db):
    """Create standard PADI certification levels."""
    levels = {}
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
    levels["nitrox"] = CertificationLevel.objects.create(
        agency=padi_agency,
        code="nitrox",
        name="Enriched Air (Nitrox) Diver",
        rank=10,
    )
    return levels


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testdiver",
        email="diver@example.com",
        password="testpass123",
    )


@pytest.fixture
def person(db):
    """Create a test person."""
    return Person.objects.create(
        first_name="Test",
        last_name="Diver",
        email="diver@example.com",
    )


@pytest.fixture
def diver(person, user, db):
    """Create a test diver profile linked to user."""
    diver = DiverProfile.objects.create(person=person)
    # Link user to person (if there's a relationship)
    person.user = user
    person.save()
    return diver


@pytest.fixture
def courseware_items(user, db):
    """Create courseware catalog items with entitlements."""
    items = {}

    # Open Water Courseware
    items["ow"] = CatalogItem.objects.create(
        display_name="Open Water Diver eLearning",
        kind="service",
        service_category="other",
        is_billable=True,
        active=True,
    )
    CatalogItemEntitlement.objects.create(
        catalog_item=items["ow"],
        entitlement_codes=["content:owd-courseware"],
    )
    Price.objects.create(
        catalog_item=items["ow"],
        amount=Decimal("99.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    # Advanced Open Water Courseware
    items["aow"] = CatalogItem.objects.create(
        display_name="Advanced Open Water eLearning",
        kind="service",
        service_category="other",
        is_billable=True,
        active=True,
    )
    CatalogItemEntitlement.objects.create(
        catalog_item=items["aow"],
        entitlement_codes=["content:aow-courseware"],
    )
    Price.objects.create(
        catalog_item=items["aow"],
        amount=Decimal("129.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    # Rescue Diver Courseware
    items["rescue"] = CatalogItem.objects.create(
        display_name="Rescue Diver eLearning",
        kind="service",
        service_category="other",
        is_billable=True,
        active=True,
    )
    CatalogItemEntitlement.objects.create(
        catalog_item=items["rescue"],
        entitlement_codes=["content:rescue-courseware"],
    )
    Price.objects.create(
        catalog_item=items["rescue"],
        amount=Decimal("149.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    # Nitrox Courseware
    items["nitrox"] = CatalogItem.objects.create(
        display_name="Enriched Air Nitrox eLearning",
        kind="service",
        service_category="other",
        is_billable=True,
        active=True,
    )
    CatalogItemEntitlement.objects.create(
        catalog_item=items["nitrox"],
        entitlement_codes=["content:nitrox-courseware"],
    )
    Price.objects.create(
        catalog_item=items["nitrox"],
        amount=Decimal("79.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    return items


@pytest.mark.django_db
class TestGetRecommendedCourseware:
    """Tests for get_recommended_courseware selector."""

    def test_returns_list_of_recommendations(
        self, diver, certification_levels, courseware_items
    ):
        """Returns a list of courseware recommendation dicts."""
        recommendations = get_recommended_courseware(diver)
        assert isinstance(recommendations, list)

    def test_recommends_ow_courseware_for_uncertified_diver(
        self, diver, certification_levels, courseware_items
    ):
        """Recommends Open Water courseware for diver with no certifications."""
        recommendations = get_recommended_courseware(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Open Water" in name for name in names)

    def test_recommends_aow_courseware_for_ow_diver(
        self, diver, certification_levels, courseware_items
    ):
        """Recommends Advanced Open Water courseware for OW certified diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_courseware(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Advanced" in name for name in names)

    def test_recommends_rescue_courseware_for_aow_diver(
        self, diver, certification_levels, courseware_items
    ):
        """Recommends Rescue Diver courseware for AOW certified diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["aow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_courseware(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Rescue" in name for name in names)

    def test_recommends_specialty_courseware_for_ow_diver(
        self, diver, certification_levels, courseware_items
    ):
        """Recommends specialty courseware (like Nitrox) for OW certified diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_courseware(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Nitrox" in name for name in names)

    def test_excludes_courseware_user_already_has(
        self, diver, user, certification_levels, courseware_items
    ):
        """Does not recommend courseware user already has entitlement for."""
        # Give user OW courseware entitlement
        EntitlementGrant.objects.create(
            user=user,
            code="content:owd-courseware",
            source_type="manual",
            source_id="test",
        )

        recommendations = get_recommended_courseware(diver)

        names = [r["item"].display_name for r in recommendations]
        assert not any("Open Water" in name and "eLearning" in name for name in names)

    def test_includes_price_in_recommendation(
        self, diver, certification_levels, courseware_items
    ):
        """Each recommendation includes the current price."""
        recommendations = get_recommended_courseware(diver)

        for rec in recommendations:
            assert "price" in rec
            assert rec["price"] is not None

    def test_includes_reason_in_recommendation(
        self, diver, certification_levels, courseware_items
    ):
        """Each recommendation includes a reason string."""
        recommendations = get_recommended_courseware(diver)

        for rec in recommendations:
            assert "reason" in rec
            assert isinstance(rec["reason"], str)
            assert len(rec["reason"]) > 0

    def test_respects_limit_parameter(
        self, diver, certification_levels, courseware_items
    ):
        """Limits number of recommendations returned."""
        recommendations = get_recommended_courseware(diver, limit=1)
        assert len(recommendations) <= 1

    def test_prioritizes_progression_courseware(
        self, diver, certification_levels, courseware_items
    ):
        """Next certification courseware has higher priority than specialties."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_courseware(diver)

        if len(recommendations) >= 2:
            # AOW should come before Nitrox
            aow_idx = next(
                (i for i, r in enumerate(recommendations)
                 if "Advanced" in r["item"].display_name),
                None
            )
            nitrox_idx = next(
                (i for i, r in enumerate(recommendations)
                 if "Nitrox" in r["item"].display_name),
                None
            )
            if aow_idx is not None and nitrox_idx is not None:
                assert aow_idx < nitrox_idx

    def test_returns_empty_for_fully_certified_diver(
        self, diver, user, certification_levels, courseware_items
    ):
        """Returns empty list when diver has all available courseware."""
        # Give user all courseware entitlements
        for code in ["content:owd-courseware", "content:aow-courseware",
                     "content:rescue-courseware", "content:nitrox-courseware"]:
            EntitlementGrant.objects.create(
                user=user,
                code=code,
                source_type="manual",
                source_id="test",
            )

        recommendations = get_recommended_courseware(diver)
        assert len(recommendations) == 0

    def test_excludes_inactive_courseware(
        self, diver, certification_levels, courseware_items
    ):
        """Does not recommend inactive catalog items."""
        # Deactivate OW courseware
        courseware_items["ow"].active = False
        courseware_items["ow"].save()

        recommendations = get_recommended_courseware(diver)

        names = [r["item"].display_name for r in recommendations]
        assert not any("Open Water" in name and "eLearning" in name for name in names)
