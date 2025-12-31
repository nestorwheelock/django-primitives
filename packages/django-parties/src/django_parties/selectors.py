"""
Django Parties Selectors - Public read-only API for the parties app.

This module provides query functions for other apps to access party data
without directly importing django_parties.models.

Usage:
    from django_parties.selectors import get_person_by_id, get_pet_owners
"""
from typing import TYPE_CHECKING

from django.db.models import QuerySet, Q

from django_parties.models import (
    Person,
    Organization,
    Group,
    PartyRelationship,
    Address,
    Phone,
    Email,
)


# =============================================================================
# PERSON SELECTORS
# =============================================================================

def get_person_by_id(person_id: int) -> Person | None:
    """Get a person by ID, or None if not found."""
    return Person.objects.filter(id=person_id).first()


def get_person_by_email(email: str) -> Person | None:
    """Get a person by their primary email address."""
    return Person.objects.filter(email__iexact=email).first()


def get_active_people() -> QuerySet[Person]:
    """Get all active people."""
    return Person.objects.filter(is_active=True)


def search_people(query: str, limit: int = 50) -> QuerySet[Person]:
    """Search people by name, email, or phone."""
    return Person.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(display_name__icontains=query) |
        Q(email__icontains=query) |
        Q(phone__icontains=query)
    ).filter(is_active=True)[:limit]


def get_people_with_relationships(relationship_type: str) -> QuerySet[Person]:
    """Get all people who have a specific type of relationship."""
    return Person.objects.filter(
        relationships_from__relationship_type=relationship_type,
        relationships_from__is_active=True,
        is_active=True,
    ).distinct()


def get_person_count() -> int:
    """Get total count of active people."""
    return get_active_people().count()


# =============================================================================
# ORGANIZATION SELECTORS
# =============================================================================

def get_organization_by_id(org_id: int) -> Organization | None:
    """Get an organization by ID, or None if not found."""
    return Organization.objects.filter(id=org_id).first()


def get_active_organizations() -> QuerySet[Organization]:
    """Get all active organizations."""
    return Organization.objects.filter(is_active=True)


def get_organizations_by_type(org_type: str) -> QuerySet[Organization]:
    """Get organizations of a specific type."""
    return Organization.objects.filter(org_type=org_type, is_active=True)


def search_organizations(query: str, limit: int = 50) -> QuerySet[Organization]:
    """Search organizations by name, legal name, or tax ID."""
    return Organization.objects.filter(
        Q(name__icontains=query) |
        Q(legal_name__icontains=query) |
        Q(tax_id__icontains=query)
    ).filter(is_active=True)[:limit]


def get_suppliers() -> QuerySet[Organization]:
    """Get all supplier organizations."""
    return get_organizations_by_type('supplier')


def get_partner_organizations() -> QuerySet[Organization]:
    """Get all partner organizations."""
    return get_organizations_by_type('partner')


# =============================================================================
# GROUP SELECTORS
# =============================================================================

def get_group_by_id(group_id: int) -> Group | None:
    """Get a group by ID, or None if not found."""
    return Group.objects.filter(id=group_id).first()


def get_active_groups() -> QuerySet[Group]:
    """Get all active groups."""
    return Group.objects.filter(is_active=True)


def get_groups_for_person(person_id: int) -> QuerySet[Group]:
    """Get all groups that a person is a member of."""
    return Group.objects.filter(
        relationships_to__from_person_id=person_id,
        relationships_to__relationship_type__in=['member', 'head', 'spouse', 'dependent'],
        relationships_to__is_active=True,
        is_active=True,
    ).distinct()


def get_households() -> QuerySet[Group]:
    """Get all household groups."""
    return Group.objects.filter(group_type='household', is_active=True)


# =============================================================================
# PARTY RELATIONSHIP SELECTORS
# =============================================================================

def get_relationships_for_person(
    person_id: int,
    relationship_type: str | None = None,
    active_only: bool = True
) -> QuerySet[PartyRelationship]:
    """Get relationships where a person is the 'from' party."""
    qs = PartyRelationship.objects.filter(from_person_id=person_id)
    if relationship_type:
        qs = qs.filter(relationship_type=relationship_type)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.select_related('to_person', 'to_organization', 'to_group')


def get_relationships_to_person(
    person_id: int,
    relationship_type: str | None = None,
    active_only: bool = True
) -> QuerySet[PartyRelationship]:
    """Get relationships where a person is the 'to' party."""
    qs = PartyRelationship.objects.filter(to_person_id=person_id)
    if relationship_type:
        qs = qs.filter(relationship_type=relationship_type)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.select_related('from_person', 'from_organization')


def get_employees_of_organization(org_id: int) -> QuerySet[PartyRelationship]:
    """Get all employee relationships for an organization."""
    return PartyRelationship.objects.filter(
        to_organization_id=org_id,
        relationship_type='employee',
        is_active=True,
    ).select_related('from_person')


def get_organization_for_employee(person_id: int) -> Organization | None:
    """Get the organization a person is employed by (primary employment)."""
    rel = PartyRelationship.objects.filter(
        from_person_id=person_id,
        relationship_type='employee',
        is_active=True,
        is_primary=True,
    ).select_related('to_organization').first()
    return rel.to_organization if rel else None


def get_emergency_contacts(person_id: int) -> QuerySet[PartyRelationship]:
    """Get emergency contact relationships for a person."""
    return PartyRelationship.objects.filter(
        from_person_id=person_id,
        relationship_type='emergency_contact',
        is_active=True,
    ).select_related('to_person')


# =============================================================================
# ADDRESS SELECTORS
# =============================================================================

def get_addresses_for_person(person_id: int) -> QuerySet[Address]:
    """Get all addresses for a person."""
    return Address.objects.filter(person_id=person_id).order_by('-is_primary', '-created_at')


def get_primary_address_for_person(person_id: int) -> Address | None:
    """Get the primary address for a person."""
    return Address.objects.filter(person_id=person_id, is_primary=True).first()


def get_addresses_for_organization(org_id: int) -> QuerySet[Address]:
    """Get all addresses for an organization."""
    return Address.objects.filter(organization_id=org_id).order_by('-is_primary', '-created_at')


# =============================================================================
# PHONE SELECTORS
# =============================================================================

def get_phones_for_person(person_id: int) -> QuerySet[Phone]:
    """Get all phone numbers for a person."""
    return Phone.objects.filter(person_id=person_id).order_by('-is_primary', '-created_at')


def get_primary_phone_for_person(person_id: int) -> Phone | None:
    """Get the primary phone number for a person."""
    return Phone.objects.filter(person_id=person_id, is_primary=True).first()


def get_whatsapp_numbers() -> QuerySet[Phone]:
    """Get all phone numbers that can receive WhatsApp messages."""
    return Phone.objects.filter(can_receive_whatsapp=True)


# =============================================================================
# EMAIL SELECTORS
# =============================================================================

def get_emails_for_person(person_id: int) -> QuerySet[Email]:
    """Get all email addresses for a person."""
    return Email.objects.filter(person_id=person_id).order_by('-is_primary', '-created_at')


def get_primary_email_for_person(person_id: int) -> Email | None:
    """Get the primary email address for a person."""
    return Email.objects.filter(person_id=person_id, is_primary=True).first()


def get_marketing_emails() -> QuerySet[Email]:
    """Get all email addresses that receive marketing emails."""
    return Email.objects.filter(receives_marketing=True, is_verified=True)
