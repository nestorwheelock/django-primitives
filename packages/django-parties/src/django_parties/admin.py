"""Admin configuration for Django Parties."""
from django.contrib import admin
from django.utils.html import format_html

from django_parties.models import (
    Person,
    Organization,
    Group,
    PartyRelationship,
    Address,
    Phone,
    Email,
    Demographics,
    PartyURL,
)


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ['address_type', 'is_primary', 'line1', 'city', 'state', 'postal_code', 'country']


class PhoneInline(admin.TabularInline):
    model = Phone
    extra = 0
    fields = ['phone_type', 'is_primary', 'country_code', 'number', 'can_receive_sms', 'can_receive_whatsapp']


class EmailInline(admin.TabularInline):
    model = Email
    extra = 0
    fields = ['email_type', 'is_primary', 'email', 'is_verified', 'receives_marketing']


class PartyURLInline(admin.TabularInline):
    model = PartyURL
    extra = 0
    fields = ['url_type', 'is_primary', 'url', 'username', 'is_public']


class RelationshipFromInline(admin.TabularInline):
    model = PartyRelationship
    fk_name = 'from_person'
    extra = 0
    fields = ['relationship_type', 'to_person', 'to_organization', 'to_group', 'title', 'is_primary', 'is_active']
    verbose_name = "Relationship (from this person)"
    verbose_name_plural = "Relationships (from this person)"


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'phone', 'age_display', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['first_name', 'last_name', 'display_name', 'email', 'phone']
    ordering = ['last_name', 'first_name']
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('first_name', 'middle_name', 'last_name', 'preferred_name', 'display_name')
        }),
        ('Status', {
            'fields': ('is_active', 'date_of_birth', 'date_of_death')
        }),
        ('Primary Contact', {
            'fields': ('email', 'phone', 'phone_is_mobile', 'phone_has_whatsapp', 'phone_can_receive_sms')
        }),
        ('Primary Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country'),
            'classes': ['collapse']
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ['collapse']
        }),
    )

    inlines = [AddressInline, PhoneInline, EmailInline, PartyURLInline, RelationshipFromInline]

    @admin.display(description='Name')
    def full_name(self, obj):
        return obj.get_full_name()

    @admin.display(description='Age')
    def age_display(self, obj):
        age = obj.age
        if age is not None:
            return f'{age} years'
        return '-'


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'org_type', 'website', 'tax_id', 'is_active', 'created_at']
    list_filter = ['org_type', 'is_active', 'created_at']
    search_fields = ['name', 'legal_name', 'tax_id']
    ordering = ['name']

    fieldsets = (
        (None, {
            'fields': ('name', 'legal_name', 'org_type', 'is_active')
        }),
        ('Business Info', {
            'fields': ('tax_id', 'website')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country'),
            'classes': ['collapse']
        }),
    )

    inlines = [AddressInline, PhoneInline, EmailInline, PartyURLInline]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'group_type', 'primary_contact', 'is_active', 'created_at']
    list_filter = ['group_type', 'is_active']
    search_fields = ['name']
    raw_id_fields = ['primary_contact']
    ordering = ['name']

    inlines = [AddressInline, PhoneInline, EmailInline]


@admin.register(PartyRelationship)
class PartyRelationshipAdmin(admin.ModelAdmin):
    list_display = [
        '__str__', 'relationship_type', 'title', 'is_primary', 'is_active', 'created_at'
    ]
    list_filter = ['relationship_type', 'is_active', 'is_primary']
    search_fields = [
        'from_person__first_name', 'from_person__last_name',
        'to_person__first_name', 'to_person__last_name',
        'from_organization__name', 'to_organization__name',
        'to_group__name', 'title'
    ]
    raw_id_fields = ['from_person', 'from_organization', 'to_person', 'to_organization', 'to_group']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('From Party', {
            'fields': ('from_person', 'from_organization')
        }),
        ('To Party', {
            'fields': ('to_person', 'to_organization', 'to_group')
        }),
        ('Relationship', {
            'fields': ('relationship_type', 'title', 'is_primary', 'is_active')
        }),
        ('Contract', {
            'fields': ('contract_start', 'contract_end', 'contract_signed'),
            'classes': ['collapse']
        }),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'address_type', 'party_display', 'is_primary', 'is_verified']
    list_filter = ['address_type', 'is_primary', 'is_verified', 'country']
    search_fields = ['line1', 'city', 'state', 'postal_code']
    raw_id_fields = ['person', 'organization', 'group']

    @admin.display(description='Party')
    def party_display(self, obj):
        return obj.party


@admin.register(Phone)
class PhoneAdmin(admin.ModelAdmin):
    list_display = ['full_number', 'phone_type', 'party_display', 'is_primary', 'can_receive_sms', 'can_receive_whatsapp']
    list_filter = ['phone_type', 'is_primary', 'can_receive_sms', 'can_receive_whatsapp']
    search_fields = ['number']
    raw_id_fields = ['person', 'organization', 'group']

    @admin.display(description='Party')
    def party_display(self, obj):
        return obj.party


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ['email', 'email_type', 'party_display', 'is_primary', 'is_verified', 'receives_marketing']
    list_filter = ['email_type', 'is_primary', 'is_verified', 'receives_marketing']
    search_fields = ['email']
    raw_id_fields = ['person', 'organization', 'group']

    @admin.display(description='Party')
    def party_display(self, obj):
        return obj.party


@admin.register(Demographics)
class DemographicsAdmin(admin.ModelAdmin):
    list_display = ['person', 'gender', 'marital_status', 'nationality', 'preferred_language']
    list_filter = ['gender', 'marital_status', 'preferred_language']
    search_fields = ['person__first_name', 'person__last_name']
    raw_id_fields = ['person']


@admin.register(PartyURL)
class PartyURLAdmin(admin.ModelAdmin):
    list_display = ['url', 'url_type', 'party_display', 'is_primary', 'is_verified', 'is_public']
    list_filter = ['url_type', 'is_primary', 'is_verified', 'is_public']
    search_fields = ['url', 'username']
    raw_id_fields = ['person', 'organization', 'group']

    @admin.display(description='Party')
    def party_display(self, obj):
        return obj.party
