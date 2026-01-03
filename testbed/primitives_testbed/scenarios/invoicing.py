"""Invoicing scenario - creates sample invoices from baskets.

Uses the invoicing module to demonstrate the basket-to-invoice flow.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.utils import timezone

from django_catalog.models import Basket, BasketItem, CatalogItem
from django_encounters.models import Encounter, EncounterDefinition
from django_parties.models import Organization, Person

from primitives_testbed.pricing.models import Price
from primitives_testbed.invoicing.models import Invoice
from primitives_testbed.invoicing.services import create_invoice_from_basket
from primitives_testbed.invoicing.payments import record_payment

User = get_user_model()


def seed():
    """Create sample invoices from baskets.

    Prerequisites: pricing scenario must be seeded first.
    """
    count = 0

    # Get or create admin user
    user, _ = User.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@springfieldclinic.local",
            "is_staff": True,
            "is_superuser": True,
        }
    )
    if not user.has_usable_password():
        user.set_password("testpass123")
        user.save()

    # Get or create the clinic
    clinic, _ = Organization.objects.get_or_create(
        name="Springfield Family Clinic",
        defaults={"org_type": "healthcare"},
    )

    # Get or create encounter definition
    encounter_def, _ = EncounterDefinition.objects.get_or_create(
        key="clinic_visit",
        defaults={
            "name": "Clinic Visit",
            "initial_state": "scheduled",
            "states": ["scheduled", "confirmed", "checked_in", "vitals", "provider", "checkout", "completed", "cancelled"],
            "terminal_states": ["completed", "cancelled"],
            "transitions": {
                "scheduled": ["confirmed", "cancelled"],
                "confirmed": ["checked_in", "cancelled"],
                "checked_in": ["vitals", "cancelled"],
                "vitals": ["provider", "cancelled"],
                "provider": ["checkout", "cancelled"],
                "checkout": ["completed", "cancelled"],
            },
        },
    )

    # Get or create catalog items
    aspirin, _ = CatalogItem.objects.get_or_create(
        display_name="Aspirin 100mg",
        defaults={
            "kind": "stock_item",
            "default_stock_action": "dispense",
            "is_billable": True,
            "active": True,
        },
    )
    exam, _ = CatalogItem.objects.get_or_create(
        display_name="General Examination",
        defaults={
            "kind": "service",
            "service_category": "consult",
            "is_billable": True,
            "active": True,
        },
    )

    now = timezone.now()

    # Ensure prices exist - check if any active price exists
    if not Price.objects.filter(catalog_item=aspirin, valid_to__isnull=True).exists():
        Price.objects.create(
            catalog_item=aspirin,
            amount=Decimal("12.50"),
            currency="USD",
            priority=50,
            valid_from=now,
            created_by=user,
            reason="Standard retail price",
        )
    if not Price.objects.filter(catalog_item=exam, valid_to__isnull=True).exists():
        Price.objects.create(
            catalog_item=exam,
            amount=Decimal("75.00"),
            currency="USD",
            priority=50,
            valid_from=now,
            created_by=user,
            reason="Standard consultation fee",
        )

    person_ct = ContentType.objects.get_for_model(Person)

    # Create sample patients and invoices
    patients_data = [
        ("Alice", "Smith", "1985-03-20"),
        ("Bob", "Johnson", "1990-07-15"),
        ("Carol", "Williams", "1978-11-08"),
    ]

    for first_name, last_name, dob in patients_data:
        # Get or create patient
        patient, _ = Person.objects.get_or_create(
            first_name=first_name,
            last_name=last_name,
            defaults={"date_of_birth": dob},
        )

        # Check if this patient already has an invoice
        existing_invoice = Invoice.objects.filter(billed_to=patient).first()
        if existing_invoice:
            continue  # Skip if already has invoice

        # Create encounter
        encounter = Encounter.objects.create(
            definition=encounter_def,
            subject_type=person_ct,
            subject_id=str(patient.pk),
            state="checkout",
            created_by=user,
        )

        # Create basket
        basket = Basket.objects.create(
            encounter=encounter,
            status="committed",
            created_by=user,
        )
        BasketItem.objects.create(
            basket=basket,
            catalog_item=aspirin,
            quantity=2,
            added_by=user,
        )
        BasketItem.objects.create(
            basket=basket,
            catalog_item=exam,
            quantity=1,
            added_by=user,
        )

        # Create invoice
        invoice = create_invoice_from_basket(
            basket=basket,
            created_by=user,
            tax_rate=Decimal("0.08"),
            issue_immediately=True,
        )
        count += 1

        # Pay one of them
        if first_name == "Alice":
            record_payment(
                invoice=invoice,
                amount=invoice.total_amount,
                payment_method="card",
                recorded_by=user,
            )

    return count


def verify():
    """Verify invoicing constraints."""
    checks = []

    # Check 1: Cannot create invoice from draft basket
    from primitives_testbed.invoicing.exceptions import BasketNotCommittedError
    from primitives_testbed.invoicing.context import extract_invoice_context

    user = User.objects.filter(is_superuser=True).first()
    if user:
        encounter_def = EncounterDefinition.objects.first()
        if encounter_def:
            person_ct = ContentType.objects.get_for_model(Person)
            patient = Person.objects.first()
            if patient:
                # Create a draft basket
                enc = Encounter.objects.create(
                    definition=encounter_def,
                    subject_type=person_ct,
                    subject_id=str(patient.pk),
                    state="scheduled",
                    created_by=user,
                )
                draft_basket = Basket.objects.create(
                    encounter=enc,
                    status="draft",
                    created_by=user,
                )

                try:
                    extract_invoice_context(draft_basket)
                    checks.append(("Draft basket should fail", False, "No error raised"))
                except BasketNotCommittedError:
                    checks.append(("Draft basket rejected", True, "BasketNotCommittedError raised"))
                except Exception as e:
                    checks.append(("Draft basket rejected", False, str(e)))

                # Cleanup
                draft_basket.delete()
                enc.delete()

    # Check 2: Cannot overpay invoice
    from primitives_testbed.invoicing.exceptions import InvoiceStateError

    invoice = Invoice.objects.filter(status="issued").first()
    if invoice:
        try:
            record_payment(
                invoice=invoice,
                amount=invoice.total_amount + Decimal("100"),
                payment_method="cash",
                recorded_by=user,
            )
            checks.append(("Overpayment should fail", False, "No error raised"))
        except InvoiceStateError:
            checks.append(("Overpayment rejected", True, "InvoiceStateError raised"))
        except Exception as e:
            checks.append(("Overpayment rejected", False, str(e)))

    return checks
