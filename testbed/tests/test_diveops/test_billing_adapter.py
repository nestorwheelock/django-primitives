"""Tests for diveops billing adapter.

These tests verify the billing flow integration with primitives:
- Basket creation for bookings
- Price resolution via pricing module
- PricedBasketItem creation
- Invoice creation from basket
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


@pytest.fixture
def trip_catalog_item(db):
    """Create a CatalogItem for dive trips."""
    from django_catalog.models import CatalogItem

    return CatalogItem.objects.create(
        display_name="Standard Dive Trip",
        kind="service",
        is_billable=True,
        active=True,
    )


@pytest.fixture
def global_trip_price(db, trip_catalog_item, user):
    """Create a global price for dive trips."""
    from primitives_testbed.pricing.models import Price

    return Price.objects.create(
        catalog_item=trip_catalog_item,
        amount=Decimal("100.00"),
        currency="USD",
        valid_from=timezone.now() - timedelta(days=30),
        priority=50,
        created_by=user,
    )


@pytest.fixture
def dive_shop_price(db, trip_catalog_item, dive_shop, user):
    """Create an organization-specific price for dive shop."""
    from primitives_testbed.pricing.models import Price

    return Price.objects.create(
        catalog_item=trip_catalog_item,
        amount=Decimal("85.00"),
        currency="USD",
        organization=dive_shop,
        valid_from=timezone.now() - timedelta(days=30),
        priority=60,
        created_by=user,
    )


@pytest.mark.django_db
class TestCreateTripBasket:
    """Tests for create_trip_basket adapter function."""

    def test_create_trip_basket_returns_basket(
        self, dive_trip, diver_profile, trip_catalog_item, user
    ):
        """create_trip_basket creates a basket for the booking."""
        from primitives_testbed.diveops.integrations import create_trip_basket

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )

        assert basket is not None
        assert basket.pk is not None
        assert basket.status == "draft"

    def test_create_trip_basket_has_one_item(
        self, dive_trip, diver_profile, trip_catalog_item, user
    ):
        """Basket contains exactly one item (the trip)."""
        from primitives_testbed.diveops.integrations import create_trip_basket

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )

        assert basket.items.count() == 1
        item = basket.items.first()
        assert item.catalog_item == trip_catalog_item
        assert item.quantity == 1

    def test_create_trip_basket_creates_encounter(
        self, dive_trip, diver_profile, trip_catalog_item, user
    ):
        """Basket has an associated encounter for the booking workflow."""
        from primitives_testbed.diveops.integrations import create_trip_basket

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )

        assert basket.encounter is not None
        assert basket.encounter.state == "draft"


@pytest.mark.django_db
class TestResolveTripPrice:
    """Tests for resolve_trip_price adapter function."""

    def test_resolve_trip_price_uses_global_price(
        self, trip_catalog_item, global_trip_price, dive_trip, diver_profile
    ):
        """resolve_trip_price returns global price when no specific price exists."""
        from primitives_testbed.diveops.integrations import resolve_trip_price

        resolved = resolve_trip_price(
            catalog_item=trip_catalog_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        assert resolved.unit_price.amount == Decimal("100.00")
        assert resolved.scope_type == "global"

    def test_resolve_trip_price_prefers_organization_price(
        self, trip_catalog_item, global_trip_price, dive_shop_price, dive_trip, diver_profile
    ):
        """resolve_trip_price prefers organization-specific price over global."""
        from primitives_testbed.diveops.integrations import resolve_trip_price

        resolved = resolve_trip_price(
            catalog_item=trip_catalog_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        assert resolved.unit_price.amount == Decimal("85.00")
        assert resolved.scope_type == "organization"

    def test_resolve_trip_price_raises_when_no_price(
        self, trip_catalog_item, dive_trip, diver_profile
    ):
        """resolve_trip_price raises NoPriceFoundError when no price exists."""
        from primitives_testbed.diveops.integrations import resolve_trip_price
        from primitives_testbed.pricing.exceptions import NoPriceFoundError

        with pytest.raises(NoPriceFoundError):
            resolve_trip_price(
                catalog_item=trip_catalog_item,
                trip=dive_trip,
                diver=diver_profile,
            )


@pytest.mark.django_db
class TestPriceBasketItem:
    """Tests for price_basket_item adapter function."""

    def test_price_basket_item_creates_priced_item(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """price_basket_item creates PricedBasketItem with resolved price."""
        from primitives_testbed.diveops.integrations import (
            create_trip_basket,
            price_basket_item,
        )

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()

        priced_item = price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        assert priced_item is not None
        assert priced_item.unit_price_amount == Decimal("100.00")
        assert priced_item.price_rule == global_trip_price

    def test_price_basket_item_stores_price_at_resolution_time(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """Priced item captures the price at resolution time (immutable snapshot)."""
        from primitives_testbed.diveops.integrations import (
            create_trip_basket,
            price_basket_item,
        )

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()

        priced_item = price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        # Change the global price
        global_trip_price.amount = Decimal("200.00")
        global_trip_price.save()

        # Priced item should still have original price
        priced_item.refresh_from_db()
        assert priced_item.unit_price_amount == Decimal("100.00")


@pytest.mark.django_db
class TestCreateBookingInvoice:
    """Tests for create_booking_invoice adapter function."""

    def test_create_booking_invoice_from_basket(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """create_booking_invoice creates invoice from priced basket."""
        from primitives_testbed.diveops.integrations import (
            create_booking_invoice,
            create_trip_basket,
            price_basket_item,
        )

        # Create and price basket
        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()
        price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        invoice = create_booking_invoice(
            basket=basket,
            trip=dive_trip,
            diver=diver_profile,
            created_by=user,
        )

        assert invoice is not None
        assert invoice.pk is not None
        assert invoice.total_amount == Decimal("100.00")
        assert invoice.status == "issued"

    def test_create_booking_invoice_commits_basket(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """Creating invoice commits the basket."""
        from primitives_testbed.diveops.integrations import (
            create_booking_invoice,
            create_trip_basket,
            price_basket_item,
        )

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()
        price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        create_booking_invoice(
            basket=basket,
            trip=dive_trip,
            diver=diver_profile,
            created_by=user,
        )

        basket.refresh_from_db()
        assert basket.status == "committed"

    def test_create_booking_invoice_has_line_items(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """Invoice has line items from priced basket items."""
        from primitives_testbed.diveops.integrations import (
            create_booking_invoice,
            create_trip_basket,
            price_basket_item,
        )

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()
        price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        invoice = create_booking_invoice(
            basket=basket,
            trip=dive_trip,
            diver=diver_profile,
            created_by=user,
        )

        assert invoice.line_items.count() == 1
        line = invoice.line_items.first()
        assert line.unit_price_amount == Decimal("100.00")
        assert line.quantity == 1
        assert line.line_total_amount == Decimal("100.00")

    def test_create_booking_invoice_bills_to_diver(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """Invoice is billed to the diver's person."""
        from primitives_testbed.diveops.integrations import (
            create_booking_invoice,
            create_trip_basket,
            price_basket_item,
        )

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()
        price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        invoice = create_booking_invoice(
            basket=basket,
            trip=dive_trip,
            diver=diver_profile,
            created_by=user,
        )

        assert invoice.billed_to == diver_profile.person

    def test_create_booking_invoice_issued_by_dive_shop(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """Invoice is issued by the dive shop."""
        from primitives_testbed.diveops.integrations import (
            create_booking_invoice,
            create_trip_basket,
            price_basket_item,
        )

        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        basket_item = basket.items.first()
        price_basket_item(
            basket_item=basket_item,
            trip=dive_trip,
            diver=diver_profile,
        )

        invoice = create_booking_invoice(
            basket=basket,
            trip=dive_trip,
            diver=diver_profile,
            created_by=user,
        )

        assert invoice.issued_by == dive_trip.dive_shop


@pytest.mark.django_db
class TestFullBillingFlow:
    """Integration tests for the complete billing flow."""

    def test_full_booking_billing_flow(
        self, dive_trip, diver_profile, trip_catalog_item, global_trip_price, user
    ):
        """Complete flow: basket → price → invoice works end-to-end."""
        from primitives_testbed.diveops.integrations import (
            create_booking_invoice,
            create_trip_basket,
            price_basket_item,
        )

        # 1. Create basket
        basket = create_trip_basket(
            trip=dive_trip,
            diver=diver_profile,
            catalog_item=trip_catalog_item,
            created_by=user,
        )
        assert basket.status == "draft"

        # 2. Price all items
        for item in basket.items.all():
            price_basket_item(
                basket_item=item,
                trip=dive_trip,
                diver=diver_profile,
            )

        # 3. Create invoice
        invoice = create_booking_invoice(
            basket=basket,
            trip=dive_trip,
            diver=diver_profile,
            created_by=user,
        )

        # Verify end state
        basket.refresh_from_db()
        assert basket.status == "committed"
        assert invoice.total_amount == Decimal("100.00")
        assert invoice.line_items.count() == 1
        assert invoice.billed_to == diver_profile.person
        assert invoice.issued_by == dive_trip.dive_shop
