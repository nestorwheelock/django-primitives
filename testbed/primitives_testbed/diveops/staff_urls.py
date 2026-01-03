"""Staff portal URL patterns for diveops."""

from django.urls import path

from . import staff_views

app_name = "diveops"

urlpatterns = [
    # Trip management
    path("trips/", staff_views.TripListView.as_view(), name="trip-list"),
    path("trips/<uuid:pk>/", staff_views.TripDetailView.as_view(), name="trip-detail"),
    path("trips/<uuid:trip_pk>/book/", staff_views.BookDiverView.as_view(), name="book-diver"),
    # Actions (POST only)
    path("bookings/<uuid:pk>/check-in/", staff_views.CheckInView.as_view(), name="check-in"),
    path("trips/<uuid:pk>/start/", staff_views.StartTripView.as_view(), name="start-trip"),
    path("trips/<uuid:pk>/complete/", staff_views.CompleteTripView.as_view(), name="complete-trip"),
]
