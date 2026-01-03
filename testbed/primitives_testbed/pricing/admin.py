"""Admin configuration for the pricing module."""

from django.contrib import admin

from .models import Price, PricedBasketItem


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = [
        "catalog_item",
        "amount",
        "currency",
        "scope_type",
        "priority",
        "valid_from",
        "valid_to",
        "created_by",
    ]
    list_filter = ["currency", "priority", "created_at"]
    search_fields = ["catalog_item__display_name", "reason"]
    readonly_fields = ["created_at", "scope_type"]
    raw_id_fields = ["catalog_item", "organization", "party", "agreement", "created_by"]
    ordering = ["-created_at"]

    fieldsets = (
        ("Item", {"fields": ("catalog_item",)}),
        ("Price", {"fields": ("amount", "currency", "priority")}),
        (
            "Scope (leave all blank for global price)",
            {"fields": ("organization", "party", "agreement")},
        ),
        ("Validity", {"fields": ("valid_from", "valid_to")}),
        ("Audit", {"fields": ("created_by", "reason", "created_at")}),
    )


@admin.register(PricedBasketItem)
class PricedBasketItemAdmin(admin.ModelAdmin):
    list_display = [
        "basket_item",
        "unit_price_amount",
        "unit_price_currency",
        "resolved_at",
    ]
    list_filter = ["unit_price_currency", "resolved_at"]
    raw_id_fields = ["basket_item", "price_rule"]
    readonly_fields = ["resolved_at"]
