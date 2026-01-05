"""Tests for DiveOps Business Hardening - T-001 Price Immutability.

This module tests INV-3: Price Immutability.

INV-3: Price Immutability
    - Price is snapshotted at booking creation
    - price_snapshot (JSONField) stores full pricing context
    - price_amount/price_currency are denormalized for queries
    - Price is NOT recomputed when pricing rules change
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


# =============================================================================
# T-001: Price Immutability Tests
# =============================================================================


@pytest.mark.django_db
class TestBookingPriceSnapshotOnCreate:
    """Test: booking captures price snapshot on create.

    Given excursion with excursion_type + site adjustment,
    book_excursion() stores:
    - price_snapshot breakdown
    - price_amount equals computed total
    - price_currency matches computed currency
    """

    def test_booking_captures_price_snapshot_on_create(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """book_excursion() stores price_snapshot with breakdown."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SitePriceAdjustment,
        )
        from primitives_testbed.diveops.services import book_excursion

        # Create excursion type with base price
        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Morning 2-Tank",
            slug="morning-2-tank-test",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
            min_certification_level=cert_level,
        )

        # Add site adjustment
        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="distance",
            amount=Decimal("25.00"),
            currency="USD",
            is_per_diver=True,
            is_active=True,
        )

        # Create excursion with type
        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("125.00"),  # Base + adjustment
            currency="USD",
            created_by=user,
        )

        # Book the excursion
        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # Verify price snapshot captured
        assert booking.price_snapshot is not None
        assert booking.price_amount == Decimal("125.00")
        assert booking.price_currency == "USD"

        # Verify snapshot contains breakdown
        assert "total" in booking.price_snapshot
        assert "base_price" in booking.price_snapshot
        assert "adjustments" in booking.price_snapshot

    def test_price_amount_equals_computed_total(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """price_amount matches the computed total from snapshot."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_ow2", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Shore Dive",
            slug="shore-dive-test",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=15,
            base_price=Decimal("75.00"),
            currency="EUR",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=3),
            max_divers=6,
            price_per_diver=Decimal("75.00"),
            currency="EUR",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # price_amount should equal the total from snapshot
        assert booking.price_amount == Decimal(booking.price_snapshot["total"])
        assert booking.price_currency == booking.price_snapshot["currency"]


@pytest.mark.django_db
class TestPriceSnapshotImmutability:
    """Test: price_snapshot is not changed if pricing rules change.

    Create booking and snapshot.
    Modify ExcursionType.base_price or SitePriceAdjustment.
    Reload booking; snapshot + amount unchanged.
    """

    def test_price_snapshot_not_changed_if_pricing_rules_change(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Booking price remains unchanged when excursion_type price changes."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_immut", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Night Dive",
            slug="night-dive-immut-test",
            dive_mode="boat",
            time_of_day="night",
            max_depth_meters=18,
            base_price=Decimal("150.00"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("150.00"),
            currency="USD",
            created_by=user,
        )

        # Book at original price
        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        original_amount = booking.price_amount
        original_snapshot = booking.price_snapshot.copy()

        # Change excursion type base price
        excursion_type.base_price = Decimal("999.99")
        excursion_type.save()

        # Change excursion price too
        excursion.price_per_diver = Decimal("999.99")
        excursion.save()

        # Reload booking - price should be unchanged
        booking.refresh_from_db()
        assert booking.price_amount == original_amount
        assert booking.price_snapshot == original_snapshot

    def test_price_snapshot_not_changed_if_site_adjustment_changes(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Booking price remains unchanged when site adjustment changes."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SitePriceAdjustment,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_adj", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Test Dive",
            slug="test-dive-adj",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        # Create site adjustment
        adjustment = SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="park_fee",
            amount=Decimal("20.00"),
            currency="USD",
            is_per_diver=True,
            is_active=True,
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("120.00"),  # Base + adjustment
            currency="USD",
            created_by=user,
        )

        # Book at original price
        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        original_amount = booking.price_amount
        original_total = booking.price_snapshot["total"]

        # Change site adjustment
        adjustment.amount = Decimal("500.00")
        adjustment.save()

        # Reload booking - price should be unchanged
        booking.refresh_from_db()
        assert booking.price_amount == original_amount
        assert booking.price_snapshot["total"] == original_total


@pytest.mark.django_db
class TestBookingWithoutTypeOrSite:
    """Test: booking without type or site has null snapshot.

    If excursion_type missing OR dive_site missing,
    booking.price_snapshot is NULL and price_amount is NULL.
    """

    def test_booking_without_excursion_type_has_null_snapshot(
        self, dive_site, dive_shop, diver_profile, user
    ):
        """Booking without excursion_type has null price_snapshot and price_amount."""
        from primitives_testbed.diveops.models import Excursion
        from primitives_testbed.diveops.services import book_excursion

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=None,  # No type
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("100.00"),  # This exists but won't be snapshotted
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        # Per INV-3: Without excursion_type, no structured price can be computed
        # Price snapshot and denormalized fields should be null
        assert booking.price_snapshot is None
        assert booking.price_amount is None
        assert booking.price_currency == ""


@pytest.mark.django_db
class TestSnapshotSchema:
    """Test: snapshot schema contains required keys.

    Ensure snapshot includes at minimum:
    - total, currency, computed_at
    - excursion_type_id, dive_site_id
    - breakdown of base + adjustments (can be list of dicts)
    """

    def test_snapshot_contains_required_keys(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """price_snapshot contains all required keys."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
            SitePriceAdjustment,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_schema", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Schema Test Dive",
            slug="schema-test-dive",
            dive_mode="boat",
            time_of_day="day",
            max_depth_meters=18,
            base_price=Decimal("100.00"),
            currency="USD",
        )

        SitePriceAdjustment.objects.create(
            dive_site=dive_site,
            kind="night",
            amount=Decimal("30.00"),
            currency="USD",
            is_per_diver=True,
            is_active=True,
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=4),
            max_divers=8,
            price_per_diver=Decimal("130.00"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        snapshot = booking.price_snapshot
        assert snapshot is not None

        # Required keys
        assert "total" in snapshot
        assert "currency" in snapshot
        assert "computed_at" in snapshot
        assert "excursion_type_id" in snapshot
        assert "dive_site_id" in snapshot
        assert "base_price" in snapshot
        assert "adjustments" in snapshot

        # Validate types
        assert isinstance(snapshot["total"], str)  # Decimal as string
        assert snapshot["currency"] == "USD"
        assert snapshot["excursion_type_id"] == str(excursion_type.pk)
        assert snapshot["dive_site_id"] == str(dive_site.pk)

    def test_snapshot_stores_decimals_as_strings(
        self, dive_site, dive_shop, diver_profile, user, padi_agency
    ):
        """Decimal values in snapshot are stored as strings to avoid float drift."""
        from primitives_testbed.diveops.models import (
            CertificationLevel,
            Excursion,
            ExcursionType,
        )
        from primitives_testbed.diveops.services import book_excursion

        cert_level = CertificationLevel.objects.create(
            agency=padi_agency, code="test_decimal", name="Open Water", rank=1
        )
        excursion_type = ExcursionType.objects.create(
            name="Decimal Test",
            slug="decimal-test",
            dive_mode="shore",
            time_of_day="day",
            max_depth_meters=12,
            base_price=Decimal("99.99"),
            currency="USD",
        )

        tomorrow = timezone.now() + timedelta(days=1)
        excursion = Excursion.objects.create(
            dive_shop=dive_shop,
            dive_site=dive_site,
            excursion_type=excursion_type,
            departure_time=tomorrow,
            return_time=tomorrow + timedelta(hours=3),
            max_divers=6,
            price_per_diver=Decimal("99.99"),
            currency="USD",
            created_by=user,
        )

        booking = book_excursion(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            skip_eligibility_check=True,
        )

        snapshot = booking.price_snapshot

        # All decimal values should be strings
        assert isinstance(snapshot["total"], str)
        assert isinstance(snapshot["base_price"], str)

        # Converting back should give exact decimal
        assert Decimal(snapshot["total"]) == Decimal("99.99")


# =============================================================================
# Model Field Tests
# =============================================================================


@pytest.mark.django_db
class TestBookingModelFields:
    """Tests for Booking model price snapshot fields."""

    def test_booking_has_price_snapshot_field(self, db):
        """Booking model has price_snapshot JSONField."""
        from primitives_testbed.diveops.models import Booking

        field = Booking._meta.get_field("price_snapshot")
        assert field is not None
        assert field.get_internal_type() == "JSONField"

    def test_booking_has_price_amount_field(self, db):
        """Booking model has price_amount DecimalField."""
        from primitives_testbed.diveops.models import Booking

        field = Booking._meta.get_field("price_amount")
        assert field is not None
        assert field.get_internal_type() == "DecimalField"

    def test_booking_has_price_currency_field(self, db):
        """Booking model has price_currency CharField."""
        from primitives_testbed.diveops.models import Booking

        field = Booking._meta.get_field("price_currency")
        assert field is not None
        assert field.get_internal_type() == "CharField"
