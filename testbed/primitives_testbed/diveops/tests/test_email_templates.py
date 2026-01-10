"""Tests for EmailTemplate model and templated email sending.

Tests the DB-stored email templates with context validation and rendering.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.exceptions import ImproperlyConfigured


@pytest.mark.django_db
class TestEmailTemplateModel:
    """Tests for EmailTemplate model."""

    def test_create_email_template(self):
        """EmailTemplate can be created with required fields."""
        from primitives_testbed.diveops.models import EmailTemplate

        template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject_template="Hello {{ user_name }}",
            body_text_template="Welcome {{ user_name }}!",
        )
        assert template.pk is not None
        assert template.key == "test_template"
        assert template.is_active is True

    def test_email_template_key_is_unique(self):
        """EmailTemplate key must be unique."""
        from primitives_testbed.diveops.models import EmailTemplate
        from django.db import IntegrityError

        EmailTemplate.objects.create(
            key="unique_key",
            name="Template 1",
            subject_template="Subject",
            body_text_template="Body",
        )

        with pytest.raises(IntegrityError):
            EmailTemplate.objects.create(
                key="unique_key",
                name="Template 2",
                subject_template="Subject 2",
                body_text_template="Body 2",
            )

    def test_email_template_html_is_optional(self):
        """EmailTemplate body_html_template can be blank."""
        from primitives_testbed.diveops.models import EmailTemplate

        template = EmailTemplate.objects.create(
            key="text_only",
            name="Text Only Template",
            subject_template="Subject",
            body_text_template="Text body only",
            body_html_template="",
        )
        assert template.body_html_template == ""

    def test_email_template_str(self):
        """String representation includes key and name."""
        from primitives_testbed.diveops.models import EmailTemplate

        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject_template="Welcome!",
            body_text_template="Hello",
        )
        assert "welcome" in str(template)

    def test_email_template_updated_by_can_be_null(self):
        """updated_by can be null."""
        from primitives_testbed.diveops.models import EmailTemplate

        template = EmailTemplate.objects.create(
            key="no_author",
            name="No Author",
            subject_template="Subject",
            body_text_template="Body",
            updated_by=None,
        )
        assert template.updated_by is None


@pytest.mark.django_db
class TestRenderEmailTemplate:
    """Tests for render_email_template helper."""

    def test_render_template_success(self):
        """render_email_template renders subject, text, and html."""
        from primitives_testbed.diveops.models import EmailTemplate
        from primitives_testbed.diveops.email_service import render_email_template

        EmailTemplate.objects.create(
            key="test_render",
            name="Test Render",
            subject_template="Hello {{ user_name }}",
            body_text_template="Welcome to {{ site_name }}, {{ user_name }}!",
            body_html_template="<h1>Welcome {{ user_name }}</h1>",
            is_active=True,
        )

        subject, text, html = render_email_template(
            "test_render",
            {"user_name": "Alice", "site_name": "DiveOps"},
        )

        assert subject == "Hello Alice"
        assert "Welcome to DiveOps, Alice!" in text
        assert "<h1>Welcome Alice</h1>" in html

    def test_render_template_missing_key_raises(self):
        """render_email_template raises for missing template key."""
        from primitives_testbed.diveops.email_service import render_email_template

        with pytest.raises(ValueError, match="not found"):
            render_email_template("nonexistent_template", {})

    def test_render_template_inactive_raises(self):
        """render_email_template raises for inactive template."""
        from primitives_testbed.diveops.models import EmailTemplate
        from primitives_testbed.diveops.email_service import render_email_template

        EmailTemplate.objects.create(
            key="inactive_template",
            name="Inactive",
            subject_template="Subject",
            body_text_template="Body",
            is_active=False,
        )

        with pytest.raises(ValueError, match="inactive"):
            render_email_template("inactive_template", {})

    def test_render_verify_email_requires_context(self):
        """verify_email template requires verify_url and user_name."""
        from primitives_testbed.diveops.models import EmailTemplate
        from primitives_testbed.diveops.email_service import render_email_template

        EmailTemplate.objects.create(
            key="verify_email",
            name="Verify Email",
            subject_template="Verify your email",
            body_text_template="Click {{ verify_url }}",
            is_active=True,
        )

        # Missing verify_url
        with pytest.raises(ValueError, match="verify_url"):
            render_email_template("verify_email", {"user_name": "Alice"})

        # Missing user_name
        with pytest.raises(ValueError, match="user_name"):
            render_email_template("verify_email", {"verify_url": "http://example.com"})

    def test_render_welcome_requires_context(self):
        """welcome template requires user_name and dashboard_url."""
        from primitives_testbed.diveops.models import EmailTemplate
        from primitives_testbed.diveops.email_service import render_email_template

        EmailTemplate.objects.create(
            key="welcome",
            name="Welcome",
            subject_template="Welcome!",
            body_text_template="Welcome {{ user_name }}! Visit {{ dashboard_url }}",
            is_active=True,
        )

        with pytest.raises(ValueError, match="dashboard_url"):
            render_email_template("welcome", {"user_name": "Bob"})

    def test_render_password_reset_requires_context(self):
        """password_reset template requires reset_url and user_name."""
        from primitives_testbed.diveops.models import EmailTemplate
        from primitives_testbed.diveops.email_service import render_email_template

        EmailTemplate.objects.create(
            key="password_reset",
            name="Password Reset",
            subject_template="Reset your password",
            body_text_template="Click {{ reset_url }} to reset, {{ user_name }}",
            is_active=True,
        )

        with pytest.raises(ValueError, match="reset_url"):
            render_email_template("password_reset", {"user_name": "Carol"})

    def test_render_html_body_is_optional(self):
        """render_email_template returns empty string for missing html."""
        from primitives_testbed.diveops.models import EmailTemplate
        from primitives_testbed.diveops.email_service import render_email_template

        EmailTemplate.objects.create(
            key="text_only_render",
            name="Text Only",
            subject_template="Subject",
            body_text_template="Text body",
            body_html_template="",
            is_active=True,
        )

        subject, text, html = render_email_template("text_only_render", {})

        assert subject == "Subject"
        assert text == "Text body"
        assert html == ""


@pytest.mark.django_db
class TestSendTemplatedEmail:
    """Tests for send_templated_email service."""

    def test_send_templated_email_console_provider(self):
        """send_templated_email with console provider sends email."""
        from primitives_testbed.diveops.models import EmailSettings, EmailTemplate
        from primitives_testbed.diveops.email_service import send_templated_email

        # Configure EmailSettings
        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.default_from_name = "Test Sender"
        settings.save()

        # Create template
        EmailTemplate.objects.create(
            key="test_console",
            name="Test Console",
            subject_template="Hello {{ user_name }}",
            body_text_template="Welcome {{ user_name }}!",
            body_html_template="<h1>Welcome {{ user_name }}</h1>",
            is_active=True,
        )

        result = send_templated_email(
            to="recipient@example.com",
            template_key="test_console",
            context={"user_name": "Alice"},
        )

        assert result.sent is True
        assert result.provider == "console"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Hello Alice"
        assert "Welcome Alice!" in mail.outbox[0].body

    def test_send_templated_email_disabled(self):
        """send_templated_email returns early when disabled."""
        from primitives_testbed.diveops.models import EmailSettings, EmailTemplate
        from primitives_testbed.diveops.email_service import send_templated_email

        settings = EmailSettings.get_instance()
        settings.enabled = False
        settings.save()

        EmailTemplate.objects.create(
            key="disabled_test",
            name="Disabled Test",
            subject_template="Subject",
            body_text_template="Body",
            is_active=True,
        )

        result = send_templated_email(
            to="recipient@example.com",
            template_key="disabled_test",
            context={},
        )

        assert result.sent is False
        assert result.reason == "disabled"

    def test_send_templated_email_ses_api_provider(self):
        """send_templated_email with ses_api provider uses boto3."""
        from primitives_testbed.diveops.models import EmailSettings, EmailTemplate
        from primitives_testbed.diveops.email_service import send_templated_email

        # Setup mock
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "ses-msg-123"}
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Configure EmailSettings
        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "ses_api"
        settings.default_from_email = "sender@example.com"
        settings.aws_region = "us-west-2"
        settings.aws_access_key_id = "AKIAEXAMPLE"
        settings.aws_secret_access_key = "secretkey"
        settings.save()

        # Create template
        EmailTemplate.objects.create(
            key="test_ses",
            name="Test SES",
            subject_template="Hello {{ user_name }}",
            body_text_template="Welcome {{ user_name }}!",
            body_html_template="<h1>Welcome {{ user_name }}</h1>",
            is_active=True,
        )

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            result = send_templated_email(
                to="recipient@example.com",
                template_key="test_ses",
                context={"user_name": "Bob"},
            )

        assert result.sent is True
        assert result.provider == "ses_api"
        assert result.message_id == "ses-msg-123"

        # Verify boto3 call
        call_kwargs = mock_client.send_email.call_args[1]
        assert call_kwargs["Message"]["Subject"]["Data"] == "Hello Bob"
        assert "Welcome Bob!" in call_kwargs["Message"]["Body"]["Text"]["Data"]

    def test_send_templated_email_ses_missing_credentials(self):
        """send_templated_email raises when SES credentials missing."""
        from primitives_testbed.diveops.models import EmailSettings, EmailTemplate
        from primitives_testbed.diveops.email_service import send_templated_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "ses_api"
        settings.default_from_email = "sender@example.com"
        settings.aws_access_key_id = ""
        settings.aws_secret_access_key = ""
        settings.save()

        EmailTemplate.objects.create(
            key="test_no_creds",
            name="Test No Creds",
            subject_template="Subject",
            body_text_template="Body",
            is_active=True,
        )

        result = send_templated_email(
            to="recipient@example.com",
            template_key="test_no_creds",
            context={},
        )

        assert result.sent is False
        assert result.reason == "not_configured"

    def test_send_templated_email_with_reply_to(self):
        """send_templated_email passes reply_to to email."""
        from primitives_testbed.diveops.models import EmailSettings, EmailTemplate
        from primitives_testbed.diveops.email_service import send_templated_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.save()

        EmailTemplate.objects.create(
            key="test_reply",
            name="Test Reply",
            subject_template="Subject",
            body_text_template="Body",
            is_active=True,
        )

        result = send_templated_email(
            to="recipient@example.com",
            template_key="test_reply",
            context={},
            reply_to="reply@example.com",
        )

        assert result.sent is True
        assert mail.outbox[0].reply_to == ["reply@example.com"]

    def test_send_templated_email_invalid_template(self):
        """send_templated_email raises for invalid template."""
        from primitives_testbed.diveops.models import EmailSettings
        from primitives_testbed.diveops.email_service import send_templated_email

        settings = EmailSettings.get_instance()
        settings.enabled = True
        settings.provider = "console"
        settings.default_from_email = "sender@example.com"
        settings.save()

        with pytest.raises(ValueError, match="not found"):
            send_templated_email(
                to="recipient@example.com",
                template_key="nonexistent",
                context={},
            )


@pytest.mark.django_db
class TestTemplateContextRequirements:
    """Tests for template context requirement enforcement."""

    def test_context_requirements_mapping_exists(self):
        """TEMPLATE_CONTEXT_REQUIREMENTS mapping should exist."""
        from primitives_testbed.diveops.email_service import TEMPLATE_CONTEXT_REQUIREMENTS

        assert "verify_email" in TEMPLATE_CONTEXT_REQUIREMENTS
        assert "welcome" in TEMPLATE_CONTEXT_REQUIREMENTS
        assert "password_reset" in TEMPLATE_CONTEXT_REQUIREMENTS

    def test_verify_email_requirements(self):
        """verify_email requires verify_url and user_name."""
        from primitives_testbed.diveops.email_service import TEMPLATE_CONTEXT_REQUIREMENTS

        reqs = TEMPLATE_CONTEXT_REQUIREMENTS["verify_email"]
        assert "verify_url" in reqs
        assert "user_name" in reqs

    def test_welcome_requirements(self):
        """welcome requires user_name and dashboard_url."""
        from primitives_testbed.diveops.email_service import TEMPLATE_CONTEXT_REQUIREMENTS

        reqs = TEMPLATE_CONTEXT_REQUIREMENTS["welcome"]
        assert "user_name" in reqs
        assert "dashboard_url" in reqs

    def test_password_reset_requirements(self):
        """password_reset requires reset_url and user_name."""
        from primitives_testbed.diveops.email_service import TEMPLATE_CONTEXT_REQUIREMENTS

        reqs = TEMPLATE_CONTEXT_REQUIREMENTS["password_reset"]
        assert "reset_url" in reqs
        assert "user_name" in reqs
