"""Medical Questionnaire PDF Generation Service.

Generates signed PDF documents from completed medical questionnaires.
Uses WeasyPrint for HTML-to-PDF conversion.
"""

import io
import base64
from datetime import datetime

from django.template.loader import render_to_string
from django.utils import timezone

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    HTML = None
    CSS = None
    WEASYPRINT_AVAILABLE = False


class MedicalQuestionnairePDFService:
    """Service for rendering medical questionnaires to PDF.

    Generates a signed PDF document containing:
    - All questions and answers
    - Signature image
    - Digital fingerprint data
    - Document hash for integrity verification
    """

    TEMPLATE = "diveops/pdf/medical_questionnaire.html"

    # Map screening questions to their follow-up boxes
    BOX_MAPPING = {
        1: "box_a",
        2: "box_b",
        4: "box_c",
        6: "box_d",
        7: "box_e",
        8: "box_f",
        9: "box_g",
    }

    BOX_TITLES = {
        "box_a": "Box A - I HAVE/HAVE HAD:",
        "box_b": "Box B - I AM OVER 45 YEARS OF AGE AND:",
        "box_c": "Box C - I HAVE/HAVE HAD:",
        "box_d": "Box D - I HAVE/HAVE HAD:",
        "box_e": "Box E - I HAVE/HAVE HAD:",
        "box_f": "Box F - I HAVE/HAVE HAD:",
        "box_g": "Box G - I HAVE HAD:",
    }

    def __init__(self, instance):
        """Initialize with QuestionnaireInstance."""
        self.instance = instance

    def get_respondent_name(self):
        """Get the display name of the respondent."""
        respondent = self.instance.respondent
        if respondent and hasattr(respondent, "person") and respondent.person:
            return f"{respondent.person.first_name} {respondent.person.last_name}"
        elif respondent:
            return str(respondent)
        return "Unknown"

    def get_organized_questions(self):
        """Get questions organized by category with responses.

        Returns a structure like:
        {
            'screening': [
                {'question': Q, 'response': R, 'answer': 'Yes/No', 'flagged': bool, 'opens_box': 'box_a'},
                ...
            ],
            'follow_up_boxes': [
                {'box_key': 'box_a', 'title': 'Box A - ...', 'parent_sequence': 1, 'visible': True, 'questions': [...]},
                ...
            ]
        }
        """
        questions = list(self.instance.definition.questions.filter(
            deleted_at__isnull=True
        ).order_by("sequence"))

        responses = {r.question_id: r for r in self.instance.responses.all()}

        # Build screening questions list
        screening = []
        screening_answers = {}  # sequence -> bool answer

        # Build follow-up boxes
        follow_up_boxes = {}

        for q in questions:
            response = responses.get(q.id)
            answer_bool = None
            answer_display = "Not answered"

            if response:
                if q.question_type == "yes_no":
                    if response.answer_bool is True:
                        answer_display = "Yes"
                        answer_bool = True
                    elif response.answer_bool is False:
                        answer_display = "No"
                        answer_bool = False
                elif q.question_type == "text":
                    answer_display = response.answer_text or "N/A"
                elif q.question_type == "number":
                    answer_display = str(response.answer_number) if response.answer_number else "N/A"
                elif q.question_type == "date":
                    answer_display = str(response.answer_date) if response.answer_date else "N/A"
                elif q.question_type in ("choice", "multi_choice"):
                    answer_display = ", ".join(response.answer_choices or []) or "N/A"

            item = {
                "question": q,
                "response": response,
                "answer_display": answer_display,
                "answer_bool": answer_bool,
                "is_flagged": response.triggered_flag if response else False,
            }

            # Get category from question metadata or validation_rules
            category = getattr(q, 'category', None)
            if not category and hasattr(q, 'metadata') and q.metadata:
                category = q.metadata.get('category')

            # Determine if this is a screening question (sequences 1-10)
            if q.sequence <= 10:
                # Check if this question opens a follow-up box
                opens_box = None
                if hasattr(q, 'validation_rules') and q.validation_rules:
                    opens_box = q.validation_rules.get('opens_box')
                elif q.sequence in self.BOX_MAPPING:
                    opens_box = self.BOX_MAPPING[q.sequence]

                item['opens_box'] = opens_box
                screening.append(item)
                screening_answers[q.sequence] = answer_bool
            else:
                # This is a follow-up question - determine which box it belongs to
                box_key = None
                if hasattr(q, 'validation_rules') and q.validation_rules:
                    show_if = q.validation_rules.get('show_if')
                    if show_if:
                        parent_seq = show_if.get('question_sequence')
                        if parent_seq in self.BOX_MAPPING:
                            box_key = self.BOX_MAPPING[parent_seq]

                if not box_key and hasattr(q, 'category'):
                    box_key = q.category

                if box_key:
                    if box_key not in follow_up_boxes:
                        # Find parent sequence for this box
                        parent_seq = None
                        for seq, bkey in self.BOX_MAPPING.items():
                            if bkey == box_key:
                                parent_seq = seq
                                break

                        follow_up_boxes[box_key] = {
                            'box_key': box_key,
                            'title': self.BOX_TITLES.get(box_key, box_key),
                            'parent_sequence': parent_seq,
                            'visible': screening_answers.get(parent_seq) is True,
                            'questions': [],
                        }
                    follow_up_boxes[box_key]['questions'].append(item)

        # Convert to sorted list
        box_order = ['box_a', 'box_b', 'box_c', 'box_d', 'box_e', 'box_f', 'box_g']
        sorted_boxes = []
        for box_key in box_order:
            if box_key in follow_up_boxes:
                sorted_boxes.append(follow_up_boxes[box_key])

        return {
            'screening': screening,
            'follow_up_boxes': sorted_boxes,
            'screening_answers': screening_answers,
        }

    def get_context(self) -> dict:
        """Build template context for rendering."""
        instance = self.instance
        metadata = instance.metadata or {}
        signature_data = metadata.get("signature", {})
        fingerprint_data = metadata.get("fingerprint", {})

        # Get definition metadata
        definition_metadata = {}
        if hasattr(instance.definition, 'metadata') and instance.definition.metadata:
            definition_metadata = instance.definition.metadata

        organized = self.get_organized_questions()

        return {
            # Instance info
            "instance": instance,
            "definition": instance.definition,
            "definition_metadata": definition_metadata,
            "respondent_name": self.get_respondent_name(),
            "completed_at": instance.completed_at,
            "expires_at": instance.expires_at,
            "status": instance.status,

            # Organized questions
            "screening_questions": organized['screening'],
            "follow_up_boxes": organized['follow_up_boxes'],

            # Signature
            "signed_by_name": signature_data.get("signed_by_name", ""),
            "signature_image": signature_data.get("signature_full", ""),
            "signed_at": signature_data.get("signed_at", ""),
            "ip_address": signature_data.get("ip_address", ""),

            # Fingerprint
            "fingerprint": fingerprint_data,

            # Hash
            "document_hash": metadata.get("document_hash", ""),

            # Generation timestamp
            "generated_at": timezone.now(),
        }

    def render_html(self) -> str:
        """Render questionnaire to HTML string."""
        return render_to_string(self.TEMPLATE, self.get_context())

    def render_pdf(self) -> bytes:
        """Render questionnaire to PDF bytes.

        Returns:
            PDF file contents as bytes

        Raises:
            RuntimeError: If WeasyPrint is not installed
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError(
                "WeasyPrint is required for PDF generation. "
                "Install with: pip install weasyprint"
            )

        html_content = self.render_html()

        # Create PDF
        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf()

        return pdf_bytes

    def generate_filename(self) -> str:
        """Generate a filename for the PDF."""
        respondent_name = self.get_respondent_name().replace(" ", "_")
        date_str = self.instance.completed_at.strftime("%Y%m%d") if self.instance.completed_at else timezone.now().strftime("%Y%m%d")
        return f"medical_questionnaire_{respondent_name}_{date_str}.pdf"


def generate_and_store_medical_pdf(instance, actor=None):
    """Generate PDF and store it as a document attached to the diver.

    Args:
        instance: QuestionnaireInstance with completed responses
        actor: User performing the action (for audit)

    Returns:
        tuple: (Document instance, pdf_file_hash)

    Raises:
        ValueError: If instance has no respondent (diver)
    """
    import hashlib
    from django.core.files.base import ContentFile
    from django_documents.services import attach_document

    # Ensure we have a diver to attach the document to
    diver = instance.respondent
    if not diver:
        raise ValueError("Cannot generate medical PDF: questionnaire instance has no respondent (diver)")

    # Generate PDF
    service = MedicalQuestionnairePDFService(instance)
    pdf_bytes = service.render_pdf()
    filename = service.generate_filename()

    # Hash the PDF file itself for integrity
    pdf_file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Create file content
    pdf_file = ContentFile(pdf_bytes, name=filename)

    # Attach document to the DIVER (not the questionnaire instance)
    # This links the signed medical PDF to the diver for easy access
    document = attach_document(
        target=diver,
        file=pdf_file,
        document_type="signed_medical_questionnaire",
        uploaded_by=actor,
        filename=filename,
        content_type="application/pdf",
        description=f"Signed medical questionnaire for {service.get_respondent_name()}",
        metadata={
            "questionnaire_instance_id": str(instance.pk),
            "respondent_id": str(diver.pk),
            "definition_slug": instance.definition.slug,
            "definition_name": instance.definition.name,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
            "expires_at": instance.expires_at.isoformat() if instance.expires_at else None,
            "document_hash": instance.metadata.get("document_hash", "") if instance.metadata else "",
            "pdf_file_hash": pdf_file_hash,
            "status": instance.status,
        },
    )

    # Update instance metadata with PDF document reference
    if instance.metadata is None:
        instance.metadata = {}
    instance.metadata["pdf_document_id"] = str(document.pk)
    instance.metadata["pdf_file_hash"] = pdf_file_hash
    instance.save(update_fields=["metadata"])

    return document, pdf_file_hash
