"""Django Parties views - CRUD views for People, Organizations, Groups, Relationships.

Copyright 2025 Nestor Wheelock. All Rights Reserved.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    DemographicsForm,
    GroupForm,
    OrganizationForm,
    PartyRelationshipForm,
    PersonForm,
)
from .models import Demographics, Group, Organization, PartyRelationship, Person


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin requiring staff access."""

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# =============================================================================
# Dashboard
# =============================================================================

class PartiesDashboardView(StaffRequiredMixin, TemplateView):
    """Dashboard for parties module with KPIs."""

    template_name = 'parties/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['people_count'] = Person.objects.count()
        context['organizations_count'] = Organization.objects.count()
        context['groups_count'] = Group.objects.count()
        context['relationships_count'] = PartyRelationship.objects.count()
        context['recent_people'] = Person.objects.order_by('-created_at')[:5]
        context['recent_organizations'] = Organization.objects.order_by('-created_at')[:5]
        return context


# =============================================================================
# Person CRUD
# =============================================================================

class PeopleListView(StaffRequiredMixin, ListView):
    """List all people."""

    model = Person
    template_name = 'parties/people_list.html'
    context_object_name = 'people'
    paginate_by = 25

    def get_queryset(self):
        return Person.objects.order_by('last_name', 'first_name')


class PersonDetailView(StaffRequiredMixin, DetailView):
    """View person details."""

    model = Person
    template_name = 'parties/person_detail.html'
    context_object_name = 'person'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = self.object
        context['relationships_from'] = person.relationships_from.select_related(
            'to_person', 'to_organization', 'to_group'
        )
        context['relationships_to'] = person.relationships_to.select_related(
            'from_person', 'from_organization'
        )
        context['addresses'] = person.addresses.all()
        context['phone_numbers'] = person.phone_numbers.all()
        context['email_addresses'] = person.email_addresses.all()
        context['urls'] = person.urls.all()
        try:
            context['demographics'] = person.demographics
        except Demographics.DoesNotExist:
            context['demographics'] = None
        return context


class PersonCreateView(StaffRequiredMixin, CreateView):
    """Create a new person."""

    model = Person
    form_class = PersonForm
    template_name = 'parties/person_form.html'
    success_url = reverse_lazy('django_parties:people_list')

    def form_valid(self, form):
        messages.success(self.request, _('Person created successfully.'))
        return super().form_valid(form)


