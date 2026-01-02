# Chapter 24: Build a Marketplace

## The Pizza Problem

"But pizza has half-toppings."

This objection comes up in every conversation about ERP primitives. The implication is that pizza ordering is somehow special—that the half-topping requirement means you need a custom data model, a specialized ordering system, a pizza-specific architecture.

It doesn't.

Half-toppings are configuration. Combo deals are agreements. Delivery zones are service areas. Driver dispatch is work sessions. Tips are ledger entries. Every "unique" pizza requirement maps to an existing primitive.

This chapter builds a pizza delivery marketplace to prove it.

---

## What We're Building

A multi-vendor pizza delivery marketplace:

- **Multiple pizzerias** - Each with their own menu and pricing
- **Customer ordering** - Browse, customize, checkout
- **Half-toppings** - The infamous pizza special case
- **Combo deals** - Promotional pricing
- **Delivery zones** - Geographic service areas
- **Driver dispatch** - Assignment and tracking
- **Split payments** - Customer to platform to vendor
- **Tips** - Pass-through to drivers

No new primitives. Just composition.

---

## The Primitive Mapping

| Domain Concept | Primitive | Package |
|----------------|-----------|---------|
| Customer | Party (Person) | django-parties |
| Pizzeria | Party (Organization) | django-parties |
| Driver | Party (Person) + Role | django-parties, django-rbac |
| Menu item | CatalogItem | django-catalog |
| Topping | CatalogItem | django-catalog |
| Shopping cart | Basket | django-catalog |
| Order | Basket (committed) | django-catalog |
| Line item | BasketItem | django-catalog |
| Payment | Transaction | django-ledger |
| Platform fee | Entry | django-ledger |
| Vendor payout | Entry | django-ledger |
| Tip | Entry | django-ledger |
| Delivery zone | ServiceArea | django-geo |
| Driver shift | WorkSession | django-worklog |
| Delivery | Encounter | django-encounters |
| Combo deal | Agreement | django-agreements |
| Promo code | Agreement | django-agreements |

---

## Project Setup

```python
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',

    # Primitives
    'django_basemodels',
    'django_parties',
    'django_rbac',
    'django_decisioning',
    'django_agreements',
    'django_audit_log',
    'django_money',
    'django_ledger',
    'django_sequence',
    'django_catalog',
    'django_encounters',
    'django_worklog',
    'django_geo',

    # Application
    'marketplace',
]
```

---

## The Menu: Catalog Configuration

### Pizza as CatalogItem

```python
# marketplace/catalog.py
from django_catalog.models import CatalogItem
from decimal import Decimal


def setup_pizzeria_menu(pizzeria):
    """Set up a pizzeria's menu items."""

    # Pizza base
    CatalogItem.objects.update_or_create(
        code=f'{pizzeria.code}-PIZZA-LARGE',
        defaults={
            'name': 'Large Pizza',
            'description': '16" hand-tossed pizza',
            'item_type': 'product',
            'unit_price': Decimal('14.99'),
            'organization': pizzeria,
            'metadata': {
                'category': 'pizza',
                'size': 'large',
                'diameter_inches': 16,
                'slices': 8,
                'allows_half_toppings': True,
                'max_toppings': 10,
            }
        }
    )

    CatalogItem.objects.update_or_create(
        code=f'{pizzeria.code}-PIZZA-MEDIUM',
        defaults={
            'name': 'Medium Pizza',
            'description': '12" hand-tossed pizza',
            'item_type': 'product',
            'unit_price': Decimal('11.99'),
            'organization': pizzeria,
            'metadata': {
                'category': 'pizza',
                'size': 'medium',
                'diameter_inches': 12,
                'slices': 6,
                'allows_half_toppings': True,
                'max_toppings': 8,
            }
        }
    )


def setup_toppings(pizzeria):
    """Set up toppings for a pizzeria."""

    toppings = [
        ('PEPPERONI', 'Pepperoni', Decimal('1.50')),
        ('SAUSAGE', 'Italian Sausage', Decimal('1.50')),
        ('MUSHROOM', 'Mushrooms', Decimal('1.00')),
        ('OLIVE', 'Black Olives', Decimal('1.00')),
        ('PEPPER', 'Green Peppers', Decimal('1.00')),
        ('ONION', 'Onions', Decimal('0.75')),
        ('BACON', 'Bacon', Decimal('2.00')),
        ('CHICKEN', 'Grilled Chicken', Decimal('2.50')),
        ('PINEAPPLE', 'Pineapple', Decimal('1.00')),
        ('JALAPENO', 'Jalapeños', Decimal('0.75')),
    ]

    for code, name, price in toppings:
        CatalogItem.objects.update_or_create(
            code=f'{pizzeria.code}-TOP-{code}',
            defaults={
                'name': name,
                'item_type': 'modifier',
                'unit_price': price,
                'organization': pizzeria,
                'metadata': {
                    'category': 'topping',
                    'half_price_multiplier': '0.5',  # Half toppings cost half
                }
            }
        )
```

