"""URL configuration for clinic scheduler."""

from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    # HTML views
    path("", views.dashboard, name="dashboard"),
    path("patients/", views.patient_list, name="patient_list"),
    path("visits/<uuid:visit_id>/", views.visit_detail, name="visit_detail"),

    # API endpoints
    path("api/patients/", views.api_patients, name="api_patients"),
    path("api/visits/", views.api_visits, name="api_visits"),
    path("api/visits/<uuid:visit_id>/", views.api_visit_detail, name="api_visit_detail"),
    path("api/visits/<uuid:visit_id>/transition/", views.api_visit_transition, name="api_visit_transition"),
    path("api/visits/<uuid:visit_id>/basket/items/", views.api_basket_add_item, name="api_basket_add_item"),
    path("api/visits/<uuid:visit_id>/basket/commit/", views.api_basket_commit, name="api_basket_commit"),
    path("api/visits/<uuid:visit_id>/consents/", views.api_visit_consents, name="api_visit_consents"),
    path("api/visits/<uuid:visit_id>/consents/sign/", views.api_visit_sign_consent, name="api_visit_sign_consent"),
    path("api/providers/<int:provider_id>/time/start/", views.api_time_start, name="api_time_start"),
    path("api/providers/<int:provider_id>/time/stop/", views.api_time_stop, name="api_time_stop"),
]
