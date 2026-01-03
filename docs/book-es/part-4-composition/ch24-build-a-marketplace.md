# Capitulo 24: Construir un Marketplace

## El Problema de la Pizza

"Pero la pizza tiene medios ingredientes."

Esta objecion surge en cada conversacion sobre primitivas ERP. La implicacion es que ordenar pizza es de alguna manera especial - que el requisito de medio ingrediente significa que necesitas un modelo de datos personalizado, un sistema de pedidos especializado, una arquitectura especifica de pizza.

No es asi.

Los medios ingredientes son configuracion. Las ofertas combo son acuerdos. Las zonas de entrega son areas de servicio. El despacho de repartidores son sesiones de trabajo. Las propinas son entradas de libro mayor. Cada requisito "unico" de pizza se mapea a una primitiva existente.

Este capitulo construye un marketplace de entrega de pizza para probarlo.

---

## Lo Que Estamos Construyendo

Un marketplace de entrega de pizza multi-vendedor:

- **Multiples pizzerias** - Cada una con su propio menu y precios
- **Pedidos de clientes** - Navegar, personalizar, pagar
- **Medios ingredientes** - El famoso caso especial de pizza
- **Ofertas combo** - Precios promocionales
- **Zonas de entrega** - Areas de servicio geograficas
- **Despacho de repartidores** - Asignacion y seguimiento
- **Pagos divididos** - Cliente a plataforma a vendedor
- **Propinas** - Transferencia directa a repartidores

Sin nuevas primitivas. Solo composicion.

---

## El Mapeo de Primitivas

| Concepto del Dominio | Primitiva | Paquete |
|---------------------|-----------|---------|
| Cliente | Party (Person) | django-parties |
| Pizzeria | Party (Organization) | django-parties |
| Repartidor | Party (Person) + Role | django-parties, django-rbac |
| Item del menu | CatalogItem | django-catalog |
| Ingrediente | CatalogItem | django-catalog |
| Carrito de compras | Basket | django-catalog |
| Pedido | Basket (committed) | django-catalog |
| Linea de item | BasketItem | django-catalog |
| Pago | Transaction | django-ledger |
| Comision de plataforma | Entry | django-ledger |
| Pago a vendedor | Entry | django-ledger |
| Propina | Entry | django-ledger |
| Zona de entrega | ServiceArea | django-geo |
| Turno de repartidor | WorkSession | django-worklog |
| Entrega | Encounter | django-encounters |
| Oferta combo | Agreement | django-agreements |
| Codigo promocional | Agreement | django-agreements |

---

## Configuracion del Proyecto

```python
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',

    # Primitivas
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

    # Aplicacion
    'marketplace',
]
```

---

## El Menu: Configuracion del Catalogo

### Pizza como CatalogItem

```python
# marketplace/catalog.py
from django_catalog.models import CatalogItem
from decimal import Decimal


def setup_pizzeria_menu(pizzeria):
    """Configurar items del menu de una pizzeria."""

    # Base de pizza
    CatalogItem.objects.update_or_create(
        code=f'{pizzeria.code}-PIZZA-LARGE',
        defaults={
            'name': 'Pizza Grande',
            'description': 'Pizza de 16" lanzada a mano',
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
            'name': 'Pizza Mediana',
            'description': 'Pizza de 12" lanzada a mano',
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
    """Configurar ingredientes para una pizzeria."""

    toppings = [
        ('PEPPERONI', 'Pepperoni', Decimal('1.50')),
        ('SAUSAGE', 'Salchicha Italiana', Decimal('1.50')),
        ('MUSHROOM', 'Champiñones', Decimal('1.00')),
        ('OLIVE', 'Aceitunas Negras', Decimal('1.00')),
        ('PEPPER', 'Pimientos Verdes', Decimal('1.00')),
        ('ONION', 'Cebollas', Decimal('0.75')),
        ('BACON', 'Tocino', Decimal('2.00')),
        ('CHICKEN', 'Pollo a la Parrilla', Decimal('2.50')),
        ('PINEAPPLE', 'Piña', Decimal('1.00')),
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
                    'half_price_multiplier': '0.5',  # Medios ingredientes cuestan la mitad
                }
            }
        )
```

### La Solucion de Medio Ingrediente