### The Half-Topping Solution

Half-toppings are not a special case. They're a quantity:

```python
# marketplace/services/ordering.py
from django_catalog.models import Basket, BasketItem, CatalogItem
from decimal import Decimal


def add_pizza_to_cart(
    basket,
    pizza_item,
    quantity: int = 1,
    toppings=None,
):
    """
    Add a pizza with toppings to the cart.

    Toppings format: [
        {'code': 'PEPPERONI', 'coverage': 'full'},
        {'code': 'MUSHROOM', 'coverage': 'left'},
        {'code': 'OLIVE', 'coverage': 'right'},
    ]
    """
    toppings = toppings or []

    # Add the pizza base
    pizza_line = BasketItem.objects.create(
        basket=basket,
        catalog_item=pizza_item,
        quantity=quantity,
        unit_price_snapshot=pizza_item.unit_price,
        metadata={
            'toppings': [],  # Will be filled below
        }
    )

    # Add each topping
    topping_details = []
    for topping in toppings:
        topping_item = CatalogItem.objects.get(
            code=topping['code'],
            organization=pizza_item.organization,
        )

        coverage = topping.get('coverage', 'full')

        # Calculate price based on coverage
        if coverage in ('left', 'right'):
            # Half topping = half price
            multiplier = Decimal(
                topping_item.metadata.get('half_price_multiplier', '0.5')
            )
        else:
            multiplier = Decimal('1')

        topping_price = topping_item.unit_price * multiplier

        # Add topping as basket item
        BasketItem.objects.create(
            basket=basket,
            catalog_item=topping_item,
            quantity=quantity,  # Same quantity as pizzas
            unit_price_snapshot=topping_price,
            parent_item=pizza_line,  # Link to pizza
            metadata={
                'coverage': coverage,
                'parent_pizza_id': str(pizza_line.id),
            }
        )

        topping_details.append({
            'name': topping_item.name,
            'coverage': coverage,
            'price': str(topping_price),
        })

    # Update pizza metadata with topping summary
    pizza_line.metadata['toppings'] = topping_details
    pizza_line.save(update_fields=['metadata'])

    return pizza_line
```

That's it. Half-toppings are just a quantity multiplier with metadata tracking which half.

---

## Combo Deals: Agreements with Pricing Rules

### Defining a Combo

```python
# marketplace/services/promotions.py
from django_agreements import create_agreement
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def create_combo_deal(
    pizzeria,
    name: str,
    items: list,
    combo_price: Decimal,
    valid_days: list = None,
    valid_from=None,
    valid_to=None,
):
    """
    Create a combo deal as an Agreement.

    items format: [
        {'code': 'PIZZA-LARGE', 'quantity': 1},
        {'code': 'DRINK-2L', 'quantity': 1},
        {'code': 'BREADSTICKS', 'quantity': 1},
    ]
    """
    valid_from = valid_from or timezone.now()
    valid_to = valid_to or (valid_from + timedelta(days=30))

    return create_agreement(
        agreement_type='combo_deal',
        parties=[pizzeria],
        terms={
            'name': name,
            'items': items,
            'combo_price': str(combo_price),
            'valid_days': valid_days or ['monday', 'tuesday', 'wednesday',
                                          'thursday', 'friday', 'saturday', 'sunday'],
            'discount_type': 'fixed_price',
        },
        valid_from=valid_from,
        valid_to=valid_to,
        metadata={
            'pizzeria_id': str(pizzeria.id),
            'display_name': name,
        }
    )


def get_active_combos(pizzeria, as_of=None):
    """Get all active combo deals for a pizzeria."""
    from django_agreements.models import Agreement

    as_of = as_of or timezone.now()
    day_of_week = as_of.strftime('%A').lower()

    return Agreement.objects.filter(
        agreement_type='combo_deal',
        parties=pizzeria,
    ).current(as_of=as_of).filter(
        terms__valid_days__contains=day_of_week
    )


def apply_combo_to_cart(basket, combo_agreement):
    """
    Apply a combo deal to a cart.

    Validates that all required items are present,
    then applies the combo pricing.
    """
    from django_catalog.models import BasketItem

    required_items = combo_agreement.terms['items']
    combo_price = Decimal(combo_agreement.terms['combo_price'])

    # Check all items are present
    for required in required_items:
        matching = basket.items.filter(
            catalog_item__code__endswith=required['code'],
            quantity__gte=required['quantity']
        ).first()

        if not matching:
            raise ValueError(
                f"Combo requires {required['quantity']}x {required['code']}"
            )

    # Calculate discount
    items_total = sum(
        item.unit_price_snapshot * item.quantity
        for item in basket.items.all()
        if any(
            item.catalog_item.code.endswith(r['code'])
            for r in required_items
        )
    )

    discount = items_total - combo_price

    # Add discount line
    return BasketItem.objects.create(
        basket=basket,
        catalog_item=None,
        description=f"Combo: {combo_agreement.terms['name']}",
        quantity=1,
        unit_price_snapshot=-discount,
        metadata={
            'combo_id': str(combo_agreement.id),
            'combo_name': combo_agreement.terms['name'],
            'original_total': str(items_total),
            'combo_price': str(combo_price),
        }
    )
```

