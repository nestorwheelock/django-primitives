"""Staff portal URL patterns for diveops."""

from django.urls import path

from . import staff_views

app_name = "diveops"

urlpatterns = [
    # Dashboard
    path("", staff_views.DashboardView.as_view(), name="dashboard"),
    # Diver management
    path("divers/", staff_views.DiverListView.as_view(), name="diver-list"),
    path("divers/add/", staff_views.CreateDiverView.as_view(), name="diver-create"),
    path("divers/<uuid:pk>/", staff_views.DiverDetailView.as_view(), name="diver-detail"),
    path("divers/<uuid:pk>/edit/", staff_views.EditDiverView.as_view(), name="diver-edit"),
    # Certification management
    path("divers/<uuid:diver_pk>/certifications/add/", staff_views.AddCertificationView.as_view(), name="certification-add"),
    path("certifications/<uuid:pk>/edit/", staff_views.EditCertificationView.as_view(), name="certification-edit"),
    path("certifications/<uuid:pk>/delete/", staff_views.DeleteCertificationView.as_view(), name="certification-delete"),
    path("certifications/<uuid:pk>/verify/", staff_views.VerifyCertificationView.as_view(), name="certification-verify"),
    # Excursion management
    path("excursions/", staff_views.ExcursionListView.as_view(), name="excursion-list"),
    path("excursions/<uuid:pk>/", staff_views.ExcursionDetailView.as_view(), name="excursion-detail"),
    path("excursions/<uuid:excursion_pk>/book/", staff_views.BookDiverView.as_view(), name="book-diver"),
    # Actions (POST only)
    path("bookings/<uuid:pk>/check-in/", staff_views.CheckInView.as_view(), name="check-in"),
    path("excursions/<uuid:pk>/start/", staff_views.StartExcursionView.as_view(), name="start-excursion"),
    path("excursions/<uuid:pk>/complete/", staff_views.CompleteExcursionView.as_view(), name="complete-excursion"),
    # Dive Site management
    path("sites/", staff_views.DiveSiteListView.as_view(), name="staff-site-list"),
    path("sites/add/", staff_views.DiveSiteCreateView.as_view(), name="staff-site-create"),
    path("sites/<uuid:pk>/", staff_views.DiveSiteDetailView.as_view(), name="staff-site-detail"),
    path("sites/<uuid:pk>/edit/", staff_views.DiveSiteUpdateView.as_view(), name="staff-site-edit"),
    path("sites/<uuid:pk>/delete/", staff_views.DiveSiteDeleteView.as_view(), name="staff-site-delete"),
    # System
    path("audit-log/", staff_views.AuditLogView.as_view(), name="audit-log"),
]