Los medios ingredientes no son un caso especial. Son una cantidad:

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
    Agregar una pizza con ingredientes al carrito.

    Formato de ingredientes: [
        {'code': 'PEPPERONI', 'coverage': 'full'},
        {'code': 'MUSHROOM', 'coverage': 'left'},
        {'code': 'OLIVE', 'coverage': 'right'},
    ]
    """
    toppings = toppings or []

    # Agregar la base de la pizza
    pizza_line = BasketItem.objects.create(
        basket=basket,
        catalog_item=pizza_item,
        quantity=quantity,
        unit_price_snapshot=pizza_item.unit_price,
        metadata={
            'toppings': [],  # Se llenara abajo
        }
    )

    # Agregar cada ingrediente
    topping_details = []
    for topping in toppings:
        topping_item = CatalogItem.objects.get(
            code=topping['code'],
            organization=pizza_item.organization,
        )

        coverage = topping.get('coverage', 'full')

        # Calcular precio basado en cobertura
        if coverage in ('left', 'right'):
            # Medio ingrediente = mitad de precio
            multiplier = Decimal(
                topping_item.metadata.get('half_price_multiplier', '0.5')
            )
        else:
            multiplier = Decimal('1')

        topping_price = topping_item.unit_price * multiplier

        # Agregar ingrediente como item de canasta
        BasketItem.objects.create(
            basket=basket,
            catalog_item=topping_item,
            quantity=quantity,  # Misma cantidad que las pizzas
            unit_price_snapshot=topping_price,
            parent_item=pizza_line,  # Vincular a la pizza
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

    # Actualizar metadata de la pizza con resumen de ingredientes
    pizza_line.metadata['toppings'] = topping_details
    pizza_line.save(update_fields=['metadata'])

    return pizza_line
```

Eso es todo. Los medios ingredientes son solo un multiplicador de cantidad con metadata rastreando cual mitad.

---

## Ofertas Combo: Acuerdos con Reglas de Precios

### Definiendo un Combo

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
    Crear una oferta combo como un Agreement.

    Formato de items: [
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
    """Obtener todas las ofertas combo activas para una pizzeria."""
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
    Aplicar una oferta combo a un carrito.

    Valida que todos los items requeridos esten presentes,
    luego aplica el precio del combo.
    """
    from django_catalog.models import BasketItem

    required_items = combo_agreement.terms['items']
    combo_price = Decimal(combo_agreement.terms['combo_price'])

    # Verificar que todos los items esten presentes
    for required in required_items:
        matching = basket.items.filter(
            catalog_item__code__endswith=required['code'],
            quantity__gte=required['quantity']
        ).first()

        if not matching:
            raise ValueError(
                f"El combo requiere {required['quantity']}x {required['code']}"
            )

    # Calcular descuento
    items_total = sum(
        item.unit_price_snapshot * item.quantity
        for item in basket.items.all()
        if any(
            item.catalog_item.code.endswith(r['code'])
            for r in required_items
        )
    )

    discount = items_total - combo_price

    # Agregar linea de descuento
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

## Zonas de Entrega: Areas de Servicio Geograficas

### Configurando Zonas

```python
# marketplace/services/delivery.py
from django_geo.models import ServiceArea, GeoPoint
from decimal import Decimal


def setup_delivery_zones(pizzeria, location):
    """Configurar zonas de entrega alrededor de una ubicacion de pizzeria."""

    # Zona de entrega gratis (dentro de 3km)
    ServiceArea.objects.update_or_create(
        code=f'{pizzeria.code}-ZONE-FREE',
        defaults={
            'name': f'{pizzeria.name} - Entrega Gratis',
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

    # Zona de entrega estandar (3-7km)
    ServiceArea.objects.update_or_create(
        code=f'{pizzeria.code}-ZONE-STANDARD',
        defaults={
            'name': f'{pizzeria.name} - Entrega Estandar',
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

    # Zona de entrega extendida (7-12km)
    ServiceArea.objects.update_or_create(
        code=f'{pizzeria.code}-ZONE-EXTENDED',
        defaults={
            'name': f'{pizzeria.name} - Entrega Extendida',
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
    """Calcular tarifa de entrega para una ubicacion de cliente."""
    from django_geo.models import ServiceArea

    zones = ServiceArea.objects.filter(
        metadata__pizzeria_id=str(pizzeria.id),
        area_type='delivery',
        is_active=True,
    ).containing(customer_lat, customer_lng).order_by('radius_km')

    if not zones:
        return None  # No esta en area de entrega

    # Encontrar la zona mas interna (radio mas pequeño que contiene el punto)
    for zone in zones:
        excludes = zone.metadata.get('excludes_zone')
        if excludes:
            inner_zone = ServiceArea.objects.filter(code=excludes).first()
            if inner_zone and inner_zone.contains(customer_lat, customer_lng):
                continue  # Saltar, usar zona interna en su lugar
        return {
            'fee': Decimal(zone.metadata['delivery_fee']),
            'min_order': Decimal(zone.metadata['min_order']),
            'zone': zone,
        }

    return None
```