---

## Delivery Zones: Geographic Service Areas

### Setting Up Zones

```python
# marketplace/services/delivery.py
from django_geo.models import ServiceArea, GeoPoint
from decimal import Decimal


def setup_delivery_zones(pizzeria, location):
    """Set up delivery zones around a pizzeria location."""

    # Free delivery zone (within 3km)
    ServiceArea.objects.update_or_create(
        code=f'{pizzeria.code}-ZONE-FREE',
        defaults={
            'name': f'{pizzeria.name} - Free Delivery',
            'area_type': 'delivery',
            'center_latitude': location.latitude,
            'center_longitude': location.longitude,
            'radius_km': Decimal('3.0'),
            'is_active': True,
            'metadata': {
                'pizzeria_id': str(pizzeria.id),
                'delivery_fee': '0.00',
                'min_order': '15.00',
            }
        }
    )

    # Standard delivery zone (3-7km)
    ServiceArea.objects.update_or_create(
        code=f'{pizzeria.code}-ZONE-STANDARD',
        defaults={
            'name': f'{pizzeria.name} - Standard Delivery',
            'area_type': 'delivery',
            'center_latitude': location.latitude,
            'center_longitude': location.longitude,
            'radius_km': Decimal('7.0'),
            'is_active': True,
            'metadata': {
                'pizzeria_id': str(pizzeria.id),
                'delivery_fee': '3.99',
                'min_order': '20.00',
                'excludes_zone': f'{pizzeria.code}-ZONE-FREE',
            }
        }
    )

    # Extended delivery zone (7-12km)
    ServiceArea.objects.update_or_create(
        code=f'{pizzeria.code}-ZONE-EXTENDED',
        defaults={
            'name': f'{pizzeria.name} - Extended Delivery',
            'area_type': 'delivery',
            'center_latitude': location.latitude,
            'center_longitude': location.longitude,
            'radius_km': Decimal('12.0'),
            'is_active': True,
            'metadata': {
                'pizzeria_id': str(pizzeria.id),
                'delivery_fee': '6.99',
                'min_order': '30.00',
                'excludes_zone': f'{pizzeria.code}-ZONE-STANDARD',
            }
        }
    )


def get_delivery_fee(pizzeria, customer_lat, customer_lng):
    """Calculate delivery fee for a customer location."""
    from django_geo.models import ServiceArea

    zones = ServiceArea.objects.filter(
        metadata__pizzeria_id=str(pizzeria.id),
        area_type='delivery',
        is_active=True,
    ).containing(customer_lat, customer_lng).order_by('radius_km')

    if not zones:
        return None  # Not in delivery area

    # Find the innermost zone (smallest radius that contains point)
    for zone in zones:
        excludes = zone.metadata.get('excludes_zone')
        if excludes:
            inner_zone = ServiceArea.objects.filter(code=excludes).first()
            if inner_zone and inner_zone.contains(customer_lat, customer_lng):
                continue  # Skip, use inner zone instead
        return {
            'fee': Decimal(zone.metadata['delivery_fee']),
            'min_order': Decimal(zone.metadata['min_order']),
            'zone': zone,
        }

    return None
```

