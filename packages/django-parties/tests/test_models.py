"""Comprehensive tests for django-parties models."""
import pytest
import uuid
from datetime import date, timedelta


@pytest.mark.django_db
class TestPersonModel:
    """Tests for Person model."""

    def test_create_person(self):
        """Can create a Person with basic fields."""
        from django_parties.models import Person
        person = Person.objects.create(
            first_name='John',
            last_name='Doe',
        )
        assert person.pk is not None
        assert isinstance(person.pk, uuid.UUID)
        assert person.first_name == 'John'
        assert person.last_name == 'Doe'

    def test_person_has_uuid_pk(self):
        """Person should use UUID as primary key."""
        from django_parties.models import Person
        person = Person.objects.create(first_name='Jane')
        assert isinstance(person.id, uuid.UUID)

    def test_person_has_timestamps(self):
        """Person should have created_at and updated_at."""
        from django_parties.models import Person
        person = Person.objects.create(first_name='Bob')
        assert person.created_at is not None
        assert person.updated_at is not None

    def test_person_get_full_name(self):
        """get_full_name returns full name with all parts."""
        from django_parties.models import Person
        person = Person(
            first_name='John',
            middle_name='Robert',
            last_name='Doe',
        )
        assert person.get_full_name() == 'John Robert Doe'

    def test_person_get_full_name_no_middle(self):
        """get_full_name works without middle name."""
        from django_parties.models import Person
        person = Person(first_name='John', last_name='Doe')
        assert person.get_full_name() == 'John Doe'

    def test_person_get_short_name_preferred(self):
        """get_short_name returns preferred_name if set."""
        from django_parties.models import Person
        person = Person(first_name='Jonathan', preferred_name='Jon')
        assert person.get_short_name() == 'Jon'

    def test_person_get_short_name_fallback(self):
        """get_short_name falls back to first_name."""
        from django_parties.models import Person
        person = Person(first_name='Jonathan')
        assert person.get_short_name() == 'Jonathan'

    def test_person_age_property(self):
        """age property calculates from date_of_birth."""
        from django_parties.models import Person
        today = date.today()
        dob = date(today.year - 30, today.month, today.day)
        person = Person(first_name='Test', date_of_birth=dob)
        assert person.age == 30

    def test_person_age_none_if_no_dob(self):
        """age returns None if date_of_birth not set."""
        from django_parties.models import Person
        person = Person(first_name='Test')
        assert person.age is None

    def test_person_display_name_auto_generated(self):
        """display_name auto-generates from name on save."""
        from django_parties.models import Person
        person = Person.objects.create(
            first_name='John',
            last_name='Doe',
        )
        assert person.display_name == 'John Doe'

    def test_person_str_method(self):
        """__str__ returns full name."""
        from django_parties.models import Person
        person = Person(first_name='John', last_name='Doe')
        assert str(person) == 'John Doe'

    def test_person_soft_delete(self):
        """Person soft delete sets deleted_at."""
        from django_parties.models import Person
        person = Person.objects.create(first_name='Delete')
        person.delete()

        assert person.is_deleted is True
        assert Person.objects.filter(pk=person.pk).exists() is False
        assert Person.all_objects.filter(pk=person.pk).exists() is True

    def test_person_restore(self):
        """Person can be restored after soft delete."""
        from django_parties.models import Person
        person = Person.objects.create(first_name='Restore')
        person.delete()
        person.restore()

        assert person.is_deleted is False
        assert Person.objects.filter(pk=person.pk).exists() is True


@pytest.mark.django_db
class TestOrganizationModel:
    """Tests for Organization model."""

    def test_create_organization(self):
        """Can create an Organization."""
        from django_parties.models import Organization
        org = Organization.objects.create(
            name='Acme Corp',
            org_type='company',
        )
        assert org.pk is not None
        assert isinstance(org.pk, uuid.UUID)

    def test_organization_types(self):
        """Organization supports various types."""
        from django_parties.models import Organization
        types = ['company', 'clinic', 'hospital', 'supplier']
        for org_type in types:
            org = Organization.objects.create(
                name=f'Test {org_type}',
                org_type=org_type,
            )
            assert org.org_type == org_type

    def test_organization_str_method(self):
        """__str__ returns organization name."""
        from django_parties.models import Organization
        org = Organization(name='Test Org')
        assert str(org) == 'Test Org'

    def test_organization_soft_delete(self):
        """Organization soft delete works."""
        from django_parties.models import Organization
        org = Organization.objects.create(name='Delete Me')
        org.delete()

        assert org.is_deleted is True
        assert Organization.objects.filter(pk=org.pk).exists() is False
        assert Organization.all_objects.filter(pk=org.pk).exists() is True


