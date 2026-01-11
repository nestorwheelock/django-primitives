"""Tests for gear recommendation logic.

Tests cover:
- get_recommended_gear: Suggest gear based on diving interests and experience
- Interest-based recommendations (photography gear, night diving lights)
- Experience-level recommendations
- Excluding gear already purchased
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_catalog.models import CatalogItem
from django_parties.models import Organization, Person

from primitives_testbed.pricing.models import Price

from ..models import PreferenceDefinition, PartyPreference, ValueType, Sensitivity
from ..selectors import get_recommended_gear
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
    person.user = user
    person.save()
    return diver


@pytest.fixture
def preference_definitions(db):
    """Create preference definitions for interests."""
    defs = {}
    defs["interests"] = PreferenceDefinition.objects.create(
        key="diving.interests",
        label="Diving Interests",
        category="diving",
        value_type=ValueType.MULTI_CHOICE,
        choices_json=["Reef/coral", "Wrecks", "Cenotes", "Night diving", "Macro photography", "Wide-angle photography"],
        sensitivity=Sensitivity.PUBLIC,
    )
    defs["likes_photography"] = PreferenceDefinition.objects.create(
        key="diving.likes_photography",
        label="Likes Photography",
        category="diving",
        value_type=ValueType.BOOL,
        sensitivity=Sensitivity.PUBLIC,
    )
    return defs


@pytest.fixture
def gear_items(user, db):
    """Create gear catalog items with prices."""
    items = {}

    # Photography gear
    items["camera_housing"] = CatalogItem.objects.create(
        display_name="Underwater Camera Housing",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["camera_housing"],
        amount=Decimal("299.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    items["dive_light"] = CatalogItem.objects.create(
        display_name="Dive Light - Night Diving",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["dive_light"],
        amount=Decimal("89.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    items["backup_light"] = CatalogItem.objects.create(
        display_name="Backup Dive Light",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["backup_light"],
        amount=Decimal("45.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    # Beginner gear
    items["dive_computer"] = CatalogItem.objects.create(
        display_name="Beginner Dive Computer",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["dive_computer"],
        amount=Decimal("199.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    items["mask"] = CatalogItem.objects.create(
        display_name="Scuba Mask - Low Volume",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["mask"],
        amount=Decimal("65.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    items["fins"] = CatalogItem.objects.create(
        display_name="Open Heel Fins",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["fins"],
        amount=Decimal("89.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    # Wreck diving gear
    items["reel"] = CatalogItem.objects.create(
        display_name="Safety Reel - Wreck Diving",
        kind="stock_item",
        is_billable=True,
        active=True,
    )
    Price.objects.create(
        catalog_item=items["reel"],
        amount=Decimal("55.00"),
        currency="USD",
        valid_from=timezone.now(),
        created_by=user,
        reason="Standard price",
    )

    return items


@pytest.mark.django_db
class TestGetRecommendedGear:
    """Tests for get_recommended_gear selector."""

    def test_returns_list_of_recommendations(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Returns a list of gear recommendation dicts."""
        recommendations = get_recommended_gear(diver)
        assert isinstance(recommendations, list)

    def test_recommends_photography_gear_for_photography_interest(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Recommends camera gear when user has photography interests."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["interests"],
            value_json=["Macro photography"],
        )

        recommendations = get_recommended_gear(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Camera" in name for name in names)

    def test_recommends_dive_light_for_night_interest(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Recommends dive light when user has night diving interests."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["interests"],
            value_json=["Night diving"],
        )

        recommendations = get_recommended_gear(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Light" in name or "light" in name for name in names)

    def test_recommends_reel_for_wreck_interest(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Recommends safety reel when user has wreck diving interests."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        PartyPreference.objects.create(
            person=diver.person,
            definition=preference_definitions["interests"],
            value_json=["Wrecks"],
        )

        recommendations = get_recommended_gear(diver)

        names = [r["item"].display_name for r in recommendations]
        assert any("Reel" in name for name in names)

    def test_recommends_basic_gear_for_new_diver(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Recommends basic gear (computer, mask, fins) for new OW diver."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_gear(diver)

        names = [r["item"].display_name for r in recommendations]
        # Should recommend at least one basic item
        has_basic = any(
            keyword in name
            for name in names
            for keyword in ["Computer", "Mask", "Fins"]
        )
        assert has_basic

    def test_includes_price_in_recommendation(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Each recommendation includes the current price."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_gear(diver)

        for rec in recommendations:
            assert "price" in rec

    def test_includes_reason_in_recommendation(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Each recommendation includes a reason string."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_gear(diver)

        for rec in recommendations:
            assert "reason" in rec
            assert isinstance(rec["reason"], str)
            assert len(rec["reason"]) > 0

    def test_respects_limit_parameter(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Limits number of recommendations returned."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_gear(diver, limit=2)
        assert len(recommendations) <= 2

    def test_excludes_inactive_gear(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Does not recommend inactive catalog items."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        # Deactivate dive computer
        gear_items["dive_computer"].active = False
        gear_items["dive_computer"].save()

        recommendations = get_recommended_gear(diver)

        names = [r["item"].display_name for r in recommendations]
        assert "Beginner Dive Computer" not in names

    def test_returns_starter_kit_for_uncertified_diver(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Returns starter kit recommendations even for uncertified/student divers."""
        # Without any certifications, should still recommend starter kit
        recommendations = get_recommended_gear(diver)
        # Should have starter kit items (mask, snorkel, fins)
        names = [r["item"].display_name for r in recommendations]
        has_starter_kit = any(
            k in name for name in names for k in ["Mask", "Snorkel", "Fins"]
        )
        assert has_starter_kit

    def test_starter_kit_items_prioritized_first(
        self, diver, certification_levels, gear_items, preference_definitions
    ):
        """Starter kit (mask, snorkel, fins) should appear first."""
        DiverCertification.objects.create(
            diver=diver,
            level=certification_levels["ow"],
            issued_on=timezone.now().date(),
        )

        recommendations = get_recommended_gear(diver, limit=5)
        names = [r["item"].display_name for r in recommendations]

        # First 3 should be starter kit items (mask, snorkel, fins in some order)
        starter_kit_in_first_three = sum(
            1 for name in names[:3]
            if any(k in name for k in ["Mask", "Snorkel", "Fins"])
        )
        assert starter_kit_in_first_three >= 2  # At least 2 starter kit items in top 3
