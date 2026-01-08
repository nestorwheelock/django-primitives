"""Store context processors."""

from .models import StoreCart


def cart_context(request):
    """Add cart info to all templates."""
    cart_item_count = 0

    if request.user.is_authenticated:
        try:
            cart = StoreCart.objects.get(user=request.user)
            cart_item_count = cart.item_count
        except StoreCart.DoesNotExist:
            pass

    return {
        "cart_item_count": cart_item_count,
    }
