"""Django Parties forms.

Copyright 2025 Nestor Wheelock. All Rights Reserved.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Person, Organization, Group, PartyRelationship, Demographics


class PersonForm(forms.ModelForm):
    """Form for creating/editing a Person."""

    class Meta:
        model = Person
        fields = [
            'first_name', 'middle_name', 'last_name', 'preferred_name',
            'date_of_birth', 'email', 'phone', 'phone_is_mobile',
            'phone_has_whatsapp', 'phone_can_receive_sms', 'postal_code',
            'address_line1', 'address_line2', 'city', 'state', 'country',
            'address_is_home', 'address_is_billing', 'address_is_shipping',
            'is_active', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'phone': forms.TextInput(attrs={'placeholder': '55 1234 5678'}),
            'email': forms.EmailInput(attrs={'placeholder': 'name@example.com'}),
            'postal_code': forms.TextInput(attrs={'placeholder': '06600'}),
            'address_line1': forms.TextInput(attrs={'placeholder': 'Street address'}),
            'address_line2': forms.TextInput(attrs={'placeholder': 'Apt, suite, unit (optional)'}),
            'city': forms.TextInput(attrs={'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'placeholder': 'State/Province'}),
            'country': forms.TextInput(attrs={'placeholder': 'Country'}),
        }


class OrganizationForm(forms.ModelForm):
    """Form for creating/editing an Organization."""

    class Meta:
        model = Organization
        fields = [
            'name', 'org_type', 'website', 'tax_id', 'legal_name',
            'email', 'phone', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'is_active'
        ]
        widgets = {
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com'}),
        }


class GroupForm(forms.ModelForm):
    """Form for creating/editing a Group."""

    class Meta:
        model = Group
        fields = [
            'name', 'group_type', 'primary_contact',
            'email', 'phone', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'is_active'
        ]


class PartyRelationshipForm(forms.ModelForm):
    """Form for creating/editing a PartyRelationship.

    Note: Validation logic (exactly-one-from, exactly-one-to) is enforced
    at the model level via PartyRelationship.clean().
    """

    class Meta:
        model = PartyRelationship
        fields = [
            'from_person', 'from_organization',
            'to_person', 'to_organization', 'to_group',
            'relationship_type', 'title', 'contract_start', 'contract_end',
            'contract_signed', 'is_primary', 'is_active'
        ]
        widgets = {
            'contract_start': forms.DateInput(attrs={'type': 'date'}),
            'contract_end': forms.DateInput(attrs={'type': 'date'}),
        }


class DemographicsForm(forms.ModelForm):
    """Form for Person demographics."""

    class Meta:
        model = Demographics
        fields = [
            'gender', 'marital_status', 'nationality', 'country_of_birth',
            'ethnicity', 'preferred_language', 'education_level', 'occupation',
            'household_size', 'has_children', 'number_of_children'
        ]
        widgets = {
            'household_size': forms.NumberInput(attrs={'min': 1, 'max': 20}),
            'number_of_children': forms.NumberInput(attrs={'min': 0, 'max': 20}),
        }
