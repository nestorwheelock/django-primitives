"""Public views for diveops.

These views do NOT require authentication and are rate-limited for security.
"""

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views import View


class PublicSigningView(View):
    """Public-facing signing page (no login required).

    Security measures:
    - Invalid token returns 404 (no existence leak)
    - Expired agreements show user-friendly error
    - POST for actual signature submission
    - Rate limiting should be applied at nginx/cloudflare level
    """

    def get(self, request, token):
        """Display the agreement for signing."""
        from .services import get_agreement_by_token

        agreement = get_agreement_by_token(token)

        # Invalid token -> 404 (no existence leak)
        if not agreement:
            raise Http404()

        # Check expiration
        if agreement.expires_at and agreement.expires_at < timezone.now():
            return render(
                request,
                "diveops/public/sign_expired.html",
                {"agreement": agreement},
            )

        # Get party name for display
        party_a = agreement.party_a
        if party_a:
            if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                party_name = f"{party_a.first_name} {party_a.last_name}"
            elif hasattr(party_a, "name"):
                party_name = party_a.name
            else:
                party_name = str(party_a)
        else:
            party_name = "Unknown"

        return render(
            request,
            "diveops/public/sign.html",
            {
                "agreement": agreement,
                "party_name": party_name,
                "token": token,
            },
        )

    def post(self, request, token):
        """Handle signature submission."""
        from .services import get_agreement_by_token, sign_agreement

        agreement = get_agreement_by_token(token)

        # Invalid token -> 404 (no existence leak)
        if not agreement:
            raise Http404()

        # Check expiration
        if agreement.expires_at and agreement.expires_at < timezone.now():
            return render(
                request,
                "diveops/public/sign_expired.html",
                {"agreement": agreement},
            )

        # Get signature data from form
        signed_by_name = request.POST.get("signed_by_name", "").strip()
        signature_data = request.POST.get("signature_data", "")
        agreed_to_terms = request.POST.get("read_checkbox") == "on"
        agreed_to_esign = request.POST.get("esign_checkbox") == "on"

        # Validate
        errors = []
        if not signed_by_name:
            errors.append("Please enter your full legal name.")
        if not signature_data:
            errors.append("Please provide your signature.")
        if not agreed_to_terms:
            errors.append("You must agree to the terms of the agreement.")
        if not agreed_to_esign:
            errors.append("You must consent to electronic signing.")

        if errors:
            # Get party name for display
            party_a = agreement.party_a
            if party_a:
                if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                    party_name = f"{party_a.first_name} {party_a.last_name}"
                elif hasattr(party_a, "name"):
                    party_name = party_a.name
                else:
                    party_name = str(party_a)
            else:
                party_name = "Unknown"

            return render(
                request,
                "diveops/public/sign.html",
                {
                    "agreement": agreement,
                    "party_name": party_name,
                    "token": token,
                    "errors": errors,
                    "signed_by_name": signed_by_name,
                },
            )

        # Get client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        # Get user agent
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        try:
            # Convert signature data (base64 data URL) to bytes
            # Format: "data:image/png;base64,iVBORw0KGgo..."
            if signature_data.startswith("data:"):
                import base64
                import json
                # Extract the base64 part
                header, encoded = signature_data.split(",", 1)
                signature_image = base64.b64decode(encoded)
            else:
                import json
                signature_image = b""

            # Extract digital fingerprint data from form (fields prefixed with fp_)
            fingerprint = {
                "screen_resolution": request.POST.get("fp_screen_resolution", ""),
                "timezone": request.POST.get("fp_timezone", ""),
                "timezone_offset": None,
                "language": request.POST.get("fp_language", ""),
                "platform": request.POST.get("fp_platform", ""),
                "device_memory": request.POST.get("fp_device_memory", ""),
                "hardware_concurrency": None,
                "touch_support": None,
                "canvas_fingerprint": request.POST.get("fp_canvas_fingerprint", ""),
                "geolocation": None,
            }

            # Parse timezone offset (integer)
            tz_offset = request.POST.get("fp_timezone_offset", "")
            if tz_offset:
                try:
                    fingerprint["timezone_offset"] = int(tz_offset)
                except (ValueError, TypeError):
                    pass

            # Parse hardware concurrency (integer)
            hw_concurrency = request.POST.get("fp_hardware_concurrency", "")
            if hw_concurrency:
                try:
                    fingerprint["hardware_concurrency"] = int(hw_concurrency)
                except (ValueError, TypeError):
                    pass

            # Parse touch support (boolean)
            touch = request.POST.get("fp_touch_support", "")
            if touch.lower() == "true":
                fingerprint["touch_support"] = True
            elif touch.lower() == "false":
                fingerprint["touch_support"] = False

            # Parse geolocation (JSON)
            geo_str = request.POST.get("fp_geolocation", "")
            if geo_str:
                try:
                    fingerprint["geolocation"] = json.loads(geo_str)
                except json.JSONDecodeError:
                    pass

            sign_agreement(
                agreement=agreement,
                raw_token=token,
                signature_image=signature_image,
                signed_by_name=signed_by_name,
                ip_address=ip_address,
                user_agent=user_agent,
                agreed_to_terms=agreed_to_terms,
                agreed_to_esign=agreed_to_esign,
                fingerprint=fingerprint,
            )

            return render(
                request,
                "diveops/public/sign_success.html",
                {
                    "agreement": agreement,
                    "signed_by_name": signed_by_name,
                    "signature_data_url": signature_data,  # Pass signature for print
                },
            )

        except Exception as e:
            # Get party name for display
            party_a = agreement.party_a
            if party_a:
                if hasattr(party_a, "first_name") and hasattr(party_a, "last_name"):
                    party_name = f"{party_a.first_name} {party_a.last_name}"
                elif hasattr(party_a, "name"):
                    party_name = party_a.name
                else:
                    party_name = str(party_a)
            else:
                party_name = "Unknown"

            return render(
                request,
                "diveops/public/sign.html",
                {
                    "agreement": agreement,
                    "party_name": party_name,
                    "token": token,
                    "errors": [str(e)],
                    "signed_by_name": signed_by_name,
                },
            )
