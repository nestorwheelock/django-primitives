"""Tests for Web Push notification functionality."""

import pytest
from django.db import IntegrityError

from django_communication.models import Channel


@pytest.mark.django_db
class TestPushSubscription:
    """Tests for PushSubscription model."""

    def test_push_subscription_creation(self, person):
        """PushSubscription can be created with required fields."""
        from django_communication.models import PushSubscription

        sub = PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/abc123",
            p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            auth_key="tBHItJI5svbpez7KI4CCXg",
        )
        assert sub.pk is not None
        assert sub.person == person
        assert sub.endpoint.startswith("https://")
        assert sub.is_active is True
        assert sub.failure_count == 0

    def test_push_subscription_unique_constraint(self, person):
        """Same person cannot have duplicate endpoint."""
        from django_communication.models import PushSubscription

        endpoint = "https://fcm.googleapis.com/fcm/send/unique123"
        PushSubscription.objects.create(
            person=person,
            endpoint=endpoint,
            p256dh_key="key1",
            auth_key="auth1",
        )
        with pytest.raises(IntegrityError):
            PushSubscription.objects.create(
                person=person,
                endpoint=endpoint,
                p256dh_key="key2",
                auth_key="auth2",
            )

    def test_push_subscription_device_info(self, person):
        """PushSubscription can store device/browser info."""
        from django_communication.models import PushSubscription

        sub = PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/device123",
            p256dh_key="key",
            auth_key="auth",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
            device_name="Chrome on Windows",
        )
        assert sub.user_agent.startswith("Mozilla")
        assert sub.device_name == "Chrome on Windows"

    def test_push_subscription_failure_tracking(self, person):
        """PushSubscription tracks failure counts."""
        from django_communication.models import PushSubscription

        sub = PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/fail123",
            p256dh_key="key",
            auth_key="auth",
        )
        assert sub.failure_count == 0
        assert sub.last_successful_push is None

        sub.failure_count = 3
        sub.save()
        sub.refresh_from_db()
        assert sub.failure_count == 3

    def test_push_subscription_deactivation(self, person):
        """PushSubscription can be deactivated."""
        from django_communication.models import PushSubscription

        sub = PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/deact123",
            p256dh_key="key",
            auth_key="auth",
            is_active=True,
        )
        assert sub.is_active is True

        sub.is_active = False
        sub.save()
        sub.refresh_from_db()
        assert sub.is_active is False

    def test_multiple_subscriptions_per_person(self, person):
        """Person can have multiple push subscriptions (different devices)."""
        from django_communication.models import PushSubscription

        sub1 = PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/device1",
            p256dh_key="key1",
            auth_key="auth1",
            device_name="Chrome Desktop",
        )
        sub2 = PushSubscription.objects.create(
            person=person,
            endpoint="https://fcm.googleapis.com/fcm/send/device2",
            p256dh_key="key2",
            auth_key="auth2",
            device_name="Firefox Mobile",
        )
        assert person.push_subscriptions.count() == 2
        assert list(person.push_subscriptions.all()) == [sub2, sub1]  # most recent first


@pytest.mark.django_db
class TestChannelEnum:
    """Tests for Channel enum with PUSH."""

    def test_push_channel_exists(self):
        """PUSH is a valid channel."""
        assert Channel.PUSH == "push"
        assert Channel.PUSH.label == "Web Push"

    def test_all_channels(self):
        """All expected channels exist."""
        channels = [c.value for c in Channel]
        assert "email" in channels
        assert "sms" in channels
        assert "in_app" in channels
        assert "push" in channels


@pytest.mark.django_db
class TestCommunicationSettingsPush:
    """Tests for push-related CommunicationSettings fields."""

    def test_push_settings_defaults(self):
        """Push settings have sensible defaults."""
        from django_communication.models import CommunicationSettings

        settings = CommunicationSettings.objects.create()
        assert settings.push_enabled is False
        assert settings.vapid_public_key == ""
        assert settings.vapid_private_key == ""
        assert settings.notification_fallback_enabled is True
        assert settings.push_failure_threshold == 3

    def test_push_configured_check(self):
        """is_push_configured returns True only when all fields set."""
        from django_communication.models import CommunicationSettings

        settings = CommunicationSettings.objects.create(
            push_enabled=True,
            vapid_public_key="BNcRdreALRFXTk...",
            vapid_private_key="private_key_here",
            vapid_contact_email="admin@example.com",
        )
        assert settings.is_push_configured() is True

    def test_push_not_configured_without_keys(self):
        """is_push_configured returns False when keys missing."""
        from django_communication.models import CommunicationSettings

        settings = CommunicationSettings.objects.create(
            push_enabled=True,
            vapid_contact_email="admin@example.com",
        )
        assert settings.is_push_configured() is False

    def test_push_not_configured_when_disabled(self):
        """is_push_configured returns False when push_enabled is False."""
        from django_communication.models import CommunicationSettings

        settings = CommunicationSettings.objects.create(
            push_enabled=False,
            vapid_public_key="BNcRdreALRFXTk...",
            vapid_private_key="private_key_here",
            vapid_contact_email="admin@example.com",
        )
        assert settings.is_push_configured() is False
