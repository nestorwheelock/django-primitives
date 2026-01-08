"""Profile URL routes."""

from django.urls import path

from . import views

app_name = "profile"

urlpatterns = [
    path("", views.ProfileView.as_view(), name="view"),
    path("edit/", views.ProfileEditView.as_view(), name="edit"),
    path("photo/", views.ProfilePhotoView.as_view(), name="photo"),
    path("photo/delete/", views.ProfilePhotoDeleteView.as_view(), name="photo_delete"),
    path("password/", views.PasswordChangeView.as_view(), name="password"),
]