---

## Despacho de Repartidores: WorkSessions y Encounters

### Turnos de Repartidores

```python
# marketplace/services/drivers.py
from django_worklog import start_session, stop_session, get_active_session
from django_encounters.models import EncounterDefinition, Encounter
from django_encounters.services import create_encounter, transition_encounter


def start_driver_shift(driver, pizzeria):
    """Iniciar turno de entrega de un repartidor."""
    session = start_session(
        user=driver.user,
        target=pizzeria,
        session_type='delivery_shift',
    )

    return session


def end_driver_shift(driver):
    """Finalizar turno de entrega de un repartidor."""
    session = stop_session(driver.user)
    return session


def get_available_drivers(pizzeria):
    """Obtener repartidores actualmente en turno para una pizzeria."""
    from django_worklog.models import WorkSession
    from django.contrib.contenttypes.models import ContentType

    pizzeria_ct = ContentType.objects.get_for_model(pizzeria)

    return WorkSession.objects.filter(
        target_content_type=pizzeria_ct,
        target_id=str(pizzeria.id),
        session_type='delivery_shift',
        stopped_at__isnull=True,  # Sesiones activas
    )
```

### Entrega como Encounter

```python
# marketplace/encounters.py
from django_encounters.models import EncounterDefinition


def register_delivery_definitions():
    """Registrar definiciones de encuentro de entrega."""

    EncounterDefinition.objects.update_or_create(
        code='pizza_delivery',
        defaults={
            'name': 'Entrega de Pizza',
            'description': 'Entrega desde pizzeria al cliente',
            'initial_state': 'pending',
            'states': [
                'pending',       # Esperando asignacion de repartidor
                'assigned',      # Repartidor asignado
                'preparing',     # La cocina esta preparando el pedido
                'ready',         # Pedido listo para recoger
                'picked_up',     # Repartidor tiene el pedido
                'en_route',      # Repartidor en camino al cliente
                'arrived',       # Repartidor en ubicacion de entrega
                'delivered',     # Entregado exitosamente
                'failed',        # Entrega fallida
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
    """Crear y asignar un encuentro de entrega."""
    from django_encounters.models import EncounterDefinition
    from django_encounters.services import create_encounter, transition_encounter

    definition = EncounterDefinition.objects.get(code='pizza_delivery')

    # Crear el encuentro de entrega
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

    # Asignar el repartidor
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
    """Actualizar estado de entrega."""
    from django_encounters.services import transition_encounter
    from django_audit_log import log_event

    transition_encounter(
        encounter=delivery,
        to_state=new_state,
        actor=actor,
        metadata=metadata or {}
    )

    # Registrar para seguimiento
    log_event(
        target=delivery,
        event_type=f'delivery_{new_state}',
        actor=actor,
        metadata=metadata or {}
    )

    return delivery
```

---

## Procesamiento de Pagos: La Division del Libro Mayor

### Checkout de Pedido con Pagos Divididos

