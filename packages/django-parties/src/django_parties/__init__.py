"""
Django Parties - Party Pattern implementation for Django.

This package provides the Party Pattern - an enterprise architecture pattern
for modeling entities (Person, Organization, Group) and their relationships.

Key Concepts:
- Party: Abstract base for any entity that can own things and do business
- Person: A human being (separate from User/authentication)
- Organization: Companies, clinics, suppliers, schools
- Group: Households, families, partnerships
- PartyRelationship: Links between parties (employee, vendor, member, etc.)

Contact Models:
- Address: Physical/mailing addresses
- Phone: Phone numbers with messaging capabilities
- Email: Email addresses with marketing preferences
- PartyURL: Websites and social media profiles

Key Design Principle:
- Person is the real-world human identity (Party type)
- User (in your auth app) is a login account that links to a Person
- One Person can have multiple User accounts (different auth methods)
- A Person can exist without any User account (contacts, leads)
- A User can exist without a Person (API/service accounts)

Usage:
    # settings.py
    INSTALLED_APPS = [
        ...
        'django_parties',
    ]

    # In your code
    from django_parties.models import Person, Organization, Group
    from django_parties.selectors import get_person_by_id, search_people
"""

__version__ = "0.1.0"
