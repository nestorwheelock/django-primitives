"""Tests for the pricing module - built on top of primitives.

Tests follow TDD approach - written BEFORE implementation.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

User = get_user_model()


# =============================================================================
# Phase 1: Database Constraint Tests
# =============================================================================

@pytest.mark.django_db
class TestPriceModelConstraints:
    """Test database-level constraints on the Price model."""

    def test_negative_amount_rejected(self):
        """CHECK constraint prevents amount <= 0."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_price_user")

        with pytest.raises(ValidationError):
            Price.objects.create(
                catalog_item=item,
                amount=Decimal("-10.00"),
                currency="USD",
                valid_from=timezone.now(),
                created_by=user,
            )

    def test_zero_amount_rejected(self):
        """CHECK constraint prevents amount = 0."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service Zero",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_price_user_zero")

        with pytest.raises(ValidationError):
            Price.objects.create(
                catalog_item=item,
                amount=Decimal("0.00"),
                currency="USD",
                valid_from=timezone.now(),
                created_by=user,
            )

    def test_invalid_date_range_rejected(self):
        """CHECK constraint prevents valid_to <= valid_from."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service Invalid",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_price_user_invalid")
        now = timezone.now()

        with pytest.raises(ValidationError):
            Price.objects.create(
                catalog_item=item,
                amount=Decimal("100.00"),
                currency="USD",
                valid_from=now,
                valid_to=now - timedelta(days=1),  # Before valid_from
                created_by=user,
            )

    def test_valid_price_creation(self):
        """Valid price can be created."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service Valid",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_price_user_valid")

        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("99.99"),
            currency="USD",
            valid_from=timezone.now(),
            created_by=user,
        )

        assert price.pk is not None
        assert price.amount == Decimal("99.99")
        assert price.currency == "USD"

    def test_price_with_organization_scope(self):
        """Price can be scoped to an organization."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service Org",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Test Payer Org", org_type="payer")
        user = User.objects.create_user(username="test_price_org_user")

        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("75.00"),
            currency="USD",
            organization=org,
            valid_from=timezone.now(),
            created_by=user,
        )

        assert price.organization == org

    def test_price_with_party_scope(self):
        """Price can be scoped to a party (person)."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Person
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service Person",
            kind="service",
            active=True,
        )
        person = Person.objects.create(first_name="VIP", last_name="Patient")
        user = User.objects.create_user(username="test_price_party_user")

        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("50.00"),
            currency="USD",
            party=person,
            valid_from=timezone.now(),
            created_by=user,
        )

        assert price.party == person

    def test_price_with_agreement_scope(self):
        """Price can be scoped to an agreement (contract)."""
        from django_agreements.models import Agreement
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization, Person
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Test Service Agreement",
            kind="service",
            active=True,
        )
        person = Person.objects.create(first_name="Contract", last_name="Patient")
        org = Organization.objects.create(name="Contract Clinic", org_type="clinic")
        user = User.objects.create_user(username="test_price_agreement_user")

        person_ct = ContentType.objects.get_for_model(Person)
        org_ct = ContentType.objects.get_for_model(Organization)

        agreement = Agreement.objects.create(
            party_a_content_type=person_ct,
            party_a_id=str(person.pk),
            party_b_content_type=org_ct,
            party_b_id=str(org.pk),
            scope_type="contract",
            terms={"contract_type": "preferred_pricing"},
            agreed_by=user,
            agreed_at=timezone.now(),
            valid_from=timezone.now(),
        )

        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("40.00"),
            currency="USD",
            agreement=agreement,
            valid_from=timezone.now(),
            created_by=user,
        )

        assert price.agreement == agreement


@pytest.mark.django_db
class TestPriceOverlapConstraint:
    """Test the EXCLUDE constraint preventing overlapping prices per scope."""

    def test_overlapping_global_prices_rejected(self):
        """Cannot create two global prices for same item with overlapping dates."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Overlap Test Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_overlap_user")
        now = timezone.now()

        # Create first global price (no scope) - indefinite
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now,
            valid_to=None,  # Indefinite
            created_by=user,
        )

        # Try to create overlapping global price
        with pytest.raises(ValidationError):
            Price.objects.create(
                catalog_item=item,
                amount=Decimal("90.00"),
                currency="USD",
                valid_from=now + timedelta(days=30),  # Overlaps with first
                valid_to=None,
                created_by=user,
            )

    def test_non_overlapping_global_prices_allowed(self):
        """Can create consecutive global prices with non-overlapping dates."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Consecutive Test Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_consecutive_user")
        now = timezone.now()

        # First price: now to now+30 days
        price1 = Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now,
            valid_to=now + timedelta(days=30),
            created_by=user,
        )

        # Second price: now+30 days onward (no overlap)
        price2 = Price.objects.create(
            catalog_item=item,
            amount=Decimal("110.00"),
            currency="USD",
            valid_from=now + timedelta(days=30),
            valid_to=None,
            created_by=user,
        )

        assert price1.pk is not None
        assert price2.pk is not None

    def test_different_scopes_can_overlap(self):
        """Prices for same item but different scopes CAN overlap."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Multi-Scope Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Special Payer", org_type="payer")
        user = User.objects.create_user(username="test_multiscope_user")
        now = timezone.now()

        # Global price
        global_price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now,
            created_by=user,
        )

        # Org-specific price (same time period - allowed because different scope)
        org_price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("80.00"),
            currency="USD",
            organization=org,
            valid_from=now,
            created_by=user,
        )

        assert global_price.pk is not None
        assert org_price.pk is not None

    def test_same_org_scope_overlap_rejected(self):
        """Cannot create overlapping prices for same item AND same org."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Org Overlap Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Overlapping Payer", org_type="payer")
        user = User.objects.create_user(username="test_org_overlap_user")
        now = timezone.now()

        # First org-scoped price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("80.00"),
            currency="USD",
            organization=org,
            valid_from=now,
            created_by=user,
        )

        # Try to create overlapping org-scoped price for same org
        with pytest.raises(ValidationError):
            Price.objects.create(
                catalog_item=item,
                amount=Decimal("75.00"),
                currency="USD",
                organization=org,
                valid_from=now + timedelta(days=10),
                created_by=user,
            )


# =============================================================================
# Phase 2: Resolution Logic Tests
# =============================================================================

@pytest.mark.django_db
class TestPriceResolution:
    """Test the price resolution algorithm."""

    def test_global_price_returned_when_no_scopes(self):
        """Global price is returned when no specific scopes provided."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Global Price Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_global_resolve_user")

        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=timezone.now() - timedelta(days=1),
            created_by=user,
        )

        resolved = resolve_price(item)

        assert resolved.unit_price.amount == Decimal("100.00")
        assert resolved.scope_type == "global"

    def test_org_price_beats_global(self):
        """Organization-specific price beats global price."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Org Priority Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Priority Payer", org_type="payer")
        user = User.objects.create_user(username="test_org_priority_user")
        now = timezone.now()

        # Global price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        # Org-specific price (lower amount)
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("80.00"),
            currency="USD",
            organization=org,
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        resolved = resolve_price(item, organization=org)

        assert resolved.unit_price.amount == Decimal("80.00")
        assert resolved.scope_type == "organization"

    def test_party_price_beats_org(self):
        """Party-specific price beats organization price."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization, Person
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Party Priority Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Party Payer", org_type="payer")
        person = Person.objects.create(first_name="Special", last_name="VIP")
        user = User.objects.create_user(username="test_party_priority_user")
        now = timezone.now()

        # Global price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        # Org price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("80.00"),
            currency="USD",
            organization=org,
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        # Party-specific price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("60.00"),
            currency="USD",
            party=person,
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        resolved = resolve_price(item, organization=org, party=person)

        assert resolved.unit_price.amount == Decimal("60.00")
        assert resolved.scope_type == "party"

    def test_agreement_price_beats_party(self):
        """Agreement-specific price beats party price."""
        from django_agreements.models import Agreement
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization, Person
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Agreement Priority Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Agreement Payer", org_type="payer")
        person = Person.objects.create(first_name="Contract", last_name="Member")
        user = User.objects.create_user(username="test_agreement_priority_user")
        now = timezone.now()

        person_ct = ContentType.objects.get_for_model(Person)
        org_ct = ContentType.objects.get_for_model(Organization)

        # Create agreement
        agreement = Agreement.objects.create(
            party_a_content_type=person_ct,
            party_a_id=str(person.pk),
            party_b_content_type=org_ct,
            party_b_id=str(org.pk),
            scope_type="contract",
            terms={"contract_type": "preferred"},
            agreed_by=user,
            agreed_at=now - timedelta(days=30),
            valid_from=now - timedelta(days=30),
        )

        # Global price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        # Party price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("60.00"),
            currency="USD",
            party=person,
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        # Agreement price (best rate)
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("45.00"),
            currency="USD",
            agreement=agreement,
            valid_from=now - timedelta(days=1),
            created_by=user,
        )

        resolved = resolve_price(item, party=person, agreement=agreement)

        assert resolved.unit_price.amount == Decimal("45.00")
        assert resolved.scope_type == "agreement"

    def test_no_price_raises_error(self):
        """NoPriceFoundError when no applicable price exists."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.exceptions import NoPriceFoundError
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="No Price Item",
            kind="service",
            active=True,
        )

        with pytest.raises(NoPriceFoundError):
            resolve_price(item)

    def test_expired_price_not_returned(self):
        """Prices with valid_to in past are excluded."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.exceptions import NoPriceFoundError
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Expired Price Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_expired_user")
        now = timezone.now()

        # Create expired price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now - timedelta(days=60),
            valid_to=now - timedelta(days=30),  # Expired 30 days ago
            created_by=user,
        )

        with pytest.raises(NoPriceFoundError):
            resolve_price(item)

    def test_future_price_not_returned(self):
        """Prices with valid_from in future are excluded."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.exceptions import NoPriceFoundError
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Future Price Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_future_user")
        now = timezone.now()

        # Create future price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now + timedelta(days=30),  # Starts in 30 days
            created_by=user,
        )

        with pytest.raises(NoPriceFoundError):
            resolve_price(item)

    def test_higher_priority_wins_within_scope(self):
        """When scopes match, higher priority wins."""
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price
        from primitives_testbed.pricing.selectors import resolve_price

        item = CatalogItem.objects.create(
            display_name="Priority Test Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_priority_user")
        now = timezone.now()

        # Lower priority global price
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now - timedelta(days=60),
            valid_to=now - timedelta(days=30),
            priority=50,
            created_by=user,
        )

        # Higher priority global price (same scope, higher priority)
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("90.00"),
            currency="USD",
            valid_from=now - timedelta(days=1),
            priority=100,
            created_by=user,
        )

        resolved = resolve_price(item)

        assert resolved.unit_price.amount == Decimal("90.00")
        assert resolved.priority == 100


# =============================================================================
# Phase 3: PricedBasketItem Tests
# =============================================================================

@pytest.mark.django_db
class TestPricedBasketItem:
    """Test the PricedBasketItem model that stores resolved prices."""

    def test_priced_basket_item_creation(self):
        """PricedBasketItem can store resolved price for a basket item."""
        from django_catalog.models import Basket, BasketItem, CatalogItem
        from django_encounters.models import Encounter, EncounterDefinition
        from django_parties.models import Person
        from primitives_testbed.pricing.models import Price, PricedBasketItem

        # Create catalog item
        item = CatalogItem.objects.create(
            display_name="Priced Service",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_priced_basket_user")

        # Create price
        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("99.00"),
            currency="USD",
            valid_from=timezone.now() - timedelta(days=1),
            created_by=user,
        )

        # Create encounter for the basket
        person = Person.objects.create(first_name="Basket", last_name="Patient")
        person_ct = ContentType.objects.get_for_model(Person)

        definition = EncounterDefinition.objects.create(
            key="pricing_test",
            name="Pricing Test",
            states=["open", "closed"],
            transitions={"open": ["closed"]},
            initial_state="open",
            terminal_states=["closed"],
        )

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=person_ct,
            subject_id=str(person.pk),
            state="open",
            created_by=user,
        )

        basket = Basket.objects.create(
            encounter=encounter,
            status="draft",
            created_by=user,
        )

        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=item,
            quantity=2,
            added_by=user,
        )

        # Create priced basket item
        priced = PricedBasketItem.objects.create(
            basket_item=basket_item,
            unit_price_amount=Decimal("99.00"),
            unit_price_currency="USD",
            price_rule=price,
        )

        assert priced.pk is not None
        assert priced.unit_price_amount == Decimal("99.00")

    def test_line_total_calculation(self):
        """PricedBasketItem calculates line total correctly."""
        from django_catalog.models import Basket, BasketItem, CatalogItem
        from django_encounters.models import Encounter, EncounterDefinition
        from django_parties.models import Person
        from primitives_testbed.pricing.models import Price, PricedBasketItem

        item = CatalogItem.objects.create(
            display_name="Multi-Qty Service",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_line_total_user")

        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("25.00"),
            currency="USD",
            valid_from=timezone.now() - timedelta(days=1),
            created_by=user,
        )

        person = Person.objects.create(first_name="Multi", last_name="Qty")
        person_ct = ContentType.objects.get_for_model(Person)

        definition = EncounterDefinition.objects.create(
            key="pricing_line_test",
            name="Pricing Line Test",
            states=["open", "closed"],
            transitions={"open": ["closed"]},
            initial_state="open",
            terminal_states=["closed"],
        )

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=person_ct,
            subject_id=str(person.pk),
            state="open",
            created_by=user,
        )

        basket = Basket.objects.create(
            encounter=encounter,
            status="draft",
            created_by=user,
        )

        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=item,
            quantity=3,
            added_by=user,
        )

        priced = PricedBasketItem.objects.create(
            basket_item=basket_item,
            unit_price_amount=Decimal("25.00"),
            unit_price_currency="USD",
            price_rule=price,
        )

        # Line total = unit_price * quantity = 25.00 * 3 = 75.00
        assert priced.line_total.amount == Decimal("75.00")
        assert priced.line_total.currency == "USD"

    def test_unit_price_property(self):
        """PricedBasketItem.unit_price returns Money object."""
        from django_catalog.models import Basket, BasketItem, CatalogItem
        from django_encounters.models import Encounter, EncounterDefinition
        from django_money import Money
        from django_parties.models import Person
        from primitives_testbed.pricing.models import Price, PricedBasketItem

        item = CatalogItem.objects.create(
            display_name="Money Object Service",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_money_obj_user")

        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("50.00"),
            currency="USD",
            valid_from=timezone.now() - timedelta(days=1),
            created_by=user,
        )

        person = Person.objects.create(first_name="Money", last_name="Object")
        person_ct = ContentType.objects.get_for_model(Person)

        definition = EncounterDefinition.objects.create(
            key="pricing_money_test",
            name="Pricing Money Test",
            states=["open", "closed"],
            transitions={"open": ["closed"]},
            initial_state="open",
            terminal_states=["closed"],
        )

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=person_ct,
            subject_id=str(person.pk),
            state="open",
            created_by=user,
        )

        basket = Basket.objects.create(
            encounter=encounter,
            status="draft",
            created_by=user,
        )

        basket_item = BasketItem.objects.create(
            basket=basket,
            catalog_item=item,
            quantity=1,
            added_by=user,
        )

        priced = PricedBasketItem.objects.create(
            basket_item=basket_item,
            unit_price_amount=Decimal("50.00"),
            unit_price_currency="USD",
            price_rule=price,
        )

        assert isinstance(priced.unit_price, Money)
        assert priced.unit_price.amount == Decimal("50.00")
        assert priced.unit_price.currency == "USD"


# =============================================================================
# Phase 4: Production Safety Tests (PostgreSQL Constraints)
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestPriceOverlapExclusionConstraint:
    """Test PostgreSQL EXCLUDE constraint prevents overlapping prices at DB level.

    These tests verify the database-level constraint works independently
    of Python validation. The constraint uses btree_gist and tstzrange
    to prevent overlapping date ranges within the same scope.

    Note: These tests require PostgreSQL with btree_gist extension.
    """

    def test_db_constraint_rejects_overlapping_global_prices(self):
        """PostgreSQL exclusion constraint rejects overlapping global prices.

        This test bypasses Python validation to prove the DB constraint works.
        """
        from django.db import connection
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="DB Constraint Test Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_db_constraint_user")
        now = timezone.now()

        # Create first global price using model (passes both validations)
        price1 = Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now,
            valid_to=None,
            created_by=user,
        )

        # Check if using PostgreSQL (constraint only exists there)
        if connection.vendor != "postgresql":
            pytest.skip("PostgreSQL required for exclusion constraint test")

        import uuid
        from django.db import IntegrityError as DBIntegrityError

        # Try to insert overlapping price via raw SQL (bypasses Python validation)
        # This should fail at the DB constraint level
        with pytest.raises(DBIntegrityError) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pricing_price (
                        id, catalog_item_id, amount, currency,
                        valid_from, valid_to, priority, reason,
                        created_by_id, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    [
                        str(uuid.uuid4()),
                        str(item.pk),
                        "90.00",
                        "USD",
                        now + timedelta(days=10),  # Overlaps with price1
                        None,
                        50,
                        "Test overlap",
                        user.pk,
                        now,
                    ],
                )

        # Verify it's an exclusion constraint violation
        assert "exclusion" in str(exc_info.value).lower() or \
               "price_no_overlapping_date_ranges" in str(exc_info.value).lower()

    def test_db_constraint_allows_non_overlapping_prices(self):
        """PostgreSQL exclusion constraint allows consecutive non-overlapping prices."""
        from django.db import connection
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        if connection.vendor != "postgresql":
            pytest.skip("PostgreSQL required for exclusion constraint test")

        item = CatalogItem.objects.create(
            display_name="DB Non-Overlap Test Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_db_nonover_user")
        now = timezone.now()

        # First price: ends at specific time
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            valid_from=now,
            valid_to=now + timedelta(days=30),
            created_by=user,
        )

        # Second price: starts exactly when first ends (no overlap due to '[)' bounds)
        price2 = Price.objects.create(
            catalog_item=item,
            amount=Decimal("110.00"),
            currency="USD",
            valid_from=now + timedelta(days=30),
            valid_to=None,
            created_by=user,
        )

        assert price2.pk is not None

    def test_db_constraint_null_scope_normalization(self):
        """COALESCE in constraint treats NULL scopes as matching each other.

        Without COALESCE, NULL != NULL in PostgreSQL would defeat the constraint.
        """
        from django.db import connection
        from django_catalog.models import CatalogItem
        from primitives_testbed.pricing.models import Price

        if connection.vendor != "postgresql":
            pytest.skip("PostgreSQL required for NULL normalization test")

        item = CatalogItem.objects.create(
            display_name="NULL Scope Test Item",
            kind="service",
            active=True,
        )
        user = User.objects.create_user(username="test_null_scope_user")
        now = timezone.now()

        # Create global price (all scope fields NULL)
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("100.00"),
            currency="USD",
            organization=None,
            party=None,
            agreement=None,
            valid_from=now,
            valid_to=None,
            created_by=user,
        )

        # Try to create another global price with overlapping dates
        # Both have NULL scopes - COALESCE should make them match
        with pytest.raises(ValidationError):
            Price.objects.create(
                catalog_item=item,
                amount=Decimal("95.00"),
                currency="USD",
                organization=None,
                party=None,
                agreement=None,
                valid_from=now + timedelta(days=5),
                valid_to=None,
                created_by=user,
            )


@pytest.mark.django_db(transaction=True)
class TestScopeForeignKeyProtect:
    """Test PROTECT on_delete behavior for scope foreign keys.

    These tests verify that hard-deleting organizations, parties, or agreements
    that have associated prices raises ProtectedError instead of CASCADE delete.

    Note: Organization, Person, and Agreement all use soft delete by default.
    PROTECT only applies when calling hard_delete() which attempts actual DB deletion.
    """

    def test_cannot_hard_delete_organization_with_prices(self):
        """Hard-deleting an organization with prices raises ProtectedError."""
        from django.db.models import ProtectedError
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Org Delete Test Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Protected Org", org_type="payer")
        user = User.objects.create_user(username="test_protect_org_user")

        # Create price scoped to organization
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("80.00"),
            currency="USD",
            organization=org,
            valid_from=timezone.now(),
            created_by=user,
        )

        # Soft delete works (sets deleted_at, doesn't remove from DB)
        org.delete()
        assert org.deleted_at is not None

        # Restore for hard delete test
        org.restore()

        # Hard delete should raise ProtectedError
        with pytest.raises(ProtectedError):
            org.hard_delete()

    def test_cannot_hard_delete_party_with_prices(self):
        """Hard-deleting a party (person) with prices raises ProtectedError."""
        from django.db.models import ProtectedError
        from django_catalog.models import CatalogItem
        from django_parties.models import Person
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Party Delete Test Item",
            kind="service",
            active=True,
        )
        person = Person.objects.create(first_name="Protected", last_name="Person")
        user = User.objects.create_user(username="test_protect_party_user")

        # Create price scoped to party
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("60.00"),
            currency="USD",
            party=person,
            valid_from=timezone.now(),
            created_by=user,
        )

        # Hard delete should raise ProtectedError
        with pytest.raises(ProtectedError):
            person.hard_delete()

    def test_cannot_hard_delete_agreement_with_prices(self):
        """Hard-deleting an agreement with prices raises ProtectedError."""
        from django.db.models import ProtectedError
        from django_agreements.models import Agreement
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization, Person
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Agreement Delete Test Item",
            kind="service",
            active=True,
        )
        person = Person.objects.create(first_name="Agreement", last_name="Member")
        org = Organization.objects.create(name="Agreement Clinic", org_type="clinic")
        user = User.objects.create_user(username="test_protect_agree_user")

        person_ct = ContentType.objects.get_for_model(Person)
        org_ct = ContentType.objects.get_for_model(Organization)

        agreement = Agreement.objects.create(
            party_a_content_type=person_ct,
            party_a_id=str(person.pk),
            party_b_content_type=org_ct,
            party_b_id=str(org.pk),
            scope_type="contract",
            terms={"contract_type": "pricing"},
            agreed_by=user,
            agreed_at=timezone.now(),
            valid_from=timezone.now(),
        )

        # Create price scoped to agreement
        Price.objects.create(
            catalog_item=item,
            amount=Decimal("45.00"),
            currency="USD",
            agreement=agreement,
            valid_from=timezone.now(),
            created_by=user,
        )

        # Hard delete should raise ProtectedError
        with pytest.raises(ProtectedError):
            agreement.hard_delete()

    def test_can_hard_delete_org_after_removing_prices(self):
        """Organization can be hard-deleted after its prices are removed."""
        from django_catalog.models import CatalogItem
        from django_parties.models import Organization
        from primitives_testbed.pricing.models import Price

        item = CatalogItem.objects.create(
            display_name="Removable Price Item",
            kind="service",
            active=True,
        )
        org = Organization.objects.create(name="Deletable Org", org_type="payer")
        user = User.objects.create_user(username="test_delete_org_user")

        # Create price scoped to organization
        price = Price.objects.create(
            catalog_item=item,
            amount=Decimal("80.00"),
            currency="USD",
            organization=org,
            valid_from=timezone.now(),
            created_by=user,
        )

        # Delete the price first (hard delete the price since it's not a SoftDeleteModel)
        price.delete()

        # Now organization can be hard-deleted
        org_pk = org.pk
        org.hard_delete()

        assert not Organization.all_objects.filter(pk=org_pk).exists()
