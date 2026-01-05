"""Forms for diveops staff portal."""

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from django_parties.models import Organization, Person

from django.db import models

from .models import (
    Booking,
    CertificationLevel,
    Dive,
    DiverCertification,
    DiverProfile,
    DiveSite,
    Excursion,
    ExcursionRequirement,
    ExcursionType,
    ExcursionTypeDive,
    SitePriceAdjustment,
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
                dive_mode=data["dive_mode"],
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
                dive_mode=data["dive_mode"],
                min_certification_level=data.get("min_certification_level"),
                rating=data.get("rating"),
                tags=data.get("tags", []),
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
    max_depth_meters = forms.IntegerField(
        min_value=1,
        max_value=100,
        label="Max Depth (meters)",
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
            self.fields["max_depth_meters"].initial = instance.max_depth_meters
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
                max_depth_meters=data["max_depth_meters"],
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
                max_depth_meters=data["max_depth_meters"],
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
    min_certification_level = forms.ModelChoiceField(
        queryset=CertificationLevel.objects.filter(is_active=True).select_related("agency").order_by("rank"),
        required=False,
        empty_label="Same as excursion type",
        label="Certification Override",
        help_text="Override certification requirement for this specific dive",
    )

    def __init__(self, *args, excursion_type=None, instance=None, **kwargs):
        """Initialize form with excursion type context and optional instance.

        Args:
            excursion_type: Parent ExcursionType (required for create)
            instance: Existing ExcursionTypeDive for editing
        """
        self.excursion_type = excursion_type or (instance.excursion_type if instance else None)
        self.instance = instance
        super().__init__(*args, **kwargs)

        if instance:
            self.fields["sequence"].initial = instance.sequence
            self.fields["name"].initial = instance.name
            self.fields["description"].initial = instance.description
            self.fields["planned_depth_meters"].initial = instance.planned_depth_meters
            self.fields["planned_duration_minutes"].initial = instance.planned_duration_minutes
            self.fields["offset_minutes"].initial = instance.offset_minutes
            self.fields["min_certification_level"].initial = instance.min_certification_level
        elif excursion_type:
            # Default sequence to next available
            max_seq = excursion_type.dive_templates.aggregate(
                models.Max("sequence")
            )["sequence__max"] or 0
            self.fields["sequence"].initial = max_seq + 1

    def clean_sequence(self):
        """Validate sequence is unique within excursion type."""
        sequence = self.cleaned_data["sequence"]

        # Check for duplicate sequence (excluding current instance if editing)
        existing = ExcursionTypeDive.objects.filter(
            excursion_type=self.excursion_type,
            sequence=sequence,
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError(
                f"Dive {sequence} already exists for this excursion type."
            )

        return sequence

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
                min_certification_level=data.get("min_certification_level"),
                clear_min_certification=data.get("min_certification_level") is None,
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
                min_certification_level=data.get("min_certification_level"),
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
