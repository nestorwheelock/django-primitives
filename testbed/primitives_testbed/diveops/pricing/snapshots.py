"""Pricing snapshot builders for diveops.

Creates immutable pricing snapshots that are stored in Booking.price_snapshot.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.utils import timezone


SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "diveops-pricing"


@dataclass
class MoneySnapshot:
    """Snapshot of a Money value."""

    amount: str  # Decimal as string for JSON
    currency: str

    @classmethod
    def from_money(cls, money) -> "MoneySnapshot":
        """Create from django_money.Money object."""
        return cls(amount=str(money.amount), currency=money.currency)

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: str) -> "MoneySnapshot":
        """Create from Decimal and currency."""
        return cls(amount=str(amount), currency=currency)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PricingLineSnapshot:
    """Snapshot of a single pricing line item."""

    key: str  # Unique identifier (boat_share, guide_fee, air_fill, etc.)
    label: str  # Human-readable label
    allocation: str  # shared, per_diver, per_selected
    shop_cost: MoneySnapshot
    customer_charge: MoneySnapshot
    refs: dict[str, str] = field(default_factory=dict)  # References to source records

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "allocation": self.allocation,
            "shop_cost": self.shop_cost.to_dict(),
            "customer_charge": self.customer_charge.to_dict(),
            "refs": self.refs,
        }


@dataclass
class EquipmentRentalSnapshot:
    """Snapshot of equipment rental for a diver."""

    diver_id: str
    catalog_item_id: str
    description: str
    quantity: int
    unit_cost: MoneySnapshot
    unit_charge: MoneySnapshot
    rental_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "diver_id": self.diver_id,
            "catalog_item_id": self.catalog_item_id,
            "description": self.description,
            "quantity": self.quantity,
            "unit_cost": self.unit_cost.to_dict(),
            "unit_charge": self.unit_charge.to_dict(),
            "rental_id": self.rental_id,
        }


@dataclass
class PricingTotalsSnapshot:
    """Snapshot of pricing totals."""

    shared_cost: MoneySnapshot
    shared_charge: MoneySnapshot
    per_diver_cost: MoneySnapshot
    per_diver_charge: MoneySnapshot
    shared_cost_per_diver: MoneySnapshot
    shared_charge_per_diver: MoneySnapshot
    total_cost_per_diver: MoneySnapshot
    total_charge_per_diver: MoneySnapshot
    margin_per_diver: MoneySnapshot
    diver_count: int

    def to_dict(self) -> dict:
        return {
            "shared_cost": self.shared_cost.to_dict(),
            "shared_charge": self.shared_charge.to_dict(),
            "per_diver_cost": self.per_diver_cost.to_dict(),
            "per_diver_charge": self.per_diver_charge.to_dict(),
            "shared_cost_per_diver": self.shared_cost_per_diver.to_dict(),
            "shared_charge_per_diver": self.shared_charge_per_diver.to_dict(),
            "total_cost_per_diver": self.total_cost_per_diver.to_dict(),
            "total_charge_per_diver": self.total_charge_per_diver.to_dict(),
            "margin_per_diver": self.margin_per_diver.to_dict(),
            "diver_count": self.diver_count,
        }


@dataclass
class PricingInputsSnapshot:
    """Snapshot of pricing calculation inputs."""

    excursion_id: str
    site_id: str | None
    site_name: str | None
    diver_count: int
    dives_count: int
    gas_type: str
    dive_shop_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "excursion_id": self.excursion_id,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "diver_count": self.diver_count,
            "dives_count": self.dives_count,
            "gas_type": self.gas_type,
            "dive_shop_id": self.dive_shop_id,
        }


@dataclass
class PricingMetadataSnapshot:
    """Snapshot metadata."""

    schema_version: str
    tool: str
    generated_at: str
    input_hash: str
    output_hash: str

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "tool": self.tool,
            "generated_at": self.generated_at,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
        }


@dataclass
class PricingSnapshot:
    """Complete pricing snapshot."""

    inputs: PricingInputsSnapshot
    lines: list[PricingLineSnapshot]
    equipment_rentals: list[EquipmentRentalSnapshot]
    totals: PricingTotalsSnapshot
    metadata: PricingMetadataSnapshot

    def to_dict(self) -> dict:
        return {
            "inputs": self.inputs.to_dict(),
            "lines": [line.to_dict() for line in self.lines],
            "equipment_rentals": [rental.to_dict() for rental in self.equipment_rentals],
            "totals": self.totals.to_dict(),
            "metadata": self.metadata.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize to deterministic JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


def compute_hash(data: Any) -> str:
    """Compute SHA256 hash of data."""
    if isinstance(data, dict):
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    elif isinstance(data, str):
        json_str = data
    else:
        json_str = str(data)

    hash_bytes = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    return f"sha256:{hash_bytes}"


def build_pricing_snapshot(
    *,
    excursion,
    lines: list[PricingLineSnapshot],
    equipment_rentals: list[EquipmentRentalSnapshot],
    totals: PricingTotalsSnapshot,
    gas_type: str = "air",
) -> PricingSnapshot:
    """Build a complete pricing snapshot.

    Args:
        excursion: Excursion instance
        lines: List of pricing line snapshots
        equipment_rentals: List of equipment rental snapshots
        totals: Pricing totals snapshot
        gas_type: Type of gas used

    Returns:
        PricingSnapshot ready for storage
    """
    # Build inputs
    inputs = PricingInputsSnapshot(
        excursion_id=str(excursion.pk),
        site_id=str(excursion.dive_site.pk) if excursion.dive_site else None,
        site_name=excursion.dive_site.name if excursion.dive_site else None,
        diver_count=totals.diver_count,
        dives_count=excursion.excursion_type.dives_per_excursion if excursion.excursion_type else 1,
        gas_type=gas_type,
        dive_shop_id=str(excursion.dive_shop.pk) if excursion.dive_shop else None,
    )

    # Compute hashes
    input_hash = compute_hash(inputs.to_dict())

    # Build output for hashing (excludes metadata)
    output_data = {
        "lines": [line.to_dict() for line in lines],
        "equipment_rentals": [rental.to_dict() for rental in equipment_rentals],
        "totals": totals.to_dict(),
    }
    output_hash = compute_hash(output_data)

    # Build metadata
    metadata = PricingMetadataSnapshot(
        schema_version=SCHEMA_VERSION,
        tool=TOOL_NAME,
        generated_at=timezone.now().isoformat(),
        input_hash=input_hash,
        output_hash=output_hash,
    )

    return PricingSnapshot(
        inputs=inputs,
        lines=lines,
        equipment_rentals=equipment_rentals,
        totals=totals,
        metadata=metadata,
    )


def extract_pricing_from_snapshot(snapshot_dict: dict) -> dict:
    """Extract key pricing values from a snapshot dict.

    Useful for displaying summary without full breakdown.

    Args:
        snapshot_dict: Parsed price_snapshot from Booking

    Returns:
        dict with key pricing values
    """
    totals = snapshot_dict.get("totals", {})

    return {
        "total_charge_per_diver": Decimal(totals.get("total_charge_per_diver", {}).get("amount", "0")),
        "total_cost_per_diver": Decimal(totals.get("total_cost_per_diver", {}).get("amount", "0")),
        "margin_per_diver": Decimal(totals.get("margin_per_diver", {}).get("amount", "0")),
        "diver_count": totals.get("diver_count", 0),
        "currency": totals.get("shared_cost", {}).get("currency", "MXN"),
        "schema_version": snapshot_dict.get("metadata", {}).get("schema_version"),
    }
