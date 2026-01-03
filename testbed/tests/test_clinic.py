"""Tests for clinic scheduler scenario.

Tests the integration of 6 primitives:
- django-encounters (visit state machine)
- django-parties (patients/providers)
- django-catalog (services/orders)
- django-worklog (provider time tracking)
- django-rbac (role hierarchy)
- django-agreements (patient consent forms)
"""

import pytest
from django.db import IntegrityError, transaction
from django.contrib.contenttypes.models import ContentType

from django_agreements.models import Agreement
from django_catalog.models import CatalogItem, Basket, BasketItem, WorkItem
from django_encounters.models import EncounterDefinition, Encounter
from django_encounters.exceptions import InvalidTransition
from django_parties.models import Organization, Person
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


# =============================================================================
# View Error Handling Tests (Unseeded State)
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestClinicViewsUnseeded:
    """Test clinic views handle missing data gracefully (no seed_testbed run)."""

    def test_dashboard_without_seed_returns_200(self, client):
        """Dashboard should not crash when EncounterDefinition doesn't exist."""
        response = client.get("/clinic/")
        # Should return 200 with empty state, not 500
        assert response.status_code == 200

    def test_patient_list_without_seed_returns_200(self, client):
        """Patient list should handle missing clinic organization."""
        response = client.get("/clinic/patients/")
        assert response.status_code == 200

    def test_api_patients_without_seed_returns_200(self, client):
        """API patients endpoint should handle missing data."""
        response = client.get("/clinic/api/patients/")
        assert response.status_code == 200

    def test_api_visits_without_seed_returns_200(self, client):
        """API visits endpoint should handle missing EncounterDefinition."""
        response = client.get("/clinic/api/visits/")
        assert response.status_code == 200


