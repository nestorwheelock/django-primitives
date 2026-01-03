"""URL configuration for pricing module."""

from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    # HTML views
    path("", views.price_list, name="price_list"),
    path("resolver/", views.price_resolver, name="resolver"),

    # API endpoints
    path("api/prices/", views.api_prices, name="api_prices"),
    path("api/prices/create/", views.api_price_create, name="api_price_create"),
    path("api/resolve/", views.api_resolve_price, name="api_resolve"),
    path("api/explain/", views.api_explain_price, name="api_explain"),
]