---

## Driver Dispatch: WorkSessions and Encounters

### Driver Shifts

```python
# marketplace/services/drivers.py
from django_worklog import start_session, stop_session, get_active_session
from django_encounters.models import EncounterDefinition, Encounter
from django_encounters.services import create_encounter, transition_encounter


def start_driver_shift(driver, pizzeria):
    """Start a driver's delivery shift."""
    session = start_session(
        user=driver.user,
        target=pizzeria,
        session_type='delivery_shift',
    )

    return session


def end_driver_shift(driver):
    """End a driver's delivery shift."""
    session = stop_session(driver.user)
    return session


def get_available_drivers(pizzeria):
    """Get drivers currently on shift for a pizzeria."""
    from django_worklog.models import WorkSession
    from django.contrib.contenttypes.models import ContentType

    pizzeria_ct = ContentType.objects.get_for_model(pizzeria)

    return WorkSession.objects.filter(
        target_content_type=pizzeria_ct,
        target_id=str(pizzeria.id),
        session_type='delivery_shift',
        stopped_at__isnull=True,  # Active sessions
    )
```

### Delivery as Encounter

```python
# marketplace/encounters.py
from django_encounters.models import EncounterDefinition


def register_delivery_definitions():
    """Register delivery encounter definitions."""

    EncounterDefinition.objects.update_or_create(
        code='pizza_delivery',
        defaults={
            'name': 'Pizza Delivery',
            'description': 'Delivery from pizzeria to customer',
            'initial_state': 'pending',
            'states': [
                'pending',       # Waiting for driver assignment
                'assigned',      # Driver assigned
                'preparing',     # Kitchen is preparing order
                'ready',         # Order ready for pickup
                'picked_up',     # Driver has the order
                'en_route',      # Driver en route to customer
                'arrived',       # Driver at delivery location
                'delivered',     # Successfully delivered
                'failed',        # Delivery failed
            ],
            'transitions': {
                'pending': ['assigned', 'failed'],
                'assigned': ['preparing', 'pending', 'failed'],
                'preparing': ['ready', 'failed'],
                'ready': ['picked_up', 'failed'],
                'picked_up': ['en_route', 'failed'],
                'en_route': ['arrived', 'failed'],
                'arrived': ['delivered', 'failed'],
                'delivered': [],  # Terminal
                'failed': [],     # Terminal
            },
            'validators': [
                {
                    'transition': '*→assigned',
                    'class': 'marketplace.validators.DriverAvailableValidator',
                },
                {
                    'transition': '*→picked_up',
                    'class': 'marketplace.validators.OrderReadyValidator',
                },
            ],
        }
    )


def assign_delivery(order, driver):
    """Create and assign a delivery encounter."""
    from django_encounters.models import EncounterDefinition
    from django_encounters.services import create_encounter, transition_encounter

    definition = EncounterDefinition.objects.get(code='pizza_delivery')

    # Create the delivery encounter
    delivery = create_encounter(
        definition=definition,
        subject=order,
        metadata={
            'order_id': str(order.id),
            'pizzeria_id': order.metadata.get('pizzeria_id'),
            'customer_id': order.metadata.get('customer_id'),
            'delivery_address': order.metadata.get('delivery_address'),
        }
    )

    # Assign the driver
    transition_encounter(
        encounter=delivery,
        to_state='assigned',
        actor=driver.user,
        metadata={
            'driver_id': str(driver.id),
            'assigned_at': timezone.now().isoformat(),
        }
    )

    return delivery


def update_delivery_status(delivery, new_state, actor, metadata=None):
    """Update delivery status."""
    from django_encounters.services import transition_encounter
    from django_audit_log import log_event

    transition_encounter(
        encounter=delivery,
        to_state=new_state,
        actor=actor,
        metadata=metadata or {}
    )

    # Log for tracking
    log_event(
        target=delivery,
        event_type=f'delivery_{new_state}',
        actor=actor,
        metadata=metadata or {}
    )

    return delivery
```

---

## Payment Processing: The Ledger Split

### Order Checkout with Split Payments