# =============================================================================
# Patient Consent Tests
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestPatientConsents:
    """Test patient consent form requirements using django-agreements."""

    def test_required_consents_constant_exists(self, seeded_database):
        """REQUIRED_CONSENTS constant defines consent form types."""
        from primitives_testbed.clinic.services import REQUIRED_CONSENTS

        assert len(REQUIRED_CONSENTS) >= 3
        assert "general_consent" in REQUIRED_CONSENTS
        assert "hipaa_acknowledgment" in REQUIRED_CONSENTS
        assert "financial_responsibility" in REQUIRED_CONSENTS

    def test_new_patient_needs_all_consents(self, seeded_database):
        """New patient with no agreements needs all consent types."""
        from primitives_testbed.clinic.services import get_missing_consents
        from django.contrib.auth import get_user_model

        # Create a brand new patient with no agreements
        new_patient = Person.objects.create(
            first_name="New",
            last_name="Patient",
        )
        clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

        missing = get_missing_consents(new_patient, clinic)

        assert len(missing) == 3
        assert "general_consent" in missing
        assert "hipaa_acknowledgment" in missing
        assert "financial_responsibility" in missing

    def test_returning_patient_has_valid_consents(self, seeded_database):
        """Patient with current agreements has no missing consents."""
        from primitives_testbed.clinic.services import (
            get_missing_consents,
            sign_consent,
            REQUIRED_CONSENTS,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        patient = Person.objects.filter(first_name="John").first()
        clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

        # Sign all consents
        for consent_type in REQUIRED_CONSENTS.keys():
            sign_consent(patient, clinic, consent_type, user)

        missing = get_missing_consents(patient, clinic)
        assert len(missing) == 0

    def test_expired_consent_is_missing(self, seeded_database):
        """Expired agreement counts as missing consent."""
        from primitives_testbed.clinic.services import get_missing_consents
        from django_agreements.services import create_agreement
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        patient = Person.objects.filter(first_name="Robert").first()
        clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

        # Create an expired consent
        past_date = timezone.now() - timedelta(days=400)
        expired_date = timezone.now() - timedelta(days=35)

        create_agreement(
            party_a=patient,
            party_b=clinic,
            scope_type="consent",
            terms={"consent_type": "general_consent", "form_version": "2024-01"},
            agreed_by=user,
            valid_from=past_date,
            valid_to=expired_date,  # Expired
        )

        missing = get_missing_consents(patient, clinic)
        assert "general_consent" in missing

    def test_sign_consent_creates_agreement(self, seeded_database):
        """Signing consent creates Agreement with correct structure."""
        from primitives_testbed.clinic.services import sign_consent
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        patient = Person.objects.filter(first_name="Lisa").first()
        clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

        agreement = sign_consent(patient, clinic, "hipaa_acknowledgment", user)

        assert agreement is not None
        assert agreement.scope_type == "consent"
        assert agreement.terms["consent_type"] == "hipaa_acknowledgment"
        assert agreement.valid_from <= timezone.now()
        assert agreement.valid_to > timezone.now()  # Not expired
        assert agreement.agreed_by == user

    def test_cannot_transition_to_checked_in_without_consents(self, seeded_database):
        """Transition from confirmed to checked_in blocked without consents."""
        from primitives_testbed.clinic.services import transition_visit
        from primitives_testbed.clinic.exceptions import ConsentRequiredError
        from django_encounters.services import create_encounter, transition
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        # Create a new patient with no consents
        new_patient = Person.objects.create(
            first_name="NoConsent",
            last_name="Patient",
        )

        encounter = create_encounter("clinic_visit", new_patient, created_by=user)
        encounter = transition(encounter, "confirmed", by_user=user)

        # Should raise ConsentRequiredError when trying to check in
        with pytest.raises(ConsentRequiredError):
            transition_visit(encounter, "checked_in", by_user=user)

    def test_can_transition_to_checked_in_with_consents(self, seeded_database):
        """Transition allowed when all consents are signed."""
        from primitives_testbed.clinic.services import (
            transition_visit,
            sign_consent,
            REQUIRED_CONSENTS,
        )
        from django_encounters.services import create_encounter, transition
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()

        # Create patient and sign all consents
        patient = Person.objects.create(
            first_name="AllConsents",
            last_name="Patient",
        )
        clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

        for consent_type in REQUIRED_CONSENTS.keys():
            sign_consent(patient, clinic, consent_type, user)

        encounter = create_encounter("clinic_visit", patient, created_by=user)
        encounter = transition(encounter, "confirmed", by_user=user)

        # Should succeed
        updated = transition_visit(encounter, "checked_in", by_user=user)
        assert updated.state == "checked_in"

    def test_consent_api_returns_status(self, seeded_database, client):
        """API returns correct consent status for patient."""
        from primitives_testbed.clinic.services import sign_consent, REQUIRED_CONSENTS
        from django_encounters.services import create_encounter
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

        # Use Robert Johnson - a patient without seeded consents
        patient = Person.objects.filter(first_name="Robert").first()

        # Sign one consent
        sign_consent(patient, clinic, "general_consent", user)

        # Create visit
        encounter = create_encounter("clinic_visit", patient, created_by=user)

        response = client.get(f"/clinic/api/visits/{encounter.pk}/consents/")
        assert response.status_code == 200

        data = response.json()
        assert data["patient_name"] == "Robert Johnson"
        assert data["all_signed"] is False
        assert len(data["required_consents"]) == 3

        # Check that general_consent is signed
        general = next(c for c in data["required_consents"] if c["type"] == "general_consent")
        assert general["signed"] is True

        # Check that others are not signed
        hipaa = next(c for c in data["required_consents"] if c["type"] == "hipaa_acknowledgment")
        assert hipaa["signed"] is False

    def test_consent_sign_api_creates_agreement(self, seeded_database, client):
        """POST to sign API creates agreement and returns success."""
        from django_encounters.services import create_encounter
        from django.contrib.auth import get_user_model
        import json

        User = get_user_model()
        user = User.objects.filter(username="dr_chen").first()
        patient = Person.objects.filter(first_name="James").first()

        encounter = create_encounter("clinic_visit", patient, created_by=user)

        response = client.post(
            f"/clinic/api/visits/{encounter.pk}/consents/sign/",
            data=json.dumps({"consent_type": "financial_responsibility"}),
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.json()
        assert data["signed"] is True
        assert data["consent_type"] == "financial_responsibility"
        assert "agreement_id" in data
        assert "expires_at" in data
