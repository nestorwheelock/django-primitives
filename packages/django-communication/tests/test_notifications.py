"""Tests for notification service with fallback ladder."""

import pytest
from unittest.mock import MagicMock, patch

from django_communication.models import (
    Channel,
    CommunicationSettings,
    Message,
    MessageStatus,
    PushSubscription,
)


@pytest.mark.django_db
class TestSendNotification:
    """Tests for send_notification fallback ladder."""

    @pytest.fixture
    def person(self, db):
        """Create a Person for testing."""
        from django_parties.models import Person

        return Person.objects.create(
            first_name="Test",
            last_name="User",
            email="testuser@example.com",
            phone="+15551234567",
        )

    @pytest.fixture
    def push_settings(self, db):
        """Create settings with push configured."""
        settings, _ = CommunicationSettings.objects.get_or_create(
            defaults={
                "push_enabled": True,
                "vapid_public_key": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "vapid_private_key": "xYmPh0VhN7cN3K4fUqDr-5cJjA5FPhMJTKKLR3pHqYE",
                "vapid_contact_email": "admin@example.com",
                "push_failure_threshold": 3,
                "notification_fallback_enabled": True,
                "email_provider": "console",
                "sms_provider": "console",
            }
        )
        return settings

    @pytest.fixture
    def push_subscription(self, person, db):
        """Create a push subscription for testing."""
        return PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/test123",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            is_active=True,
        )

    def test_send_notification_via_push_succeeds(self, push_settings, push_subscription, person):
        """Send notification successfully via push (first choice)."""
        from django_communication.services.notifications import send_notification

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            mock_webpush.return_value = MagicMock()

            message, channel_used = send_notification(
                person=person,
                subject="Test Notification",
                body_text="This is a test notification",
            )

            assert message is not None
            assert channel_used == "push"
            mock_webpush.assert_called_once()

    def test_send_notification_falls_back_to_email(self, push_settings, person):
        """Falls back to email when no push subscription exists."""
        from django_communication.services.notifications import send_notification

        # No push subscription, should fall back to email
        message, channel_used = send_notification(
            person=person,
            subject="Test Notification",
            body_text="This is a test notification",
        )

        assert message is not None
        assert channel_used == "email"
        assert message.channel == Channel.EMAIL

    def test_send_notification_falls_back_to_sms(self, push_settings, db):
        """Falls back to SMS when no push subscription and no email."""
        from django_parties.models import Person
        from django_communication.services.notifications import send_notification

        # Person with only phone, no email
        person_sms = Person.objects.create(
            first_name="SMS",
            last_name="Only",
            phone="+15559998888",
        )

        message, channel_used = send_notification(
            person=person_sms,
            subject="Test Notification",
            body_text="This is a test notification",
        )

        assert message is not None
        assert channel_used == "sms"
        assert message.channel == Channel.SMS

    def test_send_notification_push_fails_falls_back_to_email(
        self, push_settings, push_subscription, person
    ):
        """Falls back to email when push fails."""
        from django_communication.services.notifications import send_notification
        from pywebpush import WebPushException

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            error_response = MagicMock()
            error_response.status_code = 500
            mock_webpush.side_effect = WebPushException("Push failed", response=error_response)

            message, channel_used = send_notification(
                person=person,
                subject="Test Notification",
                body_text="This is a test notification",
            )

            assert message is not None
            assert channel_used == "email"

    def test_send_notification_no_fallback_when_disabled(self, push_settings, person):
        """Does not fall back when fallback is disabled."""
        from django_communication.services.notifications import send_notification

        push_settings.notification_fallback_enabled = False
        push_settings.save()

        # No push subscription and fallback disabled
        message, channel_used = send_notification(
            person=person,
            subject="Test Notification",
            body_text="This is a test notification",
        )

        assert message is None
        assert channel_used == "none"

    def test_send_notification_returns_none_when_no_channels(self, db):
        """Returns None when person has no contact methods."""
        from django_parties.models import Person
        from django_communication.services.notifications import send_notification

        # Person with no email, no phone
        person_empty = Person.objects.create(
            first_name="No",
            last_name="Contact",
        )

        # Get or create settings
        CommunicationSettings.objects.get_or_create()

        message, channel_used = send_notification(
            person=person_empty,
            subject="Test",
            body_text="Test",
        )

        assert message is None
        assert channel_used == "none"

    def test_send_notification_tries_all_push_subscriptions(
        self, push_settings, person
    ):
        """Tries all active push subscriptions before fallback."""
        from django_communication.services.notifications import send_notification
        from pywebpush import WebPushException

        # Create two push subscriptions
        PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/sub1",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            is_active=True,
        )
        PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/sub2",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            is_active=True,
        )

        call_count = 0

        def mock_push_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First subscription fails
                error_response = MagicMock()
                error_response.status_code = 500
                raise WebPushException("Push failed", response=error_response)
            # Second subscription succeeds
            return MagicMock()

        with patch("django_communication.providers.push.webpush.webpush") as mock_webpush:
            mock_webpush.side_effect = mock_push_side_effect

            message, channel_used = send_notification(
                person=person,
                subject="Test",
                body_text="Test",
            )

            assert channel_used == "push"
            assert call_count == 2  # Tried both subscriptions


