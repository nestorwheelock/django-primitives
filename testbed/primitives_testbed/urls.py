"""URL configuration for primitives_testbed project."""

from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
    path("health/", views.health_check, name="health_check"),
    path("clinic/", include("primitives_testbed.clinic.urls")),
]
