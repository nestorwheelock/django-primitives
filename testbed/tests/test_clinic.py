"""Tests for clinic scheduler scenario.

Tests the integration of 5 primitives:
- django-encounters (visit state machine)
- django-parties (patients/providers)
- django-catalog (services/orders)
- django-worklog (provider time tracking)
- django-rbac (role hierarchy)
"""

import pytest
from django.db import IntegrityError, transaction
from django.contrib.contenttypes.models import ContentType

from django_catalog.models import CatalogItem, Basket, BasketItem, WorkItem
from django_encounters.models import EncounterDefinition, Encounter
from django_encounters.exceptions import InvalidTransition
from django_parties.models import Person
from django_worklog.models import WorkSession


# =============================================================================
# State Machine Tests
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestClinicVisitStateMachine:
    """Test the 7-state clinic visit workflow."""

    def test_clinic_visit_definition_exists(self, seeded_database):
        """Clinic visit encounter definition is created by seed."""
        definition = EncounterDefinition.objects.filter(key="clinic_visit").first()
        assert definition is not None
        assert definition.initial_state == "scheduled"
        assert "completed" in definition.terminal_states
        assert "cancelled" in definition.terminal_states

    def test_valid_transition_scheduled_to_confirmed(self, seeded_database):
        """Can transition from scheduled to confirmed."""
        from django_encounters.services import transition
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        definition = EncounterDefinition.objects.get(key="clinic_visit")

        # Create a new encounter in scheduled state
        person = Person.objects.first()
        person_ct = ContentType.objects.get_for_model(Person)

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=person_ct,
            subject_id=str(person.pk),
            state="scheduled",
            created_by=user,
        )

        # Transition to confirmed
        updated = transition(encounter, "confirmed", by_user=user)
        assert updated.state == "confirmed"

    def test_invalid_transition_skip_states(self, seeded_database):
        """Cannot skip states in the workflow."""
        from django_encounters.services import transition
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        # Get a visit in vitals state
        encounter = Encounter.objects.filter(
            definition__key="clinic_visit",
            state="vitals"
        ).first()

        if encounter:
            # Try to skip to completed (should fail)
            with pytest.raises(InvalidTransition):
                transition(encounter, "completed", by_user=user)

    def test_invalid_transition_backward(self, seeded_database):
        """Cannot transition backward in the workflow."""
        from django_encounters.services import transition
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        # Get a visit in vitals state
        encounter = Encounter.objects.filter(
            definition__key="clinic_visit",
            state="vitals"
        ).first()

        if encounter:
            # Try to go backward (should fail)
            with pytest.raises(InvalidTransition):
                transition(encounter, "scheduled", by_user=user)

    def test_full_workflow(self, seeded_database):
        """Can complete full visit workflow."""
        from django_encounters.services import transition, create_encounter
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        patient = Person.objects.filter(first_name="John").first()

        if user and patient:
            # Create new encounter
            encounter = create_encounter("clinic_visit", patient, created_by=user)
            assert encounter.state == "scheduled"

            # Progress through all states
            states = ["confirmed", "checked_in", "vitals", "provider", "checkout", "completed"]
            for next_state in states:
                encounter = transition(encounter, next_state, by_user=user)
                assert encounter.state == next_state

            # Verify ended_at is set for terminal state
            assert encounter.ended_at is not None


