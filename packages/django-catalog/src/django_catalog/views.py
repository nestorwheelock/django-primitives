"""Django Catalog views - CRUD views for catalog management.

Copyright 2025 Nestor Wheelock. All Rights Reserved.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    BasketForm,
    BasketItemForm,
    CatalogItemForm,
    CatalogSearchForm,
    WorkItemStatusForm,
)
from .models import Basket, BasketItem, CatalogItem, DispenseLog, WorkItem


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin requiring staff access."""

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# =============================================================================
# Dashboard
# =============================================================================

class CatalogDashboardView(StaffRequiredMixin, TemplateView):
    """Dashboard for catalog module with KPIs."""

    template_name = 'catalog/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Catalog item counts
        context['total_items'] = CatalogItem.objects.filter(deleted_at__isnull=True).count()
        context['active_items'] = CatalogItem.objects.filter(
            active=True, deleted_at__isnull=True
        ).count()
        context['stock_items'] = CatalogItem.objects.filter(
            kind='stock_item', active=True, deleted_at__isnull=True
        ).count()
        context['service_items'] = CatalogItem.objects.filter(
            kind='service', active=True, deleted_at__isnull=True
        ).count()

        # Basket counts
        context['draft_baskets'] = Basket.objects.filter(
            status='draft', deleted_at__isnull=True
        ).count()
        context['committed_baskets'] = Basket.objects.filter(
            status='committed', deleted_at__isnull=True
        ).count()

        # Work item counts by status
        context['pending_workitems'] = WorkItem.objects.filter(
            status='pending', deleted_at__isnull=True
        ).count()
        context['in_progress_workitems'] = WorkItem.objects.filter(
            status='in_progress', deleted_at__isnull=True
        ).count()

        # Recent items
        context['recent_catalog_items'] = CatalogItem.objects.filter(
            deleted_at__isnull=True
        ).order_by('-created_at')[:5]
        context['recent_workitems'] = WorkItem.objects.filter(
            deleted_at__isnull=True
        ).select_related('basket_item').order_by('-created_at')[:5]

        return context


# =============================================================================
# CatalogItem CRUD
# =============================================================================

