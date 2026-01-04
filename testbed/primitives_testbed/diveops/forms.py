"""Forms for diveops staff portal."""

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from django_parties.models import Organization, Person

from .models import (
    Booking,
    CertificationLevel,
    DiverCertification,
    DiverProfile,
    DiveTrip,
    TripRequirement,
)


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
            self.fields["first_name"].initial = instance.person.first_name
            self.fields["last_name"].initial = instance.person.last_name
            self.fields["email"].initial = instance.person.email
            self.fields["total_dives"].initial = instance.total_dives
            self.fields["medical_clearance_date"].initial = instance.medical_clearance_date
            self.fields["medical_clearance_valid_until"].initial = instance.medical_clearance_valid_until

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

        Args:
            actor: User performing the action (for audit logging)

        Returns:
            DiverProfile instance
        """
        from .audit import Actions, log_certification_event

        data = self.cleaned_data

        if self.instance:
            # Update existing diver
            person = self.instance.person
            person.first_name = data["first_name"]
            person.last_name = data["last_name"]
            person.email = data["email"]
            person.save()

            self.instance.total_dives = data["total_dives"]
            self.instance.medical_clearance_date = data.get("medical_clearance_date")
            self.instance.medical_clearance_valid_until = data.get("medical_clearance_valid_until")
            self.instance.save()

            diver = self.instance
        else:
            # Create new diver
            person = Person.objects.create(
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
            )

            diver = DiverProfile.objects.create(
                person=person,
                total_dives=data["total_dives"],
                medical_clearance_date=data.get("medical_clearance_date"),
                medical_clearance_valid_until=data.get("medical_clearance_valid_until"),
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
                    from django_documents.models import Document

                    # Get content type before creating document (NOT NULL constraint)
                    content_type = ContentType.objects.get_for_model(DiverCertification)

                    doc = Document(
                        file=proof_file,
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

                # Create certification
                certification = DiverCertification.objects.create(
                    diver=diver,
                    level=cert_level,
                    card_number=data.get("card_number", ""),
                    issued_on=data.get("issued_on"),
                    expires_on=data.get("expires_on"),
                    proof_document=proof_document,
                )

                # Update document target_id with actual certification pk
                if proof_document:
                    proof_document.target_id = str(certification.pk)
                    proof_document.save()

                # Log audit event
                log_certification_event(
                    action=Actions.CERTIFICATION_ADDED,
                    certification=certification,
                    actor=actor,
                )

        return diver


class BookDiverForm(forms.Form):
    """Form to book a diver on a trip.

    Displays available divers (those not already booked on this trip).
    """

    diver = forms.ModelChoiceField(
        queryset=DiverProfile.objects.none(),
        label="Select Diver",
        help_text="Choose a diver to book on this trip.",
    )

    def __init__(self, *args, trip: DiveTrip, **kwargs):
        super().__init__(*args, **kwargs)
        self.trip = trip

        # Get divers already booked on this trip (excluding cancelled)
        booked_diver_ids = Booking.objects.filter(
            trip=trip,
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

        Args:
            commit: If True, save to database
            actor: User performing the action (for audit logging)

        Returns:
            DiverCertification instance
        """
        from .audit import Actions, log_certification_event

        # Use _state.adding to detect new records (pk may be set for UUID fields)
        is_new = self.instance._state.adding

        # Track changes for updates
        changes = {}
        if not is_new:
            # Compare old values with new values
            old_instance = DiverCertification.objects.get(pk=self.instance.pk)
            for field in ["card_number", "issued_on", "expires_on"]:
                old_val = getattr(old_instance, field)
                new_val = self.cleaned_data.get(field)
                if old_val != new_val:
                    changes[field] = {
                        "old": str(old_val) if old_val else None,
                        "new": str(new_val) if new_val else None,
                    }

        instance = super().save(commit=False)

        # Handle proof document upload
        proof_file = self.cleaned_data.get("proof_file")
        if proof_file:
            from django_documents.models import Document
            from django.contrib.contenttypes.models import ContentType

            # Track proof document change
            if not is_new and instance.proof_document:
                changes["proof_document"] = {"old": str(instance.proof_document_id), "new": "new_upload"}

            # Get content type for DiverCertification (needed before save due to NOT NULL constraint)
            content_type = ContentType.objects.get_for_model(DiverCertification)

            # Create Document for the proof with target_content_type set
            doc = Document(
                file=proof_file,
                filename=proof_file.name,
                content_type=proof_file.content_type or "application/octet-stream",
                file_size=proof_file.size,
                document_type="certification_proof",
                description=f"Certification proof for {instance.level.name if instance.level else 'certification'}",
                target_content_type=content_type,
                target_id="pending",  # Placeholder, will update after certification is saved
            )
            # Compute checksum
            doc.checksum = doc.compute_checksum()
            doc.save()

            instance.proof_document = doc

        if commit:
            instance.save()
            # Update document target_id now that we have the certification pk
            if instance.proof_document and not instance.proof_document.target_id:
                instance.proof_document.target_id = str(instance.pk)
                instance.proof_document.save()

            # Emit audit event
            if is_new:
                log_certification_event(
                    action=Actions.CERTIFICATION_ADDED,
                    certification=instance,
                    actor=actor,
                )
            elif changes:
                log_certification_event(
                    action=Actions.CERTIFICATION_UPDATED,
                    certification=instance,
                    actor=actor,
                    changes=changes,
                )

        return instance


class TripRequirementForm(forms.ModelForm):
    """Form for creating/editing TripRequirement."""

    class Meta:
        model = TripRequirement
        fields = [
            "trip",
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
