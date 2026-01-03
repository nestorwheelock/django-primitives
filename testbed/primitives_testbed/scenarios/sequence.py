"""Sequence scenario: Generate human-readable IDs."""

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction

from django_sequence.models import Sequence
from django_parties.models import Organization


def seed():
    """Create sample sequence data."""
    count = 0

    org = Organization.objects.first()
    if org:
        org_ct = ContentType.objects.get_for_model(Organization)

        # Create sequences for different purposes
        invoice_seq, created = Sequence.objects.get_or_create(
            scope="invoice",
            org_content_type=org_ct,
            org_id=str(org.pk),
            defaults={
                "prefix": "INV-",
                "current_value": 0,
                "pad_width": 6,
                "include_year": True,
            }
        )
        if created:
            count += 1

        order_seq, created = Sequence.objects.get_or_create(
            scope="order",
            org_content_type=org_ct,
            org_id=str(org.pk),
            defaults={
                "prefix": "ORD-",
                "current_value": 0,
                "pad_width": 5,
                "include_year": True,
            }
        )
        if created:
            count += 1

        patient_seq, created = Sequence.objects.get_or_create(
            scope="patient",
            org_content_type=org_ct,
            org_id=str(org.pk),
            defaults={
                "prefix": "PT-",
                "current_value": 0,
                "pad_width": 8,
                "include_year": False,
            }
        )
        if created:
            count += 1

        # Advance sequences by incrementing current_value
        for seq in [invoice_seq, order_seq, patient_seq]:
            seq.current_value += 3
            seq.save()

    return count


def verify():
    """Verify sequence constraints and behavior."""
    results = []

    org = Organization.objects.first()
    if org:
        org_ct = ContentType.objects.get_for_model(Organization)

        # Test 1: Sequence scope + org must be unique
        existing_seq = Sequence.objects.filter(
            scope="invoice",
            org_content_type=org_ct,
            org_id=str(org.pk),
        ).first()

        if existing_seq:
            try:
                with transaction.atomic():
                    Sequence.objects.create(
                        scope="invoice",  # Same scope
                        org_content_type=org_ct,
                        org_id=str(org.pk),  # Same org
                        prefix="DUP-",
                        current_value=0,
                    )
                results.append(("sequence_unique_per_scope_org", False, "Should have raised IntegrityError"))
            except IntegrityError:
                results.append(("sequence_unique_per_scope_org", True, "Correctly rejected duplicate"))
        else:
            results.append(("sequence_unique_per_scope_org", None, "Skipped - no existing sequence"))

        # Test 2: formatted_value property works correctly
        seq = Sequence.objects.filter(
            scope="invoice",
            org_content_type=org_ct,
            org_id=str(org.pk),
        ).first()

        if seq:
            # Test formatted output
            formatted = seq.formatted_value
            if formatted and seq.prefix in formatted:
                results.append(("sequence_formatted_output", True, f"Format: {formatted}"))
            else:
                results.append(("sequence_formatted_output", False, f"Bad format: {formatted}"))
        else:
            results.append(("sequence_tests", None, "Skipped - no sequence"))
    else:
        results.append(("sequence_tests", None, "Skipped - no organization"))

    return results