@pytest.mark.django_db
class TestGroupModel:
    """Tests for Group model."""

    def test_create_group(self):
        """Can create a Group."""
        from django_parties.models import Group
        group = Group.objects.create(
            name='Smith Family',
            group_type='household',
        )
        assert group.pk is not None
        assert isinstance(group.pk, uuid.UUID)

    def test_group_types(self):
        """Group supports various types."""
        from django_parties.models import Group
        types = ['household', 'family', 'partnership', 'team']
        for group_type in types:
            group = Group.objects.create(
                name=f'Test {group_type}',
                group_type=group_type,
            )
            assert group.group_type == group_type

    def test_group_primary_contact(self):
        """Group can have a primary contact Person."""
        from django_parties.models import Group, Person
        person = Person.objects.create(first_name='John', last_name='Smith')
        group = Group.objects.create(
            name='Smith Household',
            primary_contact=person,
        )
        assert group.primary_contact == person

    def test_group_str_method(self):
        """__str__ returns group name."""
        from django_parties.models import Group
        group = Group(name='Test Group')
        assert str(group) == 'Test Group'


@pytest.mark.django_db
class TestPartyRelationshipValidation:
    """Tests for PartyRelationship.clean() validation (model-level invariants)."""

    def test_no_from_party_fails(self):
        """Relationship without any from_party raises ValidationError."""
        from django.core.exceptions import ValidationError
        from django_parties.models import Person, PartyRelationship

        person = Person.objects.create(first_name='Target')
        rel = PartyRelationship(
            to_person=person,
            relationship_type='emergency_contact',
        )

        with pytest.raises(ValidationError) as exc_info:
            rel.full_clean()

        assert 'from_person' in exc_info.value.message_dict

    def test_both_from_parties_fails(self):
        """Relationship with both from_person and from_organization raises ValidationError."""
        from django.core.exceptions import ValidationError
        from django_parties.models import Person, Organization, PartyRelationship

        person = Person.objects.create(first_name='From Person')
        org = Organization.objects.create(name='From Org')
        target = Person.objects.create(first_name='Target')

        rel = PartyRelationship(
            from_person=person,
            from_organization=org,
            to_person=target,
            relationship_type='contact',
        )

        with pytest.raises(ValidationError) as exc_info:
            rel.full_clean()

        assert 'from_person' in exc_info.value.message_dict

    def test_no_to_party_fails(self):
        """Relationship without any to_party raises ValidationError."""
        from django.core.exceptions import ValidationError
        from django_parties.models import Person, PartyRelationship

        person = Person.objects.create(first_name='From')
        rel = PartyRelationship(
            from_person=person,
            relationship_type='employee',
        )

        with pytest.raises(ValidationError) as exc_info:
            rel.full_clean()

        assert 'to_person' in exc_info.value.message_dict

    def test_multiple_to_parties_fails(self):
        """Relationship with multiple to_party fields raises ValidationError."""
        from django.core.exceptions import ValidationError
        from django_parties.models import Person, Organization, PartyRelationship

        from_person = Person.objects.create(first_name='From')
        to_person = Person.objects.create(first_name='To Person')
        to_org = Organization.objects.create(name='To Org')

        rel = PartyRelationship(
            from_person=from_person,
            to_person=to_person,
            to_organization=to_org,
            relationship_type='contact',
        )

        with pytest.raises(ValidationError) as exc_info:
            rel.full_clean()

        assert 'to_person' in exc_info.value.message_dict

    def test_valid_person_to_person_passes(self):
        """Valid person -> person relationship passes validation."""
        from django_parties.models import Person, PartyRelationship

        person1 = Person.objects.create(first_name='From')
        person2 = Person.objects.create(first_name='To')

        rel = PartyRelationship(
            from_person=person1,
            to_person=person2,
            relationship_type='emergency_contact',
        )

        # Should not raise
        rel.full_clean()
        rel.save()
        assert rel.pk is not None

    def test_valid_person_to_org_passes(self):
        """Valid person -> organization relationship passes validation."""
        from django_parties.models import Person, Organization, PartyRelationship

        person = Person.objects.create(first_name='Employee')
        org = Organization.objects.create(name='Company')

        rel = PartyRelationship(
            from_person=person,
            to_organization=org,
            relationship_type='employee',
        )

        # Should not raise
        rel.full_clean()
        rel.save()
        assert rel.pk is not None

    def test_valid_org_to_org_passes(self):
        """Valid organization -> organization relationship passes validation."""
        from django_parties.models import Organization, PartyRelationship

        org1 = Organization.objects.create(name='Vendor')
        org2 = Organization.objects.create(name='Client')

        rel = PartyRelationship(
            from_organization=org1,
            to_organization=org2,
            relationship_type='vendor',
        )

        # Should not raise
        rel.full_clean()
        rel.save()
        assert rel.pk is not None


