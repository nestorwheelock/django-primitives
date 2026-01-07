"""Pricing service functions for diveops.

All pricing operations go through these service functions.
They compose primitives (catalog, agreements, ledger, money) with diveops domain.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_catalog.models import CatalogItem
from django_ledger.models import Account, Transaction, Entry
from django_money import Money

from ..models import Excursion, Booking, DiverProfile
from ..audit import (
    log_booking_event,
    log_diver_event,
    Actions,
)

from .calculators import (
    calculate_boat_cost,
    calculate_gas_fills,
    resolve_component_pricing,
    allocate_shared_costs,
    round_money,
)
from .exceptions import (
    PricingError,
    ConfigurationError,
    MissingVendorAgreementError,
    MissingPriceError,
    MissingCatalogItemError,
    SnapshotImmutableError,
    DuplicateRentalError,
)
from .models import DiverEquipmentRental
from .snapshots import (
    build_pricing_snapshot,
    PricingLineSnapshot,
    EquipmentRentalSnapshot,
    PricingTotalsSnapshot,
    MoneySnapshot,
    compute_hash,
)


User = get_user_model()

# Catalog item display names for standard pricing components
# Using exact display_name match (not substring) for deterministic lookup
CATALOG_DISPLAY_NAME_GUIDE_FEE = "Guide Fee"
CATALOG_DISPLAY_NAME_PARK_FEE = "Park Entry Fee"

# Gas type to O2/He fraction mapping
GAS_FRACTIONS = {
    "air": {"o2": 0.21, "he": 0.0},
    "ean32": {"o2": 0.32, "he": 0.0},
    "ean36": {"o2": 0.36, "he": 0.0},
}


def _get_catalog_item(display_name: str) -> CatalogItem:
    """Look up catalog item by exact display_name.

    Uses exact match instead of substring matching for deterministic lookup.

    Args:
        display_name: Catalog item display name (e.g., "Guide Fee", "Park Entry Fee")

    Returns:
        CatalogItem instance

    Raises:
        MissingCatalogItemError: If item not found or inactive
    """
    item = CatalogItem.objects.filter(display_name=display_name, active=True).first()
    if not item:
        raise MissingCatalogItemError(display_name)
    return item


def quote_excursion(
    *,
    excursion_id: UUID,
    actor_id: UUID,
    options: dict | None = None,
) -> dict:
    """Generate a pricing quote for an excursion.

    This is a non-binding preview of pricing. Use snapshot_booking_pricing()
    to create the immutable snapshot for a booking.

    Args:
        excursion_id: Excursion to quote
        actor_id: User requesting quote
        options: Override options:
            - gas_type: "air" | "ean32" | "ean36" (default: "air")
            - diver_count: Override diver count (default: from excursion roster)
            - include_equipment: List of equipment catalog_item_ids to include

    Returns:
        dict: Quote breakdown with lines, totals, metadata

    Emits:
        audit: excursion.quote.generated
    """
    options = options or {}
    actor = User.objects.get(pk=actor_id)
    excursion = Excursion.objects.select_related(
        "dive_site",
        "dive_shop",
        "excursion_type",
    ).get(pk=excursion_id)

    # Determine diver count
    diver_count = options.get("diver_count")
    if diver_count is None:
        # Count confirmed bookings
        diver_count = excursion.bookings.filter(
            status__in=["confirmed", "checked_in"],
            deleted_at__isnull=True,
        ).count()

    if diver_count <= 0:
        raise ConfigurationError("Diver count must be positive for quote")

    gas_type = options.get("gas_type", "air")
    dives_count = excursion.excursion_type.dives_per_excursion if excursion.excursion_type else 2

    # Calculate pricing
    lines = []
    warnings = []

    currency = "MXN"  # Default currency

    # 1. Boat cost (shared)
    try:
        boat_result = calculate_boat_cost(
            dive_site=excursion.dive_site,
            diver_count=diver_count,
        )
        currency = boat_result.total.currency
        lines.append(PricingLineSnapshot(
            key="boat_share",
            label=f"Boat Charter - {excursion.dive_site.name if excursion.dive_site else 'Unknown'}",
            allocation="shared",
            shop_cost=MoneySnapshot.from_money(boat_result.total),
            customer_charge=MoneySnapshot.from_money(boat_result.total),  # Boat cost passed through
            refs={
                "vendor_agreement_id": boat_result.agreement_id,
                "dive_site_id": str(excursion.dive_site.pk) if excursion.dive_site else None,
            },
        ))
    except MissingVendorAgreementError as e:
        warnings.append(f"Boat pricing not configured: {e}")

    # 2. Gas fills (per diver)
    try:
        fills_per_diver = dives_count
        gas_result = calculate_gas_fills(
            dive_shop=excursion.dive_shop,
            gas_type=gas_type,
            fills_count=fills_per_diver,
            customer_charge_amount=Decimal("0"),  # Gas typically included
        )
        lines.append(PricingLineSnapshot(
            key="gas_fill",
            label=f"{gas_type.upper()} Fill x{fills_per_diver}",
            allocation="per_diver",
            shop_cost=MoneySnapshot.from_money(gas_result.total_cost),
            customer_charge=MoneySnapshot.from_money(gas_result.total_charge),
            refs={
                "vendor_agreement_id": gas_result.agreement_id,
            },
        ))
    except MissingVendorAgreementError as e:
        warnings.append(f"Gas pricing not configured: {e}")

    # 3. Guide fee (shared) - look up from catalog by exact display name
    try:
        guide_item = _get_catalog_item(CATALOG_DISPLAY_NAME_GUIDE_FEE)
        pricing = resolve_component_pricing(
            catalog_item=guide_item,
            dive_shop=excursion.dive_shop,
        )
        lines.append(PricingLineSnapshot(
            key="guide_fee",
            label="Guide Fee",
            allocation="shared",
            shop_cost=MoneySnapshot.from_decimal(
                pricing["cost_amount"] or pricing["charge_amount"],
                pricing["cost_currency"],
            ),
            customer_charge=MoneySnapshot.from_decimal(
                pricing["charge_amount"],
                pricing["charge_currency"],
            ),
            refs={
                "price_rule_id": pricing["price_rule_id"],
                "catalog_item_id": str(guide_item.pk),
            },
        ))
    except (MissingPriceError, MissingCatalogItemError) as e:
        warnings.append(f"Guide fee not configured: {e}")

    # 4. Park bracelet (per diver) - look up from catalog by exact display name
    try:
        park_item = _get_catalog_item(CATALOG_DISPLAY_NAME_PARK_FEE)
        pricing = resolve_component_pricing(
            catalog_item=park_item,
            dive_shop=excursion.dive_shop,
        )
        lines.append(PricingLineSnapshot(
            key="park_bracelet",
            label="Park Entry Fee",
            allocation="per_diver",
            shop_cost=MoneySnapshot.from_decimal(
                pricing["cost_amount"] or pricing["charge_amount"],
                pricing["cost_currency"],
            ),
            customer_charge=MoneySnapshot.from_decimal(
                pricing["charge_amount"],
                pricing["charge_currency"],
            ),
            refs={
                "price_rule_id": pricing["price_rule_id"],
                "catalog_item_id": str(park_item.pk),
            },
        ))
    except (MissingPriceError, MissingCatalogItemError) as e:
        warnings.append(f"Park fee not configured: {e}")

    # Calculate totals
    totals = _calculate_totals(lines, diver_count, currency)

    # Build snapshot
    snapshot = build_pricing_snapshot(
        excursion=excursion,
        lines=lines,
        equipment_rentals=[],  # Quotes don't include equipment
        totals=totals,
        gas_type=gas_type,
    )

    result = snapshot.to_dict()
    result["warnings"] = warnings
    result["is_quote"] = True

    # Emit audit event
    from ..audit import log_excursion_event

    log_excursion_event(
        action=Actions.EXCURSION_QUOTE_GENERATED,
        excursion=excursion,
        actor=actor,
        data={
            "diver_count": diver_count,
            "gas_type": gas_type,
            "output_hash": snapshot.metadata.output_hash,
            "warnings": warnings,
        },
    )

    return result


@transaction.atomic
def snapshot_booking_pricing(
    *,
    booking_id: UUID,
    actor_id: UUID,
    gas_type: str | None = None,
    force: bool = False,
    allow_incomplete: bool = False,
) -> "Booking":
    """Create immutable pricing snapshot and ledger entries for a booking.

    This freezes the pricing for the booking. Subsequent price changes will
    not affect this booking.

    Args:
        booking_id: Booking to snapshot
        actor_id: User creating snapshot
        gas_type: Gas type for fills ("air", "ean32", "ean36"). Default: from booking or "air"
        force: If True, overwrite existing snapshot (use with caution)
        allow_incomplete: If True, allow missing pricing config (store warnings).
                         If False (default), raise ConfigurationError on missing config.

    Returns:
        Booking: Updated with price_snapshot

    Raises:
        SnapshotImmutableError: If snapshot exists and force=False
        MissingVendorAgreementError: If vendor agreement missing and allow_incomplete=False
        MissingCatalogItemError: If catalog item missing and allow_incomplete=False
        ConfigurationError: If pricing configuration incomplete and allow_incomplete=False

    Emits:
        audit: excursion.pricing.snapshotted
        audit: pricing.validation.failed (if allow_incomplete=True and warnings exist)

    Creates ledger entries:
        - Revenue entries (customer charges)
        - Expense entries (shop costs)
    """
    actor = User.objects.get(pk=actor_id)
    booking = Booking.objects.select_related(
        "excursion__dive_site",
        "excursion__dive_shop",
        "excursion__excursion_type",
        "diver__person",
    ).select_for_update().get(pk=booking_id)

    # Check for existing snapshot
    if booking.price_snapshot and not force:
        raise SnapshotImmutableError(str(booking_id))

    excursion = booking.excursion

    # Count divers for this excursion
    diver_count = excursion.bookings.filter(
        status__in=["confirmed", "checked_in"],
        deleted_at__isnull=True,
    ).count()

    if diver_count <= 0:
        diver_count = 1  # At minimum, this booking

    # Determine gas type from parameter, booking, or default
    if gas_type is None:
        gas_type = getattr(booking, "gas_type", None) or "air"
    gas_type = gas_type.lower()

    # Validate gas type
    if gas_type not in GAS_FRACTIONS:
        raise ConfigurationError(f"Unknown gas type: {gas_type}")

    gas_fractions = GAS_FRACTIONS[gas_type]
    dives_count = excursion.excursion_type.dives_per_excursion if excursion.excursion_type else 2
    currency = "MXN"

    lines = []
    warnings = []

    # 1. Boat cost (shared) - REQUIRED
    try:
        boat_result = calculate_boat_cost(
            dive_site=excursion.dive_site,
            diver_count=diver_count,
        )
        currency = boat_result.total.currency
        lines.append(PricingLineSnapshot(
            key="boat_share",
            label=f"Boat Charter - {excursion.dive_site.name if excursion.dive_site else 'Unknown'}",
            allocation="shared",
            shop_cost=MoneySnapshot.from_money(boat_result.total),
            customer_charge=MoneySnapshot.from_money(boat_result.total),
            refs={
                "vendor_agreement_id": boat_result.agreement_id,
                "dive_site_id": str(excursion.dive_site.pk) if excursion.dive_site else None,
            },
        ))
    except MissingVendorAgreementError as e:
        if not allow_incomplete:
            raise
        warnings.append(f"Boat pricing not configured: {e}")

    # 2. Gas fills (per diver) - REQUIRED
    try:
        fills_per_diver = dives_count
        gas_result = calculate_gas_fills(
            dive_shop=excursion.dive_shop,
            gas_type=gas_type,
            fills_count=fills_per_diver,
            customer_charge_amount=Decimal("0"),
        )
        lines.append(PricingLineSnapshot(
            key="gas_fill",
            label=f"{gas_type.upper()} Fill x{fills_per_diver}",
            allocation="per_diver",
            shop_cost=MoneySnapshot.from_money(gas_result.total_cost),
            customer_charge=MoneySnapshot.from_money(gas_result.total_charge),
            refs={
                "vendor_agreement_id": gas_result.agreement_id,
                "gas_type": gas_type,
                "gas_o2": gas_fractions["o2"],
                "gas_he": gas_fractions["he"],
            },
        ))
    except MissingVendorAgreementError as e:
        if not allow_incomplete:
            raise
        warnings.append(f"Gas pricing not configured: {e}")

    # 3. Guide fee (shared) - look up from catalog by exact display name
    try:
        guide_item = _get_catalog_item(CATALOG_DISPLAY_NAME_GUIDE_FEE)
        pricing = resolve_component_pricing(
            catalog_item=guide_item,
            dive_shop=excursion.dive_shop,
        )
        lines.append(PricingLineSnapshot(
            key="guide_fee",
            label="Guide Fee",
            allocation="shared",
            shop_cost=MoneySnapshot.from_decimal(
                pricing["cost_amount"] or pricing["charge_amount"],
                pricing["cost_currency"],
            ),
            customer_charge=MoneySnapshot.from_decimal(
                pricing["charge_amount"],
                pricing["charge_currency"],
            ),
            refs={
                "price_rule_id": pricing["price_rule_id"],
                "catalog_item_id": str(guide_item.pk),
            },
        ))
    except (MissingPriceError, MissingCatalogItemError) as e:
        if not allow_incomplete:
            raise
        warnings.append(f"Guide fee not configured: {e}")

    # 4. Park bracelet (per diver) - look up from catalog by exact display name
    try:
        park_item = _get_catalog_item(CATALOG_DISPLAY_NAME_PARK_FEE)
        pricing = resolve_component_pricing(
            catalog_item=park_item,
            dive_shop=excursion.dive_shop,
        )
        lines.append(PricingLineSnapshot(
            key="park_bracelet",
            label="Park Entry Fee",
            allocation="per_diver",
            shop_cost=MoneySnapshot.from_decimal(
                pricing["cost_amount"] or pricing["charge_amount"],
                pricing["cost_currency"],
            ),
            customer_charge=MoneySnapshot.from_decimal(
                pricing["charge_amount"],
                pricing["charge_currency"],
            ),
            refs={
                "price_rule_id": pricing["price_rule_id"],
                "catalog_item_id": str(park_item.pk),
            },
        ))
    except (MissingPriceError, MissingCatalogItemError) as e:
        if not allow_incomplete:
            raise
        warnings.append(f"Park fee not configured: {e}")

    # 5. Equipment rentals for this diver
    equipment_rentals = []
    for rental in booking.equipment_rentals.filter(deleted_at__isnull=True):
        equipment_rentals.append(EquipmentRentalSnapshot(
            diver_id=str(booking.diver.pk),
            catalog_item_id=str(rental.catalog_item.pk),
            description=rental.item_name_snapshot,
            quantity=rental.quantity,
            unit_cost=MoneySnapshot.from_money(rental.unit_cost),
            unit_charge=MoneySnapshot.from_money(rental.unit_charge),
            rental_id=str(rental.pk),
        ))

    # Calculate totals
    totals = _calculate_totals(lines, diver_count, currency, equipment_rentals)

    # Build snapshot
    snapshot = build_pricing_snapshot(
        excursion=excursion,
        lines=lines,
        equipment_rentals=equipment_rentals,
        totals=totals,
        gas_type=gas_type,
    )

    # Update booking with snapshot
    snapshot_dict = snapshot.to_dict()
    booking.price_snapshot = snapshot_dict
    booking.price_amount = totals.total_charge_per_diver.amount
    booking.price_currency = currency
    booking.save(update_fields=["price_snapshot", "price_amount", "price_currency", "updated_at"])

    # Create ledger entries with per-vendor payable accounts
    ledger_tx = _create_ledger_entries(
        booking=booking,
        totals=totals,
        lines=lines,
        actor=actor,
    )

    # Emit audit event
    log_booking_event(
        action=Actions.BOOKING_PRICING_SNAPSHOTTED,
        booking=booking,
        actor=actor,
        data={
            "output_hash": snapshot.metadata.output_hash,
            "total_charge_per_diver": str(totals.total_charge_per_diver.amount),
            "total_cost_per_diver": str(totals.total_cost_per_diver.amount),
            "ledger_transaction_id": str(ledger_tx.pk) if ledger_tx else None,
        },
    )

    return booking


@transaction.atomic
def add_equipment_rental(
    *,
    booking_id: UUID,
    diver_id: UUID,
    catalog_item_id: UUID,
    quantity: int,
    actor_id: UUID,
) -> DiverEquipmentRental:
    """Add equipment rental to a booking.

    Snapshots the current cost/charge at rental time.

    Args:
        booking_id: Booking to add rental to
        diver_id: Diver renting equipment (must match booking diver)
        catalog_item_id: Equipment catalog item
        quantity: Number of items
        actor_id: User adding rental

    Returns:
        DiverEquipmentRental: Created rental record

    Raises:
        ValueError: If diver doesn't match booking or quantity invalid
        MissingPriceError: If no price configured for equipment
        DuplicateRentalError: If rental already exists for this item on this booking

    Emits:
        audit: diver.equipment.rented
    """
    actor = User.objects.get(pk=actor_id)
    booking = Booking.objects.select_related("diver", "excursion__dive_shop").get(pk=booking_id)
    diver = DiverProfile.objects.get(pk=diver_id)
    catalog_item = CatalogItem.objects.get(pk=catalog_item_id)

    # Validate diver matches booking
    if booking.diver.pk != diver.pk:
        raise ValueError("Diver does not match booking diver")

    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    # Resolve pricing - raise on missing price (no silent zero defaults)
    pricing = resolve_component_pricing(
        catalog_item=catalog_item,
        dive_shop=booking.excursion.dive_shop,
    )
    cost_amount = pricing["cost_amount"] or Decimal("0")
    cost_currency = pricing["cost_currency"]
    charge_amount = pricing["charge_amount"]
    charge_currency = pricing["charge_currency"]
    price_rule_id = pricing["price_rule_id"]

    try:
        rental = DiverEquipmentRental.objects.create(
            booking=booking,
            diver=diver,
            catalog_item=catalog_item,
            quantity=quantity,
            unit_cost_amount=cost_amount,
            unit_cost_currency=cost_currency,
            unit_charge_amount=charge_amount,
            unit_charge_currency=charge_currency,
            price_rule_id=price_rule_id,
            rented_by=actor,
        )
    except IntegrityError as e:
        # Translate DB constraint violation to domain exception
        if "diveops_rental_unique_per_booking" in str(e):
            raise DuplicateRentalError(
                booking_id=str(booking_id),
                catalog_item_id=str(catalog_item_id),
            ) from e
        raise

    # Emit audit event
    log_diver_event(
        action=Actions.DIVER_EQUIPMENT_RENTED,
        diver=diver,
        actor=actor,
        data={
            "booking_id": str(booking.pk),
            "catalog_item_id": str(catalog_item.pk),
            "item_name": catalog_item.display_name,
            "quantity": quantity,
            "unit_cost": str(cost_amount),
            "unit_charge": str(charge_amount),
            "rental_id": str(rental.pk),
        },
    )

    return rental


def validate_pricing_configuration(
    excursion_id: UUID,
) -> list[str]:
    """Validate that all required pricing is configured.

    Args:
        excursion_id: Excursion to validate

    Returns:
        list: Warning/error messages (empty = valid)
    """
    excursion = Excursion.objects.select_related(
        "dive_site",
        "dive_shop",
        "excursion_type",
    ).get(pk=excursion_id)

    errors = []

    # Check boat pricing
    try:
        calculate_boat_cost(
            dive_site=excursion.dive_site,
            diver_count=4,  # Test with default
        )
    except MissingVendorAgreementError as e:
        errors.append(f"MISSING: Boat vendor agreement for site - {e}")
    except ConfigurationError as e:
        errors.append(f"INVALID: Boat pricing configuration - {e}")

    # Check gas pricing
    for gas_type in ["air", "ean32"]:
        try:
            calculate_gas_fills(
                dive_shop=excursion.dive_shop,
                gas_type=gas_type,
                fills_count=1,
            )
        except MissingVendorAgreementError:
            errors.append(f"MISSING: Gas vendor agreement for {gas_type}")
        except ConfigurationError as e:
            errors.append(f"INVALID: Gas pricing for {gas_type} - {e}")

    # Check guide fee - use deterministic display_name lookup
    try:
        guide_item = _get_catalog_item(CATALOG_DISPLAY_NAME_GUIDE_FEE)
        try:
            resolve_component_pricing(
                catalog_item=guide_item,
                dive_shop=excursion.dive_shop,
            )
        except MissingPriceError:
            errors.append("MISSING: Guide Fee price rule")
    except MissingCatalogItemError:
        errors.append(f"MISSING: Guide Fee catalog item (name: {CATALOG_DISPLAY_NAME_GUIDE_FEE})")

    # Check park fee - use deterministic display_name lookup
    try:
        park_item = _get_catalog_item(CATALOG_DISPLAY_NAME_PARK_FEE)
        try:
            resolve_component_pricing(
                catalog_item=park_item,
                dive_shop=excursion.dive_shop,
            )
        except MissingPriceError:
            errors.append("MISSING: Park Entry Fee price rule")
    except MissingCatalogItemError:
        errors.append(f"MISSING: Park Entry Fee catalog item (name: {CATALOG_DISPLAY_NAME_PARK_FEE})")

    # Emit audit if errors found
    if errors:
        from ..audit import log_excursion_event

        actor = None  # System validation
        log_excursion_event(
            action=Actions.PRICING_VALIDATION_FAILED,
            excursion=excursion,
            actor=actor,
            data={
                "errors": errors,
            },
        )

    return errors


def _calculate_totals(
    lines: list[PricingLineSnapshot],
    diver_count: int,
    currency: str,
    equipment_rentals: list[EquipmentRentalSnapshot] | None = None,
) -> PricingTotalsSnapshot:
    """Calculate pricing totals from lines."""
    shared_cost = Decimal("0")
    shared_charge = Decimal("0")
    per_diver_cost = Decimal("0")
    per_diver_charge = Decimal("0")

    for line in lines:
        cost = Decimal(line.shop_cost.amount)
        charge = Decimal(line.customer_charge.amount)

        if line.allocation == "shared":
            shared_cost += cost
            shared_charge += charge
        elif line.allocation == "per_diver":
            per_diver_cost += cost
            per_diver_charge += charge

    # Add equipment rentals to per-diver totals
    if equipment_rentals:
        for rental in equipment_rentals:
            per_diver_cost += Decimal(rental.unit_cost.amount) * rental.quantity
            per_diver_charge += Decimal(rental.unit_charge.amount) * rental.quantity

    # Calculate per-diver share of shared costs
    shared_cost_per_diver = round_money(shared_cost / diver_count) if diver_count > 0 else Decimal("0")
    shared_charge_per_diver = round_money(shared_charge / diver_count) if diver_count > 0 else Decimal("0")

    # Calculate totals per diver
    total_cost_per_diver = shared_cost_per_diver + per_diver_cost
    total_charge_per_diver = shared_charge_per_diver + per_diver_charge
    margin_per_diver = total_charge_per_diver - total_cost_per_diver

    return PricingTotalsSnapshot(
        shared_cost=MoneySnapshot.from_decimal(shared_cost, currency),
        shared_charge=MoneySnapshot.from_decimal(shared_charge, currency),
        per_diver_cost=MoneySnapshot.from_decimal(per_diver_cost, currency),
        per_diver_charge=MoneySnapshot.from_decimal(per_diver_charge, currency),
        shared_cost_per_diver=MoneySnapshot.from_decimal(shared_cost_per_diver, currency),
        shared_charge_per_diver=MoneySnapshot.from_decimal(shared_charge_per_diver, currency),
        total_cost_per_diver=MoneySnapshot.from_decimal(total_cost_per_diver, currency),
        total_charge_per_diver=MoneySnapshot.from_decimal(total_charge_per_diver, currency),
        margin_per_diver=MoneySnapshot.from_decimal(margin_per_diver, currency),
        diver_count=diver_count,
    )


def _create_ledger_entries(
    booking: "Booking",
    totals: PricingTotalsSnapshot,
    lines: list[PricingLineSnapshot],
    actor,
) -> Transaction | None:
    """Create balanced ledger entries for a booking snapshot.

    Creates double-entry accounting entries:

    Revenue side (customer charge):
    - Debit Receivable (customer owes us)
    - Credit Revenue (we earned it)

    Expense side (shop costs):
    - Debit Expense/COGS (our cost)
    - Credit Per-Vendor Payables (we owe each vendor)

    Uses per-vendor payable accounts for proper reconciliation:
    - Lines with vendor_agreement_id → vendor-specific payable account
    - Lines without vendor info → generic shop payables (fallback)

    Invariant: Total debits = Total credits (balanced transaction)

    Args:
        booking: Booking with pricing
        totals: Calculated totals
        lines: Pricing lines with vendor refs for per-vendor accounting
        actor: User creating entries

    Returns:
        Transaction if created, None if both charge and cost are zero
    """
    from django_agreements.models import Agreement

    charge = Decimal(totals.total_charge_per_diver.amount)
    cost = Decimal(totals.total_cost_per_diver.amount)
    currency = totals.total_charge_per_diver.currency
    diver_count = totals.diver_count

    if charge == 0 and cost == 0:
        return None

    # Get or create shop-level accounts
    dive_shop = booking.excursion.dive_shop
    shop_content_type = ContentType.objects.get_for_model(dive_shop)

    receivable_account, _ = Account.objects.get_or_create(
        owner_content_type=shop_content_type,
        owner_id=str(dive_shop.pk),
        account_type="receivable",
        currency=currency,
        defaults={"name": f"Receivable - {dive_shop.name}"},
    )

    revenue_account, _ = Account.objects.get_or_create(
        owner_content_type=shop_content_type,
        owner_id=str(dive_shop.pk),
        account_type="revenue",
        currency=currency,
        defaults={"name": f"Revenue - {dive_shop.name}"},
    )

    expense_account, _ = Account.objects.get_or_create(
        owner_content_type=shop_content_type,
        owner_id=str(dive_shop.pk),
        account_type="expense",
        currency=currency,
        defaults={"name": f"COGS - {dive_shop.name}"},
    )

    # Fallback payables account for lines without vendor info
    fallback_payables_account, _ = Account.objects.get_or_create(
        owner_content_type=shop_content_type,
        owner_id=str(dive_shop.pk),
        account_type="payable",
        currency=currency,
        defaults={"name": f"Unattributed Payables - {dive_shop.name}"},
    )

    # Create transaction
    tx = Transaction.objects.create(
        description=f"Booking {booking.pk} - {booking.diver.person.get_short_name()}",
        effective_at=timezone.now(),
        metadata={
            "booking_id": str(booking.pk),
            "excursion_id": str(booking.excursion.pk),
            "diver_id": str(booking.diver.pk),
        },
    )

    # Revenue entries (customer charge)
    if charge > 0:
        # Debit receivable (customer owes us)
        Entry.objects.create(
            transaction=tx,
            account=receivable_account,
            entry_type="debit",
            amount=charge,
            description=f"Customer charge for {booking.excursion}",
        )
        # Credit revenue (we earned it)
        Entry.objects.create(
            transaction=tx,
            account=revenue_account,
            entry_type="credit",
            amount=charge,
            description=f"Excursion revenue for {booking.excursion}",
        )

    # Expense entries - per-vendor payable accounts
    # Group costs by vendor for proper reconciliation
    vendor_costs: dict[str, Decimal] = {}  # vendor_id -> cost amount
    unattributed_cost = Decimal("0")

    for line in lines:
        line_cost = Decimal(line.shop_cost.amount)
        if line_cost == 0:
            continue

        # Calculate this diver's share of the line cost
        if line.allocation == "shared":
            diver_share = round_money(line_cost / diver_count) if diver_count > 0 else Decimal("0")
        else:  # per_diver
            diver_share = line_cost

        # Check for vendor agreement
        vendor_agreement_id = line.refs.get("vendor_agreement_id")
        if vendor_agreement_id:
            try:
                agreement = Agreement.objects.select_related("party_b").get(pk=vendor_agreement_id)
                vendor = agreement.party_b
                if vendor:
                    vendor_id = str(vendor.pk)
                    vendor_costs[vendor_id] = vendor_costs.get(vendor_id, Decimal("0")) + diver_share
                    continue
            except Agreement.DoesNotExist:
                pass  # Fall through to unattributed

        # No vendor info - add to unattributed
        unattributed_cost += diver_share

    # Create expense debit entries (total shop cost)
    if cost > 0:
        Entry.objects.create(
            transaction=tx,
            account=expense_account,
            entry_type="debit",
            amount=cost,
            description=f"Excursion costs for {booking.excursion}",
        )

    # Create per-vendor payable credit entries
    from django_parties.models import Organization

    for vendor_id, vendor_cost in vendor_costs.items():
        if vendor_cost == 0:
            continue

        try:
            vendor = Organization.objects.get(pk=vendor_id)
            vendor_content_type = ContentType.objects.get_for_model(vendor)

            # Get or create vendor-specific payable account
            vendor_payables_account, _ = Account.objects.get_or_create(
                owner_content_type=vendor_content_type,
                owner_id=str(vendor.pk),
                account_type="payable",
                currency=currency,
                defaults={"name": f"Payables - {vendor.name}"},
            )

            Entry.objects.create(
                transaction=tx,
                account=vendor_payables_account,
                entry_type="credit",
                amount=vendor_cost,
                description=f"Owed to {vendor.name} for {booking.excursion}",
            )
        except Organization.DoesNotExist:
            # If vendor not found, add to unattributed
            unattributed_cost += vendor_cost

    # Credit unattributed payables (fallback)
    if unattributed_cost > 0:
        Entry.objects.create(
            transaction=tx,
            account=fallback_payables_account,
            entry_type="credit",
            amount=unattributed_cost,
            description=f"Unattributed vendor costs for {booking.excursion}",
        )

    # Post the transaction
    tx.posted_at = timezone.now()
    tx.save(update_fields=["posted_at"])

    return tx
