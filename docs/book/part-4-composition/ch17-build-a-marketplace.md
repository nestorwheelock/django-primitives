# Chapter 17: Build a Marketplace

> Same primitives. E-commerce domain.

## The Domain

A pizza delivery marketplace needs:

- Customers and vendors
- Menu items
- Shopping cart
- Orders
- Payments
- Delivery zones
- Driver dispatch

## Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Customer | Party (Person) | django-parties |
| Pizzeria | Party (Organization) | django-parties |
| Driver | Party (Person) + Role | django-parties, django-rbac |
| Menu item | CatalogItem | django-catalog |
| Shopping cart | Basket | django-catalog |
| Order | Order (committed Basket) | django-catalog |
| Order line | BasketItem | django-catalog |
| Payment | Transaction | django-ledger |
| Delivery zone | ServiceArea | django-geo |
| Driver shift | WorkSession | django-worklog |
| Delivery | Encounter | django-encounters |
| Tip | Entry | django-ledger |

## The Half-Topping Problem

"But pizza has half-toppings!"

This is configuration, not a new primitive:

```python
# CatalogItem for topping
topping = CatalogItem.objects.create(
    name="Pepperoni",
    item_type="topping",
    metadata={
        "allows_half": True,
        "half_price_multiplier": 0.5
    }
)

# BasketItem with half-topping
BasketItem.objects.create(
    basket=cart,
    catalog_item=topping,
    quantity=0.5,  # Half
    unit_price_snapshot=topping.price * 0.5
)
```

No new primitives. Just configuration.

## The Combo Deal Problem

"But we have combo deals!"

This is an Agreement with Terms:

```python
Agreement.objects.create(
    agreement_type="promotion",
    terms={
        "items": ["pizza_id", "drink_id", "side_id"],
        "discount_type": "fixed_price",
        "discount_value": "19.99",
        "valid_days": ["friday", "saturday"],
    },
    valid_from=now(),
    valid_to=now() + timedelta(days=30)
)
```

No new primitives. Just agreements.

## The Pattern

Every "special case" maps to existing primitives with domain-specific configuration.

---

*Status: Planned*
