"""T-010: Settlement Run (Batch Posting)

Tests for batch settlement processing:
- SettlementRun model tracks batch of settlements
- run_settlement_batch() processes multiple bookings
- Individual SettlementRecords link to their SettlementRun
- Success/failure counts tracked
- Idempotent per booking (skips already-settled)
- Audit events emitted

INV-4: Settlement is idempotent per booking.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


def create_test_excursion_type(padi_agency, slug_suffix=""):
    """Helper to create a valid ExcursionType for tests."""
    from primitives_testbed.diveops.models import CertificationLevel, ExcursionType
    import uuid

    cert_level, _ = CertificationLevel.objects.get_or_create(
        agency=padi_agency,
        code=f"ow-{uuid.uuid4().hex[:6]}",
        defaults={"name": "Open Water", "rank": 1},
    )

    return ExcursionType.objects.create(
        name=f"Settlement Test Type {slug_suffix}",
        slug=f"settlement-test-{uuid.uuid4().hex[:8]}",
        dive_mode="boat",
        time_of_day="day",
        max_depth_meters=18,
        base_price=Decimal("100.00"),
        currency="USD",
    )


def create_test_excursion(dive_shop, dive_site, user, excursion_type, days_offset=1):
    """Helper to create a valid Excursion for tests."""
    from primitives_testbed.diveops.models import Excursion

    departure = timezone.now() + timedelta(days=days_offset)
    return_time = departure + timedelta(hours=4)

    return Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        excursion_type=excursion_type,
        departure_time=departure,
        return_time=return_time,
        max_divers=10,
        price_per_diver=Decimal("100.00"),
        currency="USD",
        status="scheduled",
        created_by=user,
    )


def create_confirmed_booking(excursion, diver_profile, user):
    """Helper to create a confirmed booking with price snapshot."""
    from primitives_testbed.diveops.services import book_excursion

    booking = book_excursion(
        excursion=excursion,
        diver=diver_profile,
        booked_by=user,
        skip_eligibility_check=True,
    )
    booking.status = "confirmed"
    booking.save()
    return booking


# =============================================================================
# T-010: SettlementRun Model Tests
# =============================================================================


@pytest.mark.django_db
class TestSettlementRunModel:
    """Test: SettlementRun model exists with required structure."""

    def test_settlement_run_model_exists(self):
        """SettlementRun model can be imported."""
        from primitives_testbed.diveops.models import SettlementRun

        assert SettlementRun is not None

    def test_settlement_run_has_dive_shop_fk(self):
        """SettlementRun has FK to dive_shop (Organization)."""
        from primitives_testbed.diveops.models import SettlementRun

        field = SettlementRun._meta.get_field("dive_shop")
        assert field.related_model.__name__ == "Organization"
        assert not field.null  # Required

    def test_settlement_run_has_period_fields(self):
        """SettlementRun has period_start and period_end DateTimeFields."""
        from primitives_testbed.diveops.models import SettlementRun

        start_field = SettlementRun._meta.get_field("period_start")
        end_field = SettlementRun._meta.get_field("period_end")

        assert "DateTime" in start_field.get_internal_type()
        assert "DateTime" in end_field.get_internal_type()

    def test_settlement_run_has_status_choices(self):
        """SettlementRun has status with appropriate choices."""
        from primitives_testbed.diveops.models import SettlementRun

        assert hasattr(SettlementRun, "Status")
        assert SettlementRun.Status.PENDING == "pending"
        assert SettlementRun.Status.PROCESSING == "processing"
        assert SettlementRun.Status.COMPLETED == "completed"
        assert SettlementRun.Status.FAILED == "failed"

    def test_settlement_run_has_count_fields(self):
        """SettlementRun has total_bookings, settled_count, failed_count."""
        from primitives_testbed.diveops.models import SettlementRun

        total_field = SettlementRun._meta.get_field("total_bookings")
        settled_field = SettlementRun._meta.get_field("settled_count")
        failed_field = SettlementRun._meta.get_field("failed_count")

        assert total_field.get_internal_type() == "IntegerField"
        assert settled_field.get_internal_type() == "IntegerField"
        assert failed_field.get_internal_type() == "IntegerField"

    def test_settlement_run_has_total_amount(self):
        """SettlementRun has total_amount DecimalField."""
        from primitives_testbed.diveops.models import SettlementRun

        field = SettlementRun._meta.get_field("total_amount")
        assert field.get_internal_type() == "DecimalField"

    def test_settlement_run_has_processed_by(self):
        """SettlementRun has processed_by FK to User."""
        from primitives_testbed.diveops.models import SettlementRun

        field = SettlementRun._meta.get_field("processed_by")
        assert field.related_model.__name__ == "User"


# =============================================================================
# T-010: SettlementRecord Links to Run
# =============================================================================


@pytest.mark.django_db
class TestSettlementRecordRunLink:
    """Test: SettlementRecord has optional FK to SettlementRun."""

    def test_settlement_record_has_run_fk(self):
        """SettlementRecord has optional FK to SettlementRun."""
        from primitives_testbed.diveops.models import SettlementRecord

        field = SettlementRecord._meta.get_field("settlement_run")
        assert field.null  # Optional (for individual settlements)
        assert field.related_model.__name__ == "SettlementRun"


# =============================================================================
# T-010: Settlement Batch Service Tests
# =============================================================================


@pytest.mark.django_db
class TestRunSettlementBatch:
    """Test: run_settlement_batch service function."""

    def test_run_settlement_batch_creates_run_record(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """run_settlement_batch creates a SettlementRun record."""
        from primitives_testbed.diveops.models import SettlementRun
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        now = timezone.now()
        period_start = now - timedelta(days=7)
        period_end = now

        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=period_start,
            period_end=period_end,
            processed_by=user,
        )

        assert run.pk is not None
        assert run.dive_shop == dive_shop
        assert run.period_start == period_start
        assert run.period_end == period_end
        assert run.status == SettlementRun.Status.COMPLETED

    def test_run_settlement_batch_settles_eligible_bookings(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """run_settlement_batch settles all confirmed, unsettled bookings in period."""
        from primitives_testbed.diveops.models import SettlementRecord
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "batch1")

        # Create 3 confirmed bookings
        bookings = []
        for i in range(3):
            excursion = create_test_excursion(
                dive_shop, dive_site, user, excursion_type, days_offset=-i
            )
            booking = create_confirmed_booking(excursion, diver_profile, user)
            bookings.append(booking)

        now = timezone.now()
        period_start = now - timedelta(days=7)
        period_end = now + timedelta(days=1)

        initial_count = SettlementRecord.objects.count()

        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=period_start,
            period_end=period_end,
            processed_by=user,
        )

        # All 3 bookings should be settled
        assert run.total_bookings == 3
        assert run.settled_count == 3
        assert run.failed_count == 0
        assert SettlementRecord.objects.count() == initial_count + 3

    def test_run_settlement_batch_skips_already_settled(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """run_settlement_batch skips bookings already settled."""
        from primitives_testbed.diveops.models import SettlementRecord
        from primitives_testbed.diveops.services import create_revenue_settlement
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "skip1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        booking = create_confirmed_booking(excursion, diver_profile, user)

        # Pre-settle this booking
        create_revenue_settlement(booking=booking, processed_by=user)
        initial_count = SettlementRecord.objects.count()

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        # Should report 0 total (already settled, not eligible)
        assert run.total_bookings == 0
        assert run.settled_count == 0
        assert SettlementRecord.objects.count() == initial_count

    def test_run_settlement_batch_links_records_to_run(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """SettlementRecords created by batch are linked to the SettlementRun."""
        from primitives_testbed.diveops.models import SettlementRecord
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "link1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        booking = create_confirmed_booking(excursion, diver_profile, user)

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        # Settlement should be linked to run
        settlement = SettlementRecord.objects.get(booking=booking)
        assert settlement.settlement_run == run

    def test_run_settlement_batch_calculates_total_amount(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """run_settlement_batch calculates total_amount from all settlements."""
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "total1")

        # Create 2 bookings at $100 each
        for i in range(2):
            excursion = create_test_excursion(
                dive_shop, dive_site, user, excursion_type, days_offset=-i
            )
            create_confirmed_booking(excursion, diver_profile, user)

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        assert run.total_amount == Decimal("200.00")  # 2 × $100


@pytest.mark.django_db
class TestSettlementBatchFiltering:
    """Test: Settlement batch respects date range and shop filters."""

    def test_batch_only_settles_bookings_in_period(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Bookings outside period_start/period_end are not settled."""
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "period1")

        # Booking in period (departure yesterday)
        excursion_in = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        booking_in = create_confirmed_booking(excursion_in, diver_profile, user)

        # Booking outside period (departure 30 days ago)
        excursion_out = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-30
        )
        booking_out = create_confirmed_booking(excursion_out, diver_profile, user)

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),  # Only last 7 days
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        # Only 1 booking should be settled
        assert run.total_bookings == 1
        assert run.settled_count == 1

    def test_batch_only_settles_shop_bookings(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Batch only settles bookings for the specified dive_shop."""
        from django_parties.models import Organization
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "shop1")

        # Create another shop
        other_shop = Organization.objects.create(
            name="Other Dive Shop",
            org_type="dive_shop",
        )

        # Booking for our shop
        excursion1 = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        create_confirmed_booking(excursion1, diver_profile, user)

        # Booking for other shop
        excursion2 = create_test_excursion(
            other_shop, dive_site, user, excursion_type, days_offset=-1
        )
        create_confirmed_booking(excursion2, diver_profile, user)

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,  # Only our shop
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        # Only 1 booking (from dive_shop) should be settled
        assert run.total_bookings == 1


@pytest.mark.django_db
class TestSettlementBatchStatusFiltering:
    """Test: Batch only settles confirmed bookings."""

    def test_batch_skips_cancelled_bookings(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Cancelled bookings are not eligible for revenue settlement."""
        from primitives_testbed.diveops.services import cancel_booking
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "cancel1")

        # Create and cancel a booking
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        booking = create_confirmed_booking(excursion, diver_profile, user)
        cancel_booking(booking, cancelled_by=user)

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        assert run.total_bookings == 0  # Cancelled not eligible

    def test_batch_skips_pending_bookings(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """Pending bookings are not eligible for revenue settlement."""
        from primitives_testbed.diveops.models import Booking
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "pending1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )

        # Create booking but leave as pending (not confirmed)
        booking = Booking.objects.create(
            excursion=excursion,
            diver=diver_profile,
            booked_by=user,
            status="pending",
            price_snapshot={"amount": "100.00", "currency": "USD"},
            price_amount=Decimal("100.00"),
            price_currency="USD",
        )

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        assert run.total_bookings == 0  # Pending not eligible


# =============================================================================
# T-010: Audit Event Tests
# =============================================================================


@pytest.mark.django_db
class TestSettlementBatchAudit:
    """Test: Settlement batch emits audit events."""

    def test_settlement_run_emits_audit_event(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """run_settlement_batch emits SETTLEMENT_RUN_COMPLETED audit event."""
        from django_audit_log.models import AuditLog
        from primitives_testbed.diveops.settlement_service import run_settlement_batch

        excursion_type = create_test_excursion_type(padi_agency, "audit1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        create_confirmed_booking(excursion, diver_profile, user)

        initial_count = AuditLog.objects.count()

        now = timezone.now()
        run = run_settlement_batch(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            processed_by=user,
        )

        # Audit event should be emitted
        assert AuditLog.objects.count() > initial_count

        audit_event = AuditLog.objects.filter(
            action__contains="settlement_run"
        ).first()
        assert audit_event is not None
        assert "run_id" in audit_event.metadata
        assert "total_bookings" in audit_event.metadata
        assert "settled_count" in audit_event.metadata
        assert "total_amount" in audit_event.metadata


# =============================================================================
# T-010: Get Unsettled Bookings Helper
# =============================================================================


@pytest.mark.django_db
class TestGetUnsettledBookings:
    """Test: get_unsettled_bookings helper function."""

    def test_get_unsettled_bookings_returns_confirmed_without_settlement(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """get_unsettled_bookings returns confirmed bookings without settlements."""
        from primitives_testbed.diveops.settlement_service import get_unsettled_bookings

        excursion_type = create_test_excursion_type(padi_agency, "unsettled1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        booking = create_confirmed_booking(excursion, diver_profile, user)

        now = timezone.now()
        unsettled = get_unsettled_bookings(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
        )

        assert booking in unsettled

    def test_get_unsettled_bookings_excludes_settled(
        self, dive_shop, dive_site, diver_profile, user, padi_agency
    ):
        """get_unsettled_bookings excludes already-settled bookings."""
        from primitives_testbed.diveops.services import create_revenue_settlement
        from primitives_testbed.diveops.settlement_service import get_unsettled_bookings

        excursion_type = create_test_excursion_type(padi_agency, "settled1")
        excursion = create_test_excursion(
            dive_shop, dive_site, user, excursion_type, days_offset=-1
        )
        booking = create_confirmed_booking(excursion, diver_profile, user)

        # Settle the booking
        create_revenue_settlement(booking=booking, processed_by=user)

        now = timezone.now()
        unsettled = get_unsettled_bookings(
            dive_shop=dive_shop,
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
        )

        assert booking not in unsettled
