"""Primitive integrations for diveops.

This module provides a single location for all primitive package imports,
following the adapter pattern recommended in DEPENDENCIES.md.

Application layers should import primitives through this module,
making dependencies explicit and easier to maintain.
"""

# Identity primitives
from django_parties.models import Organization, Person

# Location primitives
from django_geo.models import Place

# Workflow primitives
from django_encounters.models import Encounter, EncounterDefinition

# Commerce primitives
from django_catalog.models import Basket, BasketItem, CatalogItem

# Legal primitives
from django_agreements.models import Agreement

# Sequence generation
from django_sequence.services import next_sequence

# Invoicing (testbed module built on primitives)
from primitives_testbed.invoicing.models import Invoice, InvoiceLineItem

__all__ = [
    # Identity
    "Person",
    "Organization",
    # Location
    "Place",
    # Workflow
    "Encounter",
    "EncounterDefinition",
    # Commerce
    "Basket",
    "BasketItem",
    "CatalogItem",
    # Legal
    "Agreement",
    # Sequence
    "next_sequence",
    # Invoicing
    "Invoice",
    "InvoiceLineItem",
]