```python
# marketplace/services/checkout.py
from django_catalog.services import commit_basket
from django_ledger.services import create_transaction
from django_ledger.models import Account
from decimal import Decimal


def checkout_order(basket, customer, payment_method, tip_amount=Decimal('0')):
    """
    Procesar checkout de pedido con pago dividido.

    Flujo de dinero:
    - Cliente paga total (items + entrega + propina)
    - Plataforma toma comision
    - Pizzeria obtiene neto despues de comision
    - Repartidor obtiene propinas (100% transferencia directa)
    """
    from django_sequence import get_next_sequence

    # Calcular montos
    items_total = sum(
        item.unit_price_snapshot * item.quantity
        for item in basket.items.all()
    )

    delivery_fee = Decimal(basket.metadata.get('delivery_fee', '0'))
    subtotal = items_total + delivery_fee
    tax_rate = Decimal('0.0825')  # 8.25%
    tax = (subtotal * tax_rate).quantize(Decimal('0.01'))
    total = subtotal + tax + tip_amount

    # Comision de plataforma (15% de items, no de entrega o propina)
    commission_rate = Decimal('0.15')
    platform_commission = (items_total * commission_rate).quantize(Decimal('0.01'))

    # Pago a vendedor
    vendor_payout = items_total - platform_commission + delivery_fee

    # Generar numero de pedido
    order_number = get_next_sequence('order')

    # Confirmar la canasta
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

    # Crear transaccion de pago
    # Pago de cliente -> se divide a plataforma, vendedor, repartidor
    accounts = {
        'customer_payment': Account.objects.get(code='customer-payments'),
        'platform_revenue': Account.objects.get(code='platform-commission'),
        'vendor_payable': Account.objects.get(code='vendor-payable'),
        'driver_tips': Account.objects.get(code='driver-tips-payable'),
        'tax_payable': Account.objects.get(code='sales-tax-payable'),
    }

    entries = [
        # Cliente paga
        {'account': accounts['customer_payment'],
         'amount': total, 'entry_type': 'debit'},

        # Plataforma toma comision
        {'account': accounts['platform_revenue'],
         'amount': platform_commission, 'entry_type': 'credit'},

        # Vendedor obtiene su parte
        {'account': accounts['vendor_payable'],
         'amount': vendor_payout, 'entry_type': 'credit'},

        # Repartidor obtiene propinas
        {'account': accounts['driver_tips'],
         'amount': tip_amount, 'entry_type': 'credit'},

        # Impuesto recolectado
        {'account': accounts['tax_payable'],
         'amount': tax, 'entry_type': 'credit'},
    ]

    transaction = create_transaction(
        entries=entries,
        memo=f"Pedido {order_number}",
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
    """Registrar una propina para una entrega (puede agregarse despues de la entrega)."""
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
        memo=f"Propina para entrega {delivery.id}",
        metadata={
            'delivery_id': str(delivery.id),
            'driver_id': driver_id,
            'tipper_id': str(tipper.id),
        }
    )

    return transaction
```

---