# =============================================================================
# Basket and WorkItem Tests
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestClinicBasketWorkflow:
    """Test basket management and work item spawning."""

    def test_add_item_to_basket(self, seeded_database):
        """Can add items to a visit's basket."""
        from primitives_testbed.clinic.services import add_item_to_basket, get_or_create_basket
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        encounter = Encounter.objects.filter(
            definition__key="clinic_visit"
        ).first()
        catalog_item = CatalogItem.objects.filter(kind="service").first()

        if encounter and catalog_item and user:
            basket_item = add_item_to_basket(encounter, catalog_item, user, quantity=2)
            assert basket_item is not None
            assert basket_item.quantity == 2
            assert basket_item.catalog_item == catalog_item

    def test_commit_basket_spawns_work_items(self, seeded_database):
        """Committing basket creates work items."""
        from primitives_testbed.clinic.services import add_item_to_basket, commit_basket
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        # Get an encounter without existing basket
        encounter = Encounter.objects.filter(
            definition__key="clinic_visit"
        ).exclude(
            baskets__status="draft"
        ).first()

        if not encounter:
            pytest.skip("No encounter without draft basket")

        lab_item = CatalogItem.objects.filter(service_category="lab").first()
        stock_item = CatalogItem.objects.filter(kind="stock_item").first()

        if lab_item and user:
            add_item_to_basket(encounter, lab_item, user)

        if stock_item and user:
            add_item_to_basket(encounter, stock_item, user)

        # Commit basket
        work_items = commit_basket(encounter, user)

        assert len(work_items) > 0
        # Verify work items have correct routing
        for wi in work_items:
            assert wi.status == "pending"
            assert wi.target_board in ["lab", "pharmacy", "treatment", "imaging"]

    def test_lab_service_routes_to_lab_board(self, seeded_database):
        """Lab services route to lab board."""
        from primitives_testbed.clinic.services import add_item_to_basket, commit_basket
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        # Find lab catalog item
        lab_item = CatalogItem.objects.filter(
            kind="service",
            service_category="lab"
        ).first()

        if not lab_item:
            pytest.skip("No lab service catalog item")

        # Create fresh encounter for this test
        definition = EncounterDefinition.objects.get(key="clinic_visit")
        patient = Person.objects.first()
        person_ct = ContentType.objects.get_for_model(Person)

        encounter = Encounter.objects.create(
            definition=definition,
            subject_type=person_ct,
            subject_id=str(patient.pk),
            state="scheduled",
            created_by=user,
        )

        add_item_to_basket(encounter, lab_item, user)
        work_items = commit_basket(encounter, user)

        assert len(work_items) == 1
        assert work_items[0].target_board == "lab"


# =============================================================================
# Provider Time Tracking Tests
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestProviderTimeTracking:
    """Test provider time tracking via worklog."""

    def test_start_session_on_encounter(self, seeded_database):
        """Provider can start a time session on an encounter."""
        from primitives_testbed.clinic.services import start_provider_session, stop_provider_session
        from django.contrib.auth import get_user_model

        User = get_user_model()
        provider = User.objects.filter(username="dr_chen").first()
        encounter = Encounter.objects.filter(definition__key="clinic_visit").first()

        if provider and encounter:
            # Clear any existing sessions
            WorkSession.objects.filter(user=provider).delete()

            session = start_provider_session(provider, encounter)
            assert session is not None
            assert session.stopped_at is None  # Active session

            # Clean up
            stop_provider_session(provider)

    def test_stop_session_computes_duration(self, seeded_database):
        """Stopping session computes duration."""
        from primitives_testbed.clinic.services import start_provider_session, stop_provider_session
        from django.contrib.auth import get_user_model
        import time

        User = get_user_model()
        provider = User.objects.filter(username="dr_chen").first()
        encounter = Encounter.objects.filter(definition__key="clinic_visit").first()

        if provider and encounter:
            # Clear any existing sessions
            WorkSession.objects.filter(user=provider).delete()

            session = start_provider_session(provider, encounter)

            # Brief pause to ensure non-zero duration
            time.sleep(0.1)

            stopped = stop_provider_session(provider)
            assert stopped is not None
            assert stopped.stopped_at is not None
            assert stopped.duration_seconds is not None
            assert stopped.duration_seconds >= 0

    def test_session_switch_stops_previous(self, seeded_database):
        """Starting new session auto-stops previous."""
        from primitives_testbed.clinic.services import start_provider_session, stop_provider_session
        from django.contrib.auth import get_user_model

        User = get_user_model()
        provider = User.objects.filter(username="dr_chen").first()
        encounters = list(Encounter.objects.filter(definition__key="clinic_visit")[:2])

        if provider and len(encounters) >= 2:
            # Clear any existing sessions
            WorkSession.objects.filter(user=provider).delete()

            # Start first session
            session1 = start_provider_session(provider, encounters[0])

            # Start second session (should auto-stop first)
            session2 = start_provider_session(provider, encounters[1])

            # Verify first is stopped
            session1.refresh_from_db()
            assert session1.stopped_at is not None

            # Verify second is active
            assert session2.stopped_at is None

            # Clean up
            stop_provider_session(provider)


