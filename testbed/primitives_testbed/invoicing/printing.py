"""Invoice PDF rendering service.

Uses WeasyPrint to render HTML templates to PDF.
Renders from snapshotted Invoice + InvoiceLineItem data only.
"""

import io
from pathlib import Path

from django.template.loader import render_to_string
from django.conf import settings

from .selectors import InvoicePrintData

# WeasyPrint is imported lazily inside render_pdf() to avoid
# 9+ second cold-start penalty on every URL resolver warmup.
# See: render_pdf() method for actual import.


class InvoicePrintService:
    """Service for rendering invoices to HTML and PDF.

    Uses snapshotted data from Invoice and InvoiceLineItem models.
    Never accesses live pricing or catalog data.
    """

    TEMPLATE = "invoicing/invoice_print.html"
    CSS_FILE = "invoicing/print.css"

    def __init__(self, invoice_data: InvoicePrintData):
        """Initialize with InvoicePrintData from selector."""
        self.invoice = invoice_data.invoice
        self.billed_to_address = invoice_data.billed_to_address
        self.issued_by_address = invoice_data.issued_by_address

    def get_context(self) -> dict:
        """Build template context for rendering.

        All data comes from snapshotted Invoice fields.
        """
        invoice = self.invoice

        # Get line items from prefetched queryset
        line_items = list(invoice.line_items.all())

        return {
            # Invoice metadata
            "invoice": invoice,
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "currency": invoice.currency,
            # Dates
            "created_at": invoice.created_at,
            "issued_at": invoice.issued_at,
            "due_at": invoice.due_at,
            "paid_at": invoice.paid_at,
            # Parties
            "billed_to": invoice.billed_to,
            "billed_to_name": _get_party_name(invoice.billed_to),
            "billed_to_address": self.billed_to_address,
            "issued_by": invoice.issued_by,
            "issued_by_name": invoice.issued_by.name if invoice.issued_by else "",
            "issued_by_address": self.issued_by_address,
            # Line items (snapshotted data)
            "line_items": line_items,
            # Totals - use Money properties for formatting
            "subtotal": invoice.subtotal,
            "tax": invoice.tax,
            "total": invoice.total,
            # Optional references
            "agreement": invoice.agreement,
            "encounter": invoice.encounter,
            # Notes
            "notes": invoice.notes,
        }

    def render_html(self) -> str:
        """Render invoice to HTML string."""
        return render_to_string(self.TEMPLATE, self.get_context())

    def render_pdf(self) -> bytes:
        """Render invoice to PDF bytes.

        Returns:
            PDF file contents as bytes

        Raises:
            RuntimeError: If WeasyPrint is not installed
        """
        # Lazy import WeasyPrint to avoid 9+ second cold-start penalty
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise RuntimeError(
                "WeasyPrint is required for PDF generation. "
                "Install with: pip install weasyprint"
            )

        html_content = self.render_html()

        # Try to load print CSS
        css_content = None
        static_root = getattr(settings, "STATIC_ROOT", None)
        if static_root:
            css_path = Path(static_root) / self.CSS_FILE
            if css_path.exists():
                with open(css_path) as f:
                    css_content = CSS(string=f.read())

        # Try staticfiles dirs
        if css_content is None:
            staticfiles_dirs = getattr(settings, "STATICFILES_DIRS", [])
            for static_dir in staticfiles_dirs:
                css_path = Path(static_dir) / self.CSS_FILE
                if css_path.exists():
                    with open(css_path) as f:
                        css_content = CSS(string=f.read())
                    break

        # Create PDF
        base_url = str(getattr(settings, "BASE_DIR", "."))
        html = HTML(string=html_content, base_url=base_url)

        pdf_buffer = io.BytesIO()
        if css_content:
            html.write_pdf(pdf_buffer, stylesheets=[css_content])
        else:
            html.write_pdf(pdf_buffer)

        return pdf_buffer.getvalue()

    def get_filename(self) -> str:
        """Generate deterministic filename for PDF download."""
        # Use invoice number for deterministic naming
        safe_number = self.invoice.invoice_number.replace("/", "-").replace("\\", "-")
        return f"invoice-{safe_number}.pdf"


def _get_party_name(party) -> str:
    """Get display name for a party (Person or Organization)."""
    if party is None:
        return ""

    # Try Person methods
    if hasattr(party, "get_full_name"):
        name = party.get_full_name()
        if name:
            return name

    # Try display_name
    if hasattr(party, "display_name") and party.display_name:
        return party.display_name

    # Try first/last name
    if hasattr(party, "first_name") and hasattr(party, "last_name"):
        parts = [party.first_name or "", party.last_name or ""]
        name = " ".join(p for p in parts if p)
        if name:
            return name

    # Try name (for Organization)
    if hasattr(party, "name") and party.name:
        return party.name

    return str(party)


def render_invoice_pdf(invoice_data: InvoicePrintData) -> bytes:
    """Convenience function to render invoice to PDF."""
    service = InvoicePrintService(invoice_data)
    return service.render_pdf()


def render_invoice_html(invoice_data: InvoicePrintData) -> str:
    """Convenience function to render invoice to HTML."""
    service = InvoicePrintService(invoice_data)
    return service.render_html()