```python
# marketplace/services/checkout.py
from django_catalog.services import commit_basket
from django_ledger.services import create_transaction
from django_ledger.models import Account
from decimal import Decimal


def checkout_order(basket, customer, payment_method, tip_amount=Decimal('0')):
    """
    Process order checkout with split payment.

    Money flows:
    - Customer pays total (items + delivery + tip)
    - Platform takes commission
    - Pizzeria gets net after commission
    - Driver gets tips (100% pass-through)
    """
    from django_sequence import get_next_sequence

    # Calculate amounts
    items_total = sum(
        item.unit_price_snapshot * item.quantity
        for item in basket.items.all()
    )

    delivery_fee = Decimal(basket.metadata.get('delivery_fee', '0'))
    subtotal = items_total + delivery_fee
    tax_rate = Decimal('0.0825')  # 8.25%
    tax = (subtotal * tax_rate).quantize(Decimal('0.01'))
    total = subtotal + tax + tip_amount

    # Platform commission (15% of items, not delivery or tip)
    commission_rate = Decimal('0.15')
    platform_commission = (items_total * commission_rate).quantize(Decimal('0.01'))

    # Vendor payout
    vendor_payout = items_total - platform_commission + delivery_fee

    # Generate order number
    order_number = get_next_sequence('order')

    # Commit the basket
    order = commit_basket(
        basket_id=basket.id,
        committed_by=customer.user,
        metadata={
            'order_number': order_number,
            'items_total': str(items_total),
            'delivery_fee': str(delivery_fee),
            'tax': str(tax),
            'tip': str(tip_amount),
            'total': str(total),
            'payment_method': payment_method,
        }
    )

    # Create payment transaction
    # Customer payment -> splits to platform, vendor, driver
    accounts = {
        'customer_payment': Account.objects.get(code='customer-payments'),
        'platform_revenue': Account.objects.get(code='platform-commission'),
        'vendor_payable': Account.objects.get(code='vendor-payable'),
        'driver_tips': Account.objects.get(code='driver-tips-payable'),
        'tax_payable': Account.objects.get(code='sales-tax-payable'),
    }

    entries = [
        # Customer pays
        {'account': accounts['customer_payment'],
         'amount': total, 'entry_type': 'debit'},

        # Platform takes commission
        {'account': accounts['platform_revenue'],
         'amount': platform_commission, 'entry_type': 'credit'},

        # Vendor gets their share
        {'account': accounts['vendor_payable'],
         'amount': vendor_payout, 'entry_type': 'credit'},

        # Driver gets tips
        {'account': accounts['driver_tips'],
         'amount': tip_amount, 'entry_type': 'credit'},

        # Tax collected
        {'account': accounts['tax_payable'],
         'amount': tax, 'entry_type': 'credit'},
    ]

    transaction = create_transaction(
        entries=entries,
        memo=f"Order {order_number}",
        metadata={
            'order_id': str(order.id),
            'order_number': order_number,
            'customer_id': str(customer.id),
            'pizzeria_id': basket.metadata.get('pizzeria_id'),
        }
    )

    order.metadata['transaction_id'] = str(transaction.id)
    order.save(update_fields=['metadata'])

    return order, transaction


def record_tip(delivery, tip_amount, tipper):
    """Record a tip for a delivery (can be added after delivery)."""
    from django_ledger.services import create_transaction
    from django_ledger.models import Account

    driver_id = delivery.metadata.get('driver_id')

    accounts = {
        'customer_payment': Account.objects.get(code='customer-payments'),
        'driver_tips': Account.objects.get(code='driver-tips-payable'),
    }

    transaction = create_transaction(
        entries=[
            {'account': accounts['customer_payment'],
             'amount': tip_amount, 'entry_type': 'debit'},
            {'account': accounts['driver_tips'],
             'amount': tip_amount, 'entry_type': 'credit'},
        ],
        memo=f"Tip for delivery {delivery.id}",
        metadata={
            'delivery_id': str(delivery.id),
            'driver_id': driver_id,
            'tipper_id': str(tipper.id),
        }
    )

    return transaction
```

---

## The Complete Order Flow

