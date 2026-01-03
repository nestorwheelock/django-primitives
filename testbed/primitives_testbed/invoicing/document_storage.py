"""Optional invoice PDF storage service.

Stores generated PDFs as Document attachments with checksums.
Disabled by default - enable with INVOICE_STORE_PDF = True in settings.

CRITICAL: Once a PDF is stored, it cannot be regenerated or overwritten.
This ensures invoice immutability for audit and compliance purposes.
"""

import hashlib
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile

from .models import Invoice
from .printing import InvoicePrintService
from .selectors import get_invoice_for_print


INVOICE_DOCUMENT_TYPE = "invoice_pdf"


class InvoicePDFExistsError(Exception):
    """Raised when attempting to store a PDF for an invoice that already has one."""

    def __init__(self, invoice_pk):
        self.invoice_pk = invoice_pk
        super().__init__(
            f"Invoice {invoice_pk} already has a stored PDF. "
            "Invoice PDFs cannot be overwritten."
        )


def is_pdf_storage_enabled() -> bool:
    """Check if invoice PDF storage is enabled.

    Returns:
        True if INVOICE_STORE_PDF is True in settings, False otherwise.
    """
    return getattr(settings, "INVOICE_STORE_PDF", False)


def get_stored_pdf(invoice: Invoice):
    """Get the stored PDF document for an invoice, if any.

    Args:
        invoice: The invoice to check

    Returns:
        Document instance if a PDF exists, None otherwise
    """
    # Lazy import to avoid circular dependency and allow optional use
    try:
        from django_documents.models import Document
    except ImportError:
        return None

    return (
        Document.objects.for_target(invoice)
        .filter(document_type=INVOICE_DOCUMENT_TYPE)
        .first()
    )


def has_stored_pdf(invoice: Invoice) -> bool:
    """Check if an invoice has a stored PDF.

    Args:
        invoice: The invoice to check

    Returns:
        True if invoice has a stored PDF, False otherwise
    """
    return get_stored_pdf(invoice) is not None


def store_invoice_pdf(invoice: Invoice, user) -> "Document":
    """Store a generated PDF for the invoice.

    This operation is APPEND-ONLY. Once a PDF is stored, it cannot be
    regenerated or overwritten. This ensures invoice immutability.

    Args:
        invoice: The invoice to store PDF for
        user: The user performing the action (for audit trail)

    Returns:
        The created Document instance

    Raises:
        RuntimeError: If PDF storage is disabled
        InvoicePDFExistsError: If invoice already has a stored PDF
        InvoiceNotPrintableError: If invoice cannot be printed
        InvoiceAccessDeniedError: If user lacks access
    """
    # Check feature flag
    if not is_pdf_storage_enabled():
        raise RuntimeError(
            "Invoice PDF storage is disabled. "
            "Set INVOICE_STORE_PDF = True in settings to enable."
        )

    # Check for existing PDF (immutability)
    if has_stored_pdf(invoice):
        raise InvoicePDFExistsError(invoice.pk)

    # Lazy import Document
    try:
        from django_documents.models import Document
    except ImportError:
        raise RuntimeError(
            "django-documents is required for invoice PDF storage. "
            "Install with: pip install django-documents"
        )

    # Get print data and render PDF
    invoice_data = get_invoice_for_print(invoice.pk, user)
    service = InvoicePrintService(invoice_data)
    pdf_bytes = service.render_pdf()
    filename = service.get_filename()

    # Compute checksum
    checksum = hashlib.sha256(pdf_bytes).hexdigest()

    # Create Document
    pdf_file = ContentFile(pdf_bytes, name=filename)
    document = Document.objects.create(
        target=invoice,
        file=pdf_file,
        filename=filename,
        content_type="application/pdf",
        file_size=len(pdf_bytes),
        document_type=INVOICE_DOCUMENT_TYPE,
        checksum=checksum,
        metadata={
            "invoice_number": invoice.invoice_number,
            "invoice_status": invoice.status,
            "stored_by": str(user.pk) if hasattr(user, "pk") else str(user),
        },
    )

    return document
