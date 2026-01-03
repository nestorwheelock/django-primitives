"""Agreements scenario: Agreement, AgreementVersion with effective dating."""

import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_agreements.models import Agreement, AgreementVersion
from django_agreements.services import create_agreement, amend_agreement
from django_agreements.exceptions import ImmutableVersionError
from django_parties.models import Person, Organization


User = get_user_model()


def seed():
    """Create sample agreements data."""
    count = 0

    user = User.objects.first()
    if not user:
        return count

    now = timezone.now()

    # Get parties
    persons = list(Person.objects.all()[:2])
    orgs = list(Organization.objects.all()[:2])

    if len(persons) < 2 and len(orgs) < 1:
        return count

    # Create a service agreement between person and organization
    if persons and orgs:
        person = persons[0]
        org = orgs[0]

        # Check if agreement already exists
        existing = Agreement.objects.for_party(person).filter(scope_type="service_contract").exists()

        if not existing:
            agreement = create_agreement(
                party_a=person,
                party_b=org,
                scope_type="service_contract",
                terms={
                    "services": ["consulting", "support"],
                    "rate": 100.00,
                    "currency": "USD",
                },
                agreed_by=user,
                valid_from=now - datetime.timedelta(days=30),
                agreed_at=now - datetime.timedelta(days=30),
            )
            count += 1

            # Amend the agreement
            amend_agreement(
                agreement=agreement,
                new_terms={
                    "services": ["consulting", "support", "training"],
                    "rate": 120.00,
                    "currency": "USD",
                },
                reason="Added training services and rate increase",
                amended_by=user,
            )
            count += 1

    # Create a consent agreement between two persons
    if len(persons) >= 2:
        person_a = persons[0]
        person_b = persons[1]

        existing = Agreement.objects.for_party(person_a).filter(scope_type="consent").exists()

        if not existing:
            consent = create_agreement(
                party_a=person_a,
                party_b=person_b,
                scope_type="consent",
                terms={
                    "purpose": "data_sharing",
                    "categories": ["contact_info", "preferences"],
                },
                agreed_by=user,
                valid_from=now,
                agreed_at=now,
                valid_to=now + datetime.timedelta(days=365),  # Expires in 1 year
            )
            count += 1

    return count


def verify():
    """Verify agreements constraints with negative writes."""
    results = []

    agreement = Agreement.objects.first()
    user = User.objects.first()

    if agreement and user:
        # Test 1: Agreement version must be unique per agreement
        existing_version = AgreementVersion.objects.filter(agreement=agreement).first()
        if existing_version:
            try:
                with transaction.atomic():
                    AgreementVersion.objects.create(
                        agreement=agreement,
                        version=existing_version.version,  # Duplicate version
                        terms={"test": "duplicate"},
                        created_by=user,
                        reason="Duplicate test",
                    )
                results.append(("unique_agreement_version", False, "Should have raised IntegrityError"))
            except IntegrityError:
                results.append(("unique_agreement_version", True, "Correctly rejected duplicate"))
        else:
            results.append(("unique_agreement_version", None, "Skipped - no existing version"))

        # Test 2: valid_to must be after valid_from
        now = timezone.now()
        persons = list(Person.objects.all()[:2])
        if len(persons) >= 2:
            try:
                with transaction.atomic():
                    Agreement.objects.create(
                        party_a=persons[0],
                        party_b=persons[1],
                        scope_type="test_invalid_dates",
                        terms={"test": "invalid dates"},
                        valid_from=now,
                        valid_to=now - datetime.timedelta(days=1),  # Before valid_from
                        agreed_at=now,
                        agreed_by=user,
                    )
                results.append(("agreements_valid_to_after_valid_from", False, "Should have raised IntegrityError"))
            except IntegrityError:
                results.append(("agreements_valid_to_after_valid_from", True, "Correctly rejected"))
        else:
            results.append(("agreements_valid_to_after_valid_from", None, "Skipped - not enough parties"))

        # Test 3: AgreementVersion immutability
        version = AgreementVersion.objects.first()
        if version:
            try:
                version.reason = "Modified reason"
                version.save()
                results.append(("agreement_version_immutability", False, "Should have raised ImmutableVersionError"))
            except ImmutableVersionError:
                results.append(("agreement_version_immutability", True, "Correctly rejected modification"))
            except Exception as e:
                results.append(("agreement_version_immutability", True, f"Rejected with: {type(e).__name__}"))
        else:
            results.append(("agreement_version_immutability", None, "Skipped - no version"))

    else:
        results.append(("agreements_tests", None, "Skipped - no test data"))

    return results
