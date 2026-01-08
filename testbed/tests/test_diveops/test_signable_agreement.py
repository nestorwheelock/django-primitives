"""TDD tests for SignableAgreement model and constraints.

These tests verify the PostgreSQL constraints and model behavior
for the signable agreement workflow system.
"""

import hashlib
import secrets
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def dive_shop(db):
    """Create a test dive shop (Organization)."""
    from django_parties.models import Organization

    return Organization.objects.create(name="Test Dive Shop")


@pytest.fixture
def agreement_template(db, dive_shop):
    """Create a test agreement template."""
    from primitives_testbed.diveops.models import AgreementTemplate

    return AgreementTemplate.objects.create(
        dive_shop=dive_shop,
        name="Test Waiver",
        template_type="waiver",
        content="<p>Test content</p>",
        status="published",
    )


@pytest.fixture
def party(db):
    """Create a test party (Person - inherits from abstract Party)."""
    from django_parties.models import Person

    # Person inherits from Party (abstract base)
    return Person.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing."""
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.mark.django_db
class TestSignableAgreementConstraints:
    """Test PostgreSQL constraints on SignableAgreement model."""

    def test_signed_requires_signed_at(self, agreement_template, party):
        """Cannot set status=signed without signed_at timestamp."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Create valid agreement with required fields
        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="signed",  # Setting signed but no signed_at
            sent_at=timezone.now(),
            access_token_hash="a" * 64,
            # ledger_agreement not set - will also fail constraint
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        # Should fail on signed_requires_signed_at or signed_requires_ledger
        assert "signable_" in str(exc_info.value).lower()

    def test_sent_requires_sent_at(self, agreement_template, party):
        """Cannot set status=sent without sent_at timestamp."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="sent",  # Setting sent but no sent_at
            access_token_hash="a" * 64,
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_sent_requires_sent_at" in str(exc_info.value).lower()

    def test_sent_signed_requires_token(self, agreement_template, party):
        """Cannot set status=sent or signed without access_token_hash."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="sent",
            sent_at=timezone.now(),
            access_token_hash="",  # Empty - should fail
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_sent_signed_requires_token" in str(exc_info.value).lower()

    def test_valid_content_hash(self, agreement_template, party):
        """content_hash must be valid 64 character hex string."""
        from primitives_testbed.diveops.models import SignableAgreement

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot="<p>Test</p>",
            content_hash="invalid",  # Not 64 hex chars
            status="draft",
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_valid_content_hash" in str(exc_info.value).lower()

    def test_unique_pending_per_party_object(self, agreement_template, party):
        """Only one pending agreement per template+party+related_object."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Create first draft
        SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="draft",
        )

        # Attempt to create duplicate pending (same template+party, no related_object)
        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                SignableAgreement.objects.create(
                    template=agreement_template,
                    template_version="1.0",
                    party_a=party,
                    content_snapshot=content,
                    content_hash=content_hash,
                    status="draft",
                )

        assert "signable_unique_pending_per_party_object" in str(exc_info.value).lower()

    def test_signed_requires_terms_consent(self, agreement_template, party, staff_user):
        """Cannot set status=signed without agreed_to_terms=True."""
        from django_agreements.services import create_agreement as create_ledger_agreement
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Create ledger agreement for the constraint
        dive_shop = Organization.objects.create(name="Ledger Shop")
        ledger = create_ledger_agreement(
            party_a=party,
            party_b=dive_shop,
            scope_type="waiver",
            terms={"test": "data"},
            agreed_by=staff_user,
            valid_from=timezone.now(),
        )

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="signed",
            sent_at=timezone.now(),
            signed_at=timezone.now(),
            signed_by_name="Test Signer",
            signed_ip="192.168.1.1",
            signed_user_agent="Mozilla/5.0",
            access_token_hash="a" * 64,
            ledger_agreement=ledger,
            agreed_to_terms=False,  # Missing consent - should fail
            agreed_to_esign=True,
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_signed_requires_terms_consent" in str(exc_info.value).lower()

    def test_signed_requires_esign_consent(self, agreement_template, party, staff_user):
        """Cannot set status=signed without agreed_to_esign=True."""
        from django_agreements.services import create_agreement as create_ledger_agreement
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Create ledger agreement for the constraint
        dive_shop = Organization.objects.create(name="Ledger Shop 2")
        ledger = create_ledger_agreement(
            party_a=party,
            party_b=dive_shop,
            scope_type="waiver",
            terms={"test": "data"},
            agreed_by=staff_user,
            valid_from=timezone.now(),
        )

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="signed",
            sent_at=timezone.now(),
            signed_at=timezone.now(),
            signed_by_name="Test Signer",
            signed_ip="192.168.1.1",
            signed_user_agent="Mozilla/5.0",
            access_token_hash="a" * 64,
            ledger_agreement=ledger,
            agreed_to_terms=True,
            agreed_to_esign=False,  # Missing consent - should fail
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_signed_requires_esign_consent" in str(exc_info.value).lower()

    def test_signed_requires_ip_address(self, agreement_template, party, staff_user):
        """Cannot set status=signed without signed_ip."""
        from django_agreements.services import create_agreement as create_ledger_agreement
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        dive_shop = Organization.objects.create(name="IP Test Shop")
        ledger = create_ledger_agreement(
            party_a=party,
            party_b=dive_shop,
            scope_type="waiver",
            terms={"test": "data"},
            agreed_by=staff_user,
            valid_from=timezone.now(),
        )

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="signed",
            sent_at=timezone.now(),
            signed_at=timezone.now(),
            signed_by_name="Test Signer",
            signed_ip=None,  # Missing IP - should fail
            signed_user_agent="Mozilla/5.0",
            access_token_hash="a" * 64,
            ledger_agreement=ledger,
            agreed_to_terms=True,
            agreed_to_esign=True,
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_signed_requires_ip" in str(exc_info.value).lower()

    def test_signed_requires_user_agent(self, agreement_template, party, staff_user):
        """Cannot set status=signed without signed_user_agent."""
        from django_agreements.services import create_agreement as create_ledger_agreement
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        dive_shop = Organization.objects.create(name="UA Test Shop")
        ledger = create_ledger_agreement(
            party_a=party,
            party_b=dive_shop,
            scope_type="waiver",
            terms={"test": "data"},
            agreed_by=staff_user,
            valid_from=timezone.now(),
        )

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="signed",
            sent_at=timezone.now(),
            signed_at=timezone.now(),
            signed_by_name="Test Signer",
            signed_ip="192.168.1.1",
            signed_user_agent="",  # Empty user agent - should fail
            access_token_hash="a" * 64,
            ledger_agreement=ledger,
            agreed_to_terms=True,
            agreed_to_esign=True,
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_signed_requires_user_agent" in str(exc_info.value).lower()

    def test_signed_requires_signer_name(self, agreement_template, party, staff_user):
        """Cannot set status=signed without signed_by_name."""
        from django_agreements.services import create_agreement as create_ledger_agreement
        from django_parties.models import Organization
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        dive_shop = Organization.objects.create(name="Name Test Shop")
        ledger = create_ledger_agreement(
            party_a=party,
            party_b=dive_shop,
            scope_type="waiver",
            terms={"test": "data"},
            agreed_by=staff_user,
            valid_from=timezone.now(),
        )

        agreement = SignableAgreement(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="signed",
            sent_at=timezone.now(),
            signed_at=timezone.now(),
            signed_by_name="",  # Empty name - should fail
            signed_ip="192.168.1.1",
            signed_user_agent="Mozilla/5.0",
            access_token_hash="a" * 64,
            ledger_agreement=ledger,
            agreed_to_terms=True,
            agreed_to_esign=True,
        )

        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                agreement.save()

        assert "signable_signed_requires_signer_name" in str(exc_info.value).lower()


@pytest.mark.django_db
class TestSignableAgreementTokenSecurity:
    """Test token generation and hashing security."""

    def test_token_generation_is_cryptographically_random(self):
        """Token generation uses secrets module."""
        from primitives_testbed.diveops.models import SignableAgreement

        tokens = set()
        for _ in range(100):
            token, _ = SignableAgreement.generate_token()
            # Token should be URL-safe base64
            assert all(c.isalnum() or c in "-_" for c in token)
            tokens.add(token)

        # All 100 tokens should be unique
        assert len(tokens) == 100

    def test_token_hash_storage(self, agreement_template, party):
        """Raw token is never stored, only hash."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        token, token_hash = SignableAgreement.generate_token()

        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="sent",
            sent_at=timezone.now(),
            access_token_hash=token_hash,
        )

        # Refresh from DB
        agreement.refresh_from_db()

        # Raw token is NOT stored anywhere on the model
        assert token not in str(agreement.__dict__)
        assert agreement.access_token_hash == token_hash
        assert agreement.access_token_hash != token

    def test_token_verification(self, agreement_template, party):
        """verify_token correctly validates token hash."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        token, token_hash = SignableAgreement.generate_token()

        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="sent",
            sent_at=timezone.now(),
            access_token_hash=token_hash,
        )

        # Valid token should verify
        assert agreement.verify_token(token) is True

        # Invalid token should not verify
        assert agreement.verify_token("wrong-token") is False

    def test_token_consumed_after_signing(self, agreement_template, party):
        """Token cannot be reused after consumed flag is set."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        token, token_hash = SignableAgreement.generate_token()

        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="sent",
            sent_at=timezone.now(),
            access_token_hash=token_hash,
            token_consumed=False,
        )

        # Token valid before consumed
        assert agreement.verify_token(token) is True

        # Mark as consumed
        agreement.token_consumed = True
        agreement.save()

        # Token no longer valid
        assert agreement.verify_token(token) is False