# =============================================================================
# RBAC Tests
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestClinicRBAC:
    """Test role hierarchy in clinic context."""

    def test_doctor_can_manage_nurse(self, seeded_database):
        """Doctor (level 60) can manage nurse (level 40)."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        doctor = User.objects.filter(username="dr_chen").first()
        nurse = User.objects.filter(username="nurse_torres").first()

        if doctor and nurse:
            assert doctor.can_manage_user(nurse)

    def test_nurse_cannot_manage_doctor(self, seeded_database):
        """Nurse (level 40) cannot manage doctor (level 60)."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        doctor = User.objects.filter(username="dr_chen").first()
        nurse = User.objects.filter(username="nurse_torres").first()

        if doctor and nurse:
            assert not nurse.can_manage_user(doctor)

    def test_patient_cannot_manage_staff(self, seeded_database):
        """Patient (level 10) cannot manage any staff."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        patient = User.objects.filter(username="patient_smith").first()
        ma = User.objects.filter(username="ma_wilson").first()

        if patient and ma:
            assert not patient.can_manage_user(ma)


# =============================================================================
# Full Workflow Integration Test
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestClinicFullWorkflow:
    """Test complete patient visit lifecycle."""

    def test_complete_patient_visit_lifecycle(self, seeded_database):
        """Run through complete clinic visit from scheduling to completion."""
        from django_encounters.services import create_encounter, transition
        from primitives_testbed.clinic.services import (
            add_item_to_basket,
            commit_basket,
            start_provider_session,
            stop_provider_session,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        doctor = User.objects.filter(username="dr_chen").first()
        patient = Person.objects.filter(first_name="Maria").first()

        if not doctor or not patient:
            pytest.skip("Required users not found")

        # 1. Schedule visit
        encounter = create_encounter("clinic_visit", patient, created_by=doctor)
        assert encounter.state == "scheduled"

        # 2. Confirm appointment
        encounter = transition(encounter, "confirmed", by_user=doctor)
        assert encounter.state == "confirmed"

        # 3. Patient checks in
        encounter = transition(encounter, "checked_in", by_user=doctor)
        assert encounter.state == "checked_in"

        # 4. Take vitals
        encounter = transition(encounter, "vitals", by_user=doctor)
        assert encounter.state == "vitals"

        # 5. Provider starts session
        session = start_provider_session(doctor, encounter)
        assert session.stopped_at is None

        # 6. Move to provider state
        encounter = transition(encounter, "provider", by_user=doctor)
        assert encounter.state == "provider"

        # 7. Add items to basket
        blood_draw = CatalogItem.objects.filter(display_name__icontains="Blood").first()
        if blood_draw:
            add_item_to_basket(encounter, blood_draw, doctor)

        # 8. Commit basket - spawns work items
        work_items = commit_basket(encounter, doctor)
        assert len(work_items) > 0

        # 9. Stop provider session
        stopped = stop_provider_session(doctor)
        assert stopped.duration_seconds is not None

        # 10. Move to checkout
        encounter = transition(encounter, "checkout", by_user=doctor)
        assert encounter.state == "checkout"

        # 11. Complete visit
        encounter = transition(encounter, "completed", by_user=doctor)
        assert encounter.state == "completed"
        assert encounter.ended_at is not None

    def test_seed_and_verify_clinic_scenario(self, seeded_database):
        """Verify clinic scenario seed and verify functions work."""
        from primitives_testbed.scenarios.clinic import verify

        results = verify()
        failures = [(name, detail) for name, passed, detail in results if passed is False]

        assert len(failures) == 0, f"Verification failures: {failures}"
