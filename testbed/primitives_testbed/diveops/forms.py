"""Forms for diveops staff portal."""

import json
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from django_agreements.models import Agreement
from django_catalog.models import CatalogItem
from django_parties.models import Organization, Person

from .models import (
    AgreementTemplate,
    Booking,
    CertificationLevel,
    Dive,
    DiverCertification,
    DiverEligibilityProof,
    DiverProfile,
    DiveSite,
    Excursion,
    ExcursionRequirement,
    ExcursionSeries,
    ExcursionType,
    ExcursionTypeDive,
    GuidePermitDetails,
    ProtectedArea,
    ProtectedAreaFeeSchedule,
    ProtectedAreaFeeTier,
    ProtectedAreaPermit,
    ProtectedAreaRule,
    ProtectedAreaZone,
    RecurrenceRule,
    SitePriceAdjustment,
)

# Backwards compatibility aliases


class DiverForm(forms.Form):
    """Form to create or edit a diver (Person + DiverProfile + DiverCertification).

    Combines Person fields (name, email) with DiverProfile fields (experience)
    and creates a DiverCertification record with optional proof document upload.

    Uses the new normalized certification model (CertificationLevel) instead of
    legacy fields on DiverProfile.
    """

    # Person fields
    first_name = forms.CharField(
        max_length=100,
        label="First Name",
    )
    last_name = forms.CharField(
        max_length=100,
        label="Last Name",
    )
    email = forms.EmailField(
        label="Email",
    )
    date_of_birth = forms.DateField(
        required=False,
        label="Date of Birth",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    preferred_name = forms.CharField(
        required=False,
        max_length=150,
        label="Preferred Name",
        help_text="What this person prefers to be called",
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        label="Phone Number",
    )
    phone_is_mobile = forms.BooleanField(
        required=False,
        initial=True,
        label="Mobile Phone",
    )
    phone_has_whatsapp = forms.BooleanField(
        required=False,
        initial=False,
        label="Has WhatsApp",
    )
    phone_can_receive_sms = forms.BooleanField(
        required=False,
        initial=True,
        label="Can Receive SMS",
    )

    # Address fields
    address_line1 = forms.CharField(
        required=False,
        max_length=255,
        label="Address",
    )
    address_line2 = forms.CharField(
        required=False,
        max_length=255,
        label="Address Line 2",
    )
    city = forms.CharField(
        required=False,
        max_length=100,
        label="City",
    )
    state = forms.CharField(
        required=False,
        max_length=100,
        label="State/Province",
    )
    postal_code = forms.CharField(
        required=False,
        max_length=20,
        label="Postal Code",
    )
    country = forms.CharField(
        required=False,
        max_length=100,
        label="Country",
    )

    # Certification fields (using new CertificationLevel model)
    certification_agency = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type="certification_agency").order_by("name"),
        label="Certification Agency",
        required=False,
        empty_label="Select an agency...",
    )
    certification_level = forms.ModelChoiceField(
        queryset=CertificationLevel.objects.filter(is_active=True).select_related("agency").order_by("rank"),
        label="Certification Level",
        required=False,
        empty_label="Select a level...",
    )
    card_number = forms.CharField(
        max_length=100,
        label="Card Number",
        required=False,
    )
    issued_on = forms.DateField(
        label="Issue Date",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    expires_on = forms.DateField(
        label="Expiration Date",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        help_text="Leave blank if certification doesn't expire",
    )
    proof_file = forms.FileField(
        required=False,
        label="Proof Document",
        help_text="Upload certification card photo/scan (optional)",
        widget=forms.FileInput(attrs={"accept": "image/*,application/pdf"}),
    )

    # Experience fields
    total_dives = forms.IntegerField(
        min_value=0,
        initial=0,
        label="Total Dives",
    )

    # Medical fields (optional)
    medical_clearance_date = forms.DateField(
        required=False,
        label="Medical Clearance Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    medical_clearance_valid_until = forms.DateField(
        required=False,
        label="Medical Valid Until",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    # Body Measurements / Gear Sizing
    weight_kg = forms.DecimalField(
        required=False,
        label="Weight (kg)",
        max_digits=5,
        decimal_places=1,
    )
    height_cm = forms.IntegerField(
        required=False,
        label="Height (cm)",
        min_value=0,
        max_value=300,
    )
    wetsuit_size = forms.CharField(
        required=False,
        label="Wetsuit Size",
        max_length=10,
    )
    bcd_size = forms.CharField(
        required=False,
        label="BCD Size",
        max_length=10,
    )
    fin_size = forms.CharField(
        required=False,
        label="Fin Size",
        max_length=20,
    )
    mask_fit = forms.CharField(
        required=False,
        label="Mask Fit",
        max_length=50,
    )
    glove_size = forms.CharField(
        required=False,
        label="Glove Size",
        max_length=10,
    )
    weight_required_kg = forms.DecimalField(
        required=False,
        label="Weight Needed (kg)",
        max_digits=4,
        decimal_places=1,
        help_text="Weight needed for neutral buoyancy",
    )
    gear_notes = forms.CharField(
        required=False,
        label="Gear Notes",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    # Equipment Ownership
    EQUIPMENT_OWNERSHIP_CHOICES = [
        ("none", "None - Rents All"),
        ("partial", "Partial - Own Some Gear"),
        ("full", "Full - Owns All Essential Gear"),
    ]
    equipment_ownership = forms.ChoiceField(
        choices=EQUIPMENT_OWNERSHIP_CHOICES,
        initial="none",
        label="Equipment Ownership",
    )

    # Diver Type
    DIVER_TYPE_CHOICES = [
        ("identity", "Diver (Identity)"),
        ("activity", "Does Diving (Activity)"),
    ]
    diver_type = forms.ChoiceField(
        choices=DIVER_TYPE_CHOICES,
        initial="activity",
        label="Diver Type",
        help_text="Is diving their identity or just an activity?",
    )

    def __init__(self, *args, instance=None, is_edit=False, **kwargs):
        """Initialize form, optionally with existing DiverProfile.

        Args:
            instance: Existing DiverProfile for editing
            is_edit: If True, remove certification fields (use separate form)
        """
        self.instance = instance
        self.is_edit = is_edit
        super().__init__(*args, **kwargs)

        # Remove certification fields when editing (use Add Certification page instead)
        if is_edit:
            del self.fields["certification_agency"]
            del self.fields["certification_level"]
            del self.fields["card_number"]
            del self.fields["issued_on"]
            del self.fields["expires_on"]
            del self.fields["proof_file"]

        # Pre-populate fields if editing existing diver
        if instance:
            person = instance.person
            self.fields["first_name"].initial = person.first_name
            self.fields["last_name"].initial = person.last_name
            self.fields["email"].initial = person.email
            self.fields["date_of_birth"].initial = person.date_of_birth
            self.fields["preferred_name"].initial = person.preferred_name
            self.fields["phone"].initial = person.phone
            self.fields["phone_is_mobile"].initial = person.phone_is_mobile
            self.fields["phone_has_whatsapp"].initial = person.phone_has_whatsapp
            self.fields["phone_can_receive_sms"].initial = person.phone_can_receive_sms
            self.fields["address_line1"].initial = person.address_line1
            self.fields["address_line2"].initial = person.address_line2
            self.fields["city"].initial = person.city
            self.fields["state"].initial = person.state
            self.fields["postal_code"].initial = person.postal_code
            self.fields["country"].initial = person.country
            self.fields["total_dives"].initial = instance.total_dives
            self.fields["medical_clearance_date"].initial = instance.medical_clearance_date
            self.fields["medical_clearance_valid_until"].initial = instance.medical_clearance_valid_until

            # Body measurements / gear sizing
            self.fields["weight_kg"].initial = instance.weight_kg
            self.fields["height_cm"].initial = instance.height_cm
            self.fields["wetsuit_size"].initial = instance.wetsuit_size
            self.fields["bcd_size"].initial = instance.bcd_size
            self.fields["fin_size"].initial = instance.fin_size
            self.fields["mask_fit"].initial = instance.mask_fit
            self.fields["glove_size"].initial = instance.glove_size
            self.fields["weight_required_kg"].initial = instance.weight_required_kg
            self.fields["gear_notes"].initial = instance.gear_notes
            self.fields["equipment_ownership"].initial = instance.equipment_ownership
            self.fields["diver_type"].initial = instance.diver_type

            # Only pre-populate certification fields if not in edit mode
            if not is_edit:
                highest_cert = instance.certifications.filter(
                    deleted_at__isnull=True
                ).order_by("-level__rank").first()
                if highest_cert:
                    self.fields["certification_agency"].initial = highest_cert.level.agency
                    self.fields["certification_level"].initial = highest_cert.level
                    self.fields["card_number"].initial = highest_cert.card_number
                    self.fields["issued_on"].initial = highest_cert.issued_on
                    self.fields["expires_on"].initial = highest_cert.expires_on

    def clean_email(self):
        """Validate email is unique (unless editing same person)."""
        email = self.cleaned_data["email"]

        # Check for existing person with this email
        existing = Person.objects.filter(email=email).first()

        if existing:
            # If editing, allow keeping the same email
            if self.instance and self.instance.person.pk == existing.pk:
                return email
            # Otherwise it's a duplicate
            raise forms.ValidationError("A person with this email already exists.")

        return email

    def clean(self):
        """Validate certification dates."""
        cleaned_data = super().clean()
        issued_on = cleaned_data.get("issued_on")
        expires_on = cleaned_data.get("expires_on")

        if issued_on and expires_on and expires_on <= issued_on:
            raise ValidationError({
                "expires_on": "Expiration date must be after issue date."
            })

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Save Person, DiverProfile, and optionally DiverCertification.

        Delegates to service layer for all writes. Services handle audit events.

        Args:
            actor: User performing the action (passed to services)

        Returns:
            DiverProfile instance
        """
        from .services import add_certification, create_diver, update_diver

        data = self.cleaned_data

        if self.instance:
            # Update existing diver via service
            diver = update_diver(
                diver=self.instance,
                updated_by=actor,
                # Person fields
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                date_of_birth=data.get("date_of_birth"),
                preferred_name=data.get("preferred_name", ""),
                phone=data.get("phone", ""),
                phone_is_mobile=data.get("phone_is_mobile", True),
                phone_has_whatsapp=data.get("phone_has_whatsapp", False),
                phone_can_receive_sms=data.get("phone_can_receive_sms", True),
                address_line1=data.get("address_line1", ""),
                address_line2=data.get("address_line2", ""),
                city=data.get("city", ""),
                state=data.get("state", ""),
                postal_code=data.get("postal_code", ""),
                country=data.get("country", ""),
                # DiverProfile fields
                total_dives=data["total_dives"],
                medical_clearance_date=data.get("medical_clearance_date"),
                medical_clearance_valid_until=data.get("medical_clearance_valid_until"),
                # Body measurements / gear sizing
                weight_kg=data.get("weight_kg"),
                height_cm=data.get("height_cm"),
                wetsuit_size=data.get("wetsuit_size", ""),
                bcd_size=data.get("bcd_size", ""),
                fin_size=data.get("fin_size", ""),
                mask_fit=data.get("mask_fit", ""),
                glove_size=data.get("glove_size", ""),
                weight_required_kg=data.get("weight_required_kg"),
                gear_notes=data.get("gear_notes", ""),
                equipment_ownership=data.get("equipment_ownership", "none"),
                diver_type=data.get("diver_type", "activity"),
            )
        else:
            # Create new diver via service
            diver = create_diver(
                # Person fields
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                date_of_birth=data.get("date_of_birth"),
                preferred_name=data.get("preferred_name", ""),
                phone=data.get("phone", ""),
                phone_is_mobile=data.get("phone_is_mobile", True),
                phone_has_whatsapp=data.get("phone_has_whatsapp", False),
                phone_can_receive_sms=data.get("phone_can_receive_sms", True),
                address_line1=data.get("address_line1", ""),
                address_line2=data.get("address_line2", ""),
                city=data.get("city", ""),
                state=data.get("state", ""),
                postal_code=data.get("postal_code", ""),
                country=data.get("country", ""),
                # DiverProfile fields
                total_dives=data["total_dives"],
                created_by=actor,
                medical_clearance_date=data.get("medical_clearance_date"),
                medical_clearance_valid_until=data.get("medical_clearance_valid_until"),
                # Body measurements / gear sizing
                weight_kg=data.get("weight_kg"),
                height_cm=data.get("height_cm"),
                wetsuit_size=data.get("wetsuit_size", ""),
                bcd_size=data.get("bcd_size", ""),
                fin_size=data.get("fin_size", ""),
                mask_fit=data.get("mask_fit", ""),
                glove_size=data.get("glove_size", ""),
                weight_required_kg=data.get("weight_required_kg"),
                gear_notes=data.get("gear_notes", ""),
                equipment_ownership=data.get("equipment_ownership", "none"),
                diver_type=data.get("diver_type", "activity"),
            )

        # Create certification if level provided
        cert_level = data.get("certification_level")
        if cert_level:
            # Check if diver already has this certification
            existing_cert = DiverCertification.objects.filter(
                diver=diver,
                level=cert_level,
                deleted_at__isnull=True,
            ).first()

            if not existing_cert:
                # Handle proof document upload
                proof_document = None
                proof_file = data.get("proof_file")
                if proof_file:
                    from django.contrib.contenttypes.models import ContentType
                    from django_documents.models import Document, DocumentFolder

                    # Get content type before creating document (NOT NULL constraint)
                    content_type = ContentType.objects.get_for_model(DiverCertification)

                    # Get the Certifications folder
                    certifications_folder = DocumentFolder.objects.filter(
                        slug="certifications",
                        parent__isnull=True,
                    ).first()

                    doc = Document(
                        file=proof_file,
                        folder=certifications_folder,
                        filename=proof_file.name,
                        content_type=proof_file.content_type or "application/octet-stream",
                        file_size=proof_file.size,
                        document_type="certification_proof",
                        description=f"Certification proof for {cert_level.name}",
                        target_content_type=content_type,
                        target_id="pending",  # Placeholder, will update after certification is saved
                    )
                    doc.checksum = doc.compute_checksum()
                    doc.save()
                    proof_document = doc

                # Add certification via service (handles audit)
                certification = add_certification(
                    diver=diver,
                    level=cert_level,
                    added_by=actor,
                    card_number=data.get("card_number", ""),
                    issued_on=data.get("issued_on"),
                    expires_on=data.get("expires_on"),
                    proof_document=proof_document,
                )

                # Update document target_id with actual certification pk
                if proof_document:
                    proof_document.target_id = str(certification.pk)
                    proof_document.save()

        return diver


class EmergencyContactForm(forms.Form):
    """Form to add/edit emergency contact using PartyRelationship.

    Creates a PartyRelationship with relationship_type='emergency_contact'
    and a DiverRelationshipMeta for priority ordering.
    """

    # Contact selection - mutually exclusive with name fields
    existing_person = forms.ModelChoiceField(
        queryset=Person.objects.none(),
        required=False,
        label="Select Existing Contact",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # New contact fields (used if existing_person is not selected)
    first_name = forms.CharField(
        required=False,
        max_length=150,
        label="First Name",
    )
    last_name = forms.CharField(
        required=False,
        max_length=150,
        label="Last Name",
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        label="Phone Number",
    )
    email = forms.EmailField(
        required=False,
        label="Email",
    )
    date_of_birth = forms.DateField(
        required=False,
        label="Date of Birth",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    phone_is_mobile = forms.BooleanField(
        required=False,
        initial=True,
        label="Mobile Phone",
    )
    phone_has_whatsapp = forms.BooleanField(
        required=False,
        initial=False,
        label="Has WhatsApp",
    )
    phone_can_receive_sms = forms.BooleanField(
        required=False,
        initial=True,
        label="Can Receive SMS",
    )

    # Relationship details
    RELATIONSHIP_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("parent", "Parent"),
        ("child", "Child (Adult)"),
        ("sibling", "Sibling"),
        ("friend", "Friend"),
        ("other", "Other"),
    ]
    relationship = forms.ChoiceField(
        choices=RELATIONSHIP_CHOICES,
        label="Relationship",
    )
    priority = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Priority",
        help_text="1 = primary, 2 = secondary, etc.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Notes",
    )

    def __init__(self, *args, diver=None, **kwargs):
        """Initialize form with diver context.

        Args:
            diver: DiverProfile to add emergency contact for
        """
        super().__init__(*args, **kwargs)
        self.diver = diver

        # Populate existing_person queryset (exclude self)
        if diver:
            self.fields["existing_person"].queryset = Person.objects.filter(
                deleted_at__isnull=True
            ).exclude(pk=diver.person.pk).order_by("first_name", "last_name")

            # Get next priority number
            from .models import EmergencyContact
            current_count = EmergencyContact.objects.filter(
                diver=diver,
                deleted_at__isnull=True,
            ).count()
            self.fields["priority"].initial = current_count + 1

    def clean(self):
        """Validate that either existing_person OR name fields are provided, not both."""
        cleaned_data = super().clean()
        existing = cleaned_data.get("existing_person")
        first_name = cleaned_data.get("first_name", "").strip()
        last_name = cleaned_data.get("last_name", "").strip()

        # VALIDATION: Either existing_person OR (first_name AND last_name)
        if existing and (first_name or last_name):
            raise ValidationError(
                "Select an existing contact OR enter a new name, not both."
            )
        if not existing and not (first_name and last_name):
            raise ValidationError(
                "Select an existing contact or enter first and last name."
            )

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Create PartyRelationship + DiverRelationshipMeta.

        Returns:
            PartyRelationship instance
        """
        from .services import add_emergency_contact_via_party_relationship

        return add_emergency_contact_via_party_relationship(
            diver=self.diver,
            existing_person=self.cleaned_data.get("existing_person"),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
            phone=self.cleaned_data.get("phone", ""),
            email=self.cleaned_data.get("email", ""),
            date_of_birth=self.cleaned_data.get("date_of_birth"),
            phone_is_mobile=self.cleaned_data.get("phone_is_mobile", True),
            phone_has_whatsapp=self.cleaned_data.get("phone_has_whatsapp", False),
            phone_can_receive_sms=self.cleaned_data.get("phone_can_receive_sms", True),
            relationship=self.cleaned_data["relationship"],
            priority=self.cleaned_data["priority"],
            notes=self.cleaned_data.get("notes", ""),
            actor=actor,
        )


class DiverRelationshipForm(forms.Form):
    """Form to add/edit diver relationship using PartyRelationship.

    Creates a PartyRelationship with appropriate relationship_type
    and a DiverRelationshipMeta for buddy-specific fields.
    """

    # Related person - can be any Person (not just divers)
    related_person = forms.ModelChoiceField(
        queryset=Person.objects.none(),
        label="Related Person",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    RELATIONSHIP_TYPE_CHOICES = [
        ("spouse", "Spouse/Partner"),
        ("buddy", "Dive Buddy"),
        ("friend", "Friend"),
        ("relative", "Family Member"),
        ("travel_companion", "Travel Companion"),
        ("instructor", "Instructor/Trainer"),
        ("student", "Student/Trainee"),
    ]
    relationship_type = forms.ChoiceField(
        choices=RELATIONSHIP_TYPE_CHOICES,
        label="Relationship Type",
    )
    is_preferred_buddy = forms.BooleanField(
        required=False,
        label="Preferred Buddy",
        help_text="Prefer pairing these divers together (for buddy relationships)",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Notes",
    )

    def __init__(self, *args, from_diver=None, **kwargs):
        """Initialize form with diver context.

        Args:
            from_diver: DiverProfile to add relationship for
        """
        super().__init__(*args, **kwargs)
        self.from_diver = from_diver

        # Populate queryset - exclude self
        if from_diver:
            self.fields["related_person"].queryset = Person.objects.filter(
                deleted_at__isnull=True
            ).exclude(pk=from_diver.person.pk).order_by("first_name", "last_name")

    def clean(self):
        """Validate relationship constraints."""
        cleaned_data = super().clean()
        related_person = cleaned_data.get("related_person")
        relationship_type = cleaned_data.get("relationship_type")

        # Prevent self-linking (extra safety)
        if self.from_diver and related_person and related_person == self.from_diver.person:
            raise ValidationError("Cannot create a relationship with yourself.")

        # Check for duplicate relationship
        if self.from_diver and related_person and relationship_type:
            from django_parties.models import PartyRelationship
            existing = PartyRelationship.objects.filter(
                from_person=self.from_diver.person,
                to_person=related_person,
                relationship_type=relationship_type,
                deleted_at__isnull=True,
            ).exists()
            if existing:
                raise ValidationError(
                    f"A {dict(self.RELATIONSHIP_TYPE_CHOICES).get(relationship_type, relationship_type)} "
                    f"relationship with this person already exists."
                )

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Create PartyRelationship + DiverRelationshipMeta.

        Returns:
            PartyRelationship instance
        """
        from .services import add_diver_relationship_via_party_relationship

        return add_diver_relationship_via_party_relationship(
            from_diver=self.from_diver,
            to_person=self.cleaned_data["related_person"],
            relationship_type=self.cleaned_data["relationship_type"],
            is_preferred_buddy=self.cleaned_data.get("is_preferred_buddy", False),
            notes=self.cleaned_data.get("notes", ""),
            actor=actor,
        )


class BookDiverForm(forms.Form):
    """Form to book a diver on an excursion.

    Displays available divers (those not already booked on this excursion).
    """

    diver = forms.ModelChoiceField(
        queryset=DiverProfile.objects.none(),
        label="Select Diver",
        help_text="Choose a diver to book on this excursion.",
    )

    def __init__(self, *args, excursion: Excursion, **kwargs):
        super().__init__(*args, **kwargs)
        self.excursion = excursion

        # Get divers already booked on this excursion (excluding cancelled)
        booked_diver_ids = Booking.objects.filter(
            excursion=excursion,
            status__in=["pending", "confirmed", "checked_in"],
        ).values_list("diver_id", flat=True)

        # Show all divers except those already booked
        self.fields["diver"].queryset = DiverProfile.objects.select_related(
            "person"
        ).exclude(pk__in=booked_diver_ids)


class CertificationLevelForm(forms.ModelForm):
    """Form for creating/editing CertificationLevel."""

    class Meta:
        model = CertificationLevel
        fields = ["agency", "code", "name", "rank", "max_depth_m", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class DiverCertificationForm(forms.ModelForm):
    """Form for creating/editing DiverCertification.

    The level field determines the agency (agency is derived from level.agency).
    Supports file upload for proof_document.

    Audit logging is emitted for certification_added and certification_updated actions.
    The actor (user) must be passed via save(actor=request.user).
    """

    proof_file = forms.FileField(
        required=False,
        label="Proof Document",
        help_text="Upload certification card photo/scan (optional)",
        widget=forms.FileInput(attrs={"accept": "image/*,application/pdf"}),
    )

    class Meta:
        model = DiverCertification
        fields = [
            "diver",
            "level",
            "card_number",
            "issued_on",
            "expires_on",
        ]
        widgets = {
            "issued_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        issued_on = cleaned_data.get("issued_on")
        expires_on = cleaned_data.get("expires_on")

        if issued_on and expires_on:
            if expires_on <= issued_on:
                raise ValidationError({
                    "expires_on": "Expiration date must be after issue date."
                })

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True, actor=None):
        """Save certification and create proof document if file uploaded.

        Delegates to service layer for all writes. Services handle audit events.

        Args:
            commit: If True, save to database
            actor: User performing the action (passed to services)

        Returns:
            DiverCertification instance
        """
        from .services import add_certification, update_certification

        # Use _state.adding to detect new records (pk may be set for UUID fields)
        is_new = self.instance._state.adding

        # Handle proof document upload first
        proof_document = None
        proof_file = self.cleaned_data.get("proof_file")
        if proof_file:
            from django.contrib.contenttypes.models import ContentType
            from django_documents.models import Document, DocumentFolder

            # Get content type for DiverCertification (needed before save due to NOT NULL constraint)
            content_type = ContentType.objects.get_for_model(DiverCertification)

            # Get the Certifications folder
            certifications_folder = DocumentFolder.objects.filter(
                slug="certifications",
                parent__isnull=True,
            ).first()

            # Determine category from content type
            mime = proof_file.content_type or "application/octet-stream"
            if mime.startswith("image/"):
                category = "image"
            else:
                category = "document"

            # Create Document for the proof with target_content_type set
            doc = Document(
                file=proof_file,
                folder=certifications_folder,
                filename=proof_file.name,
                content_type=mime,
                file_size=proof_file.size,
                document_type="certification_proof",
                category=category,
                description=f"Certification proof for {self.cleaned_data.get('level').name if self.cleaned_data.get('level') else 'certification'}",
                target_content_type=content_type,
                target_id="pending",  # Placeholder, will update after certification is saved
            )
            # Compute checksum
            doc.checksum = doc.compute_checksum()
            doc.save()

            # Auto-extract EXIF/metadata for images
            if category == "image":
                try:
                    from .document_metadata import extract_document_metadata
                    extracted = extract_document_metadata(doc)
                    if extracted:
                        metadata = doc.metadata or {}
                        metadata.update(extracted)
                        doc.metadata = metadata
                        doc.save(update_fields=["metadata", "updated_at"])
                except Exception:
                    pass  # Metadata extraction is best-effort

            proof_document = doc

        if commit:
            if is_new:
                # Create new certification via service (handles audit)
                instance = add_certification(
                    diver=self.cleaned_data["diver"],
                    level=self.cleaned_data["level"],
                    added_by=actor,
                    card_number=self.cleaned_data.get("card_number", ""),
                    issued_on=self.cleaned_data.get("issued_on"),
                    expires_on=self.cleaned_data.get("expires_on"),
                    proof_document=proof_document,
                )
            else:
                # Refresh from database to get original values
                # (ModelForm mutates instance during validation)
                original = DiverCertification.objects.get(pk=self.instance.pk)
                # Update existing certification via service (handles audit)
                instance = update_certification(
                    certification=original,
                    updated_by=actor,
                    card_number=self.cleaned_data.get("card_number"),
                    issued_on=self.cleaned_data.get("issued_on"),
                    expires_on=self.cleaned_data.get("expires_on"),
                    proof_document=proof_document,
                )

            # Update document target_id now that we have the certification pk
            if proof_document:
                proof_document.target_id = str(instance.pk)
                proof_document.save()

            return instance
        else:
            # If not committing, just update the instance without saving
            instance = super().save(commit=False)
            if proof_document:
                instance.proof_document = proof_document
            return instance


class ExcursionRequirementForm(forms.ModelForm):
    """Form for creating/editing ExcursionRequirement."""

    class Meta:
        model = ExcursionRequirement
        fields = [
            "excursion",
            "requirement_type",
            "certification_level",
            "min_dives",
            "description",
            "is_mandatory",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        requirement_type = cleaned_data.get("requirement_type")
        certification_level = cleaned_data.get("certification_level")

        if requirement_type == "certification" and not certification_level:
            raise ValidationError({
                "certification_level": "Certification level is required for certification requirements."
            })

        return cleaned_data


# Backwards compatibility alias


class DiveSiteForm(forms.Form):
    """Form to create or edit a dive site.

    Handles coordinate input (from map JS) and delegates to service layer.
    Does NOT create models directly - passes to create_dive_site/update_dive_site services.
    """

    name = forms.CharField(
        max_length=200,
        label="Site Name",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Description",
    )
    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        label="Latitude",
        widget=forms.HiddenInput(),
        help_text="Set by clicking on the map",
    )
    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        label="Longitude",
        widget=forms.HiddenInput(),
        help_text="Set by clicking on the map",
    )
    max_depth_meters = forms.IntegerField(
        min_value=1,
        label="Maximum Depth (meters)",
    )
    difficulty = forms.ChoiceField(
        choices=DiveSite.DIFFICULTY_CHOICES,
        label="Difficulty",
    )
    dive_mode = forms.ChoiceField(
        choices=DiveSite.DiveMode.choices,
        label="Access Type",
        help_text="How divers access this site (boat, shore, cenote, cavern)",
    )
    min_certification_level = forms.ModelChoiceField(
        queryset=CertificationLevel.objects.filter(is_active=True).select_related("agency").order_by("rank"),
        required=False,
        empty_label="No requirement",
        label="Minimum Certification",
    )
    rating = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=5,
        label="Rating (1-5)",
    )
    tags = forms.CharField(
        required=False,
        label="Tags",
        help_text="Comma-separated tags (e.g., reef, coral, wreck)",
    )
    protected_area = forms.ModelChoiceField(
        queryset=ProtectedArea.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="No protected area",
        label="Protected Area",
        help_text="Optional: Assign this site to a protected area (marine park)",
    )
    protected_area_zone = forms.ModelChoiceField(
        queryset=ProtectedAreaZone.objects.filter(is_active=True).order_by("protected_area__name", "name"),
        required=False,
        empty_label="No zone",
        label="Zone",
        help_text="Optional: Specific zone within the protected area",
    )

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form, optionally with existing DiveSite.

        Args:
            instance: Existing DiveSite for editing
        """
        self.instance = instance
        super().__init__(*args, **kwargs)

        # Pre-populate fields if editing existing site
        if instance:
            self.fields["name"].initial = instance.name
            self.fields["description"].initial = instance.description
            self.fields["latitude"].initial = instance.place.latitude
            self.fields["longitude"].initial = instance.place.longitude
            self.fields["max_depth_meters"].initial = instance.max_depth_meters
            self.fields["difficulty"].initial = instance.difficulty
            self.fields["dive_mode"].initial = instance.dive_mode
            self.fields["min_certification_level"].initial = instance.min_certification_level
            self.fields["rating"].initial = instance.rating
            self.fields["tags"].initial = ", ".join(instance.tags) if instance.tags else ""
            self.fields["protected_area"].initial = instance.protected_area
            self.fields["protected_area_zone"].initial = instance.protected_area_zone

    def clean_tags(self):
        """Parse comma-separated tags into list."""
        tags_str = self.cleaned_data.get("tags", "")
        if not tags_str:
            return []
        # Split by comma, strip whitespace, filter empty
        return [tag.strip() for tag in tags_str.split(",") if tag.strip()]

    def clean(self):
        """Validate that zone belongs to selected protected area."""
        cleaned_data = super().clean()
        protected_area = cleaned_data.get("protected_area")
        protected_area_zone = cleaned_data.get("protected_area_zone")

        if protected_area_zone and not protected_area:
            raise forms.ValidationError(
                "You must select a protected area when selecting a zone."
            )

        if protected_area_zone and protected_area:
            if protected_area_zone.protected_area_id != protected_area.pk:
                raise forms.ValidationError(
                    f"Zone '{protected_area_zone.name}' does not belong to "
                    f"'{protected_area.name}'. Please select a zone from that area."
                )

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Save DiveSite via service layer.

        Delegates to create_dive_site or update_dive_site services.
        Services handle audit events.

        Args:
            actor: User performing the action (passed to services)

        Returns:
            DiveSite instance
        """
        from .services import create_dive_site, update_dive_site

        data = self.cleaned_data

        if self.instance:
            # Update existing site via service
            site = update_dive_site(
                actor=actor,
                site=self.instance,
                name=data["name"],
                description=data.get("description", ""),
                latitude=data["latitude"],
                longitude=data["longitude"],
                max_depth_meters=data["max_depth_meters"],
                difficulty=data["difficulty"],
                dive_mode=data["dive_mode"],
                min_certification_level=data.get("min_certification_level"),
                rating=data.get("rating"),
                tags=data.get("tags", []),
                protected_area=data.get("protected_area"),
                protected_area_zone=data.get("protected_area_zone"),
            )
        else:
            # Create new site via service
            site = create_dive_site(
                actor=actor,
                name=data["name"],
                description=data.get("description", ""),
                latitude=data["latitude"],
                longitude=data["longitude"],
                max_depth_meters=data["max_depth_meters"],
                difficulty=data["difficulty"],
                dive_mode=data["dive_mode"],
                min_certification_level=data.get("min_certification_level"),
                rating=data.get("rating"),
                tags=data.get("tags", []),
                protected_area=data.get("protected_area"),
                protected_area_zone=data.get("protected_area_zone"),
            )

        return site


class ExcursionForm(forms.Form):
    """Form to create or edit an excursion.

    Uses services for all write operations.
    Supports optional excursion_type selection for pricing computation.
    """

    excursion_type = forms.ModelChoiceField(
        queryset=ExcursionType.objects.filter(is_active=True).order_by("name"),
        label="Excursion Type",
        required=False,
        help_text="Optional: Select a product type for automatic pricing",
    )
    dive_site = forms.ModelChoiceField(
        queryset=DiveSite.objects.order_by("name"),
        label="Dive Site",
        help_text="Select the dive site for this excursion",
    )
    dive_shop = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type="dive_shop").order_by("name"),
        label="Dive Shop",
        help_text="Select the dive shop operating this excursion",
    )
    departure_time = forms.DateTimeField(
        label="Departure Time",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="Scheduled departure date and time",
    )
    return_time = forms.DateTimeField(
        label="Return Time",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="Scheduled return date and time",
    )
    max_divers = forms.IntegerField(
        label="Max Divers",
        min_value=1,
        max_value=100,
        initial=8,
        help_text="Maximum number of divers for this excursion",
    )
    price_per_diver = forms.DecimalField(
        label="Price per Diver",
        max_digits=10,
        decimal_places=2,
        required=False,
        help_text="Price per diver (leave blank to use computed price from excursion type)",
    )
    currency = forms.ChoiceField(
        label="Currency",
        choices=[
            ("USD", "USD"),
            ("EUR", "EUR"),
            ("GBP", "GBP"),
            ("AUD", "AUD"),
        ],
        initial="USD",
        required=False,
    )

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form with optional instance for editing."""
        self.instance = instance
        super().__init__(*args, **kwargs)

        if instance:
            # Pre-populate form with existing values
            self.fields["excursion_type"].initial = instance.excursion_type
            self.fields["dive_site"].initial = instance.dive_site
            self.fields["dive_shop"].initial = instance.dive_shop
            self.fields["departure_time"].initial = instance.departure_time
            self.fields["return_time"].initial = instance.return_time
            self.fields["max_divers"].initial = instance.max_divers
            self.fields["price_per_diver"].initial = instance.price_per_diver
            self.fields["currency"].initial = instance.currency

    def clean(self):
        """Validate that return time is after departure time."""
        cleaned_data = super().clean()
        departure = cleaned_data.get("departure_time")
        return_time = cleaned_data.get("return_time")

        if departure and return_time and return_time <= departure:
            raise ValidationError(
                "Return time must be after departure time."
            )

        return cleaned_data

    def get_computed_price(self):
        """Compute price from excursion type and dive site if available.

        Returns:
            ComputedPrice or None if no excursion_type selected
        """
        excursion_type = self.cleaned_data.get("excursion_type")
        dive_site = self.cleaned_data.get("dive_site")

        if excursion_type and dive_site:
            from .pricing_service import compute_excursion_price

            return compute_excursion_price(excursion_type, dive_site)
        return None


class DiveForm(forms.Form):
    """Form for creating/editing a dive within an excursion."""

    dive_site = forms.ModelChoiceField(
        queryset=DiveSite.objects.all(),
        label="Dive Site",
        help_text="Select the dive site for this dive",
    )
    sequence = forms.IntegerField(
        label="Dive Number",
        min_value=1,
        max_value=10,
        initial=1,
        help_text="Sequence number (1st dive, 2nd dive, etc.)",
    )
    planned_start = forms.DateTimeField(
        label="Planned Start Time",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="When this dive is scheduled to start",
    )
    planned_duration_minutes = forms.IntegerField(
        label="Planned Duration (minutes)",
        min_value=10,
        max_value=180,
        required=False,
        help_text="Estimated dive duration in minutes",
    )
    max_depth_meters = forms.IntegerField(
        label="Max Depth (meters)",
        min_value=1,
        max_value=60,
        required=False,
        help_text="Maximum planned depth in meters",
    )
    notes = forms.CharField(
        label="Notes",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Any additional notes about this dive",
    )

    def __init__(self, *args, excursion=None, instance=None, **kwargs):
        """Initialize form with excursion context and optional instance."""
        self.excursion = excursion
        self.instance = instance
        super().__init__(*args, **kwargs)

        if instance:
            self.fields["dive_site"].initial = instance.dive_site
            self.fields["sequence"].initial = instance.sequence
            self.fields["planned_start"].initial = instance.planned_start
            self.fields["planned_duration_minutes"].initial = instance.planned_duration_minutes
            self.fields["max_depth_meters"].initial = instance.max_depth_meters
            self.fields["notes"].initial = instance.notes
        elif excursion:
            # Default sequence to next available
            max_seq = excursion.dives.aggregate(models.Max("sequence"))["sequence__max"] or 0
            self.fields["sequence"].initial = max_seq + 1
            # Default planned_start to excursion departure
            self.fields["planned_start"].initial = excursion.departure_time


class ExcursionTypeForm(forms.Form):
    """Form to create or edit an excursion type.

    Handles all ExcursionType fields and delegates to service layer for writes.
    """

    name = forms.CharField(
        max_length=100,
        label="Name",
        help_text="Display name for this excursion type",
    )
    slug = forms.SlugField(
        max_length=50,
        label="Slug",
        help_text="URL-friendly identifier (unique)",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Description",
    )
    dive_mode = forms.ChoiceField(
        choices=ExcursionType.DiveMode.choices,
        label="Dive Mode",
    )
    time_of_day = forms.ChoiceField(
        choices=ExcursionType.TimeOfDay.choices,
        label="Time of Day",
    )
    typical_duration_minutes = forms.IntegerField(
        min_value=15,
        max_value=480,
        initial=60,
        label="Typical Duration (minutes)",
    )
    dives_per_excursion = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=2,
        label="Dives per Excursion",
    )
    min_certification_level = forms.ModelChoiceField(
        queryset=CertificationLevel.objects.filter(is_active=True).select_related("agency").order_by("rank"),
        required=False,
        empty_label="No requirement",
        label="Minimum Certification",
        help_text="Required certification level (leave empty for DSD)",
    )
    requires_cert = forms.BooleanField(
        required=False,
        initial=True,
        label="Requires Certification",
        help_text="Uncheck for Discover Scuba Diving (DSD)",
    )
    is_training = forms.BooleanField(
        required=False,
        initial=False,
        label="Is Training Dive",
        help_text="Check for intro/training dives (DSD)",
    )
    base_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label="Base Price",
        help_text="Starting price before site adjustments",
    )
    currency = forms.ChoiceField(
        choices=[
            ("USD", "USD"),
            ("EUR", "EUR"),
            ("GBP", "GBP"),
            ("AUD", "AUD"),
        ],
        initial="USD",
        label="Currency",
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Active",
        help_text="Inactive types are hidden from booking",
    )

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form, optionally with existing ExcursionType.

        Args:
            instance: Existing ExcursionType for editing
        """
        self.instance = instance
        super().__init__(*args, **kwargs)

        # Pre-populate fields if editing existing type
        if instance:
            self.fields["name"].initial = instance.name
            self.fields["slug"].initial = instance.slug
            self.fields["description"].initial = instance.description
            self.fields["dive_mode"].initial = instance.dive_mode
            self.fields["time_of_day"].initial = instance.time_of_day
            self.fields["typical_duration_minutes"].initial = instance.typical_duration_minutes
            self.fields["dives_per_excursion"].initial = instance.dives_per_excursion
            self.fields["min_certification_level"].initial = instance.min_certification_level
            self.fields["requires_cert"].initial = instance.requires_cert
            self.fields["is_training"].initial = instance.is_training
            self.fields["base_price"].initial = instance.base_price
            self.fields["currency"].initial = instance.currency
            self.fields["is_active"].initial = instance.is_active

    def clean_slug(self):
        """Validate slug is unique (unless editing same type)."""
        slug = self.cleaned_data["slug"]

        existing = ExcursionType.objects.filter(slug=slug).first()
        if existing:
            if self.instance and self.instance.pk == existing.pk:
                return slug
            raise forms.ValidationError("An excursion type with this slug already exists.")

        return slug

    @transaction.atomic
    def save(self, actor=None):
        """Save ExcursionType via service layer.

        Delegates to create_excursion_type or update_excursion_type services.
        Services handle audit events.

        Args:
            actor: User performing the action (passed to services)

        Returns:
            ExcursionType instance
        """
        from .services import create_excursion_type, update_excursion_type

        data = self.cleaned_data

        if self.instance:
            # Update existing type via service
            excursion_type = update_excursion_type(
                actor=actor,
                excursion_type=self.instance,
                name=data["name"],
                slug=data["slug"],
                description=data.get("description", ""),
                dive_mode=data["dive_mode"],
                time_of_day=data["time_of_day"],
                typical_duration_minutes=data["typical_duration_minutes"],
                dives_per_excursion=data["dives_per_excursion"],
                min_certification_level=data.get("min_certification_level"),
                requires_cert=data.get("requires_cert", True),
                is_training=data.get("is_training", False),
                base_price=data["base_price"],
                currency=data["currency"],
                is_active=data.get("is_active", True),
            )
        else:
            # Create new type via service
            excursion_type = create_excursion_type(
                actor=actor,
                name=data["name"],
                slug=data["slug"],
                description=data.get("description", ""),
                dive_mode=data["dive_mode"],
                time_of_day=data["time_of_day"],
                typical_duration_minutes=data["typical_duration_minutes"],
                dives_per_excursion=data["dives_per_excursion"],
                min_certification_level=data.get("min_certification_level"),
                requires_cert=data.get("requires_cert", True),
                is_training=data.get("is_training", False),
                base_price=data["base_price"],
                currency=data["currency"],
                is_active=data.get("is_active", True),
            )

        return excursion_type


class ExcursionTypeDiveForm(forms.Form):
    """Form to create or edit a dive template within an excursion type.

    Handles all ExcursionTypeDive fields. Used to define the individual dives
    that make up an excursion product (e.g., "First Tank", "Second Tank").
    """

    sequence = forms.IntegerField(
        min_value=1,
        max_value=10,
        label="Dive Number",
        help_text="Sequence within the excursion (1st dive, 2nd dive, etc.)",
    )
    name = forms.CharField(
        max_length=100,
        label="Name",
        help_text="Name for this dive (e.g., 'First Tank', 'Deep Dive')",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Description",
    )
    planned_depth_meters = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        label="Target Depth (m)",
        help_text="Maximum depth in meters for this dive",
    )
    planned_duration_minutes = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=180,
        label="Duration (min)",
        help_text="Planned duration in minutes",
    )
    offset_minutes = forms.IntegerField(
        min_value=0,
        max_value=480,
        initial=0,
        label="Offset (min)",
        help_text="Minutes after excursion departure that this dive starts",
    )
    surface_interval_minutes = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=480,
        label="Surface Interval (min)",
        help_text="Surface interval before this dive (required for dives after the first)",
    )
    min_certification_level = forms.ModelChoiceField(
        queryset=CertificationLevel.objects.filter(is_active=True).select_related("agency").order_by("rank"),
        required=False,
        empty_label="Same as excursion type",
        label="Certification Override",
        help_text="Override certification requirement for this specific dive",
    )
    catalog_item = forms.ModelChoiceField(
        queryset=CatalogItem.objects.filter(deleted_at__isnull=True, kind="service"),
        required=False,
        empty_label="No product linked",
        label="Catalog Product",
        help_text="Product sold for this dive (with components like tank, weights, etc.)",
    )
    dive_site = forms.ModelChoiceField(
        queryset=DiveSite.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="No specific site (generic template)",
        label="Dive Site",
        help_text="Specific site this dive plan is designed for",
    )

    # Dive Planning Fields
    gas = forms.ChoiceField(
        choices=[("", "Not specified")] + list(ExcursionTypeDive.GasType.choices),
        required=False,
        label="Gas Mix",
        help_text="Breathing gas for this dive",
    )
    route = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Route Description",
        help_text="Navigation plan and dive profile description",
    )
    route_segments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "class": "font-mono text-sm"}),
        label="Route Segments (JSON)",
        help_text='Dive profile as JSON array, e.g.: [{"phase": "descent", "from_depth_m": 0, "to_depth_m": 20, "duration_min": 2}, {"phase": "level", "depth_m": 20, "duration_min": 30}]',
    )
    briefing_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Briefing Text",
        help_text="Full briefing content for communication to divers",
    )
    briefing_video_url = forms.URLField(
        required=False,
        label="Briefing Video URL",
        help_text="YouTube video URL for dive briefing (e.g., https://www.youtube.com/watch?v=...)",
    )
    hazards = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Hazards",
        help_text="Known hazards and safety considerations",
    )
    access_mode = forms.ChoiceField(
        required=False,
        choices=[("", "---")] + list(ExcursionTypeDive.AccessMode.choices),
        label="Access Mode",
        help_text="How divers get to the dive site",
    )
    boat_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Boat Instructions",
        help_text="Instructions for boat dives (boarding, gear storage, entry/exit procedures)",
    )

    def __init__(self, *args, excursion_type=None, instance=None, **kwargs):
        """Initialize form with excursion type context and optional instance.

        Args:
            excursion_type: Parent ExcursionType (optional, for backwards compat)
            instance: Existing ExcursionTypeDive for editing
        """
        # Get first excursion type for backwards compat (dive plans can have multiple types)
        self.excursion_type = excursion_type or (instance.excursion_types.first() if instance else None)
        self.instance = instance
        super().__init__(*args, **kwargs)

        if instance:
            self.fields["sequence"].initial = instance.sequence
            self.fields["name"].initial = instance.name
            self.fields["description"].initial = instance.description
            self.fields["planned_depth_meters"].initial = instance.planned_depth_meters
            self.fields["planned_duration_minutes"].initial = instance.planned_duration_minutes
            self.fields["offset_minutes"].initial = instance.offset_minutes
            self.fields["surface_interval_minutes"].initial = instance.surface_interval_minutes
            self.fields["min_certification_level"].initial = instance.min_certification_level
            self.fields["catalog_item"].initial = instance.catalog_item
            self.fields["dive_site"].initial = instance.dive_site
            # Dive planning fields
            self.fields["gas"].initial = instance.gas
            self.fields["route"].initial = instance.route
            self.fields["route_segments"].initial = json.dumps(instance.route_segments, indent=2) if instance.route_segments else ""
            self.fields["briefing_text"].initial = instance.briefing_text
            self.fields["briefing_video_url"].initial = instance.briefing_video_url
            self.fields["hazards"].initial = instance.hazards
            self.fields["access_mode"].initial = instance.access_mode
            self.fields["boat_instructions"].initial = instance.boat_instructions
        elif excursion_type:
            # Default sequence to next available
            max_seq = excursion_type.dive_templates.aggregate(
                models.Max("sequence")
            )["sequence__max"] or 0
            self.fields["sequence"].initial = max_seq + 1

    def clean_sequence(self):
        """Validate sequence is a positive integer.

        Note: Dive plans can now be shared across multiple excursion types
        (M2M relationship), so sequence uniqueness per excursion type is
        no longer enforced at the model level.
        """
        sequence = self.cleaned_data["sequence"]
        return sequence

    def clean_route_segments(self):
        """Validate route_segments is valid JSON array."""
        raw = self.cleaned_data.get("route_segments", "")
        if not raw or not raw.strip():
            return []

        try:
            segments = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")

        if not isinstance(segments, list):
            raise forms.ValidationError("Route segments must be a JSON array")

        # Basic validation of segment structure
        valid_phases = {"descent", "ascent", "level", "safety_stop"}
        for i, seg in enumerate(segments):
            if not isinstance(seg, dict):
                raise forms.ValidationError(f"Segment {i + 1} must be an object")
            phase = seg.get("phase", "level")
            if phase not in valid_phases:
                raise forms.ValidationError(
                    f"Segment {i + 1}: phase must be one of {valid_phases}"
                )

        return segments

    def clean(self):
        """Cross-field validation for dive template form."""
        cleaned_data = super().clean()

        # Store excursion_type from form if dynamically added
        excursion_type = cleaned_data.get("excursion_type")
        if excursion_type and self.excursion_type is None:
            self.excursion_type = excursion_type

        sequence = cleaned_data.get("sequence")
        surface_interval = cleaned_data.get("surface_interval_minutes")

        # Surface interval validation
        # Enforce: surface interval required for all dives after first
        if sequence and sequence > 1 and surface_interval is None:
            self.add_error(
                "surface_interval_minutes",
                "Surface interval is required for subsequent dives."
            )

        # Dive 1 should not have a surface interval
        if sequence == 1 and surface_interval is not None:
            self.add_error(
                "surface_interval_minutes",
                "First dive cannot have a surface interval."
            )

        return cleaned_data

    def save(self, actor=None):
        """Save ExcursionTypeDive via service layer.

        Delegates to create_dive_template or update_dive_template services.
        Services handle audit events and transaction management.

        Args:
            actor: User performing the action (passed to services)

        Returns:
            ExcursionTypeDive instance
        """
        from .services import create_dive_template, update_dive_template

        data = self.cleaned_data

        if self.instance:
            # Update existing via service
            return update_dive_template(
                actor=actor,
                dive_template=self.instance,
                sequence=data["sequence"],
                name=data["name"],
                description=data.get("description", ""),
                planned_depth_meters=data.get("planned_depth_meters"),
                planned_duration_minutes=data.get("planned_duration_minutes"),
                offset_minutes=data["offset_minutes"],
                surface_interval_minutes=data.get("surface_interval_minutes"),
                min_certification_level=data.get("min_certification_level"),
                clear_min_certification=data.get("min_certification_level") is None,
                dive_site=data.get("dive_site"),
                clear_dive_site=data.get("dive_site") is None,
                catalog_item=data.get("catalog_item"),
                clear_catalog_item=data.get("catalog_item") is None,
                # Dive planning fields
                gas=data.get("gas", ""),
                route=data.get("route", ""),
                route_segments=data.get("route_segments", []),
                briefing_text=data.get("briefing_text", ""),
                briefing_video_url=data.get("briefing_video_url", ""),
                hazards=data.get("hazards", ""),
                access_mode=data.get("access_mode", ""),
                boat_instructions=data.get("boat_instructions", ""),
            )
        else:
            # Create new via service
            return create_dive_template(
                actor=actor,
                excursion_type=self.excursion_type,
                sequence=data["sequence"],
                name=data["name"],
                description=data.get("description", ""),
                planned_depth_meters=data.get("planned_depth_meters"),
                planned_duration_minutes=data.get("planned_duration_minutes"),
                offset_minutes=data["offset_minutes"],
                surface_interval_minutes=data.get("surface_interval_minutes"),
                min_certification_level=data.get("min_certification_level"),
                dive_site=data.get("dive_site"),
                catalog_item=data.get("catalog_item"),
                # Dive planning fields
                gas=data.get("gas", ""),
                route=data.get("route", ""),
                route_segments=data.get("route_segments", []),
                briefing_text=data.get("briefing_text", ""),
                briefing_video_url=data.get("briefing_video_url", ""),
                hazards=data.get("hazards", ""),
                access_mode=data.get("access_mode", ""),
                boat_instructions=data.get("boat_instructions", ""),
            )


class SitePriceAdjustmentForm(forms.Form):
    """Form to create or edit a site price adjustment.

    Handles all SitePriceAdjustment fields and delegates to service layer for writes.
    Note: dive_site is not a form field - it's set externally when creating adjustments.
    """

    kind = forms.ChoiceField(
        choices=SitePriceAdjustment.AdjustmentKind.choices,
        label="Adjustment Type",
        help_text="Type of price adjustment",
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Amount",
        help_text="Adjustment amount (added to base price)",
    )
    currency = forms.ChoiceField(
        choices=[
            ("USD", "USD"),
            ("EUR", "EUR"),
            ("GBP", "GBP"),
            ("AUD", "AUD"),
        ],
        label="Currency",
        initial="USD",
    )
    applies_to_mode = forms.ChoiceField(
        choices=[
            ("", "All modes"),
            ("boat", "Boat dives only"),
            ("shore", "Shore dives only"),
        ],
        required=False,
        label="Applies To",
        help_text="If set, only applies to this dive mode",
    )
    is_per_diver = forms.BooleanField(
        required=False,
        initial=True,
        label="Per Diver",
        help_text="If checked, applied per diver; otherwise per trip",
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Active",
        help_text="If unchecked, adjustment is not applied to prices",
    )

    def __init__(self, *args, instance=None, dive_site=None, **kwargs):
        """Initialize form with optional existing adjustment.

        Args:
            instance: Existing SitePriceAdjustment for editing
            dive_site: DiveSite for new adjustments (required for create)
        """
        self.instance = instance
        self.dive_site = dive_site or (instance.dive_site if instance else None)
        super().__init__(*args, **kwargs)

        # Pre-populate fields if editing existing adjustment
        if instance:
            self.fields["kind"].initial = instance.kind
            self.fields["amount"].initial = instance.amount
            self.fields["currency"].initial = instance.currency
            self.fields["applies_to_mode"].initial = instance.applies_to_mode
            self.fields["is_per_diver"].initial = instance.is_per_diver
            self.fields["is_active"].initial = instance.is_active

    @transaction.atomic
    def save(self, actor=None):
        """Save SitePriceAdjustment via service layer.

        Delegates to create_site_price_adjustment or update_site_price_adjustment services.
        Services handle audit events.

        Args:
            actor: User performing the action (passed to services)

        Returns:
            SitePriceAdjustment instance
        """
        from .services import create_site_price_adjustment, update_site_price_adjustment

        data = self.cleaned_data

        if self.instance:
            # Update existing adjustment via service
            adjustment = update_site_price_adjustment(
                actor=actor,
                adjustment=self.instance,
                kind=data["kind"],
                amount=data["amount"],
                currency=data["currency"],
                applies_to_mode=data.get("applies_to_mode", ""),
                is_per_diver=data.get("is_per_diver", True),
                is_active=data.get("is_active", True),
            )
        else:
            # Create new adjustment via service
            adjustment = create_site_price_adjustment(
                actor=actor,
                dive_site=self.dive_site,
                kind=data["kind"],
                amount=data["amount"],
                currency=data["currency"],
                applies_to_mode=data.get("applies_to_mode", ""),
                is_per_diver=data.get("is_per_diver", True),
                is_active=data.get("is_active", True),
            )

        return adjustment


class CatalogItemForm(forms.Form):
    """Form to create or edit a catalog item.

    Maps business-friendly labels to technical CatalogItem fields.
    Used for managing equipment and service catalog entries.

    Note: service_category is hidden as it's healthcare-specific.
    For diveops, we only use kind (Equipment/Service) and default_stock_action.
    """

    KIND_CHOICES = [
        ("stock_item", "Equipment"),
        ("service", "Service"),
    ]

    STOCK_ACTION_CHOICES = [
        ("", "Not applicable"),
        ("dispense", "Dispense (give to diver)"),
        ("administer", "Administer (use on site)"),
    ]

    kind = forms.ChoiceField(
        choices=KIND_CHOICES,
        label="Item Type",
        help_text="Equipment = physical items; Service = activities or fees",
    )
    display_name = forms.CharField(
        max_length=200,
        label="Name",
        help_text="Name shown to staff and on invoices",
    )
    display_name_es = forms.CharField(
        max_length=200,
        required=False,
        label="Name (Spanish)",
        help_text="Optional Spanish translation",
    )
    default_stock_action = forms.ChoiceField(
        choices=STOCK_ACTION_CHOICES,
        required=False,
        label="Usage Type",
        help_text="For equipment: how the item is used",
    )
    is_billable = forms.BooleanField(
        required=False,
        initial=True,
        label="Appears on Invoice",
        help_text="If checked, item appears on customer invoices",
    )
    active = forms.BooleanField(
        required=False,
        initial=True,
        label="Active",
        help_text="If unchecked, item cannot be added to new orders",
    )

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form, optionally with existing CatalogItem.

        Args:
            instance: Existing CatalogItem for editing
        """
        self.instance = instance
        super().__init__(*args, **kwargs)

        # Pre-populate fields if editing existing item
        if instance:
            self.fields["kind"].initial = instance.kind
            self.fields["display_name"].initial = instance.display_name
            self.fields["display_name_es"].initial = instance.display_name_es
            self.fields["default_stock_action"].initial = instance.default_stock_action
            self.fields["is_billable"].initial = instance.is_billable
            self.fields["active"].initial = instance.active

    def clean(self):
        """Validate kind-specific fields."""
        cleaned_data = super().clean()
        kind = cleaned_data.get("kind")

        # Clear stock action for services (doesn't apply)
        if kind == "service":
            cleaned_data["default_stock_action"] = ""

        return cleaned_data

    def clean_display_name(self):
        """Validate display name is unique among active items."""
        display_name = self.cleaned_data["display_name"]

        # Check for duplicate active display names
        existing = CatalogItem.objects.filter(
            display_name=display_name,
            active=True,
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError(
                "An active catalog item with this name already exists."
            )

        return display_name

    @transaction.atomic
    def save(self, actor=None):
        """Save CatalogItem via service layer.

        Args:
            actor: User performing the action (passed for audit)

        Returns:
            CatalogItem instance
        """
        from .services import create_catalog_item, update_catalog_item

        data = self.cleaned_data

        if self.instance:
            # Update existing item
            item = update_catalog_item(
                actor=actor,
                item=self.instance,
                kind=data["kind"],
                display_name=data["display_name"],
                display_name_es=data.get("display_name_es", ""),
                default_stock_action=data.get("default_stock_action", ""),
                is_billable=data.get("is_billable", True),
                active=data.get("active", True),
            )
        else:
            # Create new item
            item = create_catalog_item(
                actor=actor,
                kind=data["kind"],
                display_name=data["display_name"],
                display_name_es=data.get("display_name_es", ""),
                default_stock_action=data.get("default_stock_action", ""),
                is_billable=data.get("is_billable", True),
                active=data.get("active", True),
            )

        return item


class PriceForm(forms.Form):
    """Form to create or edit a price rule for a catalog item.

    Price rules determine what customers pay and what the shop pays vendors.
    Rules are scoped: Agreement > Party > Organization > Global.
    Higher priority wins ties, then most recent valid_from.
    """

    SCOPE_CHOICES = [
        ("global", "Global (default for all)"),
        ("organization", "Dive Shop specific"),
        ("party", "Individual specific"),
        ("agreement", "Vendor Agreement"),
    ]

    CURRENCY_CHOICES = [
        ("USD", "USD"),
        ("MXN", "MXN"),
        ("EUR", "EUR"),
    ]

    # Customer charge
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=4,
        label="Customer Charge",
        help_text="Price charged to customers",
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label="Currency",
        initial="USD",
    )

    # Shop cost (vendor pricing)
    cost_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=4,
        required=False,
        label="Shop Cost",
        help_text="What the shop pays the vendor (leave blank if not applicable)",
    )
    cost_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        required=False,
        label="Cost Currency",
        initial="USD",
    )

    # Scope selection
    scope_type = forms.ChoiceField(
        choices=SCOPE_CHOICES,
        label="Scope",
        initial="global",
        help_text="Who this price applies to. Agreement-scoped is for vendor pricing.",
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type__in=["company", "dive_shop"]).order_by("name"),
        required=False,
        empty_label="Select a dive shop...",
        label="Dive Shop",
    )
    party = forms.ModelChoiceField(
        queryset=Person.objects.all().order_by("last_name", "first_name"),
        required=False,
        empty_label="Select a person...",
        label="Individual",
    )
    agreement = forms.ModelChoiceField(
        queryset=Agreement.objects.filter(deleted_at__isnull=True).order_by("-created_at"),
        required=False,
        empty_label="Select a vendor agreement...",
        label="Vendor Agreement",
    )

    # Validity
    valid_from = forms.DateTimeField(
        label="Valid From",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text="When this price rule takes effect",
    )
    valid_to = forms.DateTimeField(
        required=False,
        label="Valid To",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text="When this price rule expires (leave blank for no expiration)",
    )
    priority = forms.IntegerField(
        initial=0,
        label="Priority",
        help_text="Higher priority wins when multiple rules match",
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Reason",
        help_text="Why this price rule was created (for audit trail)",
    )

    def __init__(self, *args, catalog_item=None, instance=None, **kwargs):
        """Initialize form with catalog item context and optional instance.

        Args:
            catalog_item: CatalogItem this price is for (required for create)
            instance: Existing Price for editing
        """
        self.catalog_item = catalog_item or (instance.catalog_item if instance else None)
        self.instance = instance
        super().__init__(*args, **kwargs)

        if instance:
            self.fields["amount"].initial = instance.amount
            self.fields["currency"].initial = instance.currency
            self.fields["cost_amount"].initial = instance.cost_amount
            self.fields["cost_currency"].initial = instance.cost_currency or instance.currency

            # Determine scope type from instance
            if instance.agreement_id:
                self.fields["scope_type"].initial = "agreement"
                self.fields["agreement"].initial = instance.agreement
            elif instance.party_id:
                self.fields["scope_type"].initial = "party"
                self.fields["party"].initial = instance.party
            elif instance.organization_id:
                self.fields["scope_type"].initial = "organization"
                self.fields["organization"].initial = instance.organization
            else:
                self.fields["scope_type"].initial = "global"

            self.fields["valid_from"].initial = instance.valid_from
            self.fields["valid_to"].initial = instance.valid_to
            self.fields["priority"].initial = instance.priority
            self.fields["reason"].initial = instance.reason
        else:
            # Default valid_from to now
            self.fields["valid_from"].initial = timezone.now()

    def clean(self):
        """Validate scope selection is consistent."""
        cleaned_data = super().clean()
        scope_type = cleaned_data.get("scope_type")

        # Clear non-selected scope fields
        if scope_type == "global":
            cleaned_data["organization"] = None
            cleaned_data["party"] = None
            cleaned_data["agreement"] = None
        elif scope_type == "organization":
            if not cleaned_data.get("organization"):
                raise ValidationError({"organization": "Select a dive shop for organization-scoped pricing."})
            cleaned_data["party"] = None
            cleaned_data["agreement"] = None
        elif scope_type == "party":
            if not cleaned_data.get("party"):
                raise ValidationError({"party": "Select an individual for party-scoped pricing."})
            cleaned_data["organization"] = None
            cleaned_data["agreement"] = None
        elif scope_type == "agreement":
            if not cleaned_data.get("agreement"):
                raise ValidationError({"agreement": "Select a vendor agreement for agreement-scoped pricing."})
            cleaned_data["organization"] = None
            cleaned_data["party"] = None

        # Validate cost_currency if cost_amount provided
        cost_amount = cleaned_data.get("cost_amount")
        if cost_amount is not None:
            if not cleaned_data.get("cost_currency"):
                cleaned_data["cost_currency"] = cleaned_data.get("currency", "USD")

        # Validate dates
        valid_from = cleaned_data.get("valid_from")
        valid_to = cleaned_data.get("valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationError({"valid_to": "Valid to must be after valid from."})

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Save Price via service layer.

        Args:
            actor: User performing the action (passed for audit)

        Returns:
            Price instance
        """
        from .services import create_price_rule, update_price_rule

        data = self.cleaned_data

        if self.instance:
            # Update existing price
            price = update_price_rule(
                actor=actor,
                price=self.instance,
                amount=data["amount"],
                currency=data["currency"],
                cost_amount=data.get("cost_amount"),
                cost_currency=data.get("cost_currency", ""),
                valid_from=data["valid_from"],
                valid_to=data.get("valid_to"),
                priority=data["priority"],
                reason=data.get("reason", ""),
            )
        else:
            # Create new price
            price = create_price_rule(
                actor=actor,
                catalog_item=self.catalog_item,
                amount=data["amount"],
                currency=data["currency"],
                cost_amount=data.get("cost_amount"),
                cost_currency=data.get("cost_currency", ""),
                organization=data.get("organization"),
                party=data.get("party"),
                agreement=data.get("agreement"),
                valid_from=data["valid_from"],
                valid_to=data.get("valid_to"),
                priority=data["priority"],
                reason=data.get("reason", ""),
            )

        return price


class AgreementForm(forms.Form):
    """Form to create a new agreement with optional signature capture.

    Agreement types:
    - vendor_agreement: Vendor pricing agreements (dual signature - vendor + shop)
    - waiver: Liability waivers (single signature - diver)
    - training_agreement: Training/student agreements (single signature - student)

    Signatures are captured as base64 data URLs from canvas and stored in terms JSON.
    """

    SCOPE_TYPE_CHOICES = [
        ("vendor_agreement", "Vendor Agreement"),
        ("waiver", "Liability Waiver"),
        ("training_agreement", "Training Agreement"),
    ]

    # Agreement type
    scope_type = forms.ChoiceField(
        choices=SCOPE_TYPE_CHOICES,
        label="Agreement Type",
        help_text="Type of agreement determines signature requirements",
    )

    # Party A (typically the shop - selected from organizations)
    party_a_type = forms.ChoiceField(
        choices=[
            ("organization", "Organization"),
            ("person", "Person"),
        ],
        initial="organization",
        label="Party A Type",
    )
    party_a_organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type__in=["company", "dive_shop"]).order_by("name"),
        required=False,
        empty_label="Select organization...",
        label="Party A (Organization)",
    )
    party_a_person = forms.ModelChoiceField(
        queryset=Person.objects.all().order_by("last_name", "first_name"),
        required=False,
        empty_label="Select person...",
        label="Party A (Person)",
    )

    # Party B (vendor, diver, or student)
    party_b_type = forms.ChoiceField(
        choices=[
            ("organization", "Organization (Vendor)"),
            ("person", "Person (Diver/Student)"),
        ],
        initial="person",
        label="Party B Type",
    )
    party_b_organization = forms.ModelChoiceField(
        queryset=Organization.objects.all().order_by("name"),
        required=False,
        empty_label="Select vendor...",
        label="Party B (Vendor)",
    )
    party_b_person = forms.ModelChoiceField(
        queryset=Person.objects.all().order_by("last_name", "first_name"),
        required=False,
        empty_label="Select person...",
        label="Party B (Person)",
    )

    # Validity dates
    valid_from = forms.DateTimeField(
        label="Valid From",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text="When this agreement takes effect",
    )
    valid_to = forms.DateTimeField(
        required=False,
        label="Valid To",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text="When this agreement expires (leave blank for indefinite)",
    )

    # Terms (free-form JSON or structured)
    terms_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Terms Description",
        help_text="Description of agreement terms",
    )
    terms_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Notes",
        help_text="Additional notes or conditions",
    )

    # Signature capture (base64 data URLs - captured via JS)
    signature_party_a = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Party A Signature",
    )
    signature_party_b = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Party B Signature",
    )

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form with optional instance.

        Args:
            instance: Existing Agreement for viewing (read-only)
        """
        self.instance = instance
        super().__init__(*args, **kwargs)

        if not instance:
            self.fields["valid_from"].initial = timezone.now()

    def clean(self):
        """Validate party selection and signature requirements."""
        cleaned_data = super().clean()
        scope_type = cleaned_data.get("scope_type")

        # Validate Party A
        party_a_type = cleaned_data.get("party_a_type")
        if party_a_type == "organization":
            if not cleaned_data.get("party_a_organization"):
                raise ValidationError({"party_a_organization": "Select an organization for Party A."})
            cleaned_data["party_a"] = cleaned_data["party_a_organization"]
        else:
            if not cleaned_data.get("party_a_person"):
                raise ValidationError({"party_a_person": "Select a person for Party A."})
            cleaned_data["party_a"] = cleaned_data["party_a_person"]

        # Validate Party B
        party_b_type = cleaned_data.get("party_b_type")
        if party_b_type == "organization":
            if not cleaned_data.get("party_b_organization"):
                raise ValidationError({"party_b_organization": "Select an organization for Party B."})
            cleaned_data["party_b"] = cleaned_data["party_b_organization"]
        else:
            if not cleaned_data.get("party_b_person"):
                raise ValidationError({"party_b_person": "Select a person for Party B."})
            cleaned_data["party_b"] = cleaned_data["party_b_person"]

        # Validate dates
        valid_from = cleaned_data.get("valid_from")
        valid_to = cleaned_data.get("valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationError({"valid_to": "Valid to must be after valid from."})

        # For vendor agreements, both signatures may be required (but can be collected separately)
        # For waivers/training, only party_b signature is needed
        # We'll allow saving without signatures and collecting them separately via AgreementSignView

        return cleaned_data

    def build_terms(self):
        """Build terms dict from form data."""
        data = self.cleaned_data
        terms = {
            "description": data.get("terms_description", ""),
            "notes": data.get("terms_notes", ""),
        }

        # Add signatures if provided
        if data.get("signature_party_a"):
            terms["signature_party_a"] = data["signature_party_a"]
            terms["signature_party_a_at"] = timezone.now().isoformat()

        if data.get("signature_party_b"):
            terms["signature_party_b"] = data["signature_party_b"]
            terms["signature_party_b_at"] = timezone.now().isoformat()

        return terms

    @transaction.atomic
    def save(self, actor=None):
        """Save Agreement via django_agreements services.

        Args:
            actor: User performing the action (passed for audit)

        Returns:
            Agreement instance
        """
        from django_agreements.services import create_agreement

        from .audit import Actions, log_agreement_event

        data = self.cleaned_data
        terms = self.build_terms()

        agreement = create_agreement(
            party_a=data["party_a"],
            party_b=data["party_b"],
            scope_type=data["scope_type"],
            terms=terms,
            agreed_by=actor,
            valid_from=data["valid_from"],
            valid_to=data.get("valid_to"),
        )

        # Audit event
        log_agreement_event(
            action=Actions.AGREEMENT_CREATED,
            agreement=agreement,
            actor=actor,
            data={"terms_description": terms.get("description", "")},
        )

        return agreement


class SignatureForm(forms.Form):
    """Form to capture a signature for an existing agreement.

    Used by the AgreementSignView to collect signatures separately from
    agreement creation. Useful when signatures need to be collected at
    different times (e.g., vendor signs first, then shop signs).
    """

    signature = forms.CharField(
        widget=forms.HiddenInput(),
        label="Signature",
        help_text="Signature captured from canvas",
    )
    signer_name = forms.CharField(
        max_length=200,
        label="Signer Name",
        help_text="Full legal name of the person signing",
    )
    signer_title = forms.CharField(
        max_length=100,
        required=False,
        label="Title/Position",
        help_text="Job title or position (for vendor representatives)",
    )

    def __init__(self, *args, agreement=None, signing_party="party_b", **kwargs):
        """Initialize form.

        Args:
            agreement: Agreement being signed
            signing_party: Which party is signing ("party_a" or "party_b")
        """
        self.agreement = agreement
        self.signing_party = signing_party
        super().__init__(*args, **kwargs)

    def clean_signature(self):
        """Validate signature is a valid data URL."""
        signature = self.cleaned_data["signature"]
        if not signature.startswith("data:image/"):
            raise ValidationError("Invalid signature format. Must be a data URL.")
        return signature

    @transaction.atomic
    def save(self, actor=None):
        """Add signature to agreement terms.

        Args:
            actor: User capturing the signature

        Returns:
            Updated Agreement instance
        """
        from django_agreements.services import amend_agreement

        from .audit import Actions, log_agreement_event

        data = self.cleaned_data

        # Get current terms and add signature
        new_terms = dict(self.agreement.terms)
        signature_key = f"signature_{self.signing_party}"
        new_terms[signature_key] = data["signature"]
        new_terms[f"{signature_key}_at"] = timezone.now().isoformat()
        new_terms[f"{signature_key}_name"] = data["signer_name"]
        if data.get("signer_title"):
            new_terms[f"{signature_key}_title"] = data["signer_title"]

        # Amend agreement with new signature
        agreement = amend_agreement(
            agreement=self.agreement,
            new_terms=new_terms,
            reason=f"Signature collected from {self.signing_party}",
            amended_by=actor,
        )

        # Audit event
        log_agreement_event(
            action=Actions.AGREEMENT_SIGNED,
            agreement=agreement,
            actor=actor,
            data={
                "signing_party": self.signing_party,
                "signer_name": data["signer_name"],
            },
        )

        return agreement


class AgreementTerminateForm(forms.Form):
    """Form to terminate an agreement.

    Sets the valid_to date and records reason for termination.
    """

    valid_to = forms.DateTimeField(
        label="Termination Date",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text="When the agreement ends",
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Reason for Termination",
        help_text="Why is this agreement being terminated?",
    )

    def __init__(self, *args, agreement=None, **kwargs):
        """Initialize form.

        Args:
            agreement: Agreement to terminate
        """
        self.agreement = agreement
        super().__init__(*args, **kwargs)
        self.fields["valid_to"].initial = timezone.now()

    def clean_valid_to(self):
        """Validate termination date is after valid_from."""
        valid_to = self.cleaned_data["valid_to"]
        if self.agreement and valid_to <= self.agreement.valid_from:
            raise ValidationError("Termination date must be after the agreement start date.")
        return valid_to

    @transaction.atomic
    def save(self, actor=None):
        """Terminate the agreement.

        Args:
            actor: User terminating the agreement

        Returns:
            Updated Agreement instance
        """
        from django_agreements.services import terminate_agreement

        from .audit import Actions, log_agreement_event

        data = self.cleaned_data

        agreement = terminate_agreement(
            agreement=self.agreement,
            terminated_by=actor,
            valid_to=data["valid_to"],
            reason=data["reason"],
        )

        # Audit event
        log_agreement_event(
            action=Actions.AGREEMENT_TERMINATED,
            agreement=agreement,
            actor=actor,
            data={"reason": data["reason"]},
        )

        return agreement


class VendorInvoiceForm(forms.Form):
    """Form to record a vendor invoice.

    Creates ledger transactions to record vendor payables:
    DR Expense, CR Vendor Payables (per-vendor account).

    Requires accounts to be seeded for the selected shop/currency.
    """

    CURRENCY_CHOICES = [
        ("USD", "USD"),
        ("MXN", "MXN"),
        ("EUR", "EUR"),
    ]

    shop = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type__in=["company", "dive_shop"]).order_by("name"),
        label="Dive Shop",
        help_text="Shop recording this invoice (must have accounts seeded)",
    )
    vendor = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type="vendor").order_by("name"),
        label="Vendor",
        help_text="Select the vendor for this invoice",
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Amount",
        help_text="Invoice amount",
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial="USD",
        label="Currency",
    )
    invoice_number = forms.CharField(
        max_length=100,
        required=False,
        label="Invoice Number",
        help_text="Vendor's invoice reference number",
    )
    invoice_date = forms.DateField(
        label="Invoice Date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date on the vendor's invoice",
    )
    due_date = forms.DateField(
        required=False,
        label="Due Date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Payment due date",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Description",
        help_text="Description of goods/services",
    )

    # Optional: link to source booking/excursion
    source_booking = forms.ModelChoiceField(
        queryset=Booking.objects.none(),  # Will be populated in __init__
        required=False,
        empty_label="Not linked to booking",
        label="Related Booking",
        help_text="Optionally link to a specific booking",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate booking choices with recent confirmed bookings
        self.fields["source_booking"].queryset = Booking.objects.filter(
            status__in=["confirmed", "checked_in", "completed"]
        ).select_related("diver__person", "excursion").order_by("-created_at")[:100]
        # Default invoice date to today
        self.fields["invoice_date"].initial = timezone.now().date()

    def clean(self):
        """Validate invoice dates."""
        cleaned_data = super().clean()
        invoice_date = cleaned_data.get("invoice_date")
        due_date = cleaned_data.get("due_date")

        if invoice_date and due_date and due_date < invoice_date:
            raise ValidationError({"due_date": "Due date cannot be before invoice date."})

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Record vendor invoice via service layer.

        Args:
            actor: User recording the invoice

        Returns:
            Transaction instance

        Raises:
            AccountConfigurationError: If required accounts are not seeded
        """
        from .services import record_vendor_invoice

        data = self.cleaned_data

        tx = record_vendor_invoice(
            actor=actor,
            shop=data["shop"],
            vendor=data["vendor"],
            amount=data["amount"],
            currency=data["currency"],
            invoice_number=data.get("invoice_number", ""),
            invoice_date=data["invoice_date"],
            due_date=data.get("due_date"),
            source=data.get("source_booking"),
            description=data.get("description", ""),
        )

        return tx


class VendorPaymentForm(forms.Form):
    """Form to record a payment to a vendor.

    Creates ledger transactions to reduce vendor payables:
    DR Vendor Payables, CR Cash/Bank.

    Requires accounts to be seeded for the selected shop/currency.
    """

    CURRENCY_CHOICES = [
        ("USD", "USD"),
        ("MXN", "MXN"),
        ("EUR", "EUR"),
    ]

    shop = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type__in=["company", "dive_shop"]).order_by("name"),
        label="Dive Shop",
        help_text="Shop making this payment (must have accounts seeded)",
    )
    vendor = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type="vendor").order_by("name"),
        label="Vendor",
        help_text="Select the vendor being paid",
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Amount",
        help_text="Payment amount",
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial="USD",
        label="Currency",
    )
    payment_date = forms.DateField(
        label="Payment Date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date payment was made",
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        label="Reference",
        help_text="Check number, transfer reference, etc.",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Description",
        help_text="Notes about this payment",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default payment date to today
        self.fields["payment_date"].initial = timezone.now().date()

    @transaction.atomic
    def save(self, actor=None):
        """Record vendor payment via service layer.

        Args:
            actor: User recording the payment

        Returns:
            Transaction instance

        Raises:
            AccountConfigurationError: If required accounts are not seeded
        """
        from .services import record_vendor_payment

        data = self.cleaned_data

        tx = record_vendor_payment(
            actor=actor,
            shop=data["shop"],
            vendor=data["vendor"],
            amount=data["amount"],
            currency=data["currency"],
            payment_date=data["payment_date"],
            reference=data.get("reference", ""),
            description=data.get("description", ""),
        )

        return tx


class AccountForm(forms.Form):
    """Form to create or edit a ledger account.

    Accounts are owned by organizations (dive shops) and have:
    - account_number: Standard accounting number (e.g., 1000, 2000)
    - account_type: revenue, expense, asset, receivable, payable
    - currency: USD, MXN, EUR
    - name: Human-readable name
    """

    ACCOUNT_TYPE_CHOICES = [
        ("revenue", "Revenue"),
        ("expense", "Expense/COGS"),
        ("asset", "Asset"),
        ("receivable", "Accounts Receivable"),
        ("payable", "Accounts Payable"),
    ]

    CURRENCY_CHOICES = [
        ("USD", "USD"),
        ("MXN", "MXN"),
        ("EUR", "EUR"),
    ]

    account_number = forms.CharField(
        max_length=20,
        required=False,
        label="Account Number",
        help_text="Standard accounting number (e.g., 1000 for assets, 2000 for liabilities, 4000 for revenue)",
    )
    name = forms.CharField(
        max_length=200,
        label="Account Name",
        help_text="Human-readable name for this account",
    )
    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        label="Account Type",
        help_text="Classification of this account",
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial="USD",
        label="Currency",
        help_text="Currency for this account's transactions",
    )
    owner = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type__in=["company", "dive_shop"]).order_by("name"),
        label="Owner (Dive Shop)",
        help_text="Organization that owns this account",
    )

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form with optional instance.

        Args:
            instance: Existing Account for editing
        """
        self.instance = instance
        super().__init__(*args, **kwargs)

        if instance:
            self.fields["account_number"].initial = instance.account_number
            self.fields["name"].initial = instance.name
            self.fields["account_type"].initial = instance.account_type
            self.fields["currency"].initial = instance.currency
            # Owner field is read-only when editing
            if instance.owner_id:
                self.fields["owner"].initial = Organization.objects.filter(
                    pk=instance.owner_id
                ).first()
                self.fields["owner"].disabled = True

    def clean_name(self):
        """Validate name is unique for owner/account_type/currency combo."""
        name = self.cleaned_data["name"]
        # Additional uniqueness checks happen at save time
        return name

    @transaction.atomic
    def save(self, actor=None):
        """Save Account via service layer.

        Args:
            actor: User performing the action

        Returns:
            Account instance
        """
        from django.contrib.contenttypes.models import ContentType

        from django_ledger.models import Account

        from .audit import Actions, log_event

        data = self.cleaned_data
        owner = data["owner"]

        if self.instance:
            # Update existing account
            self.instance.account_number = data.get("account_number", "")
            self.instance.name = data["name"]
            self.instance.account_type = data["account_type"]
            # Currency and owner cannot be changed after creation
            self.instance.save()

            log_event(
                action=Actions.ACCOUNT_UPDATED,
                actor=actor,
                target=self.instance,
                data={
                    "account_number": data.get("account_number", ""),
                    "name": data["name"],
                    "account_type": data["account_type"],
                },
            )

            return self.instance
        else:
            # Create new account
            owner_ct = ContentType.objects.get_for_model(Organization)
            account = Account.objects.create(
                owner_content_type=owner_ct,
                owner_id=str(owner.pk),
                account_number=data.get("account_number", ""),
                name=data["name"],
                account_type=data["account_type"],
                currency=data["currency"],
            )

            log_event(
                action=Actions.ACCOUNT_CREATED,
                actor=actor,
                target=account,
                data={
                    "account_number": data.get("account_number", ""),
                    "name": data["name"],
                    "account_type": data["account_type"],
                    "currency": data["currency"],
                    "owner_name": owner.name,
                },
            )

            return account


class AccountSeedForm(forms.Form):
    """Form to seed standard chart of accounts for a dive shop.

    Creates all required accounts for a shop/currency combination.
    Idempotent - existing accounts are not modified.
    """

    CURRENCY_CHOICES = [
        ("USD", "USD"),
        ("MXN", "MXN"),
        ("EUR", "EUR"),
    ]

    shop = forms.ModelChoiceField(
        queryset=Organization.objects.filter(org_type__in=["company", "dive_shop"]).order_by("name"),
        label="Dive Shop",
        help_text="Select the dive shop to seed accounts for",
    )
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial="MXN",
        label="Currency",
        help_text="Currency for the chart of accounts",
    )
    include_vendors = forms.BooleanField(
        required=False,
        initial=True,
        label="Include Vendor Accounts",
        help_text="Create per-vendor payable accounts for existing vendors",
    )

    @transaction.atomic
    def save(self, actor=None):
        """Seed accounts via service layer.

        Args:
            actor: User performing the action

        Returns:
            AccountSet with all created/existing accounts
        """
        from django_parties.models import Organization

        from .accounts import seed_accounts
        from .audit import Actions, log_event

        data = self.cleaned_data
        shop = data["shop"]
        currency = data["currency"]

        # Get vendors if requested
        vendors = []
        if data.get("include_vendors"):
            vendors = list(Organization.objects.filter(org_type="vendor"))

        # Seed accounts
        account_set = seed_accounts(shop, currency, vendors=vendors)

        log_event(
            action=Actions.ACCOUNTS_SEEDED,
            actor=actor,
            target=shop,
            data={
                "currency": currency,
                "vendor_count": len(vendors),
            },
        )

        return account_set


