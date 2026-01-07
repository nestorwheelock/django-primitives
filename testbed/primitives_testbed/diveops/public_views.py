"""Public views for diveops.

These views do NOT require authentication and are rate-limited for security.
"""

from django.http import Http404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views import View

from django_questionnaires.models import (
    QuestionnaireInstance,
    InstanceStatus,
)
from django_questionnaires.services import submit_response

from .audit import Actions, log_medical_questionnaire_event


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


class PublicMedicalQuestionnaireView(View):
    """Public-facing medical questionnaire form (no login required).

    Security measures:
    - Invalid UUID returns 404 (no existence leak)
    - Expired questionnaires show user-friendly error
    - Already completed questionnaires show confirmation
    """

    def get_instance(self, instance_id):
        """Get questionnaire instance by UUID."""
        try:
            return QuestionnaireInstance.objects.select_related(
                "definition"
            ).prefetch_related(
                "definition__questions"
            ).get(
                pk=instance_id,
                deleted_at__isnull=True,
            )
        except QuestionnaireInstance.DoesNotExist:
            return None

    def get_respondent_name(self, instance):
        """Get respondent name for display."""
        respondent = instance.respondent
        if respondent:
            if hasattr(respondent, "person"):
                return str(respondent.person)
            elif hasattr(respondent, "first_name") and hasattr(respondent, "last_name"):
                return f"{respondent.first_name} {respondent.last_name}"
            elif hasattr(respondent, "name"):
                return respondent.name
            else:
                return str(respondent)
        return "Unknown"

    def get_client_ip(self, request):
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def get_questions_by_category(self, instance):
        """Organize questions by category with conditional display info."""
        questions = instance.definition.questions.filter(
            deleted_at__isnull=True
        ).order_by("sequence")

        # Separate screening questions from follow-up boxes
        screening_questions = []
        follow_up_boxes = {}

        for q in questions:
            validation_rules = q.validation_rules or {}
            show_if = validation_rules.get("show_if")

            if show_if:
                # This is a follow-up question
                parent_seq = show_if.get("question_sequence")
                if parent_seq not in follow_up_boxes:
                    follow_up_boxes[parent_seq] = {
                        "category": q.category,
                        "questions": [],
                    }
                follow_up_boxes[parent_seq]["questions"].append(q)
            else:
                # This is a screening question
                screening_questions.append({
                    "question": q,
                    "opens_box": validation_rules.get("opens_box"),
                    "requires_physician": validation_rules.get("requires_physician", False),
                })

        return screening_questions, follow_up_boxes

    def get(self, request, instance_id):
        """Display the questionnaire form."""
        instance = self.get_instance(instance_id)

        if not instance:
            raise Http404()

        # Check if expired
        if instance.expires_at < timezone.now():
            return render(
                request,
                "diveops/public/medical_expired.html",
                {"instance": instance},
            )

        # Check if already completed
        if instance.status != InstanceStatus.PENDING:
            return render(
                request,
                "diveops/public/medical_already_completed.html",
                {
                    "instance": instance,
                    "respondent_name": self.get_respondent_name(instance),
                },
            )

        screening_questions, follow_up_boxes = self.get_questions_by_category(instance)

        return render(
            request,
            "diveops/public/medical_form.html",
            {
                "instance": instance,
                "respondent_name": self.get_respondent_name(instance),
                "screening_questions": screening_questions,
                "follow_up_boxes": follow_up_boxes,
                "metadata": instance.definition.metadata or {},
            },
        )

    def post(self, request, instance_id):
        """Handle questionnaire submission."""
        instance = self.get_instance(instance_id)

        if not instance:
            raise Http404()

        # Check if expired
        if instance.expires_at < timezone.now():
            return render(
                request,
                "diveops/public/medical_expired.html",
                {"instance": instance},
            )

        # Check if already completed
        if instance.status != InstanceStatus.PENDING:
            return render(
                request,
                "diveops/public/medical_already_completed.html",
                {
                    "instance": instance,
                    "respondent_name": self.get_respondent_name(instance),
                },
            )

        # Collect answers from form
        answers = {}
        questions = instance.definition.questions.filter(deleted_at__isnull=True)

        for question in questions:
            field_name = f"q_{question.sequence}"
            value = request.POST.get(field_name)

            # Only include answers for questions that were visible
            # Check if this is a conditional question
            validation_rules = question.validation_rules or {}
            show_if = validation_rules.get("show_if")

            if show_if:
                # This is a follow-up question - check if parent was "Yes"
                parent_seq = show_if.get("question_sequence")
                parent_field = f"q_{parent_seq}"
                parent_value = request.POST.get(parent_field)
                if parent_value != "yes":
                    # Parent was "No", skip this follow-up question
                    continue

            if value is not None:
                # Use string keys to match service expectation
                q_id = str(question.pk)
                if question.question_type == "yes_no":
                    answers[q_id] = {"answer_bool": value == "yes"}
                elif question.question_type == "text":
                    answers[q_id] = {"answer_text": value}
                elif question.question_type == "number":
                    try:
                        answers[q_id] = {"answer_number": float(value) if value else None}
                    except ValueError:
                        answers[q_id] = {"answer_number": None}
                elif question.question_type == "date":
                    answers[q_id] = {"answer_date": value if value else None}
                elif question.question_type in ("choice", "multi_choice"):
                    if question.question_type == "multi_choice":
                        values = request.POST.getlist(field_name)
                        answers[q_id] = {"answer_choices": values}
                    else:
                        answers[q_id] = {"answer_choices": [value] if value else []}

        # Collect signature and fingerprint data
        import hashlib
        import json

        signature_data = request.POST.get("signature_data", "")
        signed_by_name = request.POST.get("signed_by_name", "")

        fingerprint_data = {
            "screen_resolution": request.POST.get("fp_screen_resolution", ""),
            "timezone": request.POST.get("fp_timezone", ""),
            "timezone_offset": request.POST.get("fp_timezone_offset", ""),
            "language": request.POST.get("fp_language", ""),
            "platform": request.POST.get("fp_platform", ""),
            "device_memory": request.POST.get("fp_device_memory", ""),
            "hardware_concurrency": request.POST.get("fp_hardware_concurrency", ""),
            "touch_support": request.POST.get("fp_touch_support", ""),
            "canvas_fingerprint": request.POST.get("fp_canvas_fingerprint", ""),
        }

        # Create document hash for integrity verification
        hash_content = {
            "answers": answers,
            "signed_by_name": signed_by_name,
            "fingerprint": fingerprint_data,
            "timestamp": timezone.now().isoformat(),
        }
        document_hash = hashlib.sha256(
            json.dumps(hash_content, sort_keys=True).encode()
        ).hexdigest()

        try:
            # Submit the response
            updated_instance = submit_response(instance, answers, actor=None)

            # Store signature metadata on the instance
            updated_instance.metadata = {
                "signature": {
                    "signed_by_name": signed_by_name,
                    "signature_image": signature_data[:100] + "..." if len(signature_data) > 100 else signature_data,
                    "signature_full": signature_data,  # Full base64 PNG
                    "signed_at": timezone.now().isoformat(),
                    "ip_address": self.get_client_ip(request),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
                },
                "fingerprint": fingerprint_data,
                "document_hash": document_hash,
                "esign_consent": request.POST.get("esign_checkbox") == "on",
            }
            updated_instance.save(update_fields=["metadata"])

            # Generate and store signed PDF
            try:
                from .medical.pdf_service import generate_and_store_medical_pdf
                document, pdf_hash = generate_and_store_medical_pdf(
                    instance=updated_instance,
                    actor=None,
                )
                # Refresh instance to get updated metadata
                updated_instance.refresh_from_db()
            except Exception as pdf_error:
                # Log error but don't fail the submission
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to generate medical PDF: {pdf_error}")

            # Log to audit trail
            if updated_instance.status == InstanceStatus.FLAGGED:
                log_medical_questionnaire_event(
                    action=Actions.MEDICAL_QUESTIONNAIRE_FLAGGED,
                    instance=updated_instance,
                    actor=None,
                    request=request,
                    data={"submission_type": "public_form"},
                )
            else:
                log_medical_questionnaire_event(
                    action=Actions.MEDICAL_QUESTIONNAIRE_COMPLETED,
                    instance=updated_instance,
                    actor=None,
                    request=request,
                    data={"submission_type": "public_form"},
                )

            # Redirect to success page
            return render(
                request,
                "diveops/public/medical_success.html",
                {
                    "instance": updated_instance,
                    "respondent_name": self.get_respondent_name(updated_instance),
                    "is_flagged": updated_instance.status == InstanceStatus.FLAGGED,
                },
            )

        except Exception as e:
            screening_questions, follow_up_boxes = self.get_questions_by_category(instance)

            return render(
                request,
                "diveops/public/medical_form.html",
                {
                    "instance": instance,
                    "respondent_name": self.get_respondent_name(instance),
                    "screening_questions": screening_questions,
                    "follow_up_boxes": follow_up_boxes,
                    "metadata": instance.definition.metadata or {},
                    "errors": [str(e)],
                },
            )
