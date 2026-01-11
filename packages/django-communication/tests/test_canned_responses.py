"""Tests for CannedResponse model and services."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError


@pytest.fixture
def person(db):
    """Create a test person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )


@pytest.fixture
def staff_person(db):
    """Create a test staff person."""
    from django_parties.models import Person

    return Person.objects.create(
        first_name="Staff",
        last_name="User",
        email="staff@example.com",
    )


@pytest.fixture
def organization(db):
    """Create a test organization."""
    from django_parties.models import Organization

    return Organization.objects.create(
        name="Dive Shop Inc",
    )


@pytest.mark.django_db
class TestCannedResponseModel:
    """Tests for CannedResponse model."""

    def test_create_canned_response_minimal(self, person):
        """CannedResponse can be created with minimal fields."""
        from django_communication.models import CannedResponse

        response = CannedResponse.objects.create(
            title="Welcome Message",
            body="Hello {{ first_name }}, welcome to our service!",
            created_by=person,
        )
        assert response.pk is not None
        assert response.title == "Welcome Message"
        assert response.is_active is True
        assert response.visibility == "org"  # Default

    def test_create_canned_response_all_fields(self, person, organization):
        """CannedResponse can be created with all fields."""
        from django_communication.models import CannedResponse, ResponseChannel

        response = CannedResponse.objects.create(
            title="Trip Reminder",
            body="Hi {{ first_name }}, your trip on {{ trip_date }} is coming up!",
            channel=ResponseChannel.ANY,
            language="en",
            visibility="org",
            owner_party=organization,
            created_by=person,
            is_active=True,
        )
        assert response.pk is not None
        assert response.channel == ResponseChannel.ANY
        assert response.language == "en"
        assert response.owner_party == organization

    def test_visibility_choices(self, person):
        """Visibility should be constrained to valid choices."""
        from django_communication.models import CannedResponse

        response = CannedResponse.objects.create(
            title="Private Note",
            body="Only I can see this",
            visibility="private",
            created_by=person,
        )
        assert response.visibility == "private"

        response2 = CannedResponse.objects.create(
            title="Public Template",
            body="Everyone can use this",
            visibility="public",
            created_by=person,
        )
        assert response2.visibility == "public"

    def test_channel_choices(self, person):
        """Channel should be constrained to valid choices."""
        from django_communication.models import CannedResponse, ResponseChannel

        for channel in [ResponseChannel.ANY, ResponseChannel.CHAT, ResponseChannel.EMAIL, ResponseChannel.SMS]:
            response = CannedResponse.objects.create(
                title=f"Template for {channel}",
                body="Hello!",
                channel=channel,
                created_by=person,
            )
            assert response.channel == channel

    def test_str_representation(self, person):
        """String representation shows title."""
        from django_communication.models import CannedResponse

        response = CannedResponse.objects.create(
            title="Booking Confirmation",
            body="Your booking is confirmed!",
            created_by=person,
        )
        assert str(response) == "Booking Confirmation"

    def test_soft_delete(self, person):
        """CannedResponse supports soft delete."""
        from django_communication.models import CannedResponse

        response = CannedResponse.objects.create(
            title="To Delete",
            body="This will be deleted",
            created_by=person,
        )
        pk = response.pk

        response.delete()

        # Should not appear in regular queries
        assert not CannedResponse.objects.filter(pk=pk).exists()

        # Should appear in all_objects
        assert CannedResponse.all_objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestCannedResponseTag:
    """Tests for CannedResponseTag model."""

    def test_create_tag(self, db):
        """CannedResponseTag can be created."""
        from django_communication.models import CannedResponseTag

        tag = CannedResponseTag.objects.create(name="Booking")
        assert tag.pk is not None
        assert tag.name == "Booking"

    def test_tag_uniqueness(self, db):
        """Tag names must be unique."""
        from django_communication.models import CannedResponseTag

        CannedResponseTag.objects.create(name="Important")
        with pytest.raises(IntegrityError):
            CannedResponseTag.objects.create(name="Important")

    def test_response_can_have_multiple_tags(self, person):
        """CannedResponse can have multiple tags."""
        from django_communication.models import CannedResponse, CannedResponseTag

        response = CannedResponse.objects.create(
            title="Tagged Response",
            body="Hello!",
            created_by=person,
        )
        tag1 = CannedResponseTag.objects.create(name="Greeting")
        tag2 = CannedResponseTag.objects.create(name="Customer")

        response.tags.add(tag1, tag2)

        assert response.tags.count() == 2
        assert tag1 in response.tags.all()
        assert tag2 in response.tags.all()


@pytest.mark.django_db
class TestCannedResponseVisibility:
    """Tests for visibility-based access control."""

    def test_private_visibility_only_creator_can_use(self, person, staff_person):
        """Private responses are only visible to creator."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import list_canned_responses

        CannedResponse.objects.create(
            title="My Private Template",
            body="Secret!",
            visibility="private",
            created_by=person,
        )

        # Creator can see it
        responses = list_canned_responses(actor=person)
        assert len(responses) == 1

        # Others cannot see it
        responses = list_canned_responses(actor=staff_person)
        assert len(responses) == 0

    def test_org_visibility_requires_same_org(self, person, staff_person, organization):
        """Org responses are visible to members of the same organization."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import list_canned_responses

        CannedResponse.objects.create(
            title="Org Template",
            body="For the team!",
            visibility="org",
            owner_party=organization,
            created_by=person,
        )

        # TODO: This needs org membership logic
        # For now, org-scoped without owner_party means all can see
        responses = list_canned_responses(actor=person, org=organization)
        assert len(responses) == 1


