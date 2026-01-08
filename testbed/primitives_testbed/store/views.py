"""Store views for shopping and checkout."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView

from django_catalog.models import CatalogItem
from django_portal_ui.mixins import PublicViewMixin

from . import services
from .models import StoreOrder


class ShopListView(PublicViewMixin, ListView):
    """Public catalog listing for store."""

    template_name = "store/shop_list.html"
    context_object_name = "items"

    def get_queryset(self):
        return CatalogItem.objects.filter(
            active=True,
            is_billable=True,
            deleted_at__isnull=True,
        ).order_by("display_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add prices to items
        items_with_prices = []
        for item in context["items"]:
            price = services.get_item_price(item)
            items_with_prices.append({
                "item": item,
                "price": price,
            })
        context["items_with_prices"] = items_with_prices
        return context


class ShopDetailView(PublicViewMixin, DetailView):
    """Product detail page."""

    template_name = "store/shop_detail.html"
    context_object_name = "item"

    def get_object(self):
        return get_object_or_404(
            CatalogItem,
            pk=self.kwargs["item_id"],
            active=True,
            deleted_at__isnull=True,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["price"] = services.get_item_price(self.object)
        return context


class CartView(LoginRequiredMixin, TemplateView):
    """Shopping cart view."""

    template_name = "store/cart.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart_items"] = services.get_cart_items(self.request.user)
        context["cart_total"] = services.get_cart_total(self.request.user)
        return context


class AddToCartView(LoginRequiredMixin, View):
    """Add item to cart (POST only)."""

    login_url = "/accounts/login/"

    def post(self, request, item_id):
        item = get_object_or_404(
            CatalogItem,
            pk=item_id,
            active=True,
            deleted_at__isnull=True,
        )

        quantity = int(request.POST.get("quantity", 1))
        if quantity < 1:
            quantity = 1

        services.add_to_cart(request.user, item, quantity)
        messages.success(request, f"Added {item.display_name} to cart")

        # Redirect back to shop or cart
        next_url = request.POST.get("next", reverse("store:cart"))
        return HttpResponseRedirect(next_url)


class UpdateCartView(LoginRequiredMixin, View):
    """Update cart item quantity (POST only)."""

    login_url = "/accounts/login/"

    def post(self, request, item_id):
        quantity = int(request.POST.get("quantity", 0))
        services.update_cart_item(request.user, item_id, quantity)

        if quantity == 0:
            messages.info(request, "Item removed from cart")
        else:
            messages.success(request, "Cart updated")

        return redirect("store:cart")


class RemoveFromCartView(LoginRequiredMixin, View):
    """Remove item from cart (POST only)."""

    login_url = "/accounts/login/"

    def post(self, request, item_id):
        services.remove_from_cart(request.user, item_id)
        messages.info(request, "Item removed from cart")
        return redirect("store:cart")


class CheckoutView(LoginRequiredMixin, TemplateView):
    """Checkout page."""

    template_name = "store/checkout.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart_items"] = services.get_cart_items(self.request.user)
        context["cart_total"] = services.get_cart_total(self.request.user)
        return context

    def post(self, request):
        """Process checkout and create order."""
        try:
            order = services.create_order_from_cart(request.user)
            messages.success(request, f"Order {order.order_number} created successfully!")
            return redirect("store:checkout_complete", order_id=order.pk)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("store:cart")


class CheckoutCompleteView(LoginRequiredMixin, DetailView):
    """Order confirmation page."""

    template_name = "store/checkout_complete.html"
    context_object_name = "order"
    login_url = "/accounts/login/"

    def get_object(self):
        return get_object_or_404(
            StoreOrder,
            pk=self.kwargs["order_id"],
            user=self.request.user,
        )


class MarkOrderPaidView(LoginRequiredMixin, View):
    """Staff/dev action to mark order as paid (triggers fulfillment)."""

    login_url = "/accounts/login/"

    def post(self, request, order_id):
        order = get_object_or_404(
            StoreOrder,
            pk=order_id,
            user=request.user,
        )

        try:
            services.mark_order_paid(order, actor=request.user)
            messages.success(
                request,
                f"Order {order.order_number} marked as paid. Entitlements granted!",
            )
        except ValueError as e:
            messages.error(request, str(e))

        return redirect("store:checkout_complete", order_id=order.pk)
