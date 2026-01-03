"""Tests for check-in module.

Tests the pricing disclosure and consent checking functionality:
- Price list snapshot
- Pricing disclosure agreement creation
- Consent checking
- Invoice validation against disclosure
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django_agreements.models import Agreement
from django_catalog.models import CatalogItem
from django_encounters.models import Encounter, EncounterDefinition
from django_parties.models import Organization, Person

from primitives_testbed.pricing.models import Price

User = get_user_model()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def clinic(db):
    """Create the Springfield Family Clinic organization."""
    return Organization.objects.create(name="Springfield Family Clinic")


@pytest.fixture
def patient(db):
    """Create a test patient."""
    return Person.objects.create(
        first_name="James",
        last_name="Wilson",
        date_of_birth="1980-05-15",
    )


@pytest.fixture
def encounter_definition(db):
    """Create an encounter definition."""
    return EncounterDefinition.objects.get_or_create(
        key="clinic_visit",
        defaults={
            "name": "Clinic Visit",
            "initial_state": "scheduled",
            "states": ["scheduled", "confirmed", "checked_in", "completed", "cancelled"],
            "terminal_states": ["completed", "cancelled"],
            "transitions": {
                "scheduled": ["confirmed", "cancelled"],
                "confirmed": ["checked_in", "cancelled"],
                "checked_in": ["completed", "cancelled"],
            },
        },
    )[0]


@pytest.fixture
def encounter(db, patient, encounter_definition, user):
    """Create an encounter for the patient."""
    person_ct = ContentType.objects.get_for_model(Person)
    return Encounter.objects.create(
        definition=encounter_definition,
        subject_type=person_ct,
        subject_id=str(patient.pk),
        state="scheduled",
        created_by=user,
    )


@pytest.fixture
def billable_items(db):
    """Create billable catalog items."""
    items = []
    items_data = [
        ("Office Visit - Established", "service", True),
        ("Blood Draw", "service", True),
        ("Aspirin 100mg", "stock_item", True),
        ("Vital Signs", "service", False),  # Not billable
    ]
    for name, kind, billable in items_data:
        item = CatalogItem.objects.create(
            display_name=name,
            kind=kind,
            is_billable=billable,
            active=True,
        )
        items.append(item)
    return items


@pytest.fixture
def prices(db, billable_items, user):
    """Create prices for billable items."""
    now = timezone.now()
    prices = {}
    price_data = {
        "Office Visit - Established": Decimal("75.00"),
        "Blood Draw": Decimal("25.00"),
        "Aspirin 100mg": Decimal("12.50"),
    }
    for item in billable_items:
        if item.display_name in price_data:
            price = Price.objects.create(
                catalog_item=item,
                amount=price_data[item.display_name],
                currency="USD",
                priority=50,
                valid_from=now,
                created_by=user,
                reason="Standard price",
            )
            prices[item.display_name] = price
    return prices


# =============================================================================
# Price List Snapshot Tests
# =============================================================================


@pytest.mark.django_db
class TestPricelistSnapshot:
    """Tests for get_current_pricelist()."""

    def test_snapshots_all_billable_items(self, clinic, billable_items, prices):
        """Price list includes all billable items with prices."""
        from primitives_testbed.checkin.services import get_current_pricelist

        pricelist = get_current_pricelist(clinic)

        # Should have 3 billable items (excludes Vital Signs which is not billable)
        assert len(pricelist) == 3

        # Check item names
        names = [p["catalog_item_name"] for p in pricelist]
        assert "Office Visit - Established" in names
        assert "Blood Draw" in names
        assert "Aspirin 100mg" in names
        assert "Vital Signs" not in names

    def test_includes_price_metadata(self, clinic, billable_items, prices):
        """Each price entry includes required metadata."""
        from primitives_testbed.checkin.services import get_current_pricelist

        pricelist = get_current_pricelist(clinic)

        for entry in pricelist:
            assert "catalog_item_id" in entry
            assert "catalog_item_name" in entry
            assert "amount" in entry
            assert "currency" in entry
            assert "scope" in entry

    def test_excludes_non_billable_items(self, clinic, billable_items, prices):
        """Non-billable items are excluded from price list."""
        from primitives_testbed.checkin.services import get_current_pricelist

        pricelist = get_current_pricelist(clinic)

        names = [p["catalog_item_name"] for p in pricelist]
        assert "Vital Signs" not in names

    def test_excludes_items_without_price(self, clinic, billable_items, user):
        """Items without a current price are excluded."""
        from primitives_testbed.checkin.services import get_current_pricelist

        # Only create price for one item
        now = timezone.now()
        Price.objects.create(
            catalog_item=billable_items[0],  # Office Visit
            amount=Decimal("75.00"),
            currency="USD",
            priority=50,
            valid_from=now,
            created_by=user,
            reason="Standard price",
        )

        pricelist = get_current_pricelist(clinic)

        # Should only have the one priced item
        assert len(pricelist) == 1
        assert pricelist[0]["catalog_item_name"] == "Office Visit - Established"


# =============================================================================
# Pricing Disclosure Tests
# =============================================================================


@pytest.mark.django_db
class TestPricingDisclosure:
    """Tests for create_pricing_disclosure()."""

    def test_creates_agreement_with_prices(
        self, patient, clinic, user, billable_items, prices
    ):
        """Creates an Agreement with price snapshot in terms."""
        from primitives_testbed.checkin.services import create_pricing_disclosure

        disclosure = create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
        )

        assert isinstance(disclosure, Agreement)
        assert disclosure.scope_type == "pricing_disclosure"
        assert "prices" in disclosure.terms
        assert len(disclosure.terms["prices"]) == 3

    def test_links_to_encounter(
        self, patient, clinic, user, encounter, billable_items, prices
    ):
        """Disclosure can be linked to an encounter."""
        from primitives_testbed.checkin.services import create_pricing_disclosure

        disclosure = create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
            encounter=encounter,
        )

        # scope_ref should point to encounter
        assert disclosure.scope_ref == encounter

    def test_sets_validity_period(
        self, patient, clinic, user, billable_items, prices
    ):
        """Disclosure has valid_from and valid_to set."""
        from primitives_testbed.checkin.services import create_pricing_disclosure

        disclosure = create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
            valid_for_days=30,
        )

        assert disclosure.valid_from is not None
        assert disclosure.valid_to is not None
        # valid_to should be ~30 days after valid_from
        delta = disclosure.valid_to - disclosure.valid_from
        assert 29 <= delta.days <= 31

    def test_terms_contain_required_fields(
        self, patient, clinic, user, billable_items, prices
    ):
        """Terms contain all required metadata."""
        from primitives_testbed.checkin.services import create_pricing_disclosure

        disclosure = create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
        )

        terms = disclosure.terms
        assert terms["consent_type"] == "pricing_disclosure"
        assert terms["consent_name"] == "Price List Acknowledgment"
        assert "form_version" in terms
        assert "effective_date" in terms
        assert "prices" in terms
        assert "total_items" in terms
        assert "snapshot_at" in terms


# =============================================================================
# Consent Checking Tests
# =============================================================================


@pytest.mark.django_db
class TestConsentChecking:
    """Tests for consent checking functions."""

    def test_returns_missing_consents(self, patient, clinic, user):
        """Returns list of consent types patient needs to sign."""
        from primitives_testbed.checkin.services import get_missing_consents

        missing = get_missing_consents(patient, clinic)

        # Should include standard consents
        assert "general_consent" in missing
        assert "hipaa_acknowledgment" in missing
        assert "financial_responsibility" in missing
        assert "pricing_disclosure" in missing

    def test_excludes_signed_consents(self, patient, clinic, user):
        """Excludes consents that patient has already signed."""
        from django_agreements.services import create_agreement
        from primitives_testbed.checkin.services import get_missing_consents

        # Sign one consent
        now = timezone.now()
        create_agreement(
            party_a=patient,
            party_b=clinic,
            scope_type="consent",
            terms={
                "consent_type": "general_consent",
                "consent_name": "General Consent",
                "form_version": "2026-01",
            },
            agreed_by=user,
            valid_from=now,
            valid_to=now + timedelta(days=365),
        )

        missing = get_missing_consents(patient, clinic)

        assert "general_consent" not in missing
        assert "hipaa_acknowledgment" in missing

    def test_pricing_disclosure_in_required(self, patient, clinic, user):
        """Pricing disclosure is a required consent type."""
        from primitives_testbed.checkin.services import get_missing_consents

        missing = get_missing_consents(patient, clinic)

        assert "pricing_disclosure" in missing

    def test_has_valid_disclosure_true_when_current(
        self, patient, clinic, user, billable_items, prices
    ):
        """has_valid_pricing_disclosure returns True when disclosure is current."""
        from primitives_testbed.checkin.services import (
            create_pricing_disclosure,
            has_valid_pricing_disclosure,
        )

        # Create disclosure
        create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
        )

        assert has_valid_pricing_disclosure(patient, clinic) is True

    def test_has_valid_disclosure_false_when_expired(
        self, patient, clinic, user, billable_items, prices
    ):
        """has_valid_pricing_disclosure returns False when disclosure expired."""
        from django_agreements.services import create_agreement
        from primitives_testbed.checkin.services import (
            has_valid_pricing_disclosure,
            snapshot_prices_for_disclosure,
        )

        # Create expired disclosure
        now = timezone.now()
        terms = snapshot_prices_for_disclosure(clinic)
        create_agreement(
            party_a=patient,
            party_b=clinic,
            scope_type="pricing_disclosure",
            terms=terms,
            agreed_by=user,
            valid_from=now - timedelta(days=60),
            valid_to=now - timedelta(days=30),  # Expired 30 days ago
        )

        assert has_valid_pricing_disclosure(patient, clinic) is False

    def test_has_valid_disclosure_false_when_none(self, patient, clinic):
        """has_valid_pricing_disclosure returns False when no disclosure exists."""
        from primitives_testbed.checkin.services import has_valid_pricing_disclosure

        assert has_valid_pricing_disclosure(patient, clinic) is False


# =============================================================================
# Invoice Validation Tests
# =============================================================================


@pytest.mark.django_db
class TestInvoiceValidation:
    """Tests for invoice validation against pricing disclosure."""

    def test_validates_matching_prices(
        self, patient, clinic, user, encounter, billable_items, prices
    ):
        """No discrepancies when invoice matches disclosed prices."""
        from primitives_testbed.checkin.services import create_pricing_disclosure
        from primitives_testbed.checkin.validators import (
            validate_invoice_against_disclosure,
        )
        from primitives_testbed.invoicing.services import create_invoice_from_basket
        from django_catalog.models import Basket, BasketItem

        # Create pricing disclosure
        create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
            encounter=encounter,
        )

        # Create basket and invoice
        basket = Basket.objects.create(
            encounter=encounter,
            status="committed",
            created_by=user,
        )
        BasketItem.objects.create(
            basket=basket,
            catalog_item=billable_items[0],  # Office Visit
            quantity=1,
            added_by=user,
        )

        invoice = create_invoice_from_basket(
            basket=basket,
            created_by=user,
            issue_immediately=False,
        )

        discrepancies = validate_invoice_against_disclosure(invoice)
        assert discrepancies == []

    def test_detects_price_increase(
        self, patient, clinic, user, encounter, billable_items, prices
    ):
        """Detects when invoice price exceeds disclosed price."""
        from primitives_testbed.checkin.services import create_pricing_disclosure
        from primitives_testbed.checkin.validators import (
            validate_invoice_against_disclosure,
        )
        from primitives_testbed.invoicing.services import create_invoice_from_basket
        from django_catalog.models import Basket, BasketItem

        # Create pricing disclosure
        create_pricing_disclosure(
            patient=patient,
            organization=clinic,
            signed_by=user,
            encounter=encounter,
        )

        # Update price to be higher
        prices["Office Visit - Established"].amount = Decimal("100.00")
        prices["Office Visit - Established"].save()

        # Create basket and invoice (will use new higher price)
        basket = Basket.objects.create(
            encounter=encounter,
            status="committed",
            created_by=user,
        )
        BasketItem.objects.create(
            basket=basket,
            catalog_item=billable_items[0],  # Office Visit
            quantity=1,
            added_by=user,
        )

        invoice = create_invoice_from_basket(
            basket=basket,
            created_by=user,
            issue_immediately=False,
        )

        discrepancies = validate_invoice_against_disclosure(invoice)
        assert len(discrepancies) > 0
        assert "Office Visit" in discrepancies[0]

    def test_detects_missing_disclosure(self, patient, clinic, user, encounter, billable_items, prices):
        """Returns empty list with warning when no disclosure exists."""
        from primitives_testbed.checkin.validators import (
            validate_invoice_against_disclosure,
        )
        from primitives_testbed.invoicing.services import create_invoice_from_basket
        from django_catalog.models import Basket, BasketItem

        # Create basket and invoice WITHOUT disclosure
        basket = Basket.objects.create(
            encounter=encounter,
            status="committed",
            created_by=user,
        )
        BasketItem.objects.create(
            basket=basket,
            catalog_item=billable_items[0],
            quantity=1,
            added_by=user,
        )

        invoice = create_invoice_from_basket(
            basket=basket,
            created_by=user,
            issue_immediately=False,
        )

        # Should return empty (no disclosure to compare against)
        discrepancies = validate_invoice_against_disclosure(invoice)
        assert discrepancies == []
