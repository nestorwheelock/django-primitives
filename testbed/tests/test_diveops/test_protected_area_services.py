"""Tests for protected area inheritance-aware services.

Tests the get_applicable_rules and get_applicable_fee_schedules services
that resolve rules and fees from a zone up through the area hierarchy.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from primitives_testbed.diveops.models import (
    ProtectedArea,
    ProtectedAreaFeeSchedule,
    ProtectedAreaFeeTier,
    ProtectedAreaRule,
    ProtectedAreaZone,
)
from primitives_testbed.diveops.services import (
    get_applicable_fee_schedules,
    get_applicable_rules,
)


@pytest.fixture
def area_hierarchy(db):
    """Create a three-level protected area hierarchy.

    Region (biosphere_reserve)
    └── Park (marine_park)
        └── Zone
    """
    region = ProtectedArea.objects.create(
        name="Caribbean Biosphere Reserve",
        code="caribbean-br",
        designation_type="biosphere_reserve",
        is_active=True,
    )
    park = ProtectedArea.objects.create(
        name="Cozumel Marine Park",
        code="cozumel-mp",
        designation_type="marine_park",
        parent=region,
        is_active=True,
    )
    zone = ProtectedAreaZone.objects.create(
        protected_area=park,
        name="No-Take Zone A",
        code="ntz-a",
        zone_type="core",
        is_active=True,
    )
    return {"region": region, "park": park, "zone": zone}


class TestGetApplicableRules:
    """Tests for get_applicable_rules service."""

    def test_zone_specific_rules_returned(self, area_hierarchy):
        """Rules specific to a zone are included."""
        zone = area_hierarchy["zone"]
        park = area_hierarchy["park"]

        zone_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=zone,
            rule_type="limit",
            subject="Max divers",
            activity="diving",
            operator="<=",
            value="8",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        rules = get_applicable_rules(protected_area=park, zone=zone)

        assert len(rules) >= 1
        assert zone_rule in rules

    def test_area_wide_rules_returned_when_no_zone(self, area_hierarchy):
        """Area-wide rules (zone=null) are included when no zone specified."""
        park = area_hierarchy["park"]

        area_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,  # Area-wide
            rule_type="prohibition",
            subject="No anchoring",
            activity="mooring",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        rules = get_applicable_rules(protected_area=park)

        assert len(rules) >= 1
        assert area_rule in rules

    def test_ancestor_rules_inherited(self, area_hierarchy):
        """Rules from ancestor areas are inherited."""
        region = area_hierarchy["region"]
        park = area_hierarchy["park"]

        # Create a region-wide rule
        region_rule = ProtectedAreaRule.objects.create(
            protected_area=region,
            zone=None,
            rule_type="prohibition",
            subject="No spearfishing",
            activity="fishing",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        # Query rules for the park - should include region's rules
        rules = get_applicable_rules(protected_area=park)

        assert region_rule in rules

    def test_zone_plus_area_plus_ancestor_rules(self, area_hierarchy):
        """All levels of rules are included: zone + area + ancestors."""
        region = area_hierarchy["region"]
        park = area_hierarchy["park"]
        zone = area_hierarchy["zone"]

        # Region-level rule
        region_rule = ProtectedAreaRule.objects.create(
            protected_area=region,
            zone=None,
            rule_type="prohibition",
            subject="No spearfishing",
            activity="fishing",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        # Park-level rule
        park_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Max group size",
            activity="diving",
            operator="<=",
            value="12",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        # Zone-specific rule
        zone_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=zone,
            rule_type="limit",
            subject="Max divers",
            activity="diving",
            operator="<=",
            value="8",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        rules = get_applicable_rules(protected_area=park, zone=zone)

        assert len(rules) == 3
        assert zone_rule in rules
        assert park_rule in rules
        assert region_rule in rules

    def test_effective_date_filtering(self, area_hierarchy):
        """Only rules effective on the given date are included."""
        park = area_hierarchy["park"]
        today = date.today()

        # Future rule - not yet effective
        future_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Future limit",
            activity="diving",
            enforcement_level="mandatory",
            effective_start=today + timedelta(days=30),
            is_active=True,
        )

        # Current rule
        current_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Current limit",
            activity="diving",
            enforcement_level="mandatory",
            effective_start=today - timedelta(days=30),
            is_active=True,
        )

        # Expired rule
        expired_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Expired limit",
            activity="diving",
            enforcement_level="mandatory",
            effective_start=today - timedelta(days=60),
            effective_end=today - timedelta(days=1),
            is_active=True,
        )

        rules = get_applicable_rules(protected_area=park, as_of=today)

        assert current_rule in rules
        assert future_rule not in rules
        assert expired_rule not in rules

    def test_activity_filtering(self, area_hierarchy):
        """Only rules for the given activity are included."""
        park = area_hierarchy["park"]

        diving_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Max divers",
            activity="diving",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        snorkel_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Max snorkelers",
            activity="snorkeling",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        all_activity_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="prohibition",
            subject="No touching coral",
            activity="all",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )

        rules = get_applicable_rules(protected_area=park, activity="diving")

        assert diving_rule in rules
        assert all_activity_rule in rules
        assert snorkel_rule not in rules

    def test_inactive_rules_excluded(self, area_hierarchy):
        """Inactive rules are not included."""
        park = area_hierarchy["park"]

        inactive_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Inactive rule",
            activity="diving",
            enforcement_level="mandatory",
            effective_start=date.today() - timedelta(days=30),
            is_active=False,
        )

        rules = get_applicable_rules(protected_area=park)

        assert inactive_rule not in rules

    def test_as_of_defaults_to_today(self, area_hierarchy):
        """When as_of is not provided, it defaults to today."""
        park = area_hierarchy["park"]
        today = date.today()

        current_rule = ProtectedAreaRule.objects.create(
            protected_area=park,
            zone=None,
            rule_type="limit",
            subject="Current rule",
            activity="diving",
            enforcement_level="mandatory",
            effective_start=today - timedelta(days=1),
            is_active=True,
        )

        # Call without as_of - should use today
        rules = get_applicable_rules(protected_area=park)

        assert current_rule in rules


class TestGetApplicableFeeSchedules:
    """Tests for get_applicable_fee_schedules service."""

    def test_zone_specific_fees_returned(self, area_hierarchy):
        """Fee schedules specific to a zone are included."""
        zone = area_hierarchy["zone"]
        park = area_hierarchy["park"]

        zone_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=zone,
            name="Core Zone Entry Fee",
            fee_type="entry",
            applies_to="foreign",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=zone_fee,
            tier_code="adult",
            label="Adult",
            amount=Decimal("500.00"),
        )

        fees = get_applicable_fee_schedules(protected_area=park, zone=zone)

        assert len(fees) >= 1
        assert zone_fee in fees

    def test_area_wide_fees_returned_when_no_zone(self, area_hierarchy):
        """Area-wide fees (zone=null) are included when no zone specified."""
        park = area_hierarchy["park"]

        area_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,  # Area-wide
            name="Park Entry Fee",
            fee_type="entry",
            applies_to="all",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=area_fee,
            tier_code="adult",
            label="Adult",
            amount=Decimal("200.00"),
        )

        fees = get_applicable_fee_schedules(protected_area=park)

        assert len(fees) >= 1
        assert area_fee in fees

    def test_ancestor_fees_inherited(self, area_hierarchy):
        """Fee schedules from ancestor areas are inherited."""
        region = area_hierarchy["region"]
        park = area_hierarchy["park"]

        region_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=region,
            zone=None,
            name="Biosphere Conservation Fee",
            fee_type="conservation",
            applies_to="all",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=region_fee,
            tier_code="person",
            label="Per Person",
            amount=Decimal("100.00"),
        )

        fees = get_applicable_fee_schedules(protected_area=park)

        assert region_fee in fees

    def test_zone_plus_area_plus_ancestor_fees(self, area_hierarchy):
        """All levels of fees are included: zone + area + ancestors."""
        region = area_hierarchy["region"]
        park = area_hierarchy["park"]
        zone = area_hierarchy["zone"]

        # Region-level fee
        region_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=region,
            zone=None,
            name="Biosphere Conservation Fee",
            fee_type="conservation",
            applies_to="all",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=region_fee,
            tier_code="person",
            label="Per Person",
            amount=Decimal("100.00"),
        )

        # Park-level fee
        park_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,
            name="Park Entry Fee",
            fee_type="entry",
            applies_to="foreign",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=park_fee,
            tier_code="adult",
            label="Adult",
            amount=Decimal("200.00"),
        )

        # Zone-specific fee
        zone_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=zone,
            name="Core Zone Surcharge",
            fee_type="supplement",
            applies_to="all",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=zone_fee,
            tier_code="diver",
            label="Per Diver",
            amount=Decimal("150.00"),
        )

        fees = get_applicable_fee_schedules(protected_area=park, zone=zone)

        assert len(fees) == 3
        assert zone_fee in fees
        assert park_fee in fees
        assert region_fee in fees

    def test_effective_date_filtering(self, area_hierarchy):
        """Only fee schedules effective on the given date are included."""
        park = area_hierarchy["park"]
        today = date.today()

        # Future fee - not yet effective
        future_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,
            name="Future Fee",
            fee_type="entry",
            applies_to="all",
            currency="MXN",
            effective_start=today + timedelta(days=30),
            is_active=True,
        )

        # Current fee
        current_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,
            name="Current Fee",
            fee_type="entry",
            applies_to="all",
            currency="MXN",
            effective_start=today - timedelta(days=30),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=current_fee,
            tier_code="adult",
            label="Adult",
            amount=Decimal("200.00"),
        )

        # Expired fee
        expired_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,
            name="Expired Fee",
            fee_type="entry",
            applies_to="all",
            currency="MXN",
            effective_start=today - timedelta(days=60),
            effective_end=today - timedelta(days=1),
            is_active=True,
        )

        fees = get_applicable_fee_schedules(protected_area=park, as_of=today)

        assert current_fee in fees
        assert future_fee not in fees
        assert expired_fee not in fees

    def test_inactive_fees_excluded(self, area_hierarchy):
        """Inactive fee schedules are not included."""
        park = area_hierarchy["park"]

        inactive_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,
            name="Inactive Fee",
            fee_type="entry",
            applies_to="all",
            currency="MXN",
            effective_start=date.today() - timedelta(days=30),
            is_active=False,
        )

        fees = get_applicable_fee_schedules(protected_area=park)

        assert inactive_fee not in fees

    def test_as_of_defaults_to_today(self, area_hierarchy):
        """When as_of is not provided, it defaults to today."""
        park = area_hierarchy["park"]
        today = date.today()

        current_fee = ProtectedAreaFeeSchedule.objects.create(
            protected_area=park,
            zone=None,
            name="Current Fee",
            fee_type="entry",
            applies_to="all",
            currency="MXN",
            effective_start=today - timedelta(days=1),
            is_active=True,
        )
        ProtectedAreaFeeTier.objects.create(
            schedule=current_fee,
            tier_code="adult",
            label="Adult",
            amount=Decimal("200.00"),
        )

        # Call without as_of - should use today
        fees = get_applicable_fee_schedules(protected_area=park)

        assert current_fee in fees