@pytest.mark.django_db
class TestPartyRelationshipModel:
    """Tests for PartyRelationship model."""

    def test_person_to_organization_relationship(self):
        """Can create Person -> Organization relationship."""
        from django_parties.models import Person, Organization, PartyRelationship
        person = Person.objects.create(first_name='John')
        org = Organization.objects.create(name='Acme Corp')

        rel = PartyRelationship.objects.create(
            from_person=person,
            to_organization=org,
            relationship_type='employee',
            title='Software Engineer',
        )

        assert rel.from_party == person
        assert rel.to_party == org
        assert rel.relationship_type == 'employee'

    def test_person_to_person_relationship(self):
        """Can create Person -> Person relationship."""
        from django_parties.models import Person, PartyRelationship
        person1 = Person.objects.create(first_name='John')
        person2 = Person.objects.create(first_name='Jane')

        rel = PartyRelationship.objects.create(
            from_person=person1,
            to_person=person2,
            relationship_type='emergency_contact',
        )

        assert rel.from_party == person1
        assert rel.to_party == person2

    def test_person_to_group_relationship(self):
        """Can create Person -> Group relationship."""
        from django_parties.models import Person, Group, PartyRelationship
        person = Person.objects.create(first_name='John')
        group = Group.objects.create(name='Smith Family')

        rel = PartyRelationship.objects.create(
            from_person=person,
            to_group=group,
            relationship_type='head',
        )

        assert rel.from_party == person
        assert rel.to_party == group

    def test_relationship_str_method(self):
        """__str__ shows from -> to (type)."""
        from django_parties.models import Person, Organization, PartyRelationship
        person = Person.objects.create(first_name='John', last_name='Doe')
        org = Organization.objects.create(name='Acme')

        rel = PartyRelationship.objects.create(
            from_person=person,
            to_organization=org,
            relationship_type='employee',
        )

        assert 'John Doe' in str(rel)
        assert 'Acme' in str(rel)
        assert 'Employee' in str(rel)


@pytest.mark.django_db
class TestAddressExactlyOnePartyConstraint:
    """Tests for Address exactly-one-party FK constraint.

    Each Address must belong to exactly one party (person, organization, or group).
    This is enforced by a CheckConstraint at the DB level.
    """

    def test_cannot_create_address_with_no_party(self):
        """Cannot create Address without any party FK."""
        from django.db import IntegrityError
        from django_parties.models import Address

        with pytest.raises(IntegrityError):
            Address.objects.create(
                address_type='home',
                line1='123 Main St',
                city='Anytown',
            )

    def test_cannot_create_address_with_multiple_parties(self):
        """Cannot create Address with multiple party FKs."""
        from django.db import IntegrityError
        from django_parties.models import Person, Organization, Address

        person = Person.objects.create(first_name='John')
        org = Organization.objects.create(name='Acme')

        with pytest.raises(IntegrityError):
            Address.objects.create(
                person=person,
                organization=org,
                address_type='home',
                line1='123 Main St',
                city='Anytown',
            )

    def test_can_create_address_for_person_only(self):
        """Can create Address with exactly one party (person)."""
        from django_parties.models import Person, Address

        person = Person.objects.create(first_name='John')
        address = Address.objects.create(
            person=person,
            line1='123 Main St',
            city='Anytown',
        )
        assert address.pk is not None
        assert address.party == person


