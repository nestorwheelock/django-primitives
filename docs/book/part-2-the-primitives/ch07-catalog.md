# Chapter 7: Catalog

> What can be sold, performed, or consumed.

## The Primitive

**Catalog** answers: What things exist in this system that can be ordered, scheduled, or tracked?

- Products, services, labor
- Definitions, not instances
- No workflow logic here
- Pricing rules, not prices

## django-primitives Implementation

- `django-catalog`: CatalogItem, Basket, BasketItem, Order, WorkItem

## Historical Origin

Every marketplace needs a catalog. The Sears catalog. Restaurant menus. Service rate cards. Before you can transact, you must define what can be transacted.

## Failure Mode When Ignored

- Products scattered across tables
- No separation between definition and instance
- Prices stored on orders (not computed)
- No basket/order lifecycle
- Workflow logic mixed with product logic

## Minimal Data Model

```python
class CatalogItem(models.Model):
    id = UUIDField(primary_key=True)
    item_type = CharField()  # product, service, bundle
    name = CharField()
    sku = CharField(unique=True)
    is_active = BooleanField(default=True)
    metadata = JSONField()

class Basket(models.Model):
    id = UUIDField(primary_key=True)
    owner = ForeignKey(Party)
    status = CharField()  # draft, committed, cancelled
    created_at = DateTimeField()
    committed_at = DateTimeField(null=True)

class BasketItem(models.Model):
    basket = ForeignKey(Basket)
    catalog_item = ForeignKey(CatalogItem)
    quantity = DecimalField()
    unit_price_snapshot = DecimalField()  # Frozen at add time
```

## Invariants That Must Never Break

1. Catalog defines, transactions consume
2. Prices snapshot at transaction time
3. Baskets are immutable after commit
4. Items track lineage to catalog
5. Workflow lives elsewhere (encounters, worklog)

---

*Status: Planned*