```python
# marketplace/services/order_flow.py
from django.utils import timezone


def place_order(
    customer,
    pizzeria,
    cart_items,
    delivery_address,
    payment_method,
    tip_amount=Decimal('0'),
):
    """
    Complete order placement flow.

    Steps:
    1. Validate delivery address in zone
    2. Create basket with items
    3. Apply delivery fee
    4. Process payment (split to platform/vendor/driver)
    5. Create delivery encounter
    6. Notify pizzeria
    """
    from .delivery import get_delivery_fee
    from .ordering import add_pizza_to_cart
    from .checkout import checkout_order
    from .drivers import assign_delivery
    from django_catalog.models import Basket
    from django_audit_log import log_event

    # Step 1: Validate delivery
    delivery_info = get_delivery_fee(
        pizzeria,
        delivery_address['latitude'],
        delivery_address['longitude']
    )

    if not delivery_info:
        raise ValueError("Address not in delivery area")

    # Step 2: Create basket
    basket = Basket.objects.create(
        owner=customer,
        basket_type='order',
        metadata={
            'pizzeria_id': str(pizzeria.id),
            'customer_id': str(customer.id),
            'delivery_address': delivery_address,
            'delivery_fee': str(delivery_info['fee']),
        }
    )

    # Step 3: Add items
    for item in cart_items:
        add_pizza_to_cart(
            basket=basket,
            pizza_item=item['pizza'],
            quantity=item.get('quantity', 1),
            toppings=item.get('toppings', []),
        )

    # Check minimum order
    items_total = sum(
        i.unit_price_snapshot * i.quantity
        for i in basket.items.all()
    )

    if items_total < delivery_info['min_order']:
        basket.delete()
        raise ValueError(
            f"Minimum order is ${delivery_info['min_order']} for this zone"
        )

    # Step 4: Process payment
    order, transaction = checkout_order(
        basket=basket,
        customer=customer,
        payment_method=payment_method,
        tip_amount=tip_amount,
    )

    # Step 5: Create delivery encounter
    delivery = create_delivery_encounter(order)

    # Step 6: Log and notify
    log_event(
        target=order,
        event_type='order_placed',
        actor=customer.user,
        metadata={
            'order_number': order.metadata['order_number'],
            'total': order.metadata['total'],
        }
    )

    # Notify pizzeria (would trigger push notification, etc.)
    notify_pizzeria(pizzeria, order)

    return order, delivery


def notify_pizzeria(pizzeria, order):
    """Notify pizzeria of new order."""
    # In production: push notification, SMS, printer, etc.
    from django_audit_log import log_event

    log_event(
        target=pizzeria,
        event_type='new_order_notification',
        metadata={
            'order_id': str(order.id),
            'order_number': order.metadata['order_number'],
        }
    )
```

---

## Complete Rebuild Prompt

The following prompt demonstrates how to instruct Claude to rebuild this marketplace from scratch.

```markdown
# Prompt: Build Pizza Delivery Marketplace

## Role

You are a Django developer building a multi-vendor pizza delivery marketplace.
You must compose existing primitives from django-primitives packages.
You must NOT create new Django models for concepts that primitives already handle.

## Instruction

Build a pizza delivery marketplace by composing these primitives:
- django-parties (customers, pizzerias, drivers)
- django-catalog (menus, sizes, toppings, combos)
- django-agreements (combo deals, promotions)
- django-ledger (orders, payments, split settlements)
- django-encounters (delivery tracking workflow)
- django-worklog (driver shifts)
- django-geo (delivery zones, service areas)
- django-rbac (vendor admin, driver roles)
- django-audit-log (order events)

## Domain Purpose

Enable pizza marketplace to:
- Multiple vendor menus with sizes and toppings (including half-toppings)
- Combo deals that bundle items at discount
- Delivery zone calculation with distance-based fees
- Driver shift management
- Real-time delivery tracking through state machine
- Split payments (platform fee, vendor payment, driver tips)
- Complete order audit trail

## NO NEW MODELS

Do not create any new Django models for:
- Pizzerias (use Organization from django-parties)
- Drivers (use Person from django-parties)
- Menu items (use CatalogItem from django-catalog)
- Orders (use Basket from django-catalog)
- Line items (use BasketItem from django-catalog)
- Payments (use Transaction from django-ledger)
- Deliveries (use Encounter from django-encounters)
- Delivery zones (use ServiceArea from django-geo)
- Deals/promotions (use Agreement from django-agreements)

## Primitive Composition

### Vendors and Staff
- Pizzeria = Organization (org_type="restaurant")
- Driver = Person + PartyRelationship to pizzeria
- Customer = Person

### Menu System
- Category = Menu section (Pizzas, Sides, Drinks)
- CatalogItem = Menu item with metadata:
  - metadata.available_sizes: ["small", "medium", "large"]
  - metadata.base_prices: {"small": 12.99, ...}
  - metadata.is_topping: true/false
  - metadata.topping_price: 1.50

### Half-Topping Pattern
- BasketItem for toppings with:
  - unit_price_snapshot: price * 0.5 for half topping
  - metadata.coverage: "left" | "right" | "full"
  - metadata.parent_pizza_id: links to pizza line item

### Combo Deals
- Agreement (agreement_type="combo_deal")
  - terms.items: ["item_sku1", "item_sku2", ...]
  - terms.fixed_price: 24.99
  - metadata.savings_description: "Save $5"

### Orders and Checkout
- Basket = The cart and order
  - basket_type="order"
  - metadata.order_number, delivery_address, etc.
- BasketItem = Line items with price snapshots
- Basket.commit() = Lock prices at checkout

### Delivery Zones
- ServiceArea with radius or postal codes
  - metadata.delivery_fee: 3.99
  - metadata.min_order: 15.00
  - metadata.estimated_minutes: 30

### Delivery Tracking
- Encounter with EncounterDefinition "pizza_delivery"
- States: order_placed → preparing → ready → picked_up → en_route → delivered
- EncounterTransition records each state change with timestamp

### Split Payments
- Transaction with multiple Entry records:
  - Debit: Cash/Card (full amount)
  - Credit: Platform Revenue (commission)
  - Credit: Vendor Payable (vendor share)
  - Credit: Driver Tips (tip amount)

### Driver Shifts
- WorkSession (session_type="delivery_shift")
  - target=pizzeria
  - started_at, ended_at
  - metadata.deliveries_completed

## Service Functions

### add_pizza_to_cart()
```python
def add_pizza_to_cart(
    basket: Basket,
    pizza: CatalogItem,
    size: str,
    toppings: list[dict],  # [{item, coverage}]
    quantity: int = 1,
) -> list[BasketItem]:
    """Add pizza with toppings to cart."""
