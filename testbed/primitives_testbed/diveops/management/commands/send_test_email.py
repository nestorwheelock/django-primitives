"""Management command to send a test email.

Usage:
    # Simple test email (no template)
    python manage.py send_test_email --to recipient@example.com
    python manage.py send_test_email --to recipient@example.com --subject "Custom Subject"

    # Templated test email
    python manage.py send_test_email --to recipient@example.com --template verify_email
    python manage.py send_test_email --to recipient@example.com --template welcome
"""

from django.core.management.base import BaseCommand, CommandError

from primitives_testbed.diveops.email_service import (
    send_email,
    send_templated_email,
    TEMPLATE_CONTEXT_REQUIREMENTS,
)
from primitives_testbed.diveops.models import EmailSettings, EmailTemplate


# Sample context for each template type
SAMPLE_CONTEXTS = {
    "verify_email": {
        "user_name": "Test User",
        "verify_url": "https://example.com/verify?token=test123",
    },
    "welcome": {
        "user_name": "Test User",
        "dashboard_url": "https://example.com/dashboard",
    },
    "password_reset": {
        "user_name": "Test User",
        "reset_url": "https://example.com/reset?token=test456",
    },
}


class Command(BaseCommand):
    help = "Send a test email to verify email configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            required=True,
            help="Recipient email address",
        )
        parser.add_argument(
            "--subject",
            type=str,
            default="Test Email from DiveOps",
            help="Email subject line (default: 'Test Email from DiveOps')",
        )
        parser.add_argument(
            "--template",
            type=str,
            default=None,
            help="Template key to use (e.g., 'verify_email', 'welcome', 'password_reset')",
        )
        parser.add_argument(
            "--list-templates",
            action="store_true",
            help="List available email templates",
        )

    def handle(self, *args, **options):
        # Handle --list-templates
        if options["list_templates"]:
            self._list_templates()
            return

        to_email = options["to"]
        template_key = options["template"]

        # Check EmailSettings configuration
        settings = EmailSettings.get_instance()

        self.stdout.write(f"Email Settings:")
        self.stdout.write(f"  Enabled: {settings.enabled}")
        self.stdout.write(f"  Provider: {settings.provider}")
        self.stdout.write(f"  Sandbox Mode: {settings.sandbox_mode}")
        self.stdout.write(f"  From Email: {settings.default_from_email}")
        self.stdout.write(f"  Configured: {settings.is_configured()}")
        self.stdout.write("")

        if not settings.enabled:
            raise CommandError("Email is disabled. Enable it in Django admin first.")

        if not settings.is_configured():
            raise CommandError(
                f"Email not configured for provider '{settings.provider}'. "
                "Configure credentials in Django admin."
            )

        # Send templated or simple email
        if template_key:
            result = self._send_templated(to_email, template_key)
        else:
            result = self._send_simple(to_email, options["subject"], settings)

        # Report result
        if result.sent:
            self.stdout.write(self.style.SUCCESS(f"Email sent successfully!"))
            self.stdout.write(f"  Provider: {result.provider}")
            if result.message_id:
                self.stdout.write(f"  Message ID: {result.message_id}")
            if result.reason == "sandbox":
                self.stdout.write(
                    self.style.WARNING("  Note: Sandbox mode - email was logged but not actually sent")
                )
        else:
            raise CommandError(f"Failed to send email: {result.reason}")

    def _list_templates(self):
        """List available email templates."""
        self.stdout.write(self.style.SUCCESS("Available Email Templates:"))
        self.stdout.write("")

        templates = EmailTemplate.objects.filter(is_active=True).order_by("key")
        if not templates:
            self.stdout.write("  No templates found. Create templates in Django admin.")
            return

        for template in templates:
            self.stdout.write(f"  {template.key}")
            self.stdout.write(f"    Name: {template.name}")
            self.stdout.write(f"    Subject: {template.subject_template[:50]}...")
            required = TEMPLATE_CONTEXT_REQUIREMENTS.get(template.key, set())
            if required:
                self.stdout.write(f"    Required context: {', '.join(sorted(required))}")
            self.stdout.write("")

    def _send_templated(self, to_email, template_key):
        """Send a templated test email."""
        # Check template exists
        try:
            template = EmailTemplate.objects.get(key=template_key, is_active=True)
        except EmailTemplate.DoesNotExist:
            raise CommandError(
                f"Template '{template_key}' not found or inactive. "
                "Use --list-templates to see available templates."
            )

        # Get sample context
        context = SAMPLE_CONTEXTS.get(template_key, {})

        # Add any missing required fields with placeholder values
        required = TEMPLATE_CONTEXT_REQUIREMENTS.get(template_key, set())
        for field in required:
            if field not in context:
                context[field] = f"[sample_{field}]"

        self.stdout.write(f"Sending templated email:")
        self.stdout.write(f"  To: {to_email}")
        self.stdout.write(f"  Template: {template_key}")
        self.stdout.write(f"  Context: {context}")
        self.stdout.write("")

        try:
            return send_templated_email(
                to=to_email,
                template_key=template_key,
                context=context,
            )
        except ValueError as e:
            raise CommandError(str(e))

    def _send_simple(self, to_email, subject, settings):
        """Send a simple test email (no template)."""
        body_text = f"""This is a test email from DiveOps.

Configuration:
- Provider: {settings.provider}
- Region: {settings.aws_region}
- From: {settings.get_from_address()}
- Sandbox Mode: {settings.sandbox_mode}

If you received this email, your email configuration is working correctly.
"""

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h1 style="color: #2563eb;">Test Email from DiveOps</h1>
    <p>This is a test email to verify your email configuration.</p>

    <h2 style="color: #374151;">Configuration</h2>
    <table style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f3f4f6;">
            <td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Provider</strong></td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{settings.provider}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Region</strong></td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{settings.aws_region}</td>
        </tr>
        <tr style="background-color: #f3f4f6;">
            <td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>From</strong></td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{settings.get_from_address()}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Sandbox Mode</strong></td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{settings.sandbox_mode}</td>
        </tr>
    </table>

    <p style="margin-top: 24px; color: #059669;">
        If you received this email, your email configuration is working correctly.
    </p>
</body>
</html>
"""

        self.stdout.write(f"Sending simple test email:")
        self.stdout.write(f"  To: {to_email}")
        self.stdout.write(f"  Subject: {subject}")
        self.stdout.write("")

        return send_email(
            to=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