class CatalogItemListView(StaffRequiredMixin, ListView):
    """List all catalog items."""

    model = CatalogItem
    template_name = 'catalog/catalogitem_list.html'
    context_object_name = 'items'
    paginate_by = 25

    def get_queryset(self):
        queryset = CatalogItem.objects.filter(deleted_at__isnull=True)

        # Apply search filters
        q = self.request.GET.get('q', '')
        if q:
            queryset = queryset.filter(
                Q(display_name__icontains=q) |
                Q(display_name_es__icontains=q)
            )

        kind = self.request.GET.get('kind', '')
        if kind:
            queryset = queryset.filter(kind=kind)

        service_category = self.request.GET.get('service_category', '')
        if service_category:
            queryset = queryset.filter(service_category=service_category)

        active_only = self.request.GET.get('active_only', 'true')
        if active_only.lower() == 'true':
            queryset = queryset.filter(active=True)

        return queryset.order_by('display_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = CatalogSearchForm(self.request.GET)
        return context


class CatalogItemDetailView(StaffRequiredMixin, DetailView):
    """View catalog item details."""

    model = CatalogItem
    template_name = 'catalog/catalogitem_detail.html'
    context_object_name = 'item'

    def get_queryset(self):
        return CatalogItem.objects.filter(deleted_at__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['basket_items'] = self.object.basket_items.select_related(
            'basket'
        ).order_by('-created_at')[:10]
        return context


class CatalogItemCreateView(StaffRequiredMixin, CreateView):
    """Create a new catalog item."""

    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'catalog/catalogitem_form.html'
    success_url = reverse_lazy('django_catalog:catalogitem_list')

    def form_valid(self, form):
        messages.success(self.request, _('Catalog item created successfully.'))
        return super().form_valid(form)


class CatalogItemUpdateView(StaffRequiredMixin, UpdateView):
    """Update an existing catalog item."""

    model = CatalogItem
    form_class = CatalogItemForm
    template_name = 'catalog/catalogitem_form.html'
    context_object_name = 'item'

    def get_queryset(self):
        return CatalogItem.objects.filter(deleted_at__isnull=True)

    def get_success_url(self):
        return reverse_lazy('django_catalog:catalogitem_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _('Catalog item updated successfully.'))
        return super().form_valid(form)


class CatalogItemDeleteView(StaffRequiredMixin, DeleteView):
    """Delete (soft-delete) a catalog item."""

    model = CatalogItem
    template_name = 'catalog/catalogitem_confirm_delete.html'
    success_url = reverse_lazy('django_catalog:catalogitem_list')
    context_object_name = 'item'

    def get_queryset(self):
        return CatalogItem.objects.filter(deleted_at__isnull=True)

    def form_valid(self, form):
        self.object.soft_delete()
        messages.success(self.request, _('Catalog item deleted successfully.'))
        return redirect(self.success_url)


# =============================================================================
# Basket Management
# =============================================================================

class BasketListView(StaffRequiredMixin, ListView):
    """List all baskets."""

    model = Basket
    template_name = 'catalog/basket_list.html'
    context_object_name = 'baskets'
    paginate_by = 25

    def get_queryset(self):
        queryset = Basket.objects.filter(deleted_at__isnull=True)

        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.select_related(
            'encounter', 'created_by', 'committed_by'
        ).annotate(
            item_count=Count('items')
        ).order_by('-created_at')


class BasketDetailView(StaffRequiredMixin, DetailView):
    """View basket details with items."""

    model = Basket
    template_name = 'catalog/basket_detail.html'
    context_object_name = 'basket'

    def get_queryset(self):
        return Basket.objects.filter(deleted_at__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related(
            'catalog_item', 'added_by'
        ).order_by('created_at')
        context['add_item_form'] = BasketItemForm()
        return context


# =============================================================================
# WorkItem Management
# =============================================================================

class WorkItemListView(StaffRequiredMixin, ListView):
    """List all work items."""

    model = WorkItem
    template_name = 'catalog/workitem_list.html'
    context_object_name = 'workitems'
    paginate_by = 25

    def get_queryset(self):
        queryset = WorkItem.objects.filter(deleted_at__isnull=True)

        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)

        board = self.request.GET.get('board', '')
        if board:
            queryset = queryset.filter(target_board=board)

        return queryset.select_related(
            'basket_item', 'encounter', 'assigned_to', 'completed_by'
        ).order_by('priority', '-created_at')


class WorkItemDetailView(StaffRequiredMixin, DetailView):
    """View work item details."""

    model = WorkItem
    template_name = 'catalog/workitem_detail.html'
    context_object_name = 'workitem'

    def get_queryset(self):
        return WorkItem.objects.filter(deleted_at__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_form'] = WorkItemStatusForm(instance=self.object)
        try:
            context['dispense_log'] = self.object.dispense_log
        except DispenseLog.DoesNotExist:
            context['dispense_log'] = None
        return context


class WorkItemUpdateView(StaffRequiredMixin, UpdateView):
    """Update work item status."""

    model = WorkItem
    form_class = WorkItemStatusForm
    template_name = 'catalog/workitem_form.html'
    context_object_name = 'workitem'

    def get_queryset(self):
        return WorkItem.objects.filter(deleted_at__isnull=True)

    def get_success_url(self):
        return reverse_lazy('django_catalog:workitem_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        workitem = form.save(commit=False)

        # Update timestamps based on status
        if workitem.status == 'in_progress' and not workitem.started_at:
            workitem.started_at = timezone.now()
        elif workitem.status == 'completed' and not workitem.completed_at:
            workitem.completed_at = timezone.now()
            workitem.completed_by = self.request.user

        workitem.save()
        messages.success(self.request, _('Work item updated successfully.'))
        return redirect(self.get_success_url())


# =============================================================================
# DispenseLog
# =============================================================================

class DispenseLogListView(StaffRequiredMixin, ListView):
    """List all dispense logs."""

    model = DispenseLog
    template_name = 'catalog/dispenselog_list.html'
    context_object_name = 'logs'
    paginate_by = 25

    def get_queryset(self):
        return DispenseLog.objects.filter(
            deleted_at__isnull=True
        ).select_related(
            'workitem', 'dispensed_by'
        ).order_by('-dispensed_at')


class DispenseLogDetailView(StaffRequiredMixin, DetailView):
    """View dispense log details."""

    model = DispenseLog
    template_name = 'catalog/dispenselog_detail.html'
    context_object_name = 'log'

    def get_queryset(self):
        return DispenseLog.objects.filter(deleted_at__isnull=True)


# =============================================================================
# API Views
# =============================================================================

@login_required
@require_GET
def catalog_items_search(request):
    """Search catalog items API.

    GET /catalog/api/items/?q=<query>&kind=<kind>&service_category=<cat>

    Returns JSON: {items: [{id, display_name, kind, service_category, ...}]}
    """
    query = request.GET.get('q', '')
    kind = request.GET.get('kind', '')
    service_category = request.GET.get('service_category', '')
    limit = min(int(request.GET.get('limit', 20)), 100)

    items = CatalogItem.objects.filter(active=True, deleted_at__isnull=True)

    if query:
        items = items.filter(
            Q(display_name__icontains=query) |
            Q(display_name_es__icontains=query)
        )

    if kind:
        items = items.filter(kind=kind)

    if service_category:
        items = items.filter(service_category=service_category)

    items = items.order_by('display_name')[:limit]

    return JsonResponse({
        'items': [
            {
                'id': item.id,
                'display_name': item.display_name,
                'display_name_es': item.display_name_es,
                'kind': item.kind,
                'kind_display': item.get_kind_display(),
                'service_category': item.service_category,
                'default_stock_action': item.default_stock_action,
                'is_billable': item.is_billable,
            }
            for item in items
        ]
    })
