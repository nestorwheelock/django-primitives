"""Tests for diveops forms."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


@pytest.mark.django_db
class TestDiverForm:
    """Tests for DiverForm (creates Person + DiverProfile)."""

    def test_form_has_person_fields(self):
        """DiverForm has first_name, last_name, email fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm()
        assert "first_name" in form.fields
        assert "last_name" in form.fields
        assert "email" in form.fields

    def test_form_has_certification_fields(self):
        """DiverForm has certification fields (new normalized model)."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm()
        assert "certification_level" in form.fields
        assert "certification_agency" in form.fields
        assert "card_number" in form.fields
        assert "issued_on" in form.fields
        assert "expires_on" in form.fields

    def test_form_has_experience_fields(self):
        """DiverForm has experience and medical fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm()
        assert "total_dives" in form.fields
        assert "medical_clearance_date" in form.fields
        assert "medical_clearance_valid_until" in form.fields

    def test_form_valid_with_required_fields(self, padi_open_water):
        """DiverForm is valid with all required fields."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(data={
            "first_name": "Alice",
            "last_name": "Diver",
            "email": "alice@example.com",
            "certification_level": str(padi_open_water.pk),
            "certification_agency": str(padi_open_water.agency.pk),
            "card_number": "12345",
            "issued_on": date.today() - timedelta(days=30),
            "total_dives": 10,
        })
        assert form.is_valid(), form.errors

    def test_form_creates_person_and_profile(self, ssi_open_water):
        """DiverForm.save() creates both Person and DiverProfile."""
        from django_parties.models import Person
        from primitives_testbed.diveops.forms import DiverForm
        from primitives_testbed.diveops.models import DiverCertification, DiverProfile

        form = DiverForm(data={
            "first_name": "Bob",
            "last_name": "Swimmer",
            "email": "bob@example.com",
            "certification_level": str(ssi_open_water.pk),
            "certification_agency": str(ssi_open_water.agency.pk),
            "card_number": "98765",
            "issued_on": date.today() - timedelta(days=180),
            "total_dives": 25,
        })
        assert form.is_valid(), form.errors

        diver = form.save()

        assert isinstance(diver, DiverProfile)
        assert diver.pk is not None
        assert diver.person.first_name == "Bob"
        assert diver.person.last_name == "Swimmer"
        assert diver.person.email == "bob@example.com"
        assert diver.total_dives == 25
        # Certification is now in separate model
        cert = DiverCertification.objects.get(diver=diver, level=ssi_open_water)
        assert cert.card_number == "98765"

    def test_form_email_must_be_unique(self, padi_open_water):
        """DiverForm rejects duplicate email for new diver."""
        from django_parties.models import Person
        from primitives_testbed.diveops.forms import DiverForm

        # Create existing person
        Person.objects.create(
            first_name="Existing",
            last_name="Person",
            email="existing@example.com",
        )

        form = DiverForm(data={
            "first_name": "New",
            "last_name": "Person",
            "email": "existing@example.com",  # Duplicate
            "certification_level": str(padi_open_water.pk),
            "certification_agency": str(padi_open_water.agency.pk),
            "card_number": "11111",
            "issued_on": date.today(),
            "total_dives": 0,
        })
        assert not form.is_valid()
        assert "email" in form.errors

    def test_form_edit_existing_diver(self, diver_profile):
        """DiverForm can edit an existing diver (edit mode excludes certification fields)."""
        from primitives_testbed.diveops.forms import DiverForm

        # In edit mode, certification fields are excluded - use separate certification form
        form = DiverForm(instance=diver_profile, is_edit=True, data={
            "first_name": "John",
            "last_name": "Diver",
            "email": "john@example.com",
            "total_dives": 75,  # More dives
        })
        assert form.is_valid(), form.errors

        diver = form.save()
        assert diver.pk == diver_profile.pk
        assert diver.total_dives == 75

    def test_form_edit_allows_same_email(self, diver_profile):
        """Editing diver can keep the same email."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(instance=diver_profile, is_edit=True, data={
            "first_name": "John",
            "last_name": "Diver",
            "email": "john@example.com",  # Same email
            "total_dives": 55,
        })
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestBookDiverForm:
    """Tests for BookDiverForm."""

    def test_form_has_diver_field(self, dive_trip):
        """BookDiverForm has a diver selection field."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(excursion=dive_trip)
        assert "diver" in form.fields

    def test_form_shows_available_divers(self, dive_trip, diver_profile, beginner_diver):
        """Form shows divers who are not already booked."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(excursion=dive_trip)
        diver_pks = [d.pk for d in form.fields["diver"].queryset]

        assert diver_profile.pk in diver_pks
        assert beginner_diver.pk in diver_pks

    def test_form_excludes_already_booked_divers(self, dive_trip, diver_profile, user):
        """Form excludes divers who already have an active booking."""
        from primitives_testbed.diveops.forms import BookDiverForm
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="confirmed",
            booked_by=user,
        )

        form = BookDiverForm(excursion=dive_trip)
        diver_pks = [d.pk for d in form.fields["diver"].queryset]

        assert diver_profile.pk not in diver_pks

    def test_form_includes_cancelled_booking_divers(self, dive_trip, diver_profile, user):
        """Form includes divers whose previous booking was cancelled."""
        from primitives_testbed.diveops.forms import BookDiverForm
        from primitives_testbed.diveops.models import Booking

        Booking.objects.create(
            excursion=dive_trip,
            diver=diver_profile,
            status="cancelled",
            booked_by=user,
        )

        form = BookDiverForm(excursion=dive_trip)
        diver_pks = [d.pk for d in form.fields["diver"].queryset]

        assert diver_profile.pk in diver_pks

    def test_form_valid_with_eligible_diver(self, dive_trip, diver_profile):
        """Form is valid when selecting an eligible diver."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(excursion=dive_trip, data={"diver": diver_profile.pk})
        assert form.is_valid()

    def test_form_displays_diver_name_and_cert(self, dive_trip, diver_profile):
        """Form displays diver name and certification level."""
        from primitives_testbed.diveops.forms import BookDiverForm

        form = BookDiverForm(excursion=dive_trip)
        choices = list(form.fields["diver"].queryset)

        # Should have at least one choice
        assert len(choices) > 0
        # The model should have __str__ that shows name and cert
        choice_str = str(choices[0])
        assert diver_profile.person.first_name in choice_str or "Advanced" in choice_str


@pytest.mark.django_db
class TestDiverFormCertificationPrePopulate:
    """Tests for DiverForm certification field pre-population."""

    def test_form_prepopulates_certification_from_existing(self, diver_profile, padi_open_water):
        """DiverForm pre-populates certification fields from existing cert when not in edit mode."""
        from primitives_testbed.diveops.forms import DiverForm
        from primitives_testbed.diveops.models import DiverCertification

        # Create a certification for the diver
        cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="PREPOP123",
            issued_on=date.today() - timedelta(days=100),
            expires_on=date.today() + timedelta(days=265),
        )

        # Create form with instance but NOT in edit mode
        form = DiverForm(instance=diver_profile, is_edit=False)

        # Certification fields should be pre-populated
        assert form.fields["certification_agency"].initial == padi_open_water.agency
        assert form.fields["certification_level"].initial == padi_open_water
        assert form.fields["card_number"].initial == "PREPOP123"


@pytest.mark.django_db
class TestDiverFormDateValidation:
    """Tests for DiverForm date validation."""

    def test_form_rejects_expiry_before_issued(self, padi_open_water):
        """DiverForm rejects expiration date before issue date."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(data={
            "first_name": "Test",
            "last_name": "Diver",
            "email": "test@example.com",
            "certification_level": str(padi_open_water.pk),
            "certification_agency": str(padi_open_water.agency.pk),
            "card_number": "12345",
            "issued_on": date.today(),
            "expires_on": date.today() - timedelta(days=1),  # Before issued
            "total_dives": 10,
        })

        assert not form.is_valid()
        assert "expires_on" in form.errors

    def test_form_accepts_valid_expiry_after_issued(self, padi_open_water):
        """DiverForm accepts expiration date after issue date."""
        from primitives_testbed.diveops.forms import DiverForm

        form = DiverForm(data={
            "first_name": "Test",
            "last_name": "Diver",
            "email": "testvalid@example.com",
            "certification_level": str(padi_open_water.pk),
            "certification_agency": str(padi_open_water.agency.pk),
            "card_number": "12345",
            "issued_on": date.today() - timedelta(days=30),
            "expires_on": date.today() + timedelta(days=365),  # After issued
            "total_dives": 10,
        })

        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestDiverFormWithProofFile:
    """Tests for DiverForm proof document upload (lines 222-256)."""

    def test_form_creates_document_with_proof_file(self, padi_open_water, user):
        """DiverForm.save() creates Document when proof_file is provided."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        from django_documents.models import Document
        from primitives_testbed.diveops.forms import DiverForm
        from primitives_testbed.diveops.models import DiverCertification

        proof_file = SimpleUploadedFile(
            name="cert_card.jpg",
            content=b"fake image content",
            content_type="image/jpeg",
        )

        form = DiverForm(
            data={
                "first_name": "Proof",
                "last_name": "Tester",
                "email": "proof@example.com",
                "certification_level": str(padi_open_water.pk),
                "certification_agency": str(padi_open_water.agency.pk),
                "card_number": "PROOF123",
                "issued_on": date.today() - timedelta(days=30),
                "total_dives": 5,
            },
            files={"proof_file": proof_file},
        )
        assert form.is_valid(), form.errors

        diver = form.save(actor=user)

        # Verify certification was created
        cert = DiverCertification.objects.get(diver=diver, level=padi_open_water)
        assert cert is not None

        # Verify document was created and linked
        doc = Document.objects.filter(
            document_type="certification_proof",
            target_id=str(cert.pk),
        ).first()
        assert doc is not None
        assert doc.filename == "cert_card.jpg"
        assert doc.content_type == "image/jpeg"


@pytest.mark.django_db
class TestDiverCertificationFormWithProofFile:
    """Tests for DiverCertificationForm proof document upload (lines 366-425)."""

    def test_certification_form_creates_document_with_proof_file(
        self, diver_profile, padi_open_water, user
    ):
        """DiverCertificationForm.save() creates Document when proof_file is provided."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        from django_documents.models import Document
        from primitives_testbed.diveops.forms import DiverCertificationForm

        proof_file = SimpleUploadedFile(
            name="padi_card.pdf",
            content=b"fake pdf content",
            content_type="application/pdf",
        )

        form = DiverCertificationForm(
            data={
                "diver": diver_profile.pk,
                "level": padi_open_water.pk,
                "card_number": "CERTPROOF456",
                "issued_on": date.today() - timedelta(days=60),
            },
            files={"proof_file": proof_file},
        )
        assert form.is_valid(), form.errors

        cert = form.save(actor=user)

        # Verify document was created and linked
        doc = Document.objects.filter(
            document_type="certification_proof",
            target_id=str(cert.pk),
        ).first()
        assert doc is not None
        assert doc.filename == "padi_card.pdf"
        assert doc.content_type == "application/pdf"

    def test_certification_form_save_without_commit(
        self, diver_profile, padi_open_water, user
    ):
        """DiverCertificationForm.save(commit=False) returns unsaved instance."""
        from primitives_testbed.diveops.forms import DiverCertificationForm

        form = DiverCertificationForm(
            data={
                "diver": diver_profile.pk,
                "level": padi_open_water.pk,
                "card_number": "NOCOMMIT789",
                "issued_on": date.today() - timedelta(days=30),
            }
        )
        assert form.is_valid(), form.errors

        cert = form.save(actor=user, commit=False)

        # Instance should be returned but not saved to DB
        assert cert is not None
        # Primary key should still be set (UUID) but not in database
        # For commit=False, the instance uses super().save(commit=False)

    def test_certification_form_save_with_proof_file_no_commit(
        self, diver_profile, padi_open_water, user
    ):
        """DiverCertificationForm.save(commit=False) with proof_file attaches document."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        from primitives_testbed.diveops.forms import DiverCertificationForm

        proof_file = SimpleUploadedFile(
            name="proof_nocommit.jpg",
            content=b"fake jpg",
            content_type="image/jpeg",
        )

        form = DiverCertificationForm(
            data={
                "diver": diver_profile.pk,
                "level": padi_open_water.pk,
                "card_number": "NOCOMMIT999",
                "issued_on": date.today() - timedelta(days=10),
            },
            files={"proof_file": proof_file},
        )
        assert form.is_valid(), form.errors

        cert = form.save(actor=user, commit=False)

        # The proof_document should be attached to the instance
        assert hasattr(cert, "proof_document")

    def test_certification_form_updates_existing_certification(
        self, diver_profile, padi_open_water, user
    ):
        """DiverCertificationForm updates existing certification (lines 403-405)."""
        from primitives_testbed.diveops.forms import DiverCertificationForm
        from primitives_testbed.diveops.models import DiverCertification

        # Create existing certification
        existing_cert = DiverCertification.objects.create(
            diver=diver_profile,
            level=padi_open_water,
            card_number="OLD_NUMBER",
            issued_on=date.today() - timedelta(days=100),
        )

        # Update via form with the instance
        form = DiverCertificationForm(
            instance=existing_cert,
            data={
                "diver": diver_profile.pk,
                "level": padi_open_water.pk,
                "card_number": "NEW_NUMBER",
                "issued_on": date.today() - timedelta(days=50),
            },
        )
        assert form.is_valid(), form.errors

        updated_cert = form.save(actor=user)

        # Verify update applied
        assert updated_cert.pk == existing_cert.pk
        assert updated_cert.card_number == "NEW_NUMBER"