@pytest.mark.django_db
class TestGetNotificationStatus:
    """Tests for get_notification_status function."""

    @pytest.fixture
    def person(self, db):
        """Create a Person for testing."""
        from django_parties.models import Person

        return Person.objects.create(
            first_name="Test",
            last_name="User",
            email="testuser@example.com",
            phone="+15551234567",
        )

    @pytest.fixture
    def push_settings(self, db):
        """Create settings with push configured."""
        settings, _ = CommunicationSettings.objects.get_or_create(
            defaults={
                "push_enabled": True,
                "vapid_public_key": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "vapid_private_key": "xYmPh0VhN7cN3K4fUqDr-5cJjA5FPhMJTKKLR3pHqYE",
                "vapid_contact_email": "admin@example.com",
                "email_provider": "console",
                "sms_provider": "console",
            }
        )
        return settings

    def test_notification_status_with_push(self, push_settings, person):
        """Shows push enabled when subscription exists."""
        from django_communication.services.notifications import get_notification_status

        PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/test",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
            is_active=True,
        )

        status = get_notification_status(person)

        assert status["push_enabled"] is True
        assert status["push_subscription_count"] == 1
        assert status["primary_channel"] == "push"

    def test_notification_status_without_push(self, push_settings, person):
        """Shows email as primary when no push subscription."""
        from django_communication.services.notifications import get_notification_status

        status = get_notification_status(person)

        assert status["push_enabled"] is False
        assert status["push_subscription_count"] == 0
        assert status["email_available"] is True
        assert status["primary_channel"] == "email"

    def test_notification_status_sms_only(self, push_settings, db):
        """Shows SMS as primary when only phone available."""
        from django_parties.models import Person
        from django_communication.services.notifications import get_notification_status

        person_sms = Person.objects.create(
            first_name="SMS",
            last_name="Only",
            phone="+15559998888",
        )

        status = get_notification_status(person_sms)

        assert status["push_enabled"] is False
        assert status["email_available"] is False
        assert status["sms_available"] is True
        assert status["primary_channel"] == "sms"

    def test_notification_status_no_channels(self, push_settings, db):
        """Shows none when no channels available."""
        from django_parties.models import Person
        from django_communication.services.notifications import get_notification_status

        person_empty = Person.objects.create(
            first_name="No",
            last_name="Contact",
        )

        status = get_notification_status(person_empty)

        assert status["push_enabled"] is False
        assert status["email_available"] is False
        assert status["sms_available"] is False
        assert status["primary_channel"] == "none"

    def test_notification_status_multiple_push_subscriptions(self, push_settings, person):
        """Correctly counts multiple push subscriptions."""
        from django_communication.services.notifications import get_notification_status

        PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/sub1",
            p256dh_key="key1",
            auth_key="auth1",
            is_active=True,
        )
        PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/sub2",
            p256dh_key="key2",
            auth_key="auth2",
            is_active=True,
        )
        PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/sub3",
            p256dh_key="key3",
            auth_key="auth3",
            is_active=False,  # Inactive
        )

        status = get_notification_status(person)

        assert status["push_enabled"] is True
        assert status["push_subscription_count"] == 2  # Only active ones