```

### apply_combo_deal()
```python
def apply_combo_deal(
    basket: Basket,
    deal: Agreement,
) -> Decimal:
    """Apply combo deal, return savings amount."""
```

### calculate_delivery_fee()
```python
def calculate_delivery_fee(
    pizzeria: Organization,
    delivery_address: str,
) -> dict:
    """Calculate delivery fee and ETA for address."""
```

### checkout_order()
```python
def checkout_order(
    basket: Basket,
    customer: Person,
    payment_method: str,
    tip_amount: Decimal = Decimal("0"),
) -> tuple[Basket, Transaction]:
    """Process payment with platform/vendor/tip split."""
```

### create_delivery_encounter()
```python
def create_delivery_encounter(
    order: Basket,
) -> Encounter:
    """Create delivery tracking encounter for order."""
```

### update_delivery_status()
```python
def update_delivery_status(
    delivery: Encounter,
    new_status: str,
    actor: Person,
    notes: str = "",
) -> Encounter:
    """Transition delivery to new state."""
```

## Test Cases (40 tests)

### Menu Tests (6 tests)
1. test_create_pizzeria_menu
2. test_pizza_with_sizes
3. test_topping_catalog_item
4. test_menu_item_availability
5. test_price_by_size
6. test_seasonal_menu_item

### Cart Tests (10 tests)
7. test_add_pizza_to_cart
8. test_add_topping_full
9. test_add_topping_half_left
10. test_add_topping_half_right
11. test_half_topping_half_price
12. test_pizza_with_multiple_toppings
13. test_apply_combo_deal
14. test_combo_validates_items
15. test_remove_item_from_cart
16. test_cart_total_calculation

### Delivery Zone Tests (4 tests)
17. test_address_in_zone
18. test_address_outside_zone
19. test_delivery_fee_calculation
20. test_minimum_order_enforcement

### Checkout Tests (8 tests)
21. test_commit_basket_locks_prices
22. test_payment_creates_transaction
23. test_platform_commission_entry
24. test_vendor_payable_entry
25. test_tip_entry_to_driver
26. test_entries_balance
27. test_order_number_generated
28. test_checkout_creates_delivery

### Delivery Tracking Tests (8 tests)
29. test_create_delivery_encounter
30. test_delivery_initial_state
31. test_transition_to_preparing
32. test_transition_to_ready
33. test_driver_picks_up
34. test_transition_en_route
35. test_transition_delivered
36. test_invalid_transition_rejected

### Driver Tests (4 tests)
37. test_start_driver_shift
38. test_end_driver_shift
39. test_assign_delivery_to_driver
40. test_driver_shift_deliveries

## Key Behaviors

1. **Half-toppings via metadata** - coverage field, half price multiplier
2. **Combo deals as Agreements** - terms.items, terms.fixed_price
3. **Orders are Baskets** - commit() locks prices
4. **Split payments via Entries** - platform, vendor, driver accounts
5. **Delivery is Encounter** - state machine with transitions
6. **Zones are ServiceAreas** - fee and min_order in metadata

## Forbidden Operations

- Creating custom Order or LineItem models
- Storing prices without snapshots
- Bypassing Basket.commit() at checkout
- Direct state assignment on deliveries
- Modifying committed basket items
- Processing payment without balanced entries

## Acceptance Criteria

- [ ] No new Django models for core concepts
- [ ] Half-toppings work via BasketItem metadata
- [ ] Combo deals use Agreement with terms
- [ ] Orders use Basket with commit()
- [ ] Payments use Transaction with balanced entries
- [ ] Deliveries use Encounter with state machine
- [ ] Zones use ServiceArea
- [ ] All 40 tests passing
- [ ] README with ordering flow example
```

