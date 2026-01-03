"""Parties scenario: Person, Organization, relationships, addresses."""

from django.db import IntegrityError, transaction

from django_parties.models import (
    Person,
    Organization,
    Group,
    Address,
    Phone,
    Email,
    PartyRelationship,
)


def seed():
    """Create sample parties data."""
    count = 0

    # Create organizations
    acme, created = Organization.objects.get_or_create(
        name="Acme Corporation",
        defaults={"org_type": "company", "website": "https://acme.example.com"}
    )
    if created:
        count += 1
        # Add address to organization
        Address.objects.get_or_create(
            organization=acme,
            line1="123 Main St",
            defaults={
                "city": "Springfield",
                "state": "IL",
                "postal_code": "62701",
                "country": "US",
                "is_primary": True,
            }
        )
        count += 1

    hospital, created = Organization.objects.get_or_create(
        name="General Hospital",
        defaults={"org_type": "hospital"}
    )
    if created:
        count += 1

    # Create a group
    team, created = Group.objects.get_or_create(
        name="Engineering Team",
        defaults={"group_type": "team"}
    )
    if created:
        count += 1

    # Create persons
    alice, created = Person.objects.get_or_create(
        first_name="Alice",
        last_name="Smith",
    )
    if created:
        count += 1
        Email.objects.get_or_create(
            person=alice,
            email="alice@example.com",
            defaults={"is_primary": True}
        )
        Phone.objects.get_or_create(
            person=alice,
            number="+15551234567",
            defaults={"phone_type": "mobile", "is_primary": True}
        )
        count += 2

    bob, created = Person.objects.get_or_create(
        first_name="Bob",
        last_name="Jones",
    )
    if created:
        count += 1
        Email.objects.get_or_create(
            person=bob,
            email="bob@example.com",
            defaults={"is_primary": True}
        )
        count += 1

    # Create relationships
    PartyRelationship.objects.get_or_create(
        relationship_type='employee',
        from_person=alice,
        to_organization=acme,
    )
    PartyRelationship.objects.get_or_create(
        relationship_type='member',
        from_person=bob,
        to_group=team,
    )
    count += 2

    return count


def verify():
    """Verify parties constraints with negative writes."""
    results = []

    # Test 1: Address must belong to exactly one party (XOR constraint)
    try:
        with transaction.atomic():
            # Try to create address with no party - should fail
            Address.objects.create(
                line1="123 Test St",
                city="Test City",
                state="TS",
                postal_code="12345",
                country="US",
                # No person, organization, or group set
            )
        results.append(("address_exactly_one_party (no party)", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("address_exactly_one_party (no party)", True, "Correctly rejected"))

    # Test 2: Address with multiple parties should fail
    person = Person.objects.first()
    org = Organization.objects.first()
    if person and org:
        try:
            with transaction.atomic():
                Address.objects.create(
                    person=person,
                    organization=org,  # Both set - should fail
                    line1="456 Test St",
                    city="Test City",
                    state="TS",
                    postal_code="12345",
                    country="US",
                )
            results.append(("address_exactly_one_party (multiple)", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("address_exactly_one_party (multiple)", True, "Correctly rejected"))
    else:
        results.append(("address_exactly_one_party (multiple)", None, "Skipped - no test data"))

    # Test 3: Phone XOR constraint
    try:
        with transaction.atomic():
            Phone.objects.create(
                number="+15559999999",
                phone_type="mobile",
                # No party set
            )
        results.append(("phone_exactly_one_party", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("phone_exactly_one_party", True, "Correctly rejected"))

    # Test 4: Email XOR constraint
    try:
        with transaction.atomic():
            Email.objects.create(
                email="orphan@test.com",
                # No party set
            )
        results.append(("email_exactly_one_party", False, "Should have raised IntegrityError"))
    except IntegrityError:
        results.append(("email_exactly_one_party", True, "Correctly rejected"))

    # Test 5: PartyRelationship exactly_one_from constraint
    org = Organization.objects.first()
    if org:
        try:
            with transaction.atomic():
                PartyRelationship.objects.create(
                    relationship_type='employee',
                    # No from_person or from_organization
                    to_organization=org,
                )
            results.append(("partyrelationship_exactly_one_from", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("partyrelationship_exactly_one_from", True, "Correctly rejected"))
    else:
        results.append(("partyrelationship_exactly_one_from", None, "Skipped - no test data"))

    # Test 6: PartyRelationship exactly_one_to constraint
    person = Person.objects.first()
    if person:
        try:
            with transaction.atomic():
                PartyRelationship.objects.create(
                    relationship_type='employee',
                    from_person=person,
                    # No to_person, to_organization, or to_group
                )
            results.append(("partyrelationship_exactly_one_to", False, "Should have raised IntegrityError"))
        except IntegrityError:
            results.append(("partyrelationship_exactly_one_to", True, "Correctly rejected"))
    else:
        results.append(("partyrelationship_exactly_one_to", None, "Skipped - no test data"))

    return results
