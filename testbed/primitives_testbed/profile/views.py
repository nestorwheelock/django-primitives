"""Profile views for all user types."""

import pytz

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView, FormView

from .models import get_user_preferences


class ProfileView(LoginRequiredMixin, TemplateView):
    """Main profile page showing user info and settings."""

    template_name = "profile/profile.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        prefs = get_user_preferences(user)

        # Get diver profile if exists
        diver = None
        diver_certs = []
        try:
            from primitives_testbed.diveops.selectors import (
                get_current_diver,
                get_diver_with_certifications,
            )
            diver = get_current_diver(user)
            if diver:
                diver_with_certs = get_diver_with_certifications(diver.pk)
                if diver_with_certs:
                    diver = diver_with_certs
                    diver_certs = list(diver.certifications.all())
        except ImportError:
            pass

        # Get staff permissions if staff
        staff_modules = []
        if user.is_staff and hasattr(user, 'module_memberships'):
            staff_modules = list(user.module_memberships.select_related('module').all())

        context.update({
            "profile_user": user,
            "preferences": prefs,
            "diver": diver,
            "diver_certs": diver_certs,
            "staff_modules": staff_modules,
            "timezones": pytz.common_timezones,
        })
        return context


class ProfileEditView(LoginRequiredMixin, TemplateView):
    """Edit basic profile information."""

    template_name = "profile/profile_edit.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        prefs = get_user_preferences(user)

        # Get diver profile if exists
        diver = None
        try:
            from primitives_testbed.diveops.selectors import get_current_diver
            diver = get_current_diver(user)
        except ImportError:
            pass

        context.update({
            "profile_user": user,
            "preferences": prefs,
            "diver": diver,
            "timezones": pytz.common_timezones,
        })
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        prefs = get_user_preferences(user)

        # Update user fields
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()

        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])

        # Update preferences
        timezone = request.POST.get("timezone", "UTC")
        email_notifications = request.POST.get("email_notifications") == "on"
        marketing_emails = request.POST.get("marketing_emails") == "on"

        prefs.timezone = timezone
        prefs.email_notifications = email_notifications
        prefs.marketing_emails = marketing_emails
        prefs.save()

        # Update diver/person if exists
        try:
            from primitives_testbed.diveops.selectors import get_current_diver
            diver = get_current_diver(user)
            if diver and diver.person:
                person = diver.person
                person.first_name = first_name
                person.last_name = last_name
                phone = request.POST.get("phone", "").strip()
                if phone:
                    person.phone = phone
                person.save()
        except ImportError:
            pass

        messages.success(request, "Profile updated successfully.")
        return redirect("profile:view")


class ProfilePhotoView(LoginRequiredMixin, TemplateView):
    """Upload or change profile photo."""

    template_name = "profile/profile_photo.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        prefs = get_user_preferences(user)

        # Get diver profile photo if exists
        diver = None
        try:
            from primitives_testbed.diveops.selectors import get_current_diver
            diver = get_current_diver(user)
        except ImportError:
            pass

        context.update({
            "profile_user": user,
            "preferences": prefs,
            "diver": diver,
        })
        return context

    def post(self, request, *args, **kwargs):
        from django_documents.services import attach_document

        user = request.user
        prefs = get_user_preferences(user)

        uploaded_file = request.FILES.get("photo")
        if not uploaded_file:
            messages.error(request, "Please select a photo to upload.")
            return redirect("profile:photo")

        # Create document attached to user preferences
        document = attach_document(
            target=prefs,
            file=uploaded_file,
            document_type="profile_photo",
            uploaded_by=user,
            description=f"Profile photo for {user.get_full_name() or user.email}",
        )

        # Set as user preferences profile photo
        prefs.profile_photo = document
        prefs.save(update_fields=["profile_photo", "updated_at"])

        # Also set on diver profile if exists
        try:
            from primitives_testbed.diveops.selectors import get_current_diver
            diver = get_current_diver(user)
            if diver:
                diver.profile_photo = document
                diver.save(update_fields=["profile_photo", "updated_at"])
        except ImportError:
            pass

        messages.success(request, "Profile photo updated.")
        return redirect("profile:view")


class ProfilePhotoDeleteView(LoginRequiredMixin, TemplateView):
    """Remove profile photo."""

    login_url = "/accounts/login/"

    def post(self, request, *args, **kwargs):
        user = request.user
        prefs = get_user_preferences(user)

        # Clear preferences photo
        prefs.profile_photo = None
        prefs.save(update_fields=["profile_photo", "updated_at"])

        # Also clear diver profile photo if exists
        try:
            from primitives_testbed.diveops.selectors import get_current_diver
            diver = get_current_diver(user)
            if diver:
                diver.profile_photo = None
                diver.save(update_fields=["profile_photo", "updated_at"])
        except ImportError:
            pass

        messages.success(request, "Profile photo removed.")
        return redirect("profile:view")


class PasswordChangeView(LoginRequiredMixin, FormView):
    """Change password."""

    template_name = "profile/password_change.html"
    form_class = PasswordChangeForm
    login_url = "/accounts/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, "Password changed successfully.")
        return redirect("profile:view")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile_user"] = self.request.user
        return context
