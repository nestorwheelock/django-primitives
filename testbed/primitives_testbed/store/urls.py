"""Store URL routes."""

from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    # Public catalog
    path("", views.ShopListView.as_view(), name="list"),
    path("<uuid:item_id>/", views.ShopDetailView.as_view(), name="detail"),
    # Cart (requires login)
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/add/<uuid:item_id>/", views.AddToCartView.as_view(), name="add_to_cart"),
    path("cart/update/<uuid:item_id>/", views.UpdateCartView.as_view(), name="update_cart"),
    path("cart/remove/<uuid:item_id>/", views.RemoveFromCartView.as_view(), name="remove_from_cart"),
    # Checkout
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("checkout/complete/<uuid:order_id>/", views.CheckoutCompleteView.as_view(), name="checkout_complete"),
    # Dev action: mark paid
    path("checkout/<uuid:order_id>/mark-paid/", views.MarkOrderPaidView.as_view(), name="mark_paid"),
]