@pytest.mark.django_db
class TestPhoneExactlyOnePartyConstraint:
    """Tests for Phone exactly-one-party FK constraint."""

    def test_cannot_create_phone_with_no_party(self):
        """Cannot create Phone without any party FK."""
        from django.db import IntegrityError
        from django_parties.models import Phone

        with pytest.raises(IntegrityError):
            Phone.objects.create(
                phone_type='mobile',
                number='555-1234',
            )

    def test_cannot_create_phone_with_multiple_parties(self):
        """Cannot create Phone with multiple party FKs."""
        from django.db import IntegrityError
        from django_parties.models import Person, Organization, Phone

        person = Person.objects.create(first_name='John')
        org = Organization.objects.create(name='Acme')

        with pytest.raises(IntegrityError):
            Phone.objects.create(
                person=person,
                organization=org,
                phone_type='mobile',
                number='555-1234',
            )


@pytest.mark.django_db
class TestEmailExactlyOnePartyConstraint:
    """Tests for Email exactly-one-party FK constraint."""

    def test_cannot_create_email_with_no_party(self):
        """Cannot create Email without any party FK."""
        from django.db import IntegrityError
        from django_parties.models import Email

        with pytest.raises(IntegrityError):
            Email.objects.create(
                email_type='personal',
                email='test@example.com',
            )

    def test_cannot_create_email_with_multiple_parties(self):
        """Cannot create Email with multiple party FKs."""
        from django.db import IntegrityError
        from django_parties.models import Person, Organization, Email

        person = Person.objects.create(first_name='John')
        org = Organization.objects.create(name='Acme')

        with pytest.raises(IntegrityError):
            Email.objects.create(
                person=person,
                organization=org,
                email_type='personal',
                email='test@example.com',
            )


@pytest.mark.django_db
class TestPartyURLExactlyOnePartyConstraint:
    """Tests for PartyURL exactly-one-party FK constraint."""

    def test_cannot_create_url_with_no_party(self):
        """Cannot create PartyURL without any party FK."""
        from django.db import IntegrityError
        from django_parties.models import PartyURL

        with pytest.raises(IntegrityError):
            PartyURL.objects.create(
                url_type='website',
                url='https://example.com',
            )

    def test_cannot_create_url_with_multiple_parties(self):
        """Cannot create PartyURL with multiple party FKs."""
        from django.db import IntegrityError
        from django_parties.models import Person, Organization, PartyURL

        person = Person.objects.create(first_name='John')
        org = Organization.objects.create(name='Acme')

        with pytest.raises(IntegrityError):
            PartyURL.objects.create(
                person=person,
                organization=org,
                url_type='website',
                url='https://example.com',
            )


@pytest.mark.django_db
class TestAddressModel:
    """Tests for Address model."""

    def test_create_address_for_person(self):
        """Can create Address for Person."""
        from django_parties.models import Person, Address
        person = Person.objects.create(first_name='John')
        address = Address.objects.create(
            person=person,
            address_type='home',
            line1='123 Main St',
            city='Anytown',
            state='CA',
            postal_code='12345',
        )

        assert address.party == person
        assert address.line1 == '123 Main St'

    def test_create_address_for_organization(self):
        """Can create Address for Organization."""
        from django_parties.models import Organization, Address
        org = Organization.objects.create(name='Acme')
        address = Address.objects.create(
            organization=org,
            address_type='headquarters',
            line1='456 Corp Ave',
            city='Business City',
        )

        assert address.party == org

    def test_address_full_address_property(self):
        """full_address returns formatted address."""
        from django_parties.models import Person, Address
        person = Person.objects.create(first_name='Test')
        address = Address.objects.create(
            person=person,
            line1='123 Main St',
            line2='Apt 4',
            city='Anytown',
            state='CA',
            postal_code='12345',
            country='USA',
        )

        full = address.full_address
        assert '123 Main St' in full
        assert 'Apt 4' in full
        assert 'Anytown' in full
        assert 'USA' in full