class AgreementTemplateForm(forms.ModelForm):
    """Form to create or edit agreement templates.

    Agreement templates are reusable paperwork forms (waivers, medical
    questionnaires, briefing acknowledgments, etc.) that divers sign.
    """

    class Meta:
        model = AgreementTemplate
        fields = [
            "dive_shop",
            "name",
            "template_type",
            "description",
            "content",
            "requires_signature",
            "requires_initials",
            "is_required_for_booking",
            "validity_days",
            "version",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "content": forms.Textarea(attrs={"rows": 15}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter dive shops
        self.fields["dive_shop"].queryset = Organization.objects.filter(
            org_type__in=["company", "dive_shop"]
        ).order_by("name")
        self.fields["dive_shop"].empty_label = "Select dive shop..."

        # Add help text
        self.fields["content"].help_text = (
            "Agreement content (supports HTML). Use placeholders like "
            "{{diver_name}}, {{date}}, {{dive_shop}} for dynamic content."
        )
        self.fields["validity_days"].help_text = (
            "Number of days this agreement remains valid after signing. "
            "Leave empty for agreements that never expire."
        )

    def clean(self):
        """Validate template data."""
        cleaned_data = super().clean()

        # Ensure content is not empty
        content = cleaned_data.get("content", "").strip()
        if not content:
            self.add_error("content", "Agreement content cannot be empty.")

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None, commit=True):
        """Save agreement template.

        Args:
            actor: User performing the action
            commit: Whether to save to database

        Returns:
            AgreementTemplate instance
        """
        from .audit import Actions, log_event

        instance = super().save(commit=False)

        if commit:
            instance.save()

            # Log audit event
            action = Actions.AGREEMENT_TEMPLATE_CREATED if not self.instance.pk else Actions.AGREEMENT_TEMPLATE_UPDATED
            log_event(
                action=action,
                actor=actor,
                target=instance,
                data={
                    "name": instance.name,
                    "template_type": instance.template_type,
                    "version": instance.version,
                },
            )

        return instance


class CatalogItemComponentForm(forms.Form):
    """Form for adding/editing catalog item components (assembly BOM)."""

    component = forms.ModelChoiceField(
        queryset=CatalogItem.objects.none(),
        label="Component Item",
        help_text="Select the catalog item to include as a component",
    )
    quantity = forms.IntegerField(
        min_value=1,
        max_value=9999,
        initial=1,
        label="Quantity",
        help_text="Number of this component per parent item",
    )
    sequence = forms.IntegerField(
        min_value=0,
        max_value=999,
        initial=0,
        label="Sequence",
        help_text="Display/processing order within the assembly",
    )
    is_optional = forms.BooleanField(
        required=False,
        initial=False,
        label="Optional Component",
        help_text="If checked, component can be excluded when ordering the parent",
    )
    notes = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Optional notes about this component"}),
        label="Notes",
        help_text="Optional notes about this component relationship",
    )

    def __init__(self, *args, parent_item=None, instance=None, **kwargs):
        """Initialize form.

        Args:
            parent_item: The parent CatalogItem (assembly)
            instance: Existing CatalogItemComponent for editing
        """
        super().__init__(*args, **kwargs)
        self.parent_item = parent_item
        self.instance = instance

        # Exclude parent and items that would create cycles
        excluded_ids = [parent_item.pk] if parent_item else []

        # Also exclude items that have this parent as a component (prevent circular)
        if parent_item:
            from django_catalog.models import CatalogItemComponent

            # Items where parent_item is used as a component
            excluded_ids.extend(
                CatalogItemComponent.objects.filter(
                    component=parent_item,
                    deleted_at__isnull=True,
                ).values_list("parent_id", flat=True)
            )

        self.fields["component"].queryset = CatalogItem.objects.filter(
            deleted_at__isnull=True,
            active=True,
        ).exclude(pk__in=excluded_ids).order_by("display_name")

        # Pre-fill for editing
        if instance:
            self.fields["component"].initial = instance.component
            self.fields["quantity"].initial = instance.quantity
            self.fields["sequence"].initial = instance.sequence
            self.fields["is_optional"].initial = instance.is_optional
            self.fields["notes"].initial = instance.notes

        # Set default sequence for new components
        if not instance and parent_item:
            from django_catalog.models import CatalogItemComponent

            max_seq = CatalogItemComponent.objects.filter(
                parent=parent_item,
                deleted_at__isnull=True,
            ).aggregate(max_seq=models.Max("sequence"))["max_seq"]
            self.fields["sequence"].initial = (max_seq or 0) + 10

    def clean(self):
        """Validate component data."""
        cleaned_data = super().clean()
        component = cleaned_data.get("component")

        if component and self.parent_item:
            # Check for self-reference
            if component.pk == self.parent_item.pk:
                self.add_error("component", "An item cannot be a component of itself.")

            # Check for duplicate component (unless editing the same one)
            from django_catalog.models import CatalogItemComponent

            existing = CatalogItemComponent.objects.filter(
                parent=self.parent_item,
                component=component,
                deleted_at__isnull=True,
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                self.add_error("component", "This component is already part of this assembly.")

        return cleaned_data

    @transaction.atomic
    def save(self, actor=None):
        """Save component relationship.

        Args:
            actor: User performing the action

        Returns:
            CatalogItemComponent instance
        """
        from django_catalog.models import CatalogItemComponent
        from .audit import Actions, log_event

        if self.instance:
            # Update existing
            self.instance.component = self.cleaned_data["component"]
            self.instance.quantity = self.cleaned_data["quantity"]
            self.instance.sequence = self.cleaned_data["sequence"]
            self.instance.is_optional = self.cleaned_data["is_optional"]
            self.instance.notes = self.cleaned_data["notes"]
            self.instance.save()
            component = self.instance

            log_event(
                action=Actions.CATALOG_COMPONENT_UPDATED,
                actor=actor,
                target=component,
                data={
                    "parent": str(self.parent_item.pk),
                    "parent_name": self.parent_item.display_name,
                    "component": str(component.component.pk),
                    "component_name": component.component.display_name,
                    "quantity": component.quantity,
                },
            )
        else:
            # Create new
            component = CatalogItemComponent.objects.create(
                parent=self.parent_item,
                component=self.cleaned_data["component"],
                quantity=self.cleaned_data["quantity"],
                sequence=self.cleaned_data["sequence"],
                is_optional=self.cleaned_data["is_optional"],
                notes=self.cleaned_data["notes"],
            )

            log_event(
                action=Actions.CATALOG_COMPONENT_ADDED,
                actor=actor,
                target=component,
                data={
                    "parent": str(self.parent_item.pk),
                    "parent_name": self.parent_item.display_name,
                    "component": str(component.component.pk),
                    "component_name": component.component.display_name,
                    "quantity": component.quantity,
                },
            )

        return component


# =============================================================================
# Protected Area ModelForms
# =============================================================================


class ProtectedAreaForm(forms.ModelForm):
    """Form for creating/editing ProtectedArea with cycle prevention."""

    class Meta:
        model = ProtectedArea
        fields = [
            "name",
            "code",
            "parent",
            "designation_type",
            "place",
            "governing_authority",
            "authority_contact",
            "official_website",
            "established_date",
            "max_divers_per_site",
            "is_active",
        ]
        widgets = {
            "authority_contact": forms.Textarea(attrs={"rows": 3}),
            "established_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter parent choices to exclude self and descendants (to prevent cycles)
        if self.instance.pk:
            descendants = self._get_all_descendants(self.instance)
            exclude_ids = [self.instance.pk] + [d.pk for d in descendants]
            self.fields["parent"].queryset = ProtectedArea.objects.exclude(
                pk__in=exclude_ids
            ).filter(is_active=True)
        else:
            self.fields["parent"].queryset = ProtectedArea.objects.filter(is_active=True)

    def clean(self):
        """Validate parent to prevent cycles."""
        cleaned_data = super().clean()
        parent = cleaned_data.get("parent")

        if parent and self.instance.pk:
            # Cannot be own parent
            if parent.pk == self.instance.pk:
                raise ValidationError("Area cannot be its own parent.")
            # Cannot have a descendant as parent
            descendants = self._get_all_descendants(self.instance)
            if parent in descendants:
                raise ValidationError(
                    "Parent cannot be a descendant of this area (would create cycle)."
                )

        return cleaned_data

    def _get_all_descendants(self, area):
        """Recursively get all descendants of an area."""
        descendants = []
        for child in area.children.all():
            descendants.append(child)
            descendants.extend(self._get_all_descendants(child))
        return descendants


class ProtectedAreaZoneForm(forms.ModelForm):
    """Form for creating/editing zones within a protected area."""

    class Meta:
        model = ProtectedAreaZone
        fields = [
            "name",
            "code",
            "zone_type",
            "max_divers",
            "diving_allowed",
            "requires_guide",
            "is_active",
        ]


class ProtectedAreaRuleForm(forms.ModelForm):
    """Form for creating/editing rules within a protected area."""

    class Meta:
        model = ProtectedAreaRule
        fields = [
            "zone",
            "rule_type",
            "applies_to",
            "subject",
            "activity",
            "operator",
            "value",
            "enforcement_level",
            "effective_start",
            "effective_end",
            "is_active",
        ]
        widgets = {
            "effective_start": forms.DateInput(attrs={"type": "date"}),
            "effective_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, protected_area=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter zones to only those belonging to the protected area
        if protected_area:
            self.fields["zone"].queryset = ProtectedAreaZone.objects.filter(
                protected_area=protected_area, is_active=True
            )
        self.fields["zone"].required = False


class ProtectedAreaFeeScheduleForm(forms.ModelForm):
    """Form for creating/editing fee schedules within a protected area."""

    class Meta:
        model = ProtectedAreaFeeSchedule
        fields = [
            "name",
            "zone",
            "fee_type",
            "applies_to",
            "currency",
            "effective_start",
            "effective_end",
            "is_active",
        ]
        widgets = {
            "effective_start": forms.DateInput(attrs={"type": "date"}),
            "effective_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, protected_area=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter zones to only those belonging to the protected area
        if protected_area:
            self.fields["zone"].queryset = ProtectedAreaZone.objects.filter(
                protected_area=protected_area, is_active=True
            )
        self.fields["zone"].required = False


class ProtectedAreaFeeTierForm(forms.ModelForm):
    """Form for creating/editing fee tiers within a fee schedule."""

    class Meta:
        model = ProtectedAreaFeeTier
        fields = [
            "tier_code",
            "label",
            "amount",
            "priority",
            "requires_proof",
        ]


# =============================================================================
# Unified Permit Forms (Replaces ProtectedAreaGuideCredentialForm + VesselPermitForm)
# =============================================================================


class GuidePermitForm(forms.ModelForm):
    """Form for creating/editing GUIDE permits.

    Uses ProtectedAreaPermit model with permit_type locked to 'guide'.
    Only shows fields relevant to guide permits.
    """

    class Meta:
        model = ProtectedAreaPermit
        fields = [
            "diver",
            "permit_number",
            "issued_at",
            "expires_at",
            "authorized_zones",
            "is_active",
        ]
        widgets = {
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, protected_area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.protected_area = protected_area
        # Filter authorized_zones to only those belonging to the protected area
        if protected_area:
            self.fields["authorized_zones"].queryset = ProtectedAreaZone.objects.filter(
                protected_area=protected_area, is_active=True, deleted_at__isnull=True
            )
        # Filter diver to only show active divers
        self.fields["diver"].queryset = DiverProfile.objects.filter(
            deleted_at__isnull=True
        ).select_related("person")

    def save(self, commit=True):
        """Set permit_type to GUIDE before saving."""
        instance = super().save(commit=False)
        instance.permit_type = ProtectedAreaPermit.PermitType.GUIDE
        if self.protected_area:
            instance.protected_area = self.protected_area
        # Clear vessel fields for guide permits
        instance.vessel_name = ""
        instance.vessel_registration = ""
        instance.organization = None
        instance.max_divers = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class VesselPermitFormNew(forms.ModelForm):
    """Form for creating/editing VESSEL permits.

    Uses ProtectedAreaPermit model with permit_type locked to 'vessel'.
    Only shows fields relevant to vessel permits.
    """

    class Meta:
        model = ProtectedAreaPermit
        fields = [
            "vessel_name",
            "vessel_registration",
            "permit_number",
            "organization",
            "issued_at",
            "expires_at",
            "authorized_zones",
            "max_divers",
            "is_active",
        ]
        widgets = {
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, protected_area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.protected_area = protected_area
        # Filter authorized_zones to only those belonging to the protected area
        if protected_area:
            self.fields["authorized_zones"].queryset = ProtectedAreaZone.objects.filter(
                protected_area=protected_area, is_active=True, deleted_at__isnull=True
            )

    def save(self, commit=True):
        """Set permit_type to VESSEL before saving."""
        instance = super().save(commit=False)
        instance.permit_type = ProtectedAreaPermit.PermitType.VESSEL
        if self.protected_area:
            instance.protected_area = self.protected_area
        # Clear diver field for vessel permits
        instance.diver = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PhotographyPermitForm(forms.ModelForm):
    """Form for creating/editing PHOTOGRAPHY permits.

    Uses ProtectedAreaPermit model with permit_type locked to 'photography'.
    Photography permits are issued to individual divers (like guide permits).
    """

    class Meta:
        model = ProtectedAreaPermit
        fields = [
            "diver",
            "permit_number",
            "issued_at",
            "expires_at",
            "authorized_zones",
            "is_active",
        ]
        widgets = {
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, protected_area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.protected_area = protected_area
        # Filter authorized_zones to only those belonging to the protected area
        if protected_area:
            self.fields["authorized_zones"].queryset = ProtectedAreaZone.objects.filter(
                protected_area=protected_area, is_active=True, deleted_at__isnull=True
            )
        # Filter diver to only show active divers
        self.fields["diver"].queryset = DiverProfile.objects.filter(
            deleted_at__isnull=True
        ).select_related("person")

    def save(self, commit=True):
        """Set permit_type to PHOTOGRAPHY before saving."""
        instance = super().save(commit=False)
        instance.permit_type = ProtectedAreaPermit.PermitType.PHOTOGRAPHY
        if self.protected_area:
            instance.protected_area = self.protected_area
        # Clear vessel fields for photography permits
        instance.vessel_name = ""
        instance.vessel_registration = ""
        instance.organization = None
        instance.max_divers = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class DivingPermitForm(forms.ModelForm):
    """Form for creating/editing DIVING permits.

    Uses ProtectedAreaPermit model with permit_type locked to 'diving'.
    Diving permits can be issued to either an individual diver OR an organization.
    """

    class Meta:
        model = ProtectedAreaPermit
        fields = [
            "diver",
            "organization",
            "permit_number",
            "issued_at",
            "expires_at",
            "authorized_zones",
            "is_active",
        ]
        widgets = {
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, protected_area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.protected_area = protected_area
        # Filter authorized_zones to only those belonging to the protected area
        if protected_area:
            self.fields["authorized_zones"].queryset = ProtectedAreaZone.objects.filter(
                protected_area=protected_area, is_active=True, deleted_at__isnull=True
            )
        # Filter diver to only show active divers
        self.fields["diver"].queryset = DiverProfile.objects.filter(
            deleted_at__isnull=True
        ).select_related("person")
        # Make both optional in the form (constraint enforces at least one)
        self.fields["diver"].required = False
        self.fields["organization"].required = False

    def clean(self):
        """Ensure at least one of diver or organization is provided."""
        cleaned_data = super().clean()
        diver = cleaned_data.get("diver")
        organization = cleaned_data.get("organization")
        if not diver and not organization:
            raise forms.ValidationError(
                "A diving permit must be issued to either a diver or an organization."
            )
        return cleaned_data

    def save(self, commit=True):
        """Set permit_type to DIVING before saving."""
        instance = super().save(commit=False)
        instance.permit_type = ProtectedAreaPermit.PermitType.DIVING
        if self.protected_area:
            instance.protected_area = self.protected_area
        # Clear vessel fields for diving permits
        instance.vessel_name = ""
        instance.vessel_registration = ""
        instance.max_divers = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


# =============================================================================
# ExcursionSeries Forms (Recurring Excursions)
# =============================================================================


class ExcursionSeriesForm(forms.Form):
    """Form to create or edit an ExcursionSeries.

    Handles both ExcursionSeries fields and RecurrenceRule fields in a unified form.
    """

    # Basic Information
    name = forms.CharField(
        max_length=200,
        label="Series Name",
        help_text="Display name for this series (e.g., 'Saturday Morning 2-Tank')",
    )
    excursion_type = forms.ModelChoiceField(
        queryset=ExcursionType.objects.filter(is_active=True).order_by("name"),
        label="Excursion Type",
        help_text="Product template for generated excursions",
    )
    dive_site = forms.ModelChoiceField(
        queryset=DiveSite.objects.filter(deleted_at__isnull=True).order_by("name"),
        required=False,
        empty_label="Select default site (optional)",
        label="Default Dive Site",
        help_text="Can be overridden per occurrence",
    )

    # Recurrence Settings
    day_of_week = forms.ChoiceField(
        choices=[
            ("MO", "Monday"),
            ("TU", "Tuesday"),
            ("WE", "Wednesday"),
            ("TH", "Thursday"),
            ("FR", "Friday"),
            ("SA", "Saturday"),
            ("SU", "Sunday"),
        ],
        label="Day of Week",
    )
    start_time = forms.TimeField(
        label="Departure Time",
        widget=forms.TimeInput(attrs={"type": "time"}),
        help_text="Time excursions depart",
    )
    series_start_date = forms.DateField(
        label="First Occurrence",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date of the first occurrence",
    )
    series_end_date = forms.DateField(
        required=False,
        label="Last Occurrence",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank for indefinite series",
    )
    timezone = forms.ChoiceField(
        choices=[
            ("America/Cancun", "Cancun (EST - no DST)"),
            ("America/Mexico_City", "Mexico City (CST)"),
            ("America/New_York", "New York (EST)"),
            ("America/Los_Angeles", "Los Angeles (PST)"),
            ("UTC", "UTC"),
        ],
        initial="America/Cancun",
        label="Timezone",
    )

    # Defaults
    duration_minutes = forms.IntegerField(
        min_value=60,
        max_value=720,
        initial=240,
        label="Duration (minutes)",
        help_text="Default excursion duration (4 hours = 240)",
    )
    capacity_default = forms.IntegerField(
        min_value=1,
        max_value=50,
        initial=12,
        label="Max Divers",
        help_text="Default capacity per occurrence",
    )
    price_default = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label="Price Override",
        help_text="Leave blank to use excursion type base price",
    )
    currency = forms.ChoiceField(
        choices=[("USD", "USD"), ("MXN", "MXN"), ("EUR", "EUR")],
        initial="USD",
        label="Currency",
    )
    meeting_place = forms.CharField(
        required=False,
        max_length=500,
        label="Meeting Place",
        help_text="Default meeting location",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Internal Notes",
    )

    # Generation Control
    status = forms.ChoiceField(
        choices=ExcursionSeries.Status.choices,
        initial="draft",
        label="Status",
        help_text="Active series generate occurrences automatically",
    )
    window_days = forms.IntegerField(
        min_value=7,
        max_value=365,
        initial=60,
        label="Booking Window (days)",
        help_text="Generate occurrences this many days ahead",
    )

    def __init__(self, *args, instance=None, dive_shop=None, **kwargs):
        self.instance = instance
        self.dive_shop = dive_shop
        super().__init__(*args, **kwargs)

        # If editing, populate from instance
        if instance:
            self.fields["name"].initial = instance.name
            self.fields["excursion_type"].initial = instance.excursion_type_id
            self.fields["dive_site"].initial = instance.dive_site_id
            self.fields["duration_minutes"].initial = instance.duration_minutes
            self.fields["capacity_default"].initial = instance.capacity_default
            self.fields["price_default"].initial = instance.price_default
            self.fields["currency"].initial = instance.currency
            self.fields["meeting_place"].initial = instance.meeting_place
            self.fields["notes"].initial = instance.notes
            self.fields["status"].initial = instance.status
            self.fields["window_days"].initial = instance.window_days

            # Parse recurrence rule
            rule = instance.recurrence_rule
            self.fields["timezone"].initial = rule.timezone
            self.fields["series_start_date"].initial = rule.dtstart.date()
            if rule.dtend:
                self.fields["series_end_date"].initial = rule.dtend.date()
            # Extract time from dtstart
            self.fields["start_time"].initial = rule.dtstart.time()
            # Parse BYDAY from rrule_text
            if "BYDAY=" in rule.rrule_text:
                byday = rule.rrule_text.split("BYDAY=")[1].split(";")[0]
                self.fields["day_of_week"].initial = byday

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("series_start_date")
        end_date = cleaned_data.get("series_end_date")

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date must be after start date.")

        return cleaned_data

    def save(self, actor=None):
        """Create or update ExcursionSeries and its RecurrenceRule."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        data = self.cleaned_data
        tz = ZoneInfo(data["timezone"])

        # Build dtstart datetime
        dtstart = datetime.combine(
            data["series_start_date"],
            data["start_time"],
            tzinfo=tz,
        )

        # Build dtend if provided
        dtend = None
        if data.get("series_end_date"):
            dtend = datetime.combine(
                data["series_end_date"],
                data["start_time"],
                tzinfo=tz,
            )

        # Build RRULE string
        rrule_text = f"FREQ=WEEKLY;BYDAY={data['day_of_week']}"

        with transaction.atomic():
            if self.instance:
                # Update existing
                rule = self.instance.recurrence_rule
                rule.rrule_text = rrule_text
                rule.dtstart = dtstart
                rule.dtend = dtend
                rule.timezone = data["timezone"]
                rule.save()

                self.instance.name = data["name"]
                self.instance.excursion_type = data["excursion_type"]
                self.instance.dive_site = data.get("dive_site")
                self.instance.duration_minutes = data["duration_minutes"]
                self.instance.capacity_default = data["capacity_default"]
                self.instance.price_default = data.get("price_default")
                self.instance.currency = data["currency"]
                self.instance.meeting_place = data.get("meeting_place", "")
                self.instance.notes = data.get("notes", "")
                self.instance.status = data["status"]
                self.instance.window_days = data["window_days"]
                self.instance.save()
                return self.instance
            else:
                # Create new
                rule = RecurrenceRule.objects.create(
                    rrule_text=rrule_text,
                    dtstart=dtstart,
                    dtend=dtend,
                    timezone=data["timezone"],
                )

                series = ExcursionSeries.objects.create(
                    name=data["name"],
                    dive_shop=self.dive_shop,
                    recurrence_rule=rule,
                    excursion_type=data["excursion_type"],
                    dive_site=data.get("dive_site"),
                    duration_minutes=data["duration_minutes"],
                    capacity_default=data["capacity_default"],
                    price_default=data.get("price_default"),
                    currency=data["currency"],
                    meeting_place=data.get("meeting_place", ""),
                    notes=data.get("notes", ""),
                    status=data["status"],
                    window_days=data["window_days"],
                    created_by=actor,
                )
                return series


class LeadOnboardingForm(forms.Form):
    """Minimal form for public lead capture.

    Collects basic contact information from prospective divers and creates
    a Person + DiverProfile record without requiring authentication.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "First name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "Last name",
            }
        ),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "you@example.com",
            }
        ),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500",
                "placeholder": "+1 (555) 123-4567",
            }
        ),
    )
    experience_level = forms.ChoiceField(
        choices=[
            ("never", "Never dived before"),
            ("beginner", "A few dives (1-10)"),
            ("intermediate", "10-50 dives"),
            ("experienced", "50+ dives"),
        ],
        required=False,
        initial="never",
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            }
        ),
    )

    def clean_email(self):
        """Validate email is not already registered."""
        email = self.cleaned_data["email"].lower().strip()
        if Person.objects.filter(email__iexact=email, deleted_at__isnull=True).exists():
            raise ValidationError(
                "This email is already registered. Please log in or use a different email."
            )
        return email

    def save(self):
        """Create Person record as a new lead."""
        from django_parties.models import LeadStatusEvent

        experience = self.cleaned_data.get("experience_level", "never")
        experience_labels = {
            "never": "Never dived before",
            "beginner": "A few dives (1-10)",
            "intermediate": "10-50 dives",
            "experienced": "50+ dives",
        }

        person = Person.objects.create(
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data["email"],
            phone=self.cleaned_data.get("phone", ""),
            notes=f"Lead from website. Experience: {experience_labels.get(experience, experience)}",
            lead_status="new",
            lead_source="website",
        )

        LeadStatusEvent.objects.create(
            person=person,
            from_status="",
            to_status="new",
            note="Lead captured via website onboarding form",
        )

        return person
