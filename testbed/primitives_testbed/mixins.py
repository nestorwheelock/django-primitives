"""Testbed view mixins with impersonation support."""

from django_portal_ui.mixins import StaffPortalMixin, SuperadminMixin


class ImpersonationAwareStaffMixin(StaffPortalMixin):
    """Staff portal mixin that respects impersonation.

    When a staff user is impersonating a customer, we still want them
    to be able to access staff pages. This mixin checks the original_user
    for permissions when impersonation is active.
    """

    def test_func(self):
        # When impersonating, check the original user's permissions
        if getattr(self.request, 'is_impersonating', False):
            user = self.request.original_user
        else:
            user = self.request.user

        # Superusers always have access
        if user.is_superuser:
            return True

        # Must be staff
        if not user.is_staff:
            return False

        # If no module required, staff is enough
        if not self.required_module:
            return True

        # Check module permission via django-modules if available
        if hasattr(user, 'has_module_permission'):
            return user.has_module_permission(
                self.required_module,
                self.required_action
            )

        return True


class ImpersonationAwareSuperadminMixin(SuperadminMixin):
    """Superadmin mixin that respects impersonation."""

    def test_func(self):
        # When impersonating, check the original user
        if getattr(self.request, 'is_impersonating', False):
            return self.request.original_user.is_superuser
        return self.request.user.is_superuser
