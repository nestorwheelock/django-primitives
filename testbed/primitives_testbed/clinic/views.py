"""Views for clinic scheduler - HTML templates and REST API."""

import json
from uuid import UUID

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from django_catalog.models import CatalogItem
from django_encounters.models import Encounter
from django_parties.models import Organization, Person

from . import services

User = get_user_model()


# =============================================================================
# HTML Views
# =============================================================================

@require_GET
def dashboard(request):
    """Main clinic dashboard."""
    context = {
        "clinic_name": "Springfield Family Clinic",
        "todays_visits": list(services.get_todays_visits()),
        "status_board": services.get_status_board(),
        "providers_time": services.get_providers_time_summary(),
    }
    return render(request, "clinic/dashboard.html", context)


@require_GET
def patient_list(request):
    """List of clinic patients."""
    clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

    # Get patients linked to clinic
    patients = Person.objects.filter(
        from_relationships__to_organization=clinic,
        from_relationships__relationship_type="customer",
    ).distinct()

    context = {
        "patients": patients,
    }
    return render(request, "clinic/patient_list.html", context)


@require_GET
def visit_detail(request, visit_id: UUID):
    """Single visit management page."""
    encounter = get_object_or_404(Encounter, pk=visit_id)
    summary = services.get_visit_summary(encounter)

    # Get available catalog items for ordering
    catalog_items = CatalogItem.objects.filter(active=True).order_by("kind", "display_name")

    context = {
        "visit": summary,
        "encounter": encounter,
        "catalog_items": catalog_items,
    }
    return render(request, "clinic/visit_detail.html", context)


# =============================================================================
# REST API Views
# =============================================================================

@require_GET
def api_patients(request):
    """API: List all patients."""
    clinic = Organization.objects.filter(name="Springfield Family Clinic").first()

    patients = Person.objects.filter(
        from_relationships__to_organization=clinic,
        from_relationships__relationship_type="customer",
    ).distinct()

    data = [
        {
            "id": str(p.pk),
            "name": f"{p.first_name} {p.last_name}",
            "first_name": p.first_name,
            "last_name": p.last_name,
        }
        for p in patients
    ]
    return JsonResponse({"patients": data})


@csrf_exempt
def api_visits(request):
    """API: List today's visits or create new visit."""
    if request.method == "GET":
        visits = services.get_todays_visits()
        data = [services.get_visit_summary(v) for v in visits]
        return JsonResponse({"visits": data})

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
            patient_id = body.get("patient_id")
            patient = get_object_or_404(Person, pk=patient_id)

            # Use first provider as creator (in real app, use authenticated user)
            creator = User.objects.filter(username="dr_chen").first()
            if not creator:
                creator = User.objects.first()

            encounter = services.create_clinic_visit(patient, creator)
            return JsonResponse({
                "id": str(encounter.pk),
                "state": encounter.state,
                "created": True,
            }, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@require_GET
def api_visit_detail(request, visit_id: UUID):
    """API: Get visit details."""
    encounter = get_object_or_404(Encounter, pk=visit_id)
    summary = services.get_visit_summary(encounter)
    return JsonResponse(summary)


@csrf_exempt
@require_POST
def api_visit_transition(request, visit_id: UUID):
    """API: Transition visit to new state."""
    try:
        encounter = get_object_or_404(Encounter, pk=visit_id)
        body = json.loads(request.body)
        to_state = body.get("to_state")

        if not to_state:
            return JsonResponse({"error": "to_state is required"}, status=400)

        # Get user (in real app, use authenticated user)
        user = User.objects.filter(username="dr_chen").first()

        updated = services.transition_visit(encounter, to_state, by_user=user)
        return JsonResponse({
            "id": str(updated.pk),
            "state": updated.state,
            "allowed_transitions": services.get_visit_allowed_transitions(updated),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_POST
def api_basket_add_item(request, visit_id: UUID):
    """API: Add item to visit's basket."""
    try:
        encounter = get_object_or_404(Encounter, pk=visit_id)
        body = json.loads(request.body)

        catalog_item_id = body.get("catalog_item_id")
        quantity = body.get("quantity", 1)

        catalog_item = get_object_or_404(CatalogItem, pk=catalog_item_id)

        # Get user
        user = User.objects.filter(username="dr_chen").first()
        if not user:
            user = User.objects.first()

        basket_item = services.add_item_to_basket(encounter, catalog_item, user, quantity)
        return JsonResponse({
            "basket_item_id": str(basket_item.pk),
            "catalog_item": catalog_item.display_name,
            "quantity": basket_item.quantity,
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_POST
def api_basket_commit(request, visit_id: UUID):
    """API: Commit basket and spawn work items."""
    try:
        encounter = get_object_or_404(Encounter, pk=visit_id)

        # Get user
        user = User.objects.filter(username="dr_chen").first()
        if not user:
            user = User.objects.first()

        work_items = services.commit_basket(encounter, user)
        return JsonResponse({
            "committed": True,
            "work_items": [
                {
                    "id": str(wi.pk),
                    "display_name": wi.display_name,
                    "target_board": wi.target_board,
                    "status": wi.status,
                }
                for wi in work_items
            ],
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_POST
def api_time_start(request, provider_id: int):
    """API: Start provider time tracking session."""
    try:
        provider = get_object_or_404(User, pk=provider_id)
        body = json.loads(request.body)
        encounter_id = body.get("encounter_id")

        encounter = get_object_or_404(Encounter, pk=encounter_id)

        session = services.start_provider_session(provider, encounter)
        return JsonResponse({
            "session_id": str(session.pk),
            "started_at": session.started_at.isoformat(),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_POST
def api_time_stop(request, provider_id: int):
    """API: Stop provider time tracking session."""
    try:
        provider = get_object_or_404(User, pk=provider_id)

        session = services.stop_provider_session(provider)
        if session:
            return JsonResponse({
                "session_id": str(session.pk),
                "duration_seconds": session.duration_seconds,
            })
        else:
            return JsonResponse({"error": "No active session"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
