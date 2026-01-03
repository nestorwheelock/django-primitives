"""Views for primitives_testbed."""

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def index(request):
    """Index page showing testbed status."""
    from django.apps import apps

    # Get all installed primitive apps
    primitive_apps = []
    for app_config in apps.get_app_configs():
        if app_config.name.startswith("django_"):
            primitive_apps.append({
                "name": app_config.name,
                "verbose_name": app_config.verbose_name,
                "models": [m.__name__ for m in app_config.get_models()],
            })

    context = {
        "primitive_apps": primitive_apps,
        "total_apps": len(primitive_apps),
    }
    return render(request, "index.html", context)


def health_check(request):
    """Health check endpoint for container orchestration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return JsonResponse({
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
    })
