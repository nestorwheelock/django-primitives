"""Clinic Scheduler scenario: Full-stack integration of 5 primitives.

Demonstrates: encounters (7-state visit), parties (patients/providers),
catalog (services/orders), worklog (provider time), rbac (role hierarchy).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group as DjangoGroup
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_catalog.models import CatalogItem, Basket, BasketItem, WorkItem
from django_encounters.models import EncounterDefinition, Encounter
from django_encounters.services import create_encounter, transition
from django_encounters.exceptions import InvalidTransition
from django_parties.models import Person, Organization, PartyRelationship
from django_rbac.models import Role, UserRole
from django_worklog.models import WorkSession
from django_worklog.services import start_session, stop_session

User = get_user_model()


# =============================================================================
# Constants
# =============================================================================

CLINIC_VISIT_STATES = [
    "scheduled",
    "confirmed",
    "checked_in",
    "vitals",
    "provider",
    "checkout",
    "completed",
    "cancelled",
]

CLINIC_VISIT_TRANSITIONS = {
    "scheduled": ["confirmed", "cancelled"],
    "confirmed": ["checked_in", "cancelled"],
    "checked_in": ["vitals", "cancelled"],
    "vitals": ["provider", "cancelled"],
    "provider": ["checkout", "cancelled"],
    "checkout": ["completed", "cancelled"],
}


# =============================================================================
# Seed Functions
# =============================================================================

def seed():
    """Create clinic scheduler sample data."""
    count = 0

    # 1. Create EncounterDefinition for clinic visits
    clinic_visit, created = EncounterDefinition.objects.get_or_create(
        key="clinic_visit",
        defaults={
            "name": "Clinic Visit",
            "states": CLINIC_VISIT_STATES,
            "transitions": CLINIC_VISIT_TRANSITIONS,
            "initial_state": "scheduled",
            "terminal_states": ["completed", "cancelled"],
        }
    )
    if created:
        count += 1

    # 2. Create clinic organization
    clinic, created = Organization.objects.get_or_create(
        name="Springfield Family Clinic",
        defaults={"org_type": "clinic"}
    )
    if created:
        count += 1

    # 3. Create RBAC roles
    roles = _seed_roles()
    count += roles

    # 4. Create providers
    providers = _seed_providers(clinic)
    count += providers

    # 5. Create patients
    patients = _seed_patients(clinic)
    count += patients

    # 6. Create catalog items
    catalog = _seed_catalog_items()
    count += catalog

    # 7. Create sample visits
    visits = _seed_sample_visits(clinic_visit)
    count += visits

    return count


def _seed_roles():
    """Create RBAC roles for clinic staff and patients."""
    count = 0

    # Create Django groups for roles
    doctor_group, _ = DjangoGroup.objects.get_or_create(name="Clinic Doctors")
    nurse_group, _ = DjangoGroup.objects.get_or_create(name="Clinic Nurses")
    ma_group, _ = DjangoGroup.objects.get_or_create(name="Medical Assistants")
    patient_group, _ = DjangoGroup.objects.get_or_create(name="Clinic Patients")

    # Doctor role - highest clinic level
    _, created = Role.objects.get_or_create(
        slug="clinic_doctor",
        defaults={
            "name": "Clinic Doctor",
            "hierarchy_level": 60,
            "group": doctor_group,
            "description": "Licensed physician",
        }
    )
    if created:
        count += 1

    # Nurse role
    _, created = Role.objects.get_or_create(
        slug="clinic_nurse",
        defaults={
            "name": "Clinic Nurse",
            "hierarchy_level": 40,
            "group": nurse_group,
            "description": "Registered nurse",
        }
    )
    if created:
        count += 1

    # Medical assistant role
    _, created = Role.objects.get_or_create(
        slug="clinic_ma",
        defaults={
            "name": "Medical Assistant",
            "hierarchy_level": 30,
            "group": ma_group,
            "description": "Medical assistant",
        }
    )
    if created:
        count += 1

    # Patient role
    _, created = Role.objects.get_or_create(
        slug="clinic_patient",
        defaults={
            "name": "Clinic Patient",
            "hierarchy_level": 10,
            "group": patient_group,
            "description": "Patient/customer",
        }
    )
    if created:
        count += 1

    return count


def _seed_providers(clinic):
    """Create provider persons with users and role assignments."""
    count = 0

    providers_data = [
        ("Sarah", "Chen", "dr_chen", "clinic_doctor"),
        ("Michael", "Torres", "nurse_torres", "clinic_nurse"),
        ("Emily", "Wilson", "ma_wilson", "clinic_ma"),
    ]

    for first_name, last_name, username, role_slug in providers_data:
        # Create person
        person, created = Person.objects.get_or_create(
            first_name=first_name,
            last_name=last_name,
        )
        if created:
            count += 1

        # Create user account
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@springfield-clinic.local",
                "first_name": first_name,
                "last_name": last_name,
            }
        )
        if created:
            user.set_password("clinic123")
            user.save()
            count += 1

        # Assign role
        role = Role.objects.get(slug=role_slug)
        _, created = UserRole.objects.get_or_create(
            user=user,
            role=role,
            defaults={"is_primary": True}
        )
        if created:
            count += 1

        # Link to clinic as employee
        _, created = PartyRelationship.objects.get_or_create(
            from_person=person,
            to_organization=clinic,
            relationship_type="employee",
        )
        if created:
            count += 1

    return count


def _seed_patients(clinic):
    """Create patient persons with role assignments."""
    count = 0

    patients_data = [
        ("John", "Smith", "patient_smith"),
        ("Maria", "Garcia", "patient_garcia"),
        ("Robert", "Johnson", "patient_johnson"),
        ("Lisa", "Wang", "patient_wang"),
        ("James", "Brown", "patient_brown"),
    ]

    patient_role = Role.objects.get(slug="clinic_patient")

    for first_name, last_name, username in patients_data:
        # Create person
        person, created = Person.objects.get_or_create(
            first_name=first_name,
            last_name=last_name,
        )
        if created:
            count += 1

        # Create user account
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@email.local",
                "first_name": first_name,
                "last_name": last_name,
            }
        )
        if created:
            user.set_password("patient123")
            user.save()
            count += 1

        # Assign patient role
        _, created = UserRole.objects.get_or_create(
            user=user,
            role=patient_role,
            defaults={"is_primary": True}
        )
        if created:
            count += 1

        # Link to clinic as customer
        _, created = PartyRelationship.objects.get_or_create(
            from_person=person,
            to_organization=clinic,
            relationship_type="customer",
        )
        if created:
            count += 1

    return count


def _seed_catalog_items():
    """Create medical services and stock items."""
    count = 0

    # Services
    services_data = [
        ("Office Visit - New Patient", "consult", True),
        ("Office Visit - Established", "consult", True),
        ("Blood Draw", "lab", True),
        ("Urinalysis", "lab", True),
        ("Vital Signs", "procedure", False),
        ("EKG", "procedure", True),
    ]

    for name, category, billable in services_data:
        _, created = CatalogItem.objects.get_or_create(
            display_name=name,
            kind="service",
            defaults={
                "service_category": category,
                "is_billable": billable,
                "active": True,
            }
        )
        if created:
            count += 1

    # Stock items
    stock_data = [
        ("Acetaminophen 500mg", "dispense", True),
        ("Ibuprofen 200mg", "dispense", True),
        ("Bandage Roll", "dispense", True),
        ("Flu Vaccine", "administer", True),
    ]

    for name, action, billable in stock_data:
        _, created = CatalogItem.objects.get_or_create(
            display_name=name,
            kind="stock_item",
            defaults={
                "default_stock_action": action,
                "is_billable": billable,
                "active": True,
            }
        )
        if created:
            count += 1

    return count


def _seed_sample_visits(definition):
    """Create sample visits in various states."""
    count = 0

    person_ct = ContentType.objects.get_for_model(Person)
    dr_chen = User.objects.filter(username="dr_chen").first()

    # Patient visits in different states
    visit_data = [
        ("John", "Smith", "vitals"),        # In vitals, about to see provider
        ("Maria", "Garcia", "provider"),    # With provider
        ("Robert", "Johnson", "scheduled"), # Just scheduled
        ("Lisa", "Wang", "checkout"),       # Ready to leave
        ("James", "Brown", "completed"),    # Already done
    ]

    for first_name, last_name, target_state in visit_data:
        patient = Person.objects.filter(
            first_name=first_name,
            last_name=last_name
        ).first()

        if not patient:
            continue

        # Create encounter
        encounter, created = Encounter.objects.get_or_create(
            definition=definition,
            subject_type=person_ct,
            subject_id=str(patient.pk),
            defaults={
                "state": definition.initial_state,
                "created_by": dr_chen,
            }
        )
        if created:
            count += 1

            # Progress to target state
            state_order = ["scheduled", "confirmed", "checked_in", "vitals", "provider", "checkout", "completed"]
            current_idx = state_order.index("scheduled")
            target_idx = state_order.index(target_state)

            for i in range(current_idx + 1, target_idx + 1):
                next_state = state_order[i]
                try:
                    transition(encounter, next_state, by_user=dr_chen)
                    count += 1
                except Exception:
                    break

    return count


# =============================================================================
# Verify Functions
# =============================================================================

def verify():
    """Verify clinic constraints with negative writes."""
    results = []

    # Test 1: Invalid state transition
    results.extend(_verify_state_machine())

    # Test 2: Provider time tracking (one active session)
    results.extend(_verify_time_tracking())

    # Test 3: RBAC hierarchy
    results.extend(_verify_rbac_hierarchy())

    return results


def _verify_state_machine():
    """Verify encounter state machine rejects invalid transitions."""
    results = []

    definition = EncounterDefinition.objects.filter(key="clinic_visit").first()
    encounter = Encounter.objects.filter(
        definition=definition,
        state="vitals"  # Patient in vitals state
    ).first()

    if encounter:
        # Try to skip to completed (invalid - must go through provider, checkout)
        try:
            transition(encounter, "completed")
            results.append(("clinic_visit_invalid_transition", False, "Should reject skip to completed"))
        except InvalidTransition:
            results.append(("clinic_visit_invalid_transition", True, "Correctly rejected skip"))

        # Try to go backwards (invalid)
        try:
            transition(encounter, "scheduled")
            results.append(("clinic_visit_backward_transition", False, "Should reject backward transition"))
        except InvalidTransition:
            results.append(("clinic_visit_backward_transition", True, "Correctly rejected backward"))
    else:
        results.append(("clinic_visit_state_machine", None, "Skipped - no vitals encounter"))

    return results


def _verify_time_tracking():
    """Verify one active session per provider constraint."""
    results = []

    provider_user = User.objects.filter(username="dr_chen").first()
    encounter1 = Encounter.objects.filter(state="provider").first()
    encounter2 = Encounter.objects.filter(state="vitals").first()

    if provider_user and encounter1 and encounter2:
        # Clear any existing sessions
        WorkSession.objects.filter(user=provider_user).delete()

        # Start first session
        session1 = start_session(provider_user, encounter1)

        # Start second session (should auto-stop first)
        session2 = start_session(provider_user, encounter2)

        # Verify first session is now stopped
        session1.refresh_from_db()
        if session1.stopped_at is not None and session2.stopped_at is None:
            results.append(("one_active_session_per_provider", True, "Auto-stopped previous session"))
        else:
            results.append(("one_active_session_per_provider", False, "Session switch failed"))

        # Clean up
        stop_session(provider_user)
    else:
        results.append(("time_tracking", None, "Skipped - missing test data"))

    return results


def _verify_rbac_hierarchy():
    """Verify RBAC hierarchy enforcement."""
    results = []

    doctor = User.objects.filter(username="dr_chen").first()
    nurse = User.objects.filter(username="nurse_torres").first()
    patient = User.objects.filter(username="patient_smith").first()

    if doctor and nurse and patient:
        # Doctor (60) can manage nurse (40)
        if doctor.can_manage_user(nurse):
            results.append(("doctor_manages_nurse", True, "Doctor can manage nurse"))
        else:
            results.append(("doctor_manages_nurse", False, "Doctor should manage nurse"))

        # Nurse (40) cannot manage doctor (60)
        if not nurse.can_manage_user(doctor):
            results.append(("nurse_cannot_manage_doctor", True, "Nurse cannot manage doctor"))
        else:
            results.append(("nurse_cannot_manage_doctor", False, "Nurse should not manage doctor"))

        # Patient (10) cannot manage anyone
        if not patient.can_manage_user(nurse):
            results.append(("patient_cannot_manage_staff", True, "Patient cannot manage staff"))
        else:
            results.append(("patient_cannot_manage_staff", False, "Patient should not manage staff"))
    else:
        results.append(("rbac_hierarchy", None, "Skipped - missing users"))

    return results
