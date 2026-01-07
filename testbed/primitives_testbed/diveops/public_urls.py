"""Public URL patterns for diveops.

These URLs do NOT require authentication.
"""

from django.urls import path

from . import public_views

app_name = "diveops_public"

urlpatterns = [
    # Public agreement signing (token-based, rate-limited)
    path("<str:token>/", public_views.PublicSigningView.as_view(), name="sign"),
    # Public medical questionnaire (UUID-based)
    path(
        "medical/<uuid:instance_id>/",
        public_views.PublicMedicalQuestionnaireView.as_view(),
        name="medical-questionnaire",
    ),
]
