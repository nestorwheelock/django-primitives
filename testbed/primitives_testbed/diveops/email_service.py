"""Email sending service for diveops.

Provides a simple interface for sending emails using the configured provider
from EmailSettings. Supports Django console backend (development) and
Amazon SES API (production).

Usage:
    # Simple email (no template)
    from primitives_testbed.diveops.email_service import send_email

    result = send_email(
        to="recipient@example.com",
        subject="Welcome!",
        body_text="Hello, welcome to our dive shop.",
        body_html="<html><body><h1>Hello!</h1></body></html>",
    )

    # Templated email (uses EmailTemplate from DB)
    from primitives_testbed.diveops.email_service import send_templated_email

    result = send_templated_email(
        to="recipient@example.com",
        template_key="verify_email",
        context={"user_name": "Alice", "verify_url": "https://..."},
    )

    if result.sent:
        print(f"Email sent via {result.provider}")
    else:
        print(f"Email not sent: {result.reason}")
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template

logger = logging.getLogger(__name__)


# =============================================================================
# Template Context Requirements
# =============================================================================

TEMPLATE_CONTEXT_REQUIREMENTS: dict[str, set[str]] = {
    "verify_email": {"verify_url", "user_name"},
    "welcome": {"user_name", "dashboard_url"},
    "password_reset": {"reset_url", "user_name"},
}


@dataclass
class EmailResult:
    """Result of an email send attempt.

    Attributes:
        sent: Whether the email was successfully sent
        provider: The provider used (console, ses_api, etc.)
        message_id: Message ID from the provider (for SES)
        reason: Reason for failure if sent is False
    """

    sent: bool
    provider: Optional[str] = None
    message_id: Optional[str] = None
    reason: Optional[str] = None


def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> EmailResult:
    """Send an email using the configured provider.

    Args:
        to: Recipient email address
        subject: Email subject line
        body_text: Plain text body (required)
        body_html: HTML body (optional)
        reply_to: Override reply-to address (optional)

    Returns:
        EmailResult with send status and details

    Note:
        - If EmailSettings.enabled is False, returns immediately with sent=False
        - If provider is not configured, returns with reason='not_configured'
        - Never logs AWS credentials
    """
    from .models import EmailSettings

    settings = EmailSettings.get_instance()

    # Check if email is enabled
    if not settings.enabled:
        logger.debug("Email sending is disabled")
        return EmailResult(sent=False, reason="disabled")

    # Check if properly configured
    if not settings.is_configured():
        logger.warning("Email not configured for provider: %s", settings.provider)
        return EmailResult(sent=False, provider=settings.provider, reason="not_configured")

    # Sandbox mode - log but don't send
    if settings.sandbox_mode:
        logger.info(
            "Sandbox mode: would send email to=%s subject=%s provider=%s",
            to,
            subject,
            settings.provider,
        )
        return EmailResult(sent=True, provider=settings.provider, reason="sandbox")

    # Determine reply-to address
    effective_reply_to = reply_to or settings.reply_to_email or None

    # Route to appropriate provider
    if settings.provider == "console":
        return _send_via_console(settings, to, subject, body_text, body_html, effective_reply_to)
    elif settings.provider == "ses_api":
        return _send_via_ses_api(settings, to, subject, body_text, body_html, effective_reply_to)
    else:
        logger.error("Unsupported email provider: %s", settings.provider)
        return EmailResult(sent=False, provider=settings.provider, reason="unsupported_provider")


def _send_via_console(
    settings,
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    reply_to: Optional[str],
) -> EmailResult:
    """Send email via Django's email backend (console in development)."""
    from_email = settings.get_from_address()

    email = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=[to],
        reply_to=[reply_to] if reply_to else None,
    )

    if body_html:
        email.attach_alternative(body_html, "text/html")

    try:
        email.send()
        logger.info("Email sent via console to=%s subject=%s", to, subject)
        return EmailResult(sent=True, provider="console")
    except Exception as e:
        logger.exception("Failed to send email via console: %s", str(e))
        return EmailResult(sent=False, provider="console", reason=str(e))


def _send_via_ses_api(
    settings,
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    reply_to: Optional[str],
) -> EmailResult:
    """Send email via boto3 SES API."""
    try:
        import boto3
    except ImportError:
        logger.error("boto3 not installed - required for SES API provider")
        return EmailResult(sent=False, provider="ses_api", reason="boto3_not_installed")

    from_email = settings.get_from_address()

    # Create SES client with credentials from settings
    # Note: Never log the secret access key
    client = boto3.client(
        "ses",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    # Build message body
    body = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
    if body_html:
        body["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    # Build send_email parameters
    send_params = {
        "Source": from_email,
        "Destination": {"ToAddresses": [to]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": body,
        },
    }

    if reply_to:
        send_params["ReplyToAddresses"] = [reply_to]

    if settings.configuration_set:
        send_params["ConfigurationSetName"] = settings.configuration_set

    try:
        response = client.send_email(**send_params)
        message_id = response.get("MessageId")
        logger.info(
            "Email sent via SES to=%s subject=%s message_id=%s",
            to,
            subject,
            message_id,
        )
        return EmailResult(sent=True, provider="ses_api", message_id=message_id)
    except Exception as e:
        # Log error but never log credentials
        logger.exception("Failed to send email via SES: %s", str(e))
        return EmailResult(sent=False, provider="ses_api", reason=str(e))


# =============================================================================
# Template Rendering
# =============================================================================


def render_email_template(
    key: str,
    context: dict,
) -> Tuple[str, str, str]:
    """Render an email template from the database.

    Args:
        key: Template key (e.g., "verify_email", "welcome")
        context: Dictionary of variables for template rendering

    Returns:
        Tuple of (subject, text_body, html_body)

    Raises:
        ValueError: If template not found, inactive, or missing required context
    """
    from .models import EmailTemplate

    # Load template from database
    try:
        template = EmailTemplate.objects.get(key=key)
    except EmailTemplate.DoesNotExist:
        raise ValueError(f"Email template '{key}' not found")

    if not template.is_active:
        raise ValueError(f"Email template '{key}' is inactive")

    # Validate required context fields
    required_fields = TEMPLATE_CONTEXT_REQUIREMENTS.get(key, set())
    missing_fields = required_fields - set(context.keys())
    if missing_fields:
        raise ValueError(
            f"Email template '{key}' missing required context fields: {', '.join(sorted(missing_fields))}"
        )

    # Render templates using Django template engine
    django_context = Context(context)

    subject = Template(template.subject_template).render(django_context).strip()
    text_body = Template(template.body_text_template).render(django_context)
    html_body = ""
    if template.body_html_template:
        html_body = Template(template.body_html_template).render(django_context)

    return subject, text_body, html_body


def send_templated_email(
    to: str,
    template_key: str,
    context: dict,
    reply_to: Optional[str] = None,
) -> EmailResult:
    """Send an email using a template from the database.

    Args:
        to: Recipient email address
        template_key: Template key (e.g., "verify_email", "welcome")
        context: Dictionary of variables for template rendering
        reply_to: Override reply-to address (optional)

    Returns:
        EmailResult with send status and details

    Raises:
        ValueError: If template not found, inactive, or missing required context
    """
    # Render the template
    subject, text_body, html_body = render_email_template(template_key, context)

    # Log template usage (no secrets)
    logger.info(
        "Sending templated email: template_key=%s to=%s",
        template_key,
        to,
    )

    # Send using the regular send_email function
    return send_email(
        to=to,
        subject=subject,
        body_text=text_body,
        body_html=html_body if html_body else None,
        reply_to=reply_to,
    )