@pytest.mark.django_db
class TestPhoneModel:
    """Tests for Phone model."""

    def test_create_phone_for_person(self):
        """Can create Phone for Person."""
        from django_parties.models import Person, Phone
        person = Person.objects.create(first_name='John')
        phone = Phone.objects.create(
            person=person,
            phone_type='mobile',
            country_code='+1',
            number='555-1234',
        )

        assert phone.party == person
        assert phone.full_number == '+1 555-1234'

    def test_phone_full_number_with_extension(self):
        """full_number includes extension."""
        from django_parties.models import Person, Phone
        person = Person.objects.create(first_name='Test')
        phone = Phone.objects.create(
            person=person,
            number='555-1234',
            extension='101',
        )

        assert 'ext. 101' in phone.full_number


@pytest.mark.django_db
class TestEmailModel:
    """Tests for Email model."""

    def test_create_email_for_person(self):
        """Can create Email for Person."""
        from django_parties.models import Person, Email
        person = Person.objects.create(first_name='John')
        email = Email.objects.create(
            person=person,
            email_type='personal',
            email='john@example.com',
        )

        assert email.party == person
        assert str(email) == 'john@example.com'


@pytest.mark.django_db
class TestDemographicsModel:
    """Tests for Demographics model."""

    def test_create_demographics(self):
        """Can create Demographics for Person."""
        from django_parties.models import Person, Demographics
        person = Person.objects.create(first_name='John')
        demo = Demographics.objects.create(
            person=person,
            gender='male',
            nationality='American',
            preferred_language='en',
        )

        assert demo.person == person
        assert demo.gender == 'male'

    def test_demographics_one_to_one(self):
        """Demographics is one-to-one with Person."""
        from django_parties.models import Person, Demographics
        person = Person.objects.create(first_name='Test')
        Demographics.objects.create(person=person)

        # Access through reverse relation
        person.refresh_from_db()
        assert hasattr(person, 'demographics')


@pytest.mark.django_db
class TestPartyURLModel:
    """Tests for PartyURL model."""

    def test_create_url_for_person(self):
        """Can create PartyURL for Person."""
        from django_parties.models import Person, PartyURL
        person = Person.objects.create(first_name='John')
        url = PartyURL.objects.create(
            person=person,
            url_type='linkedin',
            url='https://linkedin.com/in/johndoe',
            username='johndoe',
        )

        assert url.party == person
        assert url.icon == 'linkedin'

    def test_create_url_for_organization(self):
        """Can create PartyURL for Organization."""
        from django_parties.models import Organization, PartyURL
        org = Organization.objects.create(name='Acme')
        url = PartyURL.objects.create(
            organization=org,
            url_type='website',
            url='https://acme.com',
        )

        assert url.party == org
        assert url.icon == 'globe'


@pytest.mark.django_db
class TestAllModelsHaveSoftDelete:
    """Verify all models have soft delete functionality."""

    def test_all_models_soft_delete(self):
        """All party models should support soft delete."""
        from django_parties.models import (
            Person, Organization, Group, PartyRelationship,
            Address, Phone, Email, Demographics, PartyURL,
        )

        # Create instances
        person = Person.objects.create(first_name='Test')
        org = Organization.objects.create(name='Test Org')
        group = Group.objects.create(name='Test Group')
        rel = PartyRelationship.objects.create(
            from_person=person,
            to_organization=org,
            relationship_type='employee',
        )
        address = Address.objects.create(
            person=person, line1='123 St', city='City',
        )
        phone = Phone.objects.create(person=person, number='555-1234')
        email = Email.objects.create(person=person, email='test@test.com')
        demo = Demographics.objects.create(person=person)
        url = PartyURL.objects.create(person=person, url='https://example.com')

        # Soft delete all
        for obj in [person, org, group, rel, address, phone, email, demo, url]:
            obj.delete()
            assert obj.is_deleted is True
            assert obj.deleted_at is not None

        # All should be invisible in default manager
        assert Person.objects.count() == 0
        assert Organization.objects.count() == 0
        assert Group.objects.count() == 0

        # All should still exist in all_objects
        assert Person.all_objects.count() == 1
        assert Organization.all_objects.count() == 1
        assert Group.all_objects.count() == 1
