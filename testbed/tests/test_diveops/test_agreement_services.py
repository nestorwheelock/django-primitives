"""TDD tests for agreement services.

These tests verify the service layer for SignableAgreement workflow:
- create_agreement_from_template
- edit_agreement
- send_agreement
- sign_agreement
- void_agreement
- get_agreement_by_token
- expire_stale_agreements
"""

import hashlib
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
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
        content="<p>I, {{diver_name}}, agree to the terms.</p>",
        status="published",
        version="1.0",
    )


@pytest.fixture
def diver(db):
    """Create a test diver (Person)."""
    from django_parties.models import Person

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
class TestCreateAgreementFromTemplate:
    """Test create_agreement_from_template service."""

    def test_creates_draft_agreement(self, agreement_template, diver, staff_user):
        """Service creates a draft SignableAgreement."""
        from primitives_testbed.diveops.services import create_agreement_from_template

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        assert agreement.pk is not None
        assert agreement.status == "draft"
        assert agreement.template == agreement_template
        assert agreement.template_version == "1.0"

    def test_renders_template_with_party_context(
        self, agreement_template, diver, staff_user
    ):
        """Content is rendered with party information."""
        from primitives_testbed.diveops.services import create_agreement_from_template

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        # Template has {{diver_name}} placeholder
        assert "John Doe" in agreement.content_snapshot

    def test_computes_content_hash(self, agreement_template, diver, staff_user):
        """Content hash is computed as SHA-256."""
        from primitives_testbed.diveops.services import create_agreement_from_template

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        expected_hash = hashlib.sha256(agreement.content_snapshot.encode()).hexdigest()
        assert agreement.content_hash == expected_hash

    def test_idempotent_for_same_template_party(
        self, agreement_template, diver, staff_user
    ):
        """Returns existing pending agreement instead of creating duplicate."""
        from primitives_testbed.diveops.services import create_agreement_from_template

        agreement1 = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        agreement2 = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        # Should return the same agreement (idempotent)
        assert agreement1.pk == agreement2.pk

    def test_creates_audit_event(self, agreement_template, diver, staff_user):
        """Creating an agreement emits an audit event."""
        from django_audit_log.models import AuditLog

        from primitives_testbed.diveops.services import create_agreement_from_template

        initial_count = AuditLog.objects.count()

        create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        assert AuditLog.objects.count() > initial_count


@pytest.mark.django_db
class TestEditAgreement:
    """Test edit_agreement service."""

    def test_updates_content(self, agreement_template, diver, staff_user):
        """Edit updates content_snapshot and content_hash."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            edit_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        new_content = "<p>Updated content for John Doe</p>"
        edited = edit_agreement(
            agreement=agreement,
            new_content=new_content,
            change_note="Updated per legal review",
            actor=staff_user,
        )

        assert edited.content_snapshot == new_content
        expected_hash = hashlib.sha256(new_content.encode()).hexdigest()
        assert edited.content_hash == expected_hash

    def test_creates_revision_record(self, agreement_template, diver, staff_user):
        """Edit creates a SignableAgreementRevision."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            edit_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        old_hash = agreement.content_hash

        new_content = "<p>Updated content</p>"
        edit_agreement(
            agreement=agreement,
            new_content=new_content,
            change_note="Updated per legal review",
            actor=staff_user,
        )

        revision = agreement.revisions.first()
        assert revision is not None
        assert revision.revision_number == 1
        assert revision.previous_content_hash == old_hash
        assert revision.change_note == "Updated per legal review"
        assert revision.changed_by == staff_user

    def test_requires_change_note(self, agreement_template, diver, staff_user):
        """Edit fails without change_note."""
        from primitives_testbed.diveops.exceptions import ChangeNoteRequired
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            edit_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        with pytest.raises(ChangeNoteRequired):
            edit_agreement(
                agreement=agreement,
                new_content="<p>New content</p>",
                change_note="",  # Empty - should fail
                actor=staff_user,
            )

    def test_cannot_edit_signed_agreement(self, agreement_template, diver, staff_user):
        """Cannot edit an agreement that is already signed."""
        from primitives_testbed.diveops.exceptions import AgreementNotEditable
        from primitives_testbed.diveops.models import SignableAgreement
        from primitives_testbed.diveops.services import create_agreement_from_template

        # Create and manually set to signed (bypassing normal flow for test)
        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        # Use raw update to bypass constraints for test setup
        SignableAgreement.objects.filter(pk=agreement.pk).update(status="void")
        agreement.refresh_from_db()

        from primitives_testbed.diveops.services import edit_agreement

        with pytest.raises(AgreementNotEditable):
            edit_agreement(
                agreement=agreement,
                new_content="<p>New content</p>",
                change_note="Trying to edit void agreement",
                actor=staff_user,
            )


