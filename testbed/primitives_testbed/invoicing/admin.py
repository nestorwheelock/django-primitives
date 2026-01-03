"""Django admin configuration for invoicing module."""

from django.contrib import admin

from .models import Invoice, InvoiceLineItem


class InvoiceLineItemInline(admin.TabularInline):
    """Inline for invoice line items."""

    model = InvoiceLineItem
    extra = 0
    readonly_fields = [
        "description",
        "quantity",
        "unit_price_amount",
        "line_total_amount",
        "tax_rate",
        "tax_amount",
        "price_scope_type",
        "price_rule_id",
        "created_at",
    ]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for Invoice model."""

    list_display = [
        "invoice_number",
        "status",
        "billed_to",
        "issued_by",
        "total_display",
        "created_at",
        "issued_at",
    ]
    list_filter = ["status", "currency", "created_at"]
    search_fields = ["invoice_number", "billed_to__first_name", "billed_to__last_name"]
    readonly_fields = [
        "id",
        "invoice_number",
        "basket",
        "encounter",
        "billed_to",
        "issued_by",
        "agreement",
        "subtotal_amount",
        "tax_amount",
        "total_amount",
        "currency",
        "ledger_transaction",
        "created_at",
        "updated_at",
        "issued_at",
        "paid_at",
        "created_by",
    ]
    inlines = [InvoiceLineItemInline]

    def total_display(self, obj):
        return f"{obj.currency} {obj.total_amount}"

    total_display.short_description = "Total"


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    """Admin for InvoiceLineItem model."""

    list_display = [
        "invoice",
        "description",
        "quantity",
        "unit_price_amount",
        "line_total_amount",
    ]
    list_filter = ["price_scope_type"]
    search_fields = ["description", "invoice__invoice_number"]
    readonly_fields = [
        "id",
        "invoice",
        "priced_basket_item",
        "description",
        "quantity",
        "unit_price_amount",
        "line_total_amount",
        "tax_rate",
        "tax_amount",
        "price_scope_type",
        "price_rule_id",
        "created_at",
    ]
