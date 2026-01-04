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
    DiveSite,
    Excursion,
    ExcursionRequirement,
)

# Backwards compatibility aliases
DiveTrip = Excursion
TripRequirement = ExcursionRequirement


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
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                total_dives=data["total_dives"],
                medical_clearance_date=data.get("medical_clearance_date"),
                medical_clearance_valid_until=data.get("medical_clearance_valid_until"),
            )
        else:
            # Create new diver via service
            diver = create_diver(
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                total_dives=data["total_dives"],
                created_by=actor,
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
            from django_documents.models import Document

            # Get content type for DiverCertification (needed before save due to NOT NULL constraint)
            content_type = ContentType.objects.get_for_model(DiverCertification)

            # Create Document for the proof with target_content_type set
            doc = Document(
                file=proof_file,
                filename=proof_file.name,
                content_type=proof_file.content_type or "application/octet-stream",
                file_size=proof_file.size,
                document_type="certification_proof",
                description=f"Certification proof for {self.cleaned_data.get('level').name if self.cleaned_data.get('level') else 'certification'}",
                target_content_type=content_type,
                target_id="pending",  # Placeholder, will update after certification is saved
            )
            # Compute checksum
            doc.checksum = doc.compute_checksum()
            doc.save()
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
TripRequirementForm = ExcursionRequirementForm


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
            self.fields["min_certification_level"].initial = instance.min_certification_level
            self.fields["rating"].initial = instance.rating
            self.fields["tags"].initial = ", ".join(instance.tags) if instance.tags else ""

    def clean_tags(self):
        """Parse comma-separated tags into list."""
        tags_str = self.cleaned_data.get("tags", "")
        if not tags_str:
            return []
        # Split by comma, strip whitespace, filter empty
        return [tag.strip() for tag in tags_str.split(",") if tag.strip()]

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
                min_certification_level=data.get("min_certification_level"),
                rating=data.get("rating"),
                tags=data.get("tags", []),
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
                min_certification_level=data.get("min_certification_level"),
                rating=data.get("rating"),
                tags=data.get("tags", []),
            )

        return site
