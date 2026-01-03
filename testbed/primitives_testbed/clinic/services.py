"""Clinic Scheduler business logic.

Wraps primitives (encounters, catalog, worklog) with clinic-specific operations.
"""

from datetime import date, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet, Sum
from django.utils import timezone

from django_catalog.models import Basket, BasketItem, CatalogItem, WorkItem
from django_encounters.models import Encounter, EncounterDefinition
from django_encounters.services import (
    create_encounter,
    get_allowed_transitions,
    transition,
)
from django_parties.models import Organization, Person
from django_worklog.models import WorkSession
from django_worklog.services import (
    get_active_session,
    start_session,
    stop_session,
)

User = get_user_model()


# =============================================================================
# Visit Management
# =============================================================================

def get_clinic_definition() -> EncounterDefinition:
    """Get the clinic_visit encounter definition."""
    return EncounterDefinition.objects.get(key="clinic_visit")


def create_clinic_visit(
    patient: Person,
    created_by: User,
    scheduled_time: Optional[timezone.datetime] = None,
) -> Encounter:
    """Create a new clinic visit for a patient."""
    definition = get_clinic_definition()
    encounter = create_encounter(
        definition_key="clinic_visit",
        subject=patient,
        created_by=created_by,
        metadata={
            "scheduled_time": (scheduled_time or timezone.now()).isoformat(),
        },
    )
    return encounter


def get_todays_visits(clinic: Optional[Organization] = None) -> QuerySet[Encounter]:
    """Get all clinic visits for today."""
    definition = get_clinic_definition()
    today = date.today()
    tomorrow = today + timedelta(days=1)

    visits = Encounter.objects.filter(
        definition=definition,
        created_at__date=today,
    ).select_related("definition").order_by("created_at")

    return visits


def get_visits_by_state(state: str) -> QuerySet[Encounter]:
    """Get all visits in a specific state."""
    definition = get_clinic_definition()
    return Encounter.objects.filter(
        definition=definition,
        state=state,
    ).select_related("definition")


def transition_visit(
    encounter: Encounter,
    to_state: str,
    by_user: Optional[User] = None,
) -> Encounter:
    """Transition a visit to a new state."""
    return transition(encounter, to_state, by_user=by_user)


def get_visit_allowed_transitions(encounter: Encounter) -> list[str]:
    """Get allowed next states for a visit."""
    return get_allowed_transitions(encounter)


def get_visit_summary(encounter: Encounter) -> dict:
    """Get a summary of a visit including patient, basket, work items."""
    person_ct = ContentType.objects.get_for_model(Person)

    # Get patient
    patient = None
    if encounter.subject_type == person_ct:
        patient = Person.objects.filter(pk=encounter.subject_id).first()

    # Get basket
    basket = Basket.objects.filter(encounter=encounter).first()
    basket_items = []
    if basket:
        basket_items = list(
            BasketItem.objects.filter(basket=basket)
            .select_related("catalog_item")
            .values("id", "catalog_item__display_name", "quantity")
        )

    # Get work items
    work_items = list(
        WorkItem.objects.filter(encounter=encounter)
        .values("id", "display_name", "target_board", "status", "priority")
    )

    return {
        "id": str(encounter.pk),
        "state": encounter.state,
        "allowed_transitions": get_allowed_transitions(encounter),
        "patient": {
            "id": str(patient.pk) if patient else None,
            "name": f"{patient.first_name} {patient.last_name}" if patient else None,
        },
        "basket": {
            "id": str(basket.pk) if basket else None,
            "status": basket.status if basket else None,
            "items": basket_items,
        },
        "work_items": work_items,
        "created_at": encounter.created_at.isoformat(),
        "metadata": encounter.metadata or {},
    }


# =============================================================================
# Basket Management
# =============================================================================

def get_or_create_basket(encounter: Encounter, user: User) -> Basket:
    """Get or create a draft basket for the encounter."""
    basket, created = Basket.objects.get_or_create(
        encounter=encounter,
        status="draft",
        defaults={"created_by": user},
    )
    return basket


def add_item_to_basket(
    encounter: Encounter,
    catalog_item: CatalogItem,
    user: User,
    quantity: int = 1,
) -> BasketItem:
    """Add an item to the encounter's basket."""
    basket = get_or_create_basket(encounter, user)

    basket_item, created = BasketItem.objects.update_or_create(
        basket=basket,
        catalog_item=catalog_item,
        defaults={"quantity": quantity, "added_by": user},
    )
    return basket_item


