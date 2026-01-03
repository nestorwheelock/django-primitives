"""Scenario modules for primitives testbed.

Each scenario module provides:
- seed(): Create sample data for that primitive
- verify(): Run negative write tests to confirm constraints
"""

from .parties import seed as seed_parties, verify as verify_parties
from .rbac import seed as seed_rbac, verify as verify_rbac
from .catalog import seed as seed_catalog, verify as verify_catalog
from .geo import seed as seed_geo, verify as verify_geo
from .encounters import seed as seed_encounters, verify as verify_encounters
from .documents import seed as seed_documents, verify as verify_documents
from .notes import seed as seed_notes, verify as verify_notes
from .sequence import seed as seed_sequence, verify as verify_sequence
from .ledger import seed as seed_ledger, verify as verify_ledger
from .worklog import seed as seed_worklog, verify as verify_worklog
from .agreements import seed as seed_agreements, verify as verify_agreements
from .pricing import seed as seed_pricing, verify as verify_pricing
from .invoicing import seed as seed_invoicing, verify as verify_invoicing
from .clinic import seed as seed_clinic, verify as verify_clinic

# Order matters: dependencies first
SCENARIOS = [
    ("parties", seed_parties, verify_parties),
    ("rbac", seed_rbac, verify_rbac),
    ("geo", seed_geo, verify_geo),
    ("sequence", seed_sequence, verify_sequence),
    ("encounters", seed_encounters, verify_encounters),
    ("catalog", seed_catalog, verify_catalog),
    ("documents", seed_documents, verify_documents),
    ("notes", seed_notes, verify_notes),
    ("ledger", seed_ledger, verify_ledger),
    ("worklog", seed_worklog, verify_worklog),
    ("agreements", seed_agreements, verify_agreements),
    ("pricing", seed_pricing, verify_pricing),
    ("invoicing", seed_invoicing, verify_invoicing),
    ("clinic", seed_clinic, verify_clinic),
]


def seed_all():
    """Seed all scenarios."""
    results = []
    for name, seed_fn, _ in SCENARIOS:
        try:
            count = seed_fn()
            results.append((name, "OK", count))
        except Exception as e:
            results.append((name, "ERROR", str(e)))
    return results


def verify_all():
    """Run verification for all scenarios."""
    results = []
    for name, _, verify_fn in SCENARIOS:
        try:
            checks = verify_fn()
            results.append((name, checks))
        except Exception as e:
            results.append((name, [("ERROR", False, str(e))]))
    return results
