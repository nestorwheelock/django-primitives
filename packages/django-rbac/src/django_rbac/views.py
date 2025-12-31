"""
RBAC View Mixins for class-based views.

Provides mixins to protect views with permission and hierarchy checks.

Usage:
    class StaffListView(ModulePermissionMixin, ListView):
        required_module = 'practice'
        required_action = 'view'
        model = StaffProfile

    class StaffEditView(HierarchyPermissionMixin, UpdateView):
        model = StaffProfile

        def get_target_user(self):
            return self.get_object().user
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ModulePermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to check module-level permissions for class-based views.

    Set required_module and required_action to specify the permission needed.
    The user must have the permission via their role's group.

    Attributes:
        required_module: The module name (e.g., 'practice', 'accounting')
        required_action: The action name (e.g., 'view', 'manage'). Defaults to 'view'.

    Examples:
        class StaffListView(ModulePermissionMixin, ListView):
            required_module = 'practice'
            required_action = 'view'
            model = StaffProfile

        class AccountingDashboard(ModulePermissionMixin, TemplateView):
            required_module = 'accounting'
            required_action = 'view'
            template_name = 'accounting/dashboard.html'
    """

    required_module = None
    required_action = 'view'

    def test_func(self):
        """Check if user has the required module permission."""
        if not self.required_module:
            return True

        if not hasattr(self.request.user, 'has_module_permission'):
            return False

        return self.request.user.has_module_permission(
            self.required_module,
            self.required_action,
        )


class HierarchyPermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to check if user can manage the target user (hierarchy check).

    Override get_target_user() to return the user being managed.
    The current user must have a higher hierarchy level than the target.

    This enforces CONTRACT Rule 2:
    "Users can only manage users with LOWER hierarchy levels."

    Examples:
        class StaffEditView(HierarchyPermissionMixin, UpdateView):
            model = StaffProfile

            def get_target_user(self):
                return self.get_object().user

        class UserDeleteView(HierarchyPermissionMixin, DeleteView):
            model = User

            def get_target_user(self):
                return self.get_object()
    """

    def get_target_user(self):
        """Override to return the user being managed.

        Returns:
            User: The user that this action targets.

        Raises:
            NotImplementedError: If not overridden in subclass.
        """
        raise NotImplementedError(
            'Subclasses must implement get_target_user()'
        )

    def test_func(self):
        """Check if requesting user can manage the target user."""
        if not hasattr(self.request.user, 'can_manage_user'):
            return False

        try:
            target = self.get_target_user()
        except NotImplementedError:
            return True

        if target is None:
            return True

        return self.request.user.can_manage_user(target)


class CombinedPermissionMixin(ModulePermissionMixin, HierarchyPermissionMixin):
    """Mixin that combines module permission and hierarchy checks.

    Use when you need both:
    1. Module-level permission (e.g., 'practice.edit')
    2. Hierarchy check (can only edit users below your level)

    Examples:
        class StaffEditView(CombinedPermissionMixin, UpdateView):
            required_module = 'practice'
            required_action = 'edit'
            model = StaffProfile

            def get_target_user(self):
                return self.get_object().user
    """

    def test_func(self):
        """Check both module permission and hierarchy."""
        # First check module permission
        if self.required_module:
            if not hasattr(self.request.user, 'has_module_permission'):
                return False

            if not self.request.user.has_module_permission(
                self.required_module,
                self.required_action,
            ):
                return False

        # Then check hierarchy if target user exists
        if not hasattr(self.request.user, 'can_manage_user'):
            return False

        try:
            target = self.get_target_user()
            if target is not None:
                return self.request.user.can_manage_user(target)
        except NotImplementedError:
            # No target user specified, just check module permission
            pass

        return True


class HierarchyLevelMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to require minimum hierarchy level for class-based views.

    Set required_level to the minimum hierarchy level needed.

    Attributes:
        required_level: The minimum hierarchy level (10-100).

    Examples:
        class SystemSettingsView(HierarchyLevelMixin, UpdateView):
            required_level = 80  # Administrator or higher
            model = SystemSettings

    Hierarchy levels reference:
        100 = Superuser
        80 = Administrator
        60 = Manager
        40 = Professional
        30 = Technician
        20 = Staff
        10 = Customer
    """

    required_level = 0

    def test_func(self):
        """Check if user meets minimum hierarchy level."""
        if not hasattr(self.request.user, 'hierarchy_level'):
            return False

        return self.request.user.hierarchy_level >= self.required_level