def commit_basket(encounter: Encounter, user: User) -> list[WorkItem]:
    """Commit basket and spawn work items."""
    basket = Basket.objects.filter(encounter=encounter, status="draft").first()
    if not basket:
        return []

    work_items = []

    with transaction.atomic():
        # Create work items for each basket item
        for basket_item in basket.items.select_related("catalog_item"):
            item = basket_item.catalog_item

            # Determine target board based on item type
            if item.kind == "stock_item":
                if item.default_stock_action == "administer":
                    target_board = "treatment"
                else:
                    target_board = "pharmacy"
            else:  # service
                category = item.service_category or "treatment"
                if category == "lab":
                    target_board = "lab"
                elif category == "imaging":
                    target_board = "imaging"
                else:
                    target_board = "treatment"

            work_item = WorkItem.objects.create(
                basket_item=basket_item,
                encounter=encounter,
                spawn_role="primary",
                display_name=item.display_name,
                kind=item.kind,
                target_board=target_board,
                status="pending",
                priority=50,
            )
            work_items.append(work_item)

        # Mark basket as committed
        basket.status = "committed"
        basket.save()

    return work_items


# =============================================================================
# Provider Time Tracking
# =============================================================================

def start_provider_session(provider: User, encounter: Encounter) -> WorkSession:
    """Start a time tracking session for a provider on an encounter."""
    return start_session(provider, encounter)


def stop_provider_session(provider: User) -> Optional[WorkSession]:
    """Stop the provider's active session."""
    try:
        return stop_session(provider)
    except Exception:
        return None


def get_provider_active_session(provider: User) -> Optional[WorkSession]:
    """Get the provider's current active session."""
    return get_active_session(provider)


def get_provider_sessions_today(provider: User) -> QuerySet[WorkSession]:
    """Get all sessions for a provider today."""
    today = date.today()
    return WorkSession.objects.filter(
        user=provider,
        started_at__date=today,
    ).order_by("-started_at")


def get_provider_total_time_today(provider: User) -> int:
    """Get total seconds worked by provider today."""
    sessions = get_provider_sessions_today(provider)

    total = sessions.filter(
        duration_seconds__isnull=False
    ).aggregate(total=Sum("duration_seconds"))["total"] or 0

    # Add time from active session
    active = get_provider_active_session(provider)
    if active:
        elapsed = (timezone.now() - active.started_at).total_seconds()
        total += int(elapsed)

    return total


# =============================================================================
# Status Board
# =============================================================================

def get_status_board() -> dict[str, list[dict]]:
    """Get visits organized by state for a kanban-style board."""
    definition = get_clinic_definition()
    person_ct = ContentType.objects.get_for_model(Person)

    board = {
        "checked_in": [],
        "vitals": [],
        "provider": [],
        "checkout": [],
        "completed": [],
        "cancelled": [],
    }

    visits = Encounter.objects.filter(
        definition=definition,
        state__in=board.keys(),
        created_at__date=date.today(),
    ).select_related("definition")

    for visit in visits:
        patient = None
        if visit.subject_type == person_ct:
            patient = Person.objects.filter(pk=visit.subject_id).first()

        board[visit.state].append({
            "id": str(visit.pk),
            "patient_name": f"{patient.first_name} {patient.last_name}" if patient else "Unknown",
            "created_at": visit.created_at.isoformat(),
        })

    return board


def get_providers_time_summary() -> list[dict]:
    """Get time summary for all providers today."""
    from django_rbac.models import UserRole

    # Get users with provider roles (hierarchy >= 30)
    provider_user_ids = UserRole.objects.filter(
        role__hierarchy_level__gte=30,
    ).values_list("user_id", flat=True)

    providers = User.objects.filter(pk__in=provider_user_ids)
    summaries = []

    for provider in providers:
        total_seconds = get_provider_total_time_today(provider)
        active_session = get_provider_active_session(provider)

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        summaries.append({
            "id": provider.pk,
            "name": f"{provider.first_name} {provider.last_name}",
            "total_time": f"{hours}h {minutes}m",
            "total_seconds": total_seconds,
            "is_active": active_session is not None,
        })

    return summaries