---

## Using This Prompt

To rebuild this marketplace with Claude:

**Step 1: Provide the constraint context**

Before the rebuild prompt, give Claude:
- The django-primitives package documentation
- The CLAUDE.md file with layer rules
- This prompt as the specification

**Step 2: Request incrementally**

Break into phases:
1. "Set up the catalog: pizzeria, menu categories, menu items with sizes"
2. "Implement add_pizza_to_cart with half-topping support"
3. "Implement combo deals using Agreement"
4. "Implement checkout with split payment entries"
5. "Create the delivery encounter workflow"

**Step 3: Validate each output**

After each generation, check:
- Are all models from primitives (not custom)?
- Is the half-topping logic using metadata, not a custom model?
- Are payments using Transaction with balanced Entry records?

**Step 4: Correct constraint violations**

If Claude creates a custom model:
"Don't create a DeliveryZone model. Use ServiceArea from django-geo with metadata.delivery_fee and metadata.min_order."

**The prompt is the contract. Enforce it.**

---

## What We Didn't Build

Notice what the marketplace does NOT contain:

1. **No custom order model** - Uses Basket from django-catalog
2. **No custom line item model** - Uses BasketItem with metadata
3. **No custom payment model** - Uses Transaction from django-ledger
4. **No custom delivery model** - Uses Encounter from django-encounters
5. **No custom promo system** - Uses Agreement from django-agreements
6. **No custom zone model** - Uses ServiceArea from django-geo

The application code is purely:
- **Configuration**: Menu items, zones, encounter definitions
- **Business logic**: Commission calculation, tip routing
- **Composition**: Connecting primitives for the pizza domain

---

## The Half-Topping Answer

Remember the objection from the beginning?

"But pizza has half-toppings."

Here's the complete answer:

```python
# Half-topping: quantity 0.5 with coverage metadata
BasketItem.objects.create(
    basket=basket,
    catalog_item=pepperoni,
    quantity=1,  # Per pizza
    unit_price_snapshot=pepperoni.unit_price * Decimal('0.5'),  # Half price
    metadata={
        'coverage': 'left',  # or 'right', 'full'
        'parent_pizza_id': pizza_line.id,
    }
)
```

Three fields:
- `quantity`: Same as pizza quantity
- `unit_price_snapshot`: Half price for half topping
- `metadata.coverage`: Which half

No new models. No special cases. Just configuration.

---

## Hands-On Exercise

Build a minimal pizza ordering system:

**Step 1: Set up catalog items**
- One pizza size
- Three toppings
- One combo deal

**Step 2: Implement add_pizza_to_cart**
- Handle full and half toppings
- Calculate correct prices

**Step 3: Implement checkout**
- Split payment between platform and vendor
- Handle tips

**Step 4: Test the flow**
- Order a pizza with half-pepperoni, half-mushroom
- Apply a combo deal
- Process payment with tip

---

## Summary

| Domain Concept | Primitive | Configuration |
|----------------|-----------|---------------|
| Half-topping | BasketItem | coverage in metadata, half multiplier |
| Combo deal | Agreement | items list, fixed price |
| Delivery zone | ServiceArea | radius, fee in metadata |
| Driver shift | WorkSession | target=pizzeria |
| Delivery tracking | Encounter | 9-state machine |
| Split payment | Transaction | Multiple entries |
| Tips | Entry | Pass-through to driver account |

Every "unique" pizza requirement is configuration of existing primitives.

The primitives don't care about pizza. They care about ordering, geography, work tracking, money movement, and state machines.

Pizza is just one composition. The same primitives build sushi delivery, flower delivery, or any other logistics marketplace.

That's the point.