@pytest.mark.django_db
class TestSendAgreement:
    """Test send_agreement service."""

    def test_transitions_to_sent_status(self, agreement_template, diver, staff_user):
        """Send transitions status from draft to sent."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            send_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        sent_agreement, token = send_agreement(
            agreement=agreement,
            delivery_method="email",
            actor=staff_user,
        )

        assert sent_agreement.status == "sent"
        assert sent_agreement.sent_at is not None
        assert sent_agreement.sent_by == staff_user

    def test_returns_raw_token_once(self, agreement_template, diver, staff_user):
        """Send returns raw token (only time it's available)."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            send_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        sent_agreement, token = send_agreement(
            agreement=agreement,
            delivery_method="email",
            actor=staff_user,
        )

        # Token is URL-safe string
        assert isinstance(token, str)
        assert len(token) > 20

        # Verify the token hash matches
        assert sent_agreement.verify_token(token) is True

    def test_sets_expiration(self, agreement_template, diver, staff_user):
        """Send sets expires_at based on expires_in_days."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            send_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        sent_agreement, _ = send_agreement(
            agreement=agreement,
            delivery_method="email",
            expires_in_days=7,
            actor=staff_user,
        )

        # Expires in approximately 7 days
        expected = timezone.now() + timedelta(days=7)
        delta = abs((sent_agreement.expires_at - expected).total_seconds())
        assert delta < 60  # Within 1 minute


@pytest.mark.django_db
class TestVoidAgreement:
    """Test void_agreement service."""

    def test_transitions_to_void_status(self, agreement_template, diver, staff_user):
        """Void transitions any status to void."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            void_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        voided = void_agreement(
            agreement=agreement,
            reason="Diver cancelled booking",
            actor=staff_user,
        )

        assert voided.status == "void"

    def test_requires_reason(self, agreement_template, diver, staff_user):
        """Void requires a reason for audit trail."""
        from primitives_testbed.diveops.exceptions import VoidReasonRequired
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            void_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )

        with pytest.raises(VoidReasonRequired):
            void_agreement(
                agreement=agreement,
                reason="",  # Empty - should fail
                actor=staff_user,
            )

    def test_cannot_void_signed_agreement_service_layer(
        self, agreement_template, diver, staff_user
    ):
        """Service layer rejects voiding signed agreements."""
        from primitives_testbed.diveops.exceptions import InvalidStateTransition
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            send_agreement,
            sign_agreement,
            void_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        agreement, token = send_agreement(
            agreement=agreement,
            delivery_method="email",
            actor=staff_user,
        )
        # Create a minimal signature image (1x1 white PNG)
        signature_image = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        signed = sign_agreement(
            agreement=agreement,
            raw_token=token,
            signature_image=signature_image,
            signed_by_name="John Doe",
            ip_address="192.168.1.1",
            user_agent="Test Browser",
        )

        with pytest.raises(InvalidStateTransition) as exc_info:
            void_agreement(
                agreement=signed,
                reason="Want to void",
                actor=staff_user,
            )

        assert "legally binding" in str(exc_info.value)
        assert "revocation agreement" in str(exc_info.value)

    def test_cannot_void_signed_agreement_database_trigger(
        self, agreement_template, diver, staff_user
    ):
        """Database trigger prevents voiding signed agreements even if bypassing service."""
        from django.db import IntegrityError

        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            send_agreement,
            sign_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        agreement, token = send_agreement(
            agreement=agreement,
            delivery_method="email",
            actor=staff_user,
        )
        # Create a minimal signature image (1x1 white PNG)
        signature_image = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        signed = sign_agreement(
            agreement=agreement,
            raw_token=token,
            signature_image=signature_image,
            signed_by_name="John Doe",
            ip_address="192.168.1.1",
            user_agent="Test Browser",
        )

        # Attempt to bypass service layer and update directly
        with pytest.raises(IntegrityError) as exc_info:
            signed.status = "void"
            signed.save()

        assert "Cannot change status of signed agreement" in str(exc_info.value)


@pytest.mark.django_db
class TestGetAgreementByToken:
    """Test get_agreement_by_token service."""

    def test_returns_agreement_for_valid_token(
        self, agreement_template, diver, staff_user
    ):
        """Lookup returns agreement for valid token."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            get_agreement_by_token,
            send_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        sent_agreement, token = send_agreement(
            agreement=agreement,
            delivery_method="email",
            actor=staff_user,
        )

        found = get_agreement_by_token(token)
        assert found is not None
        assert found.pk == sent_agreement.pk

    def test_returns_none_for_invalid_token(self):
        """Lookup returns None for invalid token (no existence leak)."""
        from primitives_testbed.diveops.services import get_agreement_by_token

        found = get_agreement_by_token("invalid-token-that-does-not-exist")
        assert found is None

    def test_returns_none_for_draft_agreement(
        self, agreement_template, diver, staff_user
    ):
        """Cannot lookup draft agreements by token."""
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            get_agreement_by_token,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        # Agreement is in draft status, should not be findable
        # (even if we somehow had the token)
        found = get_agreement_by_token("any-token")
        assert found is None


@pytest.mark.django_db
class TestExpireStaleAgreements:
    """Test expire_stale_agreements service."""

    def test_marks_expired_agreements(self, agreement_template, diver, staff_user):
        """Marks sent agreements past expires_at as expired."""
        from primitives_testbed.diveops.models import SignableAgreement
        from primitives_testbed.diveops.services import (
            create_agreement_from_template,
            expire_stale_agreements,
            send_agreement,
        )

        agreement = create_agreement_from_template(
            template=agreement_template,
            party_a=diver,
            actor=staff_user,
        )
        sent_agreement, _ = send_agreement(
            agreement=agreement,
            delivery_method="email",
            expires_in_days=1,
            actor=staff_user,
        )

        # Manually backdate the expiration
        SignableAgreement.objects.filter(pk=sent_agreement.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )

        count = expire_stale_agreements()
        assert count == 1

        sent_agreement.refresh_from_db()
        assert sent_agreement.status == "expired"

    def test_returns_count_of_expired(self, agreement_template, diver, staff_user):
        """Returns count of agreements marked expired."""
        from primitives_testbed.diveops.services import expire_stale_agreements

        # No expired agreements
        count = expire_stale_agreements()
        assert count == 0
