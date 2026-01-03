"""URL configuration for invoicing module."""

from django.urls import path

from . import views

app_name = "invoicing"

urlpatterns = [
    # HTML print preview
    path(
        "<uuid:invoice_id>/print/",
        views.invoice_print_html,
        name="invoice_print_html",
    ),
    # PDF download
    path(
        "<uuid:invoice_id>/pdf/",
        views.invoice_download_pdf,
        name="invoice_download_pdf",
    ),
    # PDF inline view
    path(
        "<uuid:invoice_id>/pdf/view/",
        views.invoice_view_pdf,
        name="invoice_view_pdf",
    ),
]
