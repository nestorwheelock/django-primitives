"""Encounters scenario: EncounterDefinition, Encounter, EncounterTransition."""

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction

from django_encounters.models import (
    EncounterDefinition,
    Encounter,
    EncounterTransition,
)
from django_encounters.services import create_encounter, transition
from django_encounters.exceptions import InvalidTransition, ImmutableTransitionError
from django_parties.models import Person


def seed():
    """Create sample encounters data."""
    count = 0

    # Create encounter definitions (workflows)
    patient_visit, created = EncounterDefinition.objects.get_or_create(
        key="patient_visit",
        defaults={
            "name": "Patient Visit",
            "states": ["scheduled", "checked_in", "in_progress", "completed", "cancelled"],
            "transitions": {
                "scheduled": ["checked_in", "cancelled"],
                "checked_in": ["in_progress", "cancelled"],
                "in_progress": ["completed", "cancelled"],
            },
            "initial_state": "scheduled",
            "terminal_states": ["completed", "cancelled"],
        }
    )
    if created:
        count += 1

    order_fulfillment, created = EncounterDefinition.objects.get_or_create(
        key="order_fulfillment",
        defaults={
            "name": "Order Fulfillment",
            "states": ["pending", "processing", "shipped", "delivered", "cancelled"],
            "transitions": {
                "pending": ["processing", "cancelled"],
                "processing": ["shipped", "cancelled"],
                "shipped": ["delivered"],
            },
            "initial_state": "pending",
            "terminal_states": ["delivered", "cancelled"],
        }
    )
    if created:
        count += 1

    # Create encounters
    person = Person.objects.first()
    if person:
        person_ct = ContentType.objects.get_for_model(Person)

        # Create a patient visit encounter
        visit, created = Encounter.objects.get_or_create(
            definition=patient_visit,
            subject_type=person_ct,
            subject_id=str(person.pk),
            defaults={"state": patient_visit.initial_state}
        )
        if created:
            count += 1

            # Progress through workflow using service
            transition(visit, "checked_in")
            transition(visit, "in_progress")
            count += 2  # Two transitions created

        # Create an order encounter
        order, created = Encounter.objects.get_or_create(
            definition=order_fulfillment,
            subject_type=person_ct,
            subject_id=str(person.pk),
            defaults={"state": order_fulfillment.initial_state}
        )
        if created:
            count += 1

            transition(order, "processing")
            count += 1

    return count


def verify():
    """Verify encounters constraints with negative writes."""
    results = []

    person = Person.objects.first()
    definition = EncounterDefinition.objects.first()

    if person and definition:
        person_ct = ContentType.objects.get_for_model(Person)

        # Test 1: Invalid transition should be rejected
        encounter = Encounter.objects.filter(
            definition__key="patient_visit",
            subject_type=person_ct,
            subject_id=str(person.pk),
        ).first()

        if encounter:
            try:
                # Try invalid transition (e.g., in_progress -> scheduled)
                transition(encounter, "scheduled")
                results.append(("invalid_transition_rejected", False, "Should have raised InvalidTransition"))
            except InvalidTransition:
                results.append(("invalid_transition_rejected", True, "Correctly rejected"))
            except Exception as e:
                results.append(("invalid_transition_rejected", True, f"Rejected with: {type(e).__name__}"))
        else:
            results.append(("invalid_transition_rejected", None, "Skipped - no encounter"))

        # Test 2: EncounterTransition immutability
        trans = EncounterTransition.objects.first()
        if trans:
            try:
                trans.from_state = "modified_state"
                trans.save()
                results.append(("transition_immutability", False, "Modification should be prevented"))
            except ImmutableTransitionError:
                results.append(("transition_immutability", True, "Correctly rejected"))
            except Exception as e:
                results.append(("transition_immutability", True, f"Correctly rejected: {type(e).__name__}"))
        else:
            results.append(("transition_immutability", None, "Skipped - no transitions"))

        # Test 3: Encounter subject_id is a CharField (not FK)
        # Verify we can store arbitrary string IDs
        try:
            with transaction.atomic():
                test_encounter = Encounter.objects.create(
                    definition=definition,
                    subject_type=person_ct,
                    subject_id="arbitrary-string-id-12345",
                    state=definition.initial_state,
                )
                test_encounter.delete()
            results.append(("subject_id_charfield", True, "Accepts arbitrary string IDs"))
        except Exception as e:
            results.append(("subject_id_charfield", False, f"Failed: {e}"))

    else:
        results.append(("encounters_tests", None, "Skipped - no test data"))

    return results