@pytest.mark.django_db
class TestSignableAgreementRevision:
    """Test SignableAgreementRevision model for edit history."""

    def test_revision_requires_change_note(self, agreement_template, party, staff_user):
        """Cannot create revision without change_note."""
        from primitives_testbed.diveops.models import (
            SignableAgreement,
            SignableAgreementRevision,
        )

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="draft",
        )

        # Try to create revision without change_note
        with pytest.raises(IntegrityError) as exc_info:
            with transaction.atomic():
                SignableAgreementRevision.objects.create(
                    agreement=agreement,
                    revision_number=1,
                    previous_content_hash=content_hash,
                    new_content_hash="b" * 64,
                    change_note="",  # Empty - should fail
                    changed_by=staff_user,
                )

        assert "revision_requires_change_note" in str(exc_info.value).lower()

    def test_revision_tracks_content_changes(self, agreement_template, party, staff_user):
        """Revision stores hash transitions and change notes."""
        from primitives_testbed.diveops.models import (
            SignableAgreement,
            SignableAgreementRevision,
        )

        content = "<p>Original content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="draft",
        )

        new_content = "<p>Updated content</p>"
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()

        revision = SignableAgreementRevision.objects.create(
            agreement=agreement,
            revision_number=1,
            previous_content_hash=content_hash,
            new_content_hash=new_hash,
            change_note="Updated legal clause per legal review",
            changed_by=staff_user,
        )

        assert revision.agreement == agreement
        assert revision.revision_number == 1
        assert revision.previous_content_hash == content_hash
        assert revision.new_content_hash == new_hash
        assert "legal" in revision.change_note.lower()
        assert revision.changed_by == staff_user


@pytest.mark.django_db
class TestSignableAgreementDraftCreation:
    """Test creating draft SignableAgreement instances."""

    def test_create_draft_agreement(self, agreement_template, party):
        """Can create a draft agreement with valid data."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test waiver content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="draft",
        )

        assert agreement.pk is not None
        assert agreement.status == "draft"
        assert agreement.template == agreement_template
        assert agreement.party_a == party
        assert agreement.content_hash == content_hash

    def test_draft_does_not_require_token(self, agreement_template, party):
        """Draft status does not require access_token_hash."""
        from primitives_testbed.diveops.models import SignableAgreement

        content = "<p>Test content</p>"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Draft with empty token should succeed
        agreement = SignableAgreement.objects.create(
            template=agreement_template,
            template_version="1.0",
            party_a=party,
            content_snapshot=content,
            content_hash=content_hash,
            status="draft",
            access_token_hash="",  # Empty is OK for draft
        )

        assert agreement.pk is not None
        assert agreement.access_token_hash == ""
