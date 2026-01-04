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
    """Form to create or edit a diver (Person + DiverProfile).

    Combines Person fields (name, email) with DiverProfile fields
    (certification, experience) into a single form.
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

    # Certification fields
    certification_level = forms.ChoiceField(
        choices=DiverProfile.CERTIFICATION_LEVELS,
        label="Certification Level",
    )
    certification_agency = forms.CharField(
        max_length=50,
        label="Certification Agency",
        help_text="e.g., PADI, SSI, NAUI, SDI",
    )
    certification_number = forms.CharField(
        max_length=100,
        label="Certification Number",
        required=False,
    )
    certification_date = forms.DateField(
        label="Certification Date",
        widget=forms.DateInput(attrs={"type": "date"}),
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

    def __init__(self, *args, instance=None, **kwargs):
        """Initialize form, optionally with existing DiverProfile."""
        self.instance = instance
        super().__init__(*args, **kwargs)

        # Pre-populate fields if editing existing diver
        if instance:
            self.fields["first_name"].initial = instance.person.first_name
            self.fields["last_name"].initial = instance.person.last_name
            self.fields["email"].initial = instance.person.email
            self.fields["certification_level"].initial = instance.certification_level
            self.fields["certification_agency"].initial = instance.certification_agency
            self.fields["certification_number"].initial = instance.certification_number
            self.fields["certification_date"].initial = instance.certification_date
            self.fields["total_dives"].initial = instance.total_dives
            self.fields["medical_clearance_date"].initial = instance.medical_clearance_date
            self.fields["medical_clearance_valid_until"].initial = instance.medical_clearance_valid_until

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

    @transaction.atomic
    def save(self):
        """Save Person and DiverProfile."""
        data = self.cleaned_data

        if self.instance:
            # Update existing
            person = self.instance.person
            person.first_name = data["first_name"]
            person.last_name = data["last_name"]
            person.email = data["email"]
            person.save()

            self.instance.certification_level = data["certification_level"]
            self.instance.certification_agency = data["certification_agency"]
            self.instance.certification_number = data.get("certification_number", "")
            self.instance.certification_date = data["certification_date"]
            self.instance.total_dives = data["total_dives"]
            self.instance.medical_clearance_date = data.get("medical_clearance_date")
            self.instance.medical_clearance_valid_until = data.get("medical_clearance_valid_until")
            self.instance.save()

            return self.instance
        else:
            # Create new
            person = Person.objects.create(
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
            )

            diver = DiverProfile.objects.create(
                person=person,
                certification_level=data["certification_level"],
                certification_agency=data["certification_agency"],
                certification_number=data.get("certification_number", ""),
                certification_date=data["certification_date"],
                total_dives=data["total_dives"],
                medical_clearance_date=data.get("medical_clearance_date"),
                medical_clearance_valid_until=data.get("medical_clearance_valid_until"),
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
        fields = ["code", "name", "rank", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class DiverCertificationForm(forms.ModelForm):
    """Form for creating/editing DiverCertification."""

    class Meta:
        model = DiverCertification
        fields = [
            "diver",
            "level",
            "agency",
            "certification_number",
            "certified_on",
            "expires_on",
        ]
        widgets = {
            "certified_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        certified_on = cleaned_data.get("certified_on")
        expires_on = cleaned_data.get("expires_on")

        if certified_on and expires_on:
            if expires_on <= certified_on:
                raise ValidationError({
                    "expires_on": "Expiration date must be after certification date."
                })

        return cleaned_data


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
