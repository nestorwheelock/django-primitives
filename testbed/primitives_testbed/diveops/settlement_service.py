"""Settlement batch processing service for dive operations.

Provides functions for batch settlement processing:
- get_unsettled_bookings: Find confirmed bookings without settlements
- run_settlement_batch: Process multiple bookings in a single run

T-010: Settlement Run (Batch Posting)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django_parties.models import Organization

    from .models import Booking, SettlementRun


def get_unsettled_bookings(
    dive_shop: "Organization",
    period_start: datetime,
    period_end: datetime,
) -> list["Booking"]:
    """Find confirmed bookings that haven't been settled yet.

    Returns bookings where:
    - excursion.dive_shop matches dive_shop
    - excursion.departure_time is within period
    - status is "confirmed"
    - no revenue SettlementRecord exists

    Args:
        dive_shop: Organization to filter by
        period_start: Start of period (inclusive)
        period_end: End of period (inclusive)

    Returns:
        List of Booking objects eligible for settlement
    """
    from .models import Booking, SettlementRecord

    # Subquery to check if booking has a revenue settlement
    has_settlement = SettlementRecord.objects.filter(
        booking=OuterRef("pk"),
        settlement_type="revenue",
    )

    return list(
        Booking.objects.filter(
            excursion__dive_shop=dive_shop,
            excursion__departure_time__gte=period_start,
            excursion__departure_time__lte=period_end,
            status="confirmed",
        )
        .exclude(Exists(has_settlement))
        .select_related("excursion", "diver")
        .order_by("excursion__departure_time")
    )


@transaction.atomic
def run_settlement_batch(
    dive_shop: "Organization",
    period_start: datetime,
    period_end: datetime,
    processed_by: "User",
    notes: str = "",
) -> "SettlementRun":
    """Run batch settlement for all eligible bookings in period.

    Creates a SettlementRun record and processes all confirmed, unsettled
    bookings in the specified period:
    1. Creates SettlementRun with PROCESSING status
    2. Finds all eligible bookings
    3. For each booking, calls create_revenue_settlement
    4. Links each SettlementRecord to the SettlementRun
    5. Updates run stats and marks COMPLETED

    Args:
        dive_shop: Organization to settle for
        period_start: Start of period
        period_end: End of period
        processed_by: User initiating the run
        notes: Optional notes for the run

    Returns:
        SettlementRun with results
    """
    from .audit import Actions, log_event
    from .models import SettlementRun
    from .services import create_revenue_settlement

    # Create the run record
    run = SettlementRun.objects.create(
        dive_shop=dive_shop,
        period_start=period_start,
        period_end=period_end,
        status=SettlementRun.Status.PROCESSING,
        processed_by=processed_by,
        notes=notes,
    )

    # Find eligible bookings
    eligible_bookings = get_unsettled_bookings(
        dive_shop=dive_shop,
        period_start=period_start,
        period_end=period_end,
    )

    run.total_bookings = len(eligible_bookings)
    total_amount = Decimal("0.00")
    settled_count = 0
    failed_count = 0
    error_details = {}

    # Process each booking with per-booking savepoints
    # This ensures one failed booking doesn't poison the entire batch
    for booking in eligible_bookings:
        sid = transaction.savepoint()
        try:
            settlement = create_revenue_settlement(
                booking=booking,
                processed_by=processed_by,
            )
            # Link settlement to run
            settlement.settlement_run = run
            settlement.save(update_fields=["settlement_run"])

            total_amount += settlement.amount
            settled_count += 1
            transaction.savepoint_commit(sid)
        except Exception as e:
            transaction.savepoint_rollback(sid)
            failed_count += 1
            error_details[str(booking.pk)] = str(e)

    # Update run with results
    run.settled_count = settled_count
    run.failed_count = failed_count
    run.total_amount = total_amount
    run.error_details = error_details
    run.completed_at = timezone.now()
    run.status = (
        SettlementRun.Status.COMPLETED
        if failed_count == 0
        else SettlementRun.Status.FAILED
        if settled_count == 0
        else SettlementRun.Status.COMPLETED  # Partial success still completes
    )
    run.save()

    # Emit audit event
    log_event(
        action=Actions.SETTLEMENT_RUN_COMPLETED,
        target=run,
        actor=processed_by,
        data={
            "run_id": str(run.pk),
            "dive_shop_id": str(dive_shop.pk),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_bookings": run.total_bookings,
            "settled_count": run.settled_count,
            "failed_count": run.failed_count,
            "total_amount": str(run.total_amount),
            "currency": run.currency,
        },
    )

    return run