class PersonUpdateView(StaffRequiredMixin, UpdateView):
    """Update an existing person."""

    model = Person
    form_class = PersonForm
    template_name = 'parties/person_form.html'
    context_object_name = 'person'

    def get_success_url(self):
        return reverse_lazy('django_parties:person_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _('Person updated successfully.'))
        return super().form_valid(form)


class PersonDeleteView(StaffRequiredMixin, DeleteView):
    """Delete a person."""

    model = Person
    template_name = 'parties/person_confirm_delete.html'
    success_url = reverse_lazy('django_parties:people_list')
    context_object_name = 'person'

    def form_valid(self, form):
        messages.success(self.request, _('Person deleted successfully.'))
        return super().form_valid(form)


# =============================================================================
# Organization CRUD
# =============================================================================

class OrganizationsListView(StaffRequiredMixin, ListView):
    """List all organizations."""

    model = Organization
    template_name = 'parties/organizations_list.html'
    context_object_name = 'organizations'
    paginate_by = 25

    def get_queryset(self):
        return Organization.objects.order_by('name')


class OrganizationDetailView(StaffRequiredMixin, DetailView):
    """View organization details."""

    model = Organization
    template_name = 'parties/organization_detail.html'
    context_object_name = 'organization'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.object
        context['members'] = org.relationships_to.select_related(
            'from_person', 'from_organization'
        )
        context['addresses'] = org.addresses.all()
        context['phone_numbers'] = org.phone_numbers.all()
        context['email_addresses'] = org.email_addresses.all()
        context['urls'] = org.urls.all()
        return context


class OrganizationCreateView(StaffRequiredMixin, CreateView):
    """Create a new organization."""

    model = Organization
    form_class = OrganizationForm
    template_name = 'parties/organization_form.html'
    success_url = reverse_lazy('django_parties:organizations_list')

    def form_valid(self, form):
        messages.success(self.request, _('Organization created successfully.'))
        return super().form_valid(form)


class OrganizationUpdateView(StaffRequiredMixin, UpdateView):
    """Update an existing organization."""

    model = Organization
    form_class = OrganizationForm
    template_name = 'parties/organization_form.html'
    context_object_name = 'organization'

    def get_success_url(self):
        return reverse_lazy('django_parties:organization_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _('Organization updated successfully.'))
        return super().form_valid(form)


class OrganizationDeleteView(StaffRequiredMixin, DeleteView):
    """Delete an organization."""

    model = Organization
    template_name = 'parties/organization_confirm_delete.html'
    success_url = reverse_lazy('django_parties:organizations_list')
    context_object_name = 'organization'

    def form_valid(self, form):
        messages.success(self.request, _('Organization deleted successfully.'))
        return super().form_valid(form)


# =============================================================================
# Group CRUD
# =============================================================================

class GroupsListView(StaffRequiredMixin, ListView):
    """List all groups (households, families)."""

    model = Group
    template_name = 'parties/groups_list.html'
    context_object_name = 'groups'
    paginate_by = 25

    def get_queryset(self):
        return Group.objects.select_related('primary_contact').order_by('name')


class GroupDetailView(StaffRequiredMixin, DetailView):
    """View group details."""

    model = Group
    template_name = 'parties/group_detail.html'
    context_object_name = 'group'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.object
        context['members'] = group.relationships_to.select_related(
            'from_person', 'from_organization'
        )
        context['addresses'] = group.addresses.all()
        context['phone_numbers'] = group.phone_numbers.all()
        context['email_addresses'] = group.email_addresses.all()
        context['urls'] = group.urls.all()
        return context


class GroupCreateView(StaffRequiredMixin, CreateView):
    """Create a new group (household/family)."""

    model = Group
    form_class = GroupForm
    template_name = 'parties/group_form.html'
    success_url = reverse_lazy('django_parties:groups_list')

    def form_valid(self, form):
        messages.success(self.request, _('Group created successfully.'))
        return super().form_valid(form)


class GroupUpdateView(StaffRequiredMixin, UpdateView):
    """Update an existing group."""

    model = Group
    form_class = GroupForm
    template_name = 'parties/group_form.html'
    context_object_name = 'group'

    def get_success_url(self):
        return reverse_lazy('django_parties:group_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _('Group updated successfully.'))
        return super().form_valid(form)


class GroupDeleteView(StaffRequiredMixin, DeleteView):
    """Delete a group."""

    model = Group
    template_name = 'parties/group_confirm_delete.html'
    success_url = reverse_lazy('django_parties:groups_list')
    context_object_name = 'group'

    def form_valid(self, form):
        messages.success(self.request, _('Group deleted successfully.'))
        return super().form_valid(form)


# =============================================================================
# PartyRelationship CRUD
# =============================================================================

class RelationshipsListView(StaffRequiredMixin, ListView):
    """List all party relationships."""

    model = PartyRelationship
    template_name = 'parties/relationships_list.html'
    context_object_name = 'relationships'
    paginate_by = 25

    def get_queryset(self):
        return PartyRelationship.objects.select_related(
            'from_person', 'from_organization',
            'to_person', 'to_organization', 'to_group'
        ).order_by('-created_at')


class RelationshipCreateView(StaffRequiredMixin, CreateView):
    """Create a new party relationship."""

    model = PartyRelationship
    form_class = PartyRelationshipForm
    template_name = 'parties/relationship_form.html'
    success_url = reverse_lazy('django_parties:relationships_list')

    def form_valid(self, form):
        messages.success(self.request, _('Relationship created successfully.'))
        return super().form_valid(form)


class RelationshipUpdateView(StaffRequiredMixin, UpdateView):
    """Update an existing relationship."""

    model = PartyRelationship
    form_class = PartyRelationshipForm
    template_name = 'parties/relationship_form.html'
    success_url = reverse_lazy('django_parties:relationships_list')
    context_object_name = 'relationship'

    def form_valid(self, form):
        messages.success(self.request, _('Relationship updated successfully.'))
        return super().form_valid(form)


class RelationshipDeleteView(StaffRequiredMixin, DeleteView):
    """Delete a relationship."""

    model = PartyRelationship
    template_name = 'parties/relationship_confirm_delete.html'
    success_url = reverse_lazy('django_parties:relationships_list')
    context_object_name = 'relationship'

    def form_valid(self, form):
        messages.success(self.request, _('Relationship deleted successfully.'))
        return super().form_valid(form)