## El Flujo Completo de Pedido

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
    Flujo completo de colocacion de pedido.

    Pasos:
    1. Validar direccion de entrega en zona
    2. Crear canasta con items
    3. Aplicar tarifa de entrega
    4. Procesar pago (dividir a plataforma/vendedor/repartidor)
    5. Crear encuentro de entrega
    6. Notificar a pizzeria
    """
    from .delivery import get_delivery_fee
    from .ordering import add_pizza_to_cart
    from .checkout import checkout_order
    from .drivers import assign_delivery
    from django_catalog.models import Basket
    from django_audit_log import log_event

    # Paso 1: Validar entrega
    delivery_info = get_delivery_fee(
        pizzeria,
        delivery_address['latitude'],
        delivery_address['longitude']
    )

    if not delivery_info:
        raise ValueError("La direccion no esta en area de entrega")

    # Paso 2: Crear canasta
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

    # Paso 3: Agregar items
    for item in cart_items:
        add_pizza_to_cart(
            basket=basket,
            pizza_item=item['pizza'],
            quantity=item.get('quantity', 1),
            toppings=item.get('toppings', []),
        )

    # Verificar pedido minimo
    items_total = sum(
        i.unit_price_snapshot * i.quantity
        for i in basket.items.all()
    )

    if items_total < delivery_info['min_order']:
        basket.delete()
        raise ValueError(
            f"El pedido minimo es ${delivery_info['min_order']} para esta zona"
        )

    # Paso 4: Procesar pago
    order, transaction = checkout_order(
        basket=basket,
        customer=customer,
        payment_method=payment_method,
        tip_amount=tip_amount,
    )

    # Paso 5: Crear encuentro de entrega
    delivery = create_delivery_encounter(order)

    # Paso 6: Registrar y notificar
    log_event(
        target=order,
        event_type='order_placed',
        actor=customer.user,
        metadata={
            'order_number': order.metadata['order_number'],
            'total': order.metadata['total'],
        }
    )

    # Notificar a pizzeria (activaria notificacion push, etc.)
    notify_pizzeria(pizzeria, order)

    return order, delivery


def notify_pizzeria(pizzeria, order):
    """Notificar a pizzeria de nuevo pedido."""
    # En produccion: notificacion push, SMS, impresora, etc.
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

## Prompt Completo de Reconstruccion

El siguiente prompt demuestra como instruir a Claude para reconstruir este marketplace desde cero.

```markdown
# Prompt: Construir Marketplace de Entrega de Pizza

## Rol

Eres un desarrollador Django construyendo un marketplace de entrega de pizza multi-vendedor.
Debes componer primitivas existentes de los paquetes django-primitives.
NO debes crear nuevos modelos Django para conceptos que las primitivas ya manejan.

## Instruccion

Construir un marketplace de entrega de pizza componiendo estas primitivas:
- django-parties (clientes, pizzerias, repartidores)
- django-catalog (menus, tamaños, ingredientes, combos)
- django-agreements (ofertas combo, promociones)
- django-ledger (pedidos, pagos, liquidaciones divididas)
- django-encounters (flujo de seguimiento de entrega)
- django-worklog (turnos de repartidores)
- django-geo (zonas de entrega, areas de servicio)
- django-rbac (admin de vendedor, roles de repartidor)
- django-audit-log (eventos de pedido)

## Proposito del Dominio

Permitir al marketplace de pizza:
- Menus de multiples vendedores con tamaños e ingredientes (incluyendo medios ingredientes)
- Ofertas combo que agrupan items con descuento
- Calculo de zona de entrega con tarifas basadas en distancia
- Gestion de turnos de repartidores
- Seguimiento de entrega en tiempo real a traves de maquina de estados
- Pagos divididos (comision de plataforma, pago a vendedor, propinas a repartidor)
- Pista de auditoria completa de pedidos

## SIN NUEVOS MODELOS

No crear ningun nuevo modelo Django para:
- Pizzerias (usar Organization de django-parties)
- Repartidores (usar Person de django-parties)
- Items del menu (usar CatalogItem de django-catalog)
- Pedidos (usar Basket de django-catalog)
- Lineas de items (usar BasketItem de django-catalog)
- Pagos (usar Transaction de django-ledger)
- Entregas (usar Encounter de django-encounters)
- Zonas de entrega (usar ServiceArea de django-geo)
- Ofertas/promociones (usar Agreement de django-agreements)

## Composicion de Primitivas

### Vendedores y Personal
- Pizzeria = Organization (org_type="restaurant")
- Repartidor = Person + PartyRelationship a pizzeria
- Cliente = Person

### Sistema de Menu
- Category = Seccion del menu (Pizzas, Complementos, Bebidas)
- CatalogItem = Item del menu con metadata:
  - metadata.available_sizes: ["small", "medium", "large"]
  - metadata.base_prices: {"small": 12.99, ...}
  - metadata.is_topping: true/false
  - metadata.topping_price: 1.50

### Patron de Medio Ingrediente
- BasketItem para ingredientes con:
  - unit_price_snapshot: price * 0.5 para medio ingrediente
  - metadata.coverage: "left" | "right" | "full"
  - metadata.parent_pizza_id: vincula a linea de pizza

### Ofertas Combo
- Agreement (agreement_type="combo_deal")
  - terms.items: ["item_sku1", "item_sku2", ...]
  - terms.fixed_price: 24.99
  - metadata.savings_description: "Ahorra $5"

### Pedidos y Checkout
- Basket = El carrito y pedido
  - basket_type="order"
  - metadata.order_number, delivery_address, etc.
- BasketItem = Lineas de items con instantaneas de precio
- Basket.commit() = Bloquear precios en checkout

### Zonas de Entrega
- ServiceArea con radio o codigos postales
  - metadata.delivery_fee: 3.99
  - metadata.min_order: 15.00
  - metadata.estimated_minutes: 30

### Seguimiento de Entrega
- Encounter con EncounterDefinition "pizza_delivery"
- Estados: order_placed → preparing → ready → picked_up → en_route → delivered
- EncounterTransition registra cada cambio de estado con timestamp

### Pagos Divididos
- Transaction con multiples registros Entry:
  - Debito: Efectivo/Tarjeta (monto total)
  - Credito: Ingreso de Plataforma (comision)
  - Credito: Por Pagar a Vendedor (parte del vendedor)
  - Credito: Propinas de Repartidor (monto de propina)

### Turnos de Repartidores
- WorkSession (session_type="delivery_shift")
  - target=pizzeria
  - started_at, ended_at
  - metadata.deliveries_completed

## Funciones de Servicio

### add_pizza_to_cart()
```python
def add_pizza_to_cart(
    basket: Basket,
    pizza: CatalogItem,
    size: str,
    toppings: list[dict],  # [{item, coverage}]
    quantity: int = 1,
) -> list[BasketItem]:
    """Agregar pizza con ingredientes al carrito."""
```

### apply_combo_deal()
```python
def apply_combo_deal(
    basket: Basket,
    deal: Agreement,
) -> Decimal:
    """Aplicar oferta combo, retornar monto de ahorro."""
```

### calculate_delivery_fee()
```python
def calculate_delivery_fee(
    pizzeria: Organization,
    delivery_address: str,
) -> dict:
    """Calcular tarifa de entrega y ETA para direccion."""
```

### checkout_order()
```python
def checkout_order(
    basket: Basket,
    customer: Person,
    payment_method: str,
    tip_amount: Decimal = Decimal("0"),
) -> tuple[Basket, Transaction]:
    """Procesar pago con division plataforma/vendedor/propina."""
```

### create_delivery_encounter()
```python
def create_delivery_encounter(
    order: Basket,
) -> Encounter:
    """Crear encuentro de seguimiento de entrega para pedido."""
```

### update_delivery_status()
```python
def update_delivery_status(
    delivery: Encounter,
    new_status: str,
    actor: Person,
    notes: str = "",
) -> Encounter:
    """Transicionar entrega a nuevo estado."""
```

## Casos de Prueba (40 pruebas)

### Pruebas de Menu (6 pruebas)
1. test_create_pizzeria_menu
2. test_pizza_with_sizes
3. test_topping_catalog_item
4. test_menu_item_availability
5. test_price_by_size
6. test_seasonal_menu_item

### Pruebas de Carrito (10 pruebas)
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

### Pruebas de Zona de Entrega (4 pruebas)
17. test_address_in_zone
18. test_address_outside_zone
19. test_delivery_fee_calculation
20. test_minimum_order_enforcement

### Pruebas de Checkout (8 pruebas)
21. test_commit_basket_locks_prices
22. test_payment_creates_transaction
23. test_platform_commission_entry
24. test_vendor_payable_entry
25. test_tip_entry_to_driver
26. test_entries_balance
27. test_order_number_generated
28. test_checkout_creates_delivery

### Pruebas de Seguimiento de Entrega (8 pruebas)
29. test_create_delivery_encounter
30. test_delivery_initial_state
31. test_transition_to_preparing
32. test_transition_to_ready
33. test_driver_picks_up
34. test_transition_en_route
35. test_transition_delivered
36. test_invalid_transition_rejected

### Pruebas de Repartidor (4 pruebas)
37. test_start_driver_shift
38. test_end_driver_shift
39. test_assign_delivery_to_driver
40. test_driver_shift_deliveries

## Comportamientos Clave

1. **Medios ingredientes via metadata** - campo coverage, multiplicador de mitad de precio
2. **Ofertas combo como Agreements** - terms.items, terms.fixed_price
3. **Pedidos son Baskets** - commit() bloquea precios
4. **Pagos divididos via Entries** - cuentas de plataforma, vendedor, repartidor
5. **Entrega es Encounter** - maquina de estados con transiciones
6. **Zonas son ServiceAreas** - tarifa y min_order en metadata

## Operaciones Prohibidas

- Crear modelos Order o LineItem personalizados
- Almacenar precios sin instantaneas
- Evadir Basket.commit() en checkout
- Asignacion directa de estado en entregas
- Modificar items de canasta confirmados
- Procesar pago sin entradas balanceadas

## Criterios de Aceptacion

- [ ] Sin nuevos modelos Django para conceptos core
- [ ] Medios ingredientes funcionan via metadata de BasketItem
- [ ] Ofertas combo usan Agreement con terms
- [ ] Pedidos usan Basket con commit()
- [ ] Pagos usan Transaction con entradas balanceadas
- [ ] Entregas usan Encounter con maquina de estados
- [ ] Zonas usan ServiceArea
- [ ] Las 40 pruebas pasando
- [ ] README con ejemplo de flujo de pedido
```

---

## Usando Este Prompt

Para reconstruir este marketplace con Claude:

**Paso 1: Proporcionar el contexto de restricciones**

Antes del prompt de reconstruccion, dale a Claude:
- La documentacion de paquetes django-primitives
- El archivo CLAUDE.md con reglas de capas
- Este prompt como la especificacion

**Paso 2: Solicitar incrementalmente**

Dividir en fases:
1. "Configurar el catalogo: pizzeria, categorias de menu, items de menu con tamaños"
2. "Implementar add_pizza_to_cart con soporte de medio ingrediente"
3. "Implementar ofertas combo usando Agreement"
4. "Implementar checkout con entradas de pago dividido"
5. "Crear el flujo de trabajo de encuentro de entrega"

**Paso 3: Validar cada salida**

Despues de cada generacion, verificar:
- Son todos los modelos de primitivas (no personalizados)?
- La logica de medio ingrediente usa metadata, no un modelo personalizado?
- Los pagos usan Transaction con registros Entry balanceados?

**Paso 4: Corregir violaciones de restricciones**

Si Claude crea un modelo personalizado:
"No crees un modelo DeliveryZone. Usa ServiceArea de django-geo con metadata.delivery_fee y metadata.min_order."

**El prompt es el contrato. Hazlo cumplir.**

---

## Lo Que No Construimos

Nota lo que el marketplace NO contiene:

1. **Sin modelo de pedido personalizado** - Usa Basket de django-catalog
2. **Sin modelo de linea de item personalizado** - Usa BasketItem con metadata
3. **Sin modelo de pago personalizado** - Usa Transaction de django-ledger
4. **Sin modelo de entrega personalizado** - Usa Encounter de django-encounters
5. **Sin sistema de promociones personalizado** - Usa Agreement de django-agreements
6. **Sin modelo de zona personalizado** - Usa ServiceArea de django-geo

El codigo de aplicacion es puramente:
- **Configuracion**: Items de menu, zonas, definiciones de encuentros
- **Logica de negocio**: Calculo de comision, enrutamiento de propinas
- **Composicion**: Conectando primitivas para el dominio de pizza

---

## La Respuesta del Medio Ingrediente

Recuerdas la objecion del principio?

"Pero la pizza tiene medios ingredientes."

Aqui esta la respuesta completa:

```python
# Medio ingrediente: cantidad 0.5 con metadata de cobertura
BasketItem.objects.create(
    basket=basket,
    catalog_item=pepperoni,
    quantity=1,  # Por pizza
    unit_price_snapshot=pepperoni.unit_price * Decimal('0.5'),  # Mitad de precio
    metadata={
        'coverage': 'left',  # o 'right', 'full'
        'parent_pizza_id': pizza_line.id,
    }
)
```

Tres campos:
- `quantity`: Igual que cantidad de pizza
- `unit_price_snapshot`: Mitad de precio para medio ingrediente
- `metadata.coverage`: Cual mitad

Sin nuevos modelos. Sin casos especiales. Solo configuracion.

---

## Ejercicio Practico

Construir un sistema minimo de pedido de pizza:

**Paso 1: Configurar items del catalogo**
- Un tamaño de pizza
- Tres ingredientes
- Una oferta combo

**Paso 2: Implementar add_pizza_to_cart**
- Manejar ingredientes completos y medios
- Calcular precios correctos

**Paso 3: Implementar checkout**
- Dividir pago entre plataforma y vendedor
- Manejar propinas

**Paso 4: Probar el flujo**
- Ordenar una pizza con medio pepperoni, medio champiñon
- Aplicar una oferta combo
- Procesar pago con propina

---

## Resumen

| Concepto del Dominio | Primitiva | Configuracion |
|---------------------|-----------|---------------|
| Medio ingrediente | BasketItem | coverage en metadata, multiplicador de mitad |
| Oferta combo | Agreement | lista de items, precio fijo |
| Zona de entrega | ServiceArea | radio, tarifa en metadata |
| Turno de repartidor | WorkSession | target=pizzeria |
| Seguimiento de entrega | Encounter | maquina de 9 estados |
| Pago dividido | Transaction | Multiples entradas |
| Propinas | Entry | Transferencia directa a cuenta de repartidor |

Cada requisito "unico" de pizza es configuracion de primitivas existentes.

A las primitivas no les importa la pizza. Les importa ordenar, geografia, seguimiento de trabajo, movimiento de dinero y maquinas de estado.

Pizza es solo una composicion. Las mismas primitivas construyen entrega de sushi, entrega de flores, o cualquier otro marketplace de logistica.

Ese es el punto.
