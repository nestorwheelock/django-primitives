"""Views for invoice printing.

Provides HTML print preview and PDF download endpoints.
All views require authentication and enforce org access control.
"""

from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .exceptions import InvoiceAccessDeniedError, InvoiceNotPrintableError
from .models import Invoice
from .printing import InvoicePrintService
from .selectors import get_invoice_for_print


@require_GET
@login_required
def invoice_print_html(request, invoice_id: UUID):
    """HTML print preview of an invoice.

    Renders the invoice in a print-friendly HTML format.
    User can use browser's print function (Ctrl+P).
    """
    try:
        invoice_data = get_invoice_for_print(
            invoice_id,
            request.user,
            check_org_access=True,
        )
    except Invoice.DoesNotExist:
        raise Http404("Invoice not found")
    except InvoiceNotPrintableError as e:
        return HttpResponse(str(e), status=400, content_type="text/plain")
    except InvoiceAccessDeniedError:
        return HttpResponse("Access denied", status=403, content_type="text/plain")

    service = InvoicePrintService(invoice_data)
    context = service.get_context()

    return render(request, "invoicing/invoice_print.html", context)


@require_GET
@login_required
def invoice_download_pdf(request, invoice_id: UUID):
    """Download invoice as PDF file.

    Generates a PDF from the invoice template and returns
    it as a file download (Content-Disposition: attachment).
    """
    try:
        invoice_data = get_invoice_for_print(
            invoice_id,
            request.user,
            check_org_access=True,
        )
    except Invoice.DoesNotExist:
        raise Http404("Invoice not found")
    except InvoiceNotPrintableError as e:
        return HttpResponse(str(e), status=400, content_type="text/plain")
    except InvoiceAccessDeniedError:
        return HttpResponse("Access denied", status=403, content_type="text/plain")

    service = InvoicePrintService(invoice_data)

    try:
        pdf_bytes = service.render_pdf()
    except RuntimeError as e:
        return HttpResponse(str(e), status=500, content_type="text/plain")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{service.get_filename()}"'

    return response


@require_GET
@login_required
def invoice_view_pdf(request, invoice_id: UUID):
    """View invoice PDF inline in browser.

    Same as download but with Content-Disposition: inline
    so browser displays the PDF instead of downloading.
    """
    try:
        invoice_data = get_invoice_for_print(
            invoice_id,
            request.user,
            check_org_access=True,
        )
    except Invoice.DoesNotExist:
        raise Http404("Invoice not found")
    except InvoiceNotPrintableError as e:
        return HttpResponse(str(e), status=400, content_type="text/plain")
    except InvoiceAccessDeniedError:
        return HttpResponse("Access denied", status=403, content_type="text/plain")

    service = InvoicePrintService(invoice_data)

    try:
        pdf_bytes = service.render_pdf()
    except RuntimeError as e:
        return HttpResponse(str(e), status=500, content_type="text/plain")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{service.get_filename()}"'

    return response
