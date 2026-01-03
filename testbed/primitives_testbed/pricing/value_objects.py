"""Value objects for the pricing module."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django_money import Money


@dataclass(frozen=True)
class ResolvedPrice:
    """Immutable result of price resolution.

    Contains the resolved unit price and metadata about how it was determined.
    """

    unit_price: Money
    price_id: UUID
    scope_type: str  # 'agreement' | 'party' | 'organization' | 'global'
    scope_id: UUID | None
    valid_from: datetime
    valid_to: datetime | None
    priority: int

    def explain(self) -> str:
        """Human-readable explanation of why this price was selected."""
        scope_desc = {
            "agreement": "contract-specific pricing",
            "party": "individual-specific pricing",
            "organization": "organization-specific pricing",
            "global": "standard list price",
        }
        desc = scope_desc.get(self.scope_type, self.scope_type)
        validity = (
            f"valid from {self.valid_from.strftime('%Y-%m-%d')}"
            if self.valid_from
            else "no start date"
        )
        if self.valid_to:
            validity += f" until {self.valid_to.strftime('%Y-%m-%d')}"

        return f"{self.unit_price} ({desc}, priority {self.priority}, {validity})"