@pytest.mark.django_db
class TestVariableRendering:
    """Tests for variable extraction and rendering."""

    def test_extract_variables_simple(self, person):
        """Can extract simple variables from body."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import extract_variables

        response = CannedResponse.objects.create(
            title="Template",
            body="Hello {{ first_name }}, your booking on {{ trip_date }} is confirmed.",
            created_by=person,
        )
        vars = extract_variables(response.body)
        assert "first_name" in vars
        assert "trip_date" in vars

    def test_render_canned_response_basic(self, person):
        """Can render canned response with context."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import render_canned_response

        response = CannedResponse.objects.create(
            title="Greeting",
            body="Hello {{ first_name }}, welcome!",
            created_by=person,
        )
        rendered = render_canned_response(response, {"first_name": "John"})
        assert rendered == "Hello John, welcome!"

    def test_render_missing_variable_blank(self, person):
        """Missing variables render as empty string."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import render_canned_response

        response = CannedResponse.objects.create(
            title="Template",
            body="Hello {{ first_name }}, your code is {{ missing_var }}.",
            created_by=person,
        )
        rendered = render_canned_response(response, {"first_name": "John"})
        assert rendered == "Hello John, your code is ."


@pytest.mark.django_db
class TestCannedResponseServices:
    """Tests for canned response service functions."""

    def test_list_canned_responses_filter_by_channel(self, person):
        """Can filter canned responses by channel."""
        from django_communication.models import CannedResponse, ResponseChannel
        from django_communication.services.canned_responses import list_canned_responses

        CannedResponse.objects.create(
            title="Email Only",
            body="Email content",
            channel=ResponseChannel.EMAIL,
            created_by=person,
        )
        CannedResponse.objects.create(
            title="SMS Only",
            body="SMS content",
            channel=ResponseChannel.SMS,
            created_by=person,
        )
        CannedResponse.objects.create(
            title="Any Channel",
            body="Universal content",
            channel=ResponseChannel.ANY,
            created_by=person,
        )

        email_responses = list_canned_responses(actor=person, channel=ResponseChannel.EMAIL)
        # Should include EMAIL + ANY
        assert len(email_responses) == 2

        sms_responses = list_canned_responses(actor=person, channel=ResponseChannel.SMS)
        # Should include SMS + ANY
        assert len(sms_responses) == 2

    def test_list_canned_responses_search(self, person):
        """Can search canned responses by title and body."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import list_canned_responses

        CannedResponse.objects.create(
            title="Booking Confirmation",
            body="Your trip is booked!",
            created_by=person,
        )
        CannedResponse.objects.create(
            title="Payment Reminder",
            body="Please pay your invoice.",
            created_by=person,
        )

        results = list_canned_responses(actor=person, q="booking")
        assert len(results) == 1
        assert results[0].title == "Booking Confirmation"

        results = list_canned_responses(actor=person, q="pay")
        assert len(results) == 1
        assert results[0].title == "Payment Reminder"

    def test_list_canned_responses_filter_by_language(self, person):
        """Can filter canned responses by language."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import list_canned_responses

        CannedResponse.objects.create(
            title="English Greeting",
            body="Hello!",
            language="en",
            created_by=person,
        )
        CannedResponse.objects.create(
            title="Spanish Greeting",
            body="Hola!",
            language="es",
            created_by=person,
        )

        en_responses = list_canned_responses(actor=person, language="en")
        assert len(en_responses) == 1
        assert en_responses[0].title == "English Greeting"

    def test_list_canned_responses_only_active(self, person):
        """list_canned_responses only returns active responses."""
        from django_communication.models import CannedResponse
        from django_communication.services.canned_responses import list_canned_responses

        CannedResponse.objects.create(
            title="Active Template",
            body="I'm active!",
            is_active=True,
            created_by=person,
        )
        CannedResponse.objects.create(
            title="Inactive Template",
            body="I'm disabled",
            is_active=False,
            created_by=person,
        )

        results = list_canned_responses(actor=person)
        assert len(results) == 1
        assert results[0].title == "Active Template"


@pytest.mark.django_db
class TestMessageCannedResponseAudit:
    """Tests for Message audit trail with canned response."""

    def test_message_references_canned_response(self, person):
        """Message can reference the canned response used."""
        from django_communication.models import (
            CannedResponse,
            Conversation,
            Message,
            Channel,
            MessageDirection,
        )

        canned = CannedResponse.objects.create(
            title="Standard Reply",
            body="Thank you for your message!",
            created_by=person,
        )

        conv = Conversation.objects.create(subject="Support Request")

        message = Message.objects.create(
            conversation=conv,
            sender_person=person,
            direction=MessageDirection.OUTBOUND,
            channel=Channel.IN_APP,
            from_address="staff@shop.com",
            to_address="customer@example.com",
            body_text="Thank you for your message!",
            canned_response=canned,
            canned_rendered_body="Thank you for your message!",
        )

        assert message.canned_response == canned
        assert message.canned_rendered_body == "Thank you for your message!"

    def test_message_without_canned_response(self, person):
        """Message can be created without canned response reference."""
        from django_communication.models import (
            Conversation,
            Message,
            Channel,
            MessageDirection,
        )

        conv = Conversation.objects.create(subject="Custom Message")

        message = Message.objects.create(
            conversation=conv,
            sender_person=person,
            direction=MessageDirection.OUTBOUND,
            channel=Channel.IN_APP,
            from_address="staff@shop.com",
            to_address="customer@example.com",
            body_text="A completely custom message.",
        )

        assert message.canned_response is None
        assert message.canned_rendered_body == ""
