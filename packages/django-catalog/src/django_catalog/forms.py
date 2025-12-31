"""Django Catalog forms.

Copyright 2025 Nestor Wheelock. All Rights Reserved.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import CatalogItem, Basket, BasketItem, WorkItem


class CatalogItemForm(forms.ModelForm):
    """Form for creating/editing catalog items."""

    class Meta:
        model = CatalogItem
        fields = [
            'kind', 'display_name', 'display_name_es',
            'service_category', 'default_stock_action',
            'is_billable', 'active'
        ]
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Item name'}),
            'display_name_es': forms.TextInput(attrs={'placeholder': 'Nombre del artículo'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        kind = cleaned_data.get('kind')
        service_category = cleaned_data.get('service_category')
        default_stock_action = cleaned_data.get('default_stock_action')

        if kind == 'service' and not service_category:
            self.add_error('service_category', _('Service category is required for services.'))

        if kind == 'stock_item' and not default_stock_action:
            self.add_error('default_stock_action', _('Stock action is required for stock items.'))

        return cleaned_data


class BasketForm(forms.ModelForm):
    """Form for creating baskets."""

    class Meta:
        model = Basket
        fields = ['encounter']


class BasketItemForm(forms.ModelForm):
    """Form for adding items to a basket."""

    class Meta:
        model = BasketItem
        fields = ['catalog_item', 'quantity', 'stock_action_override', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'value': 1}),
        }


class WorkItemStatusForm(forms.ModelForm):
    """Form for updating work item status."""

    class Meta:
        model = WorkItem
        fields = ['status', 'status_detail', 'assigned_to', 'priority', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'priority': forms.NumberInput(attrs={'min': 0, 'max': 100}),
        }


class CatalogSearchForm(forms.Form):
    """Form for searching catalog items."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': _('Search catalog...'),
            'class': 'form-control',
        })
    )
    kind = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(CatalogItem.KIND_CHOICES),
    )
    service_category = forms.ChoiceField(
        required=False,
        choices=[('', _('All Categories'))] + list(CatalogItem.SERVICE_CATEGORY_CHOICES),
    )
    active_only = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Active only'),
    )
