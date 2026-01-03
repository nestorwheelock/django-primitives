# Capitulo 25: Construir un Servicio de Suscripcion

## La Hoja de Calculo de Abandono

En 2012, una fundadora de SaaS bootstrapped descubrio que sus clientes abandonaban mas rapido de lo que podia adquirirlos. Su sistema de gestion de suscripciones - una coleccion de webhooks de Stripe y cron jobs - no podia responder preguntas basicas:

- Cuando cambio realmente el plan de este cliente?
- Cual fue su uso durante el periodo de facturacion que acaba de terminar?
- Por que les cobramos $127.43 en lugar de $99?
- Quien en su equipo tenia acceso a que funciones, y cuando?

Paso tres semanas reconstruyendo su sistema de suscripciones con seguimiento temporal apropiado y registros de facturacion inmutables. El abandono cayo 23% en el siguiente trimestre - no por cambios en el producto, sino por poder responder preguntas de facturacion de clientes con precision.

Este capitulo construye ese sistema: gestion de suscripciones con semantica temporal, seguimiento de uso y facturacion basada en libro mayor. Las mismas primitivas. Diferente dominio.

---

## El Dominio

Un servicio de suscripcion SaaS necesita:

- **Clientes y cuentas** - individuos u organizaciones que se suscriben
- **Planes y precios** - lo que pueden comprar y a que precio
- **Suscripciones** - la relacion continua entre cliente y plan
- **Ciclos de facturacion** - cuando y cuanto cobrar
- **Seguimiento de uso** - lo que realmente usaron (para precios basados en uso)
- **Facturas** - registros inmutables de lo que se cobro
- **Acceso a funciones** - que funciones estan disponibles en que planes
- **Cambios de plan** - upgrades, downgrades y prorrateo

## Mapeo de Primitivas

| Concepto del Dominio | Primitiva | Paquete |
|---------------------|-----------|---------|
| Cliente | Party (Person) | django-parties |
| Cuenta de empresa | Party (Organization) | django-parties |
| Miembro de equipo | PartyRelationship | django-parties |
| Plan | CatalogItem | django-catalog |
| Nivel de plan | Category | django-catalog |
| Suscripcion | Agreement | django-agreements |
| Ciclo de facturacion | Agreement terms | django-agreements |
| Factura | Transaction | django-ledger |
| Pago | Entry | django-ledger |
| Evento de uso | AuditLog (evento personalizado) | django-audit-log |
| Acceso a funciones | Role + Permission | django-rbac |
| Funciones del plan | Agreement terms | django-agreements |

Cero nuevos modelos. Las suscripciones son composiciones de primitivas existentes.

---

## Cuentas de Cliente

Un cliente SaaS puede ser un individuo o una organizacion. Las organizaciones tienen miembros de equipo con diferentes roles.

### Persona como Cliente

```python
from django_parties.models import Person

# Cliente individual
customer = Person.objects.create(
    email="developer@example.com",
    full_name="Alex Developer",
    metadata={
        "source": "organic_signup",
        "referral_code": "HACKERNEWS",
    }
)
```

### Organizacion como Cliente

```python
from django_parties.models import Organization, Person, PartyRelationship

# Cuenta de empresa
company = Organization.objects.create(
    name="Acme Corp",
    email="billing@acme.com",
    metadata={
        "industry": "technology",
        "employee_count": "50-200",
    }
)

# Propietario de cuenta
owner = Person.objects.create(
    email="cto@acme.com",
    full_name="Jamie CTO",
)

# Relacion con rol
PartyRelationship.objects.create(
    from_party=owner,
    to_party=company,
    relationship_type="account_owner",
    valid_from=timezone.now(),
)

# Miembro del equipo con acceso de facturacion
billing_admin = Person.objects.create(
    email="finance@acme.com",
    full_name="Morgan Finance",
)

PartyRelationship.objects.create(
    from_party=billing_admin,
    to_party=company,
    relationship_type="billing_admin",
    valid_from=timezone.now(),
)
```

### Consultando Equipo en Cualquier Momento

```python
# Equipo actual
current_team = PartyRelationship.objects.filter(
    to_party=company,
).current()

# Equipo a la fecha de la ultima facturacion
team_at_billing = PartyRelationship.objects.filter(
    to_party=company,
).as_of(last_invoice_date)

# Quien era propietario de cuenta cuando hicieron upgrade?
owner_at_upgrade = PartyRelationship.objects.filter(
    to_party=company,
    relationship_type="account_owner",
).as_of(upgrade_date).first()
```

---

## Planes como Items del Catalogo

Los planes de suscripcion son items del catalogo con metadata de precios y funciones.

### Jerarquia de Planes

```python
from django_catalog.models import Category, CatalogItem
from decimal import Decimal

# Niveles de plan
tier_starter = Category.objects.create(
    name="Starter",
    code="starter",
    metadata={"max_seats": 5, "support_level": "community"},
)

tier_pro = Category.objects.create(
    name="Professional",
    code="pro",
    metadata={"max_seats": 50, "support_level": "email"},
)

tier_enterprise = Category.objects.create(
    name="Enterprise",
    code="enterprise",
    metadata={"max_seats": None, "support_level": "dedicated"},  # Ilimitado
)
```

### Definiciones de Plan

```python
# Planes mensuales
starter_monthly = CatalogItem.objects.create(
    category=tier_starter,
    name="Starter Mensual",
    sku="starter_monthly",
    unit_price=Decimal("29.00"),
    currency="USD",
    metadata={
        "billing_interval": "month",
        "billing_interval_count": 1,
        "features": [
            "5_team_members",
            "1000_api_calls",
            "community_support",
            "basic_analytics",
        ],
        "limits": {
            "team_members": 5,
            "api_calls_per_month": 1000,
            "storage_gb": 5,
        },
    }
)

pro_monthly = CatalogItem.objects.create(
    category=tier_pro,
    name="Professional Mensual",
    sku="pro_monthly",
    unit_price=Decimal("99.00"),
    currency="USD",
    metadata={
        "billing_interval": "month",
        "billing_interval_count": 1,
        "features": [
            "50_team_members",
            "50000_api_calls",
            "email_support",
            "advanced_analytics",
            "api_access",
            "custom_integrations",
        ],
        "limits": {
            "team_members": 50,
            "api_calls_per_month": 50000,
            "storage_gb": 100,
        },
    }
)

# Planes anuales (con descuento)
pro_annual = CatalogItem.objects.create(
    category=tier_pro,
    name="Professional Anual",
    sku="pro_annual",
    unit_price=Decimal("990.00"),  # 2 meses gratis
    currency="USD",
    metadata={
        "billing_interval": "year",
        "billing_interval_count": 1,
        "features": pro_monthly.metadata["features"],  # Mismas funciones
        "limits": pro_monthly.metadata["limits"],      # Mismos limites
        "annual_discount": "16.67%",
    }
)
```

### Add-ons Basados en Uso

```python
# Excedente de llamadas API
api_overage = CatalogItem.objects.create(
    category=tier_pro,
    name="Llamadas API (excedente)",
    sku="api_calls_overage",
    unit_price=Decimal("0.001"),  # $0.001 por llamada
    currency="USD",
    metadata={
        "billing_type": "usage",
        "unit": "api_call",
    }
)

# Almacenamiento adicional
storage_addon = CatalogItem.objects.create(
    category=tier_pro,
    name="Almacenamiento Adicional",
    sku="storage_addon_10gb",
    unit_price=Decimal("5.00"),
    currency="USD",
    metadata={
        "billing_type": "recurring",
        "storage_gb": 10,
    }
)
```

---

## Suscripciones como Agreements

Una suscripcion es un acuerdo entre un cliente y el proveedor del servicio. El acuerdo captura en que plan estan, cuando comenzo y los terminos de facturacion.

### Creando una Suscripcion

```python
from django_agreements.models import Agreement
from django_parties.models import Organization

# El proveedor (tu empresa)
provider = Organization.objects.get(name="CloudSoft Inc")

# Suscribir cliente a Pro Mensual
subscription = Agreement.objects.create(
    agreement_type="subscription",
    status="active",
    valid_from=timezone.now(),
    valid_to=None,  # Hasta cancelacion
    metadata={
        "plan_sku": "pro_monthly",
        "price_at_signup": "99.00",
        "currency": "USD",
        "billing_day": 15,  # Facturar el dia 15 de cada mes
        "payment_method_id": "pm_card_visa_4242",
    }
)

# Vincular partes al acuerdo
from django_agreements.models import AgreementParty

AgreementParty.objects.create(
    agreement=subscription,
    party=company,  # Cliente
    role="subscriber",
)

AgreementParty.objects.create(
    agreement=subscription,
    party=provider,
    role="provider",
)
```

### Suscripcion con Prueba

```python
from datetime import timedelta

trial_start = timezone.now()
trial_end = trial_start + timedelta(days=14)

subscription = Agreement.objects.create(
    agreement_type="subscription",
    status="trialing",
    valid_from=trial_start,
    valid_to=None,
    metadata={
        "plan_sku": "pro_monthly",
        "price_at_signup": "99.00",
        "trial_start": trial_start.isoformat(),
        "trial_end": trial_end.isoformat(),
        "billing_starts": trial_end.isoformat(),
    }
)
```

### Consultando Suscripciones Activas

```python
# Todas las suscripciones activas actualmente
active_subs = Agreement.objects.filter(
    agreement_type="subscription",
    status__in=["active", "trialing"],
).current()

# Suscripciones que estaban activas en una fecha especifica
subs_last_month = Agreement.objects.filter(
    agreement_type="subscription",
).as_of(last_month)

# Encontrar suscripcion del cliente
customer_sub = Agreement.objects.filter(
    agreement_type="subscription",
    agreementparty__party=customer,
    agreementparty__role="subscriber",
).current().first()
```

---

## Ciclos de Facturacion y Emision de Facturas

La facturacion usa el libro mayor. Cada factura es una transaccion inmutable que registra lo que se cobro y por que.

### Estructura de Cuentas

```python
from django_ledger.models import Account

# Cuentas de ingresos
subscription_revenue = Account.objects.create(
    name="Ingresos por Suscripcion",
    code="4100",
    account_type="revenue",
)

usage_revenue = Account.objects.create(
    name="Ingresos por Uso",
    code="4200",
    account_type="revenue",
)

# Cuentas de activo
accounts_receivable = Account.objects.create(
    name="Cuentas por Cobrar",
    code="1200",
    account_type="asset",
)

cash = Account.objects.create(
    name="Efectivo",
    code="1000",
    account_type="asset",
)
```

### Creando una Factura

```python
from django_ledger.models import Transaction, Entry
from django_ledger.services import post_transaction

def create_invoice(subscription, billing_period_start, billing_period_end):
    """Crear factura para un periodo de facturacion."""
    plan = CatalogItem.objects.get(sku=subscription.metadata["plan_sku"])
    amount = plan.unit_price

    # Crear la transaccion de factura
    invoice = Transaction.objects.create(
        transaction_type="invoice",
        effective_at=billing_period_end,
        metadata={
            "subscription_id": str(subscription.id),
            "billing_period_start": billing_period_start.isoformat(),
            "billing_period_end": billing_period_end.isoformat(),
            "plan_sku": plan.sku,
            "plan_name": plan.name,
        }
    )

    # Debitar cuentas por cobrar, acreditar ingresos
    Entry.objects.create(
        transaction=invoice,
        account=accounts_receivable,
        amount=amount,
        entry_type="debit",
        description=f"Suscripcion: {plan.name}",
    )

    Entry.objects.create(
        transaction=invoice,
        account=subscription_revenue,
        amount=amount,
        entry_type="credit",
        description=f"Suscripcion: {plan.name}",
    )

    # Publicar la transaccion (la hace inmutable)
    post_transaction(invoice)

    return invoice
```

### Registrando Pago

```python
def record_payment(invoice, payment_method, payment_ref):
    """Registrar pago contra una factura."""
    amount = invoice.entries.filter(entry_type="debit").aggregate(
        total=Sum("amount")
    )["total"]

    payment = Transaction.objects.create(
        transaction_type="payment",
        effective_at=timezone.now(),
        metadata={
            "invoice_id": str(invoice.id),
            "payment_method": payment_method,
            "payment_ref": payment_ref,
        }
    )

    # Debitar efectivo, acreditar cuentas por cobrar
    Entry.objects.create(
        transaction=payment,
        account=cash,
        amount=amount,
        entry_type="debit",
    )

    Entry.objects.create(
        transaction=payment,
        account=accounts_receivable,
        amount=amount,
        entry_type="credit",
    )

    post_transaction(payment)

    # Registrar el evento de pago
    log_event(
        target=invoice,
        event_type="payment_received",
        metadata={
            "payment_id": str(payment.id),
            "amount": str(amount),
            "method": payment_method,
        }
    )

    return payment
```

### Ejecucion de Facturacion

```python
from dateutil.relativedelta import relativedelta

def run_monthly_billing(billing_date):
    """Ejecutar facturacion para todas las suscripciones vencidas en esta fecha."""

    # Encontrar suscripciones activas con dia de facturacion coincidente
    due_subscriptions = Agreement.objects.filter(
        agreement_type="subscription",
        status="active",
        metadata__billing_day=billing_date.day,
    ).current()

    results = []

    for subscription in due_subscriptions:
        # Calcular periodo de facturacion
        period_end = billing_date
        period_start = period_end - relativedelta(months=1)

        try:
            # Crear factura
            invoice = create_invoice(
                subscription=subscription,
                billing_period_start=period_start,
                billing_period_end=period_end,
            )

            # Intentar pago
            payment_method = subscription.metadata.get("payment_method_id")
            payment_result = charge_payment_method(
                payment_method,
                invoice.total,
            )

            if payment_result.success:
                record_payment(invoice, "card", payment_result.charge_id)
                results.append({"subscription": subscription.id, "status": "paid"})
            else:
                results.append({
                    "subscription": subscription.id,
                    "status": "failed",
                    "reason": payment_result.error,
                })

        except Exception as e:
            results.append({
                "subscription": subscription.id,
                "status": "error",
                "reason": str(e),
            })

    return results
```

---

## Seguimiento de Uso

La facturacion basada en uso requiere rastrear lo que los clientes realmente usan. El log de auditoria captura eventos de uso.

### Registrando Uso

```python
from django_audit_log.services import log_event

def record_api_call(subscription, endpoint, response_time_ms, response_code):
    """Registrar una llamada API para seguimiento de uso."""
    log_event(
        target=subscription,
        event_type="api_call",
        metadata={
            "endpoint": endpoint,
            "response_time_ms": response_time_ms,
            "response_code": response_code,
            "timestamp": timezone.now().isoformat(),
        }
    )

def record_storage_usage(subscription, bytes_stored):
    """Registrar instantanea de almacenamiento para seguimiento de uso."""
    log_event(
        target=subscription,
        event_type="storage_snapshot",
        metadata={
            "bytes_stored": bytes_stored,
            "gb_stored": bytes_stored / (1024 ** 3),
            "timestamp": timezone.now().isoformat(),
        }
    )
```

### Consultando Uso

```python
from django_audit_log.models import AuditLog
from django.db.models import Count, Avg

def get_usage_for_period(subscription, start_date, end_date):
    """Obtener metricas de uso para un periodo de facturacion."""

    events = AuditLog.objects.for_target(subscription).filter(
        created_at__gte=start_date,
        created_at__lt=end_date,
    )

    # Llamadas API
    api_calls = events.filter(event_type="api_call").count()

    # Tiempo de respuesta promedio
    avg_response = events.filter(event_type="api_call").aggregate(
        avg_ms=Avg("metadata__response_time_ms")
    )["avg_ms"]

    # Almacenamiento pico (ultima instantanea en el periodo)
    storage_snapshot = events.filter(
        event_type="storage_snapshot"
    ).order_by("-created_at").first()

    storage_gb = 0
    if storage_snapshot:
        storage_gb = storage_snapshot.metadata.get("gb_stored", 0)

    return {
        "api_calls": api_calls,
        "avg_response_ms": avg_response,
        "storage_gb": storage_gb,
    }
```

### Facturacion Basada en Uso

```python
def calculate_overage_charges(subscription, period_start, period_end):
    """Calcular cargos por excedente para un periodo de facturacion."""
    plan = CatalogItem.objects.get(sku=subscription.metadata["plan_sku"])
    limits = plan.metadata.get("limits", {})

    usage = get_usage_for_period(subscription, period_start, period_end)
    charges = []

    # Excedente de llamadas API
    api_limit = limits.get("api_calls_per_month", 0)
    api_used = usage["api_calls"]

    if api_used > api_limit:
        overage = api_used - api_limit
        overage_rate = Decimal("0.001")  # $0.001 por llamada
        charges.append({
            "type": "api_overage",
            "quantity": overage,
            "unit_price": overage_rate,
            "amount": overage * overage_rate,
            "description": f"Excedente de llamadas API: {overage} llamadas @ ${overage_rate}/llamada",
        })

    # Excedente de almacenamiento
    storage_limit = limits.get("storage_gb", 0)
    storage_used = usage["storage_gb"]

    if storage_used > storage_limit:
        overage = storage_used - storage_limit
        overage_rate = Decimal("0.50")  # $0.50 por GB
        charges.append({
            "type": "storage_overage",
            "quantity": overage,
            "unit_price": overage_rate,
            "amount": Decimal(overage) * overage_rate,
            "description": f"Excedente de almacenamiento: {overage:.2f} GB @ ${overage_rate}/GB",
        })

    return charges
```

---

## Acceso a Funciones con RBAC

Diferentes planes desbloquean diferentes funciones. RBAC controla lo que los usuarios pueden hacer.

### Roles Basados en Plan

```python
from django_rbac.models import Role, Permission

# Crear permisos para funciones
api_access = Permission.objects.create(
    code="api_access",
    name="Acceso a API",
    description="Puede usar la API",
)

advanced_analytics = Permission.objects.create(
    code="advanced_analytics",
    name="Analiticas Avanzadas",
    description="Puede acceder a analiticas avanzadas",
)

custom_integrations = Permission.objects.create(
    code="custom_integrations",
    name="Integraciones Personalizadas",
    description="Puede configurar integraciones personalizadas",
)

priority_support = Permission.objects.create(
    code="priority_support",
    name="Soporte Prioritario",
    description="Puede acceder al canal de soporte prioritario",
)

# Crear roles basados en plan
starter_role = Role.objects.create(
    name="Plan Starter",
    code="plan_starter",
)
# Starter no obtiene permisos premium

pro_role = Role.objects.create(
    name="Plan Professional",
    code="plan_pro",
)
pro_role.permissions.add(api_access, advanced_analytics, custom_integrations)

enterprise_role = Role.objects.create(
    name="Plan Enterprise",
    code="plan_enterprise",
)
enterprise_role.permissions.add(
    api_access, advanced_analytics, custom_integrations, priority_support
)
```

### Sincronizando Suscripcion con Rol

```python
from django_rbac.models import UserRole

def sync_subscription_role(subscription, user):
    """Sincronizar rol del usuario basado en su suscripcion."""
    plan_sku = subscription.metadata["plan_sku"]

    # Mapear plan a rol
    plan_role_map = {
        "starter_monthly": "plan_starter",
        "starter_annual": "plan_starter",
        "pro_monthly": "plan_pro",
        "pro_annual": "plan_pro",
        "enterprise_monthly": "plan_enterprise",
        "enterprise_annual": "plan_enterprise",
    }

    role_code = plan_role_map.get(plan_sku)
    if not role_code:
        return

    role = Role.objects.get(code=role_code)

    # Expirar cualquier rol de plan existente
    UserRole.objects.filter(
        user=user,
        role__code__startswith="plan_",
        valid_to__isnull=True,
    ).update(valid_to=timezone.now())

    # Asignar nuevo rol
    UserRole.objects.create(
        user=user,
        role=role,
        valid_from=timezone.now(),
    )
```

### Verificando Acceso a Funciones

```python
def user_can_access_feature(user, permission_code):
    """Verificar si el usuario tiene acceso a una funcion."""
    return UserRole.objects.filter(
        user=user,
        role__permissions__code=permission_code,
    ).current().exists()

# Uso
if user_can_access_feature(user, "api_access"):
    # Permitir llamada API
    pass
else:
    raise PermissionDenied("El acceso a API requiere plan Professional o superior")
```

---

## Cambios de Plan

Los clientes hacen upgrade, downgrade y cancelan. Cada cambio es una nueva version del acuerdo.

### Upgrade

```python
def upgrade_subscription(subscription, new_plan_sku, prorate=True):
    """Hacer upgrade de una suscripcion a un plan superior."""
    old_plan = CatalogItem.objects.get(sku=subscription.metadata["plan_sku"])
    new_plan = CatalogItem.objects.get(sku=new_plan_sku)

    now = timezone.now()

    if prorate:
        # Calcular credito de prorrateo por tiempo no usado
        days_in_period = 30  # Simplificado
        days_remaining = calculate_days_remaining(subscription)
        daily_rate = old_plan.unit_price / days_in_period
        credit_amount = daily_rate * days_remaining

        # Calcular cargo prorrateado para nuevo plan
        new_daily_rate = new_plan.unit_price / days_in_period
        charge_amount = new_daily_rate * days_remaining

        # Diferencia neta
        proration = charge_amount - credit_amount

        # Crear factura de prorrateo
        if proration > 0:
            create_proration_invoice(
                subscription=subscription,
                amount=proration,
                description=f"Prorrateo de upgrade: {old_plan.name} a {new_plan.name}",
            )

    # Terminar suscripcion actual
    subscription.valid_to = now
    subscription.status = "upgraded"
    subscription.save()

    # Crear nueva suscripcion
    new_subscription = Agreement.objects.create(
        agreement_type="subscription",
        status="active",
        valid_from=now,
        valid_to=None,
        metadata={
            "plan_sku": new_plan_sku,
            "price_at_signup": str(new_plan.unit_price),
            "currency": subscription.metadata["currency"],
            "billing_day": subscription.metadata["billing_day"],
            "payment_method_id": subscription.metadata["payment_method_id"],
            "upgraded_from": str(subscription.id),
        }
    )

    # Copiar relaciones de party
    for party in subscription.agreementparty_set.all():
        AgreementParty.objects.create(
            agreement=new_subscription,
            party=party.party,
            role=party.role,
        )

    # Registrar el upgrade
    log_event(
        target=subscription,
        event_type="subscription_upgraded",
        metadata={
            "old_plan": old_plan.sku,
            "new_plan": new_plan.sku,
            "new_subscription_id": str(new_subscription.id),
            "proration_amount": str(proration) if prorate else "0",
        }
    )

    # Sincronizar roles RBAC
    subscriber = subscription.agreementparty_set.filter(role="subscriber").first()
    if subscriber:
        sync_subscription_role(new_subscription, subscriber.party)

    return new_subscription
```

### Downgrade

```python
def schedule_downgrade(subscription, new_plan_sku):
    """Programar un downgrade para fin del periodo de facturacion."""
    # No aplicar inmediatamente - esperar hasta que termine el periodo
    subscription.metadata["scheduled_plan_change"] = {
        "new_plan_sku": new_plan_sku,
        "effective_date": calculate_next_billing_date(subscription).isoformat(),
        "reason": "customer_requested_downgrade",
    }
    subscription.save()

    log_event(
        target=subscription,
        event_type="downgrade_scheduled",
        metadata=subscription.metadata["scheduled_plan_change"],
    )
```

### Cancelacion

```python
def cancel_subscription(subscription, reason, immediate=False):
    """Cancelar una suscripcion."""
    now = timezone.now()

    if immediate:
        # Cancelar inmediatamente
        subscription.valid_to = now
        subscription.status = "cancelled"
    else:
        # Cancelar al fin del periodo de facturacion
        subscription.metadata["scheduled_cancellation"] = {
            "effective_date": calculate_next_billing_date(subscription).isoformat(),
            "reason": reason,
        }
        subscription.status = "pending_cancellation"

    subscription.save()

    log_event(
        target=subscription,
        event_type="subscription_cancelled",
        metadata={
            "reason": reason,
            "immediate": immediate,
            "effective_date": subscription.valid_to.isoformat() if immediate else subscription.metadata["scheduled_cancellation"]["effective_date"],
        }
    )

    # Expirar roles RBAC si es inmediato
    if immediate:
        subscriber = subscription.agreementparty_set.filter(role="subscriber").first()
        if subscriber:
            UserRole.objects.filter(
                user=subscriber.party,
                role__code__startswith="plan_",
                valid_to__isnull=True,
            ).update(valid_to=now)
```

### Reactivacion

```python
def reactivate_subscription(old_subscription, plan_sku=None):
    """Reactivar una suscripcion cancelada."""
    if not plan_sku:
        plan_sku = old_subscription.metadata["plan_sku"]

    now = timezone.now()

    new_subscription = Agreement.objects.create(
        agreement_type="subscription",
        status="active",
        valid_from=now,
        valid_to=None,
        metadata={
            "plan_sku": plan_sku,
            "price_at_signup": CatalogItem.objects.get(sku=plan_sku).unit_price,
            "currency": old_subscription.metadata["currency"],
            "billing_day": now.day,  # Nuevo dia de facturacion
            "payment_method_id": old_subscription.metadata["payment_method_id"],
            "reactivated_from": str(old_subscription.id),
        }
    )

    # Copiar parties
    for party in old_subscription.agreementparty_set.all():
        AgreementParty.objects.create(
            agreement=new_subscription,
            party=party.party,
            role=party.role,
        )

    log_event(
        target=old_subscription,
        event_type="subscription_reactivated",
        metadata={
            "new_subscription_id": str(new_subscription.id),
        }
    )

    return new_subscription
```

---

## Historial de Suscripciones

Debido a que las suscripciones son acuerdos con limites temporales, puedes consultar el historial completo.

### Linea de Tiempo de Suscripcion

```python
def get_subscription_history(customer):
    """Obtener historial completo de suscripcion para un cliente."""
    return Agreement.objects.filter(
        agreement_type="subscription",
        agreementparty__party=customer,
        agreementparty__role="subscriber",
    ).order_by("valid_from")

# Uso
history = get_subscription_history(company)
for sub in history:
    print(f"{sub.valid_from} - {sub.valid_to or 'Actual'}: {sub.metadata['plan_sku']} ({sub.status})")
```

### Calculo de MRR

```python
def calculate_mrr(as_of=None):
    """Calcular Ingresos Recurrentes Mensuales."""
    if as_of is None:
        as_of = timezone.now()

    active_subs = Agreement.objects.filter(
        agreement_type="subscription",
        status="active",
    ).as_of(as_of)

    mrr = Decimal("0")
    for sub in active_subs:
        plan = CatalogItem.objects.get(sku=sub.metadata["plan_sku"])
        interval = plan.metadata.get("billing_interval", "month")

        if interval == "month":
            mrr += plan.unit_price
        elif interval == "year":
            mrr += plan.unit_price / 12  # Convertir a mensual

    return mrr

# MRR historico
for month in range(1, 13):
    date = datetime(2024, month, 1, tzinfo=timezone.utc)
    mrr = calculate_mrr(as_of=date)
    print(f"{date.strftime('%B %Y')}: ${mrr:,.2f} MRR")
```

### Analisis de Abandono

```python
def calculate_churn_rate(period_start, period_end):
    """Calcular tasa de abandono para un periodo."""
    # Suscripciones activas al inicio
    subs_at_start = Agreement.objects.filter(
        agreement_type="subscription",
        status="active",
    ).as_of(period_start).count()

    # Suscripciones que abandonaron durante el periodo
    churned = Agreement.objects.filter(
        agreement_type="subscription",
        status__in=["cancelled", "expired"],
        valid_to__gte=period_start,
        valid_to__lt=period_end,
    ).count()

    if subs_at_start == 0:
        return Decimal("0")

    return (Decimal(churned) / Decimal(subs_at_start)) * 100
```

---

## Prompt Completo de Reconstruccion

```markdown
# Prompt: Reconstruir Servicio de Suscripcion

## Instruccion

Construir un servicio de gestion de suscripciones SaaS componiendo estas primitivas:
- django-parties (clientes, organizaciones, miembros de equipo)
- django-catalog (planes, precios)
- django-agreements (suscripciones)
- django-ledger (facturas, pagos)
- django-audit-log (seguimiento de uso)
- django-rbac (acceso a funciones)

## Proposito del Dominio

Permitir a negocios SaaS:
- Gestionar clientes (individuos y organizaciones)
- Definir planes de suscripcion con funciones y limites
- Manejar ciclo de vida de suscripcion (prueba, activa, cancelada)
- Facturar clientes en calendarios recurrentes
- Rastrear uso para precios basados en uso
- Controlar acceso a funciones basado en plan

## SIN NUEVOS MODELOS

No crear ningun nuevo modelo Django. Toda la funcionalidad de suscripcion
se implementa componiendo primitivas existentes.

## Composicion de Primitivas

### Clientes
- Person = Cliente individual
- Organization = Cuenta de empresa
- PartyRelationship = Miembro de equipo con rol (owner, admin, member, billing)

### Planes
- Category = Nivel de plan (Starter, Pro, Enterprise)
- CatalogItem = Plan especifico con precio y funciones
  - metadata.billing_interval: "month" o "year"
  - metadata.features: lista de codigos de funcion
  - metadata.limits: diccionario de limites de uso

### Suscripciones
- Agreement (agreement_type="subscription")
  - status: "trialing", "active", "pending_cancellation", "cancelled"
  - valid_from: inicio de suscripcion
  - valid_to: fin de suscripcion (null = en curso)
  - metadata.plan_sku: referencia a CatalogItem
  - metadata.billing_day: dia del mes para facturar
  - metadata.payment_method_id: metodo de pago almacenado
- AgreementParty = vincula cliente a suscripcion

### Facturacion
- Transaction (transaction_type="invoice") = factura
  - entries: debitar cuentas por cobrar, acreditar ingresos
  - metadata.billing_period_start/end
  - metadata.subscription_id
- Transaction (transaction_type="payment") = pago
  - entries: debitar efectivo, acreditar cuentas por cobrar
  - metadata.invoice_id

### Seguimiento de Uso
- AuditLog (event_type="api_call") = uso de API
- AuditLog (event_type="storage_snapshot") = uso de almacenamiento
- Consultar con .for_target(subscription)

### Acceso a Funciones
- Permission = capacidad de funcion
- Role = rol basado en plan (plan_starter, plan_pro, plan_enterprise)
- UserRole = asigna rol de plan a usuario

## Funciones de Servicio

### subscribe_customer()
```python
def subscribe_customer(
    customer: Party,
    plan_sku: str,
    payment_method_id: str,
    trial_days: int = 0,
) -> Agreement:
    """Crear nueva suscripcion para un cliente."""
```

### upgrade_subscription()
```python
def upgrade_subscription(
    subscription: Agreement,
    new_plan_sku: str,
    prorate: bool = True,
) -> Agreement:
    """Hacer upgrade a un plan superior con prorrateo opcional."""
```

### cancel_subscription()
```python
def cancel_subscription(
    subscription: Agreement,
    reason: str,
    immediate: bool = False,
) -> Agreement:
    """Cancelar suscripcion inmediatamente o al fin del periodo."""
```

### run_billing()
```python
def run_billing(billing_date: date) -> list[dict]:
    """Ejecutar facturacion para todas las suscripciones vencidas en esta fecha."""
```

### record_usage()
```python
def record_usage(
    subscription: Agreement,
    event_type: str,
    metadata: dict,
) -> AuditLog:
    """Registrar un evento de uso para una suscripcion."""
```

### get_usage_for_period()
```python
def get_usage_for_period(
    subscription: Agreement,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Obtener metricas de uso para un periodo de facturacion."""
```

### sync_subscription_role()
```python
def sync_subscription_role(
    subscription: Agreement,
    user: User,
) -> UserRole:
    """Sincronizar rol RBAC del usuario basado en plan de suscripcion."""
```

## Casos de Prueba (42 pruebas)

### Pruebas de Cliente (6 pruebas)
1. test_create_individual_customer
2. test_create_organization_customer
3. test_add_team_member
4. test_team_member_roles
5. test_team_at_point_in_time
6. test_organization_hierarchy

### Pruebas de Plan (8 pruebas)
7. test_create_plan_tiers
8. test_create_monthly_plan
9. test_create_annual_plan
10. test_plan_with_features
11. test_plan_with_limits
12. test_usage_addon_plan
13. test_plan_price_snapshot
14. test_plan_comparison

### Pruebas de Suscripcion (12 pruebas)
15. test_create_subscription
16. test_subscription_with_trial
17. test_subscription_active_query
18. test_subscription_as_of_query
19. test_upgrade_subscription
20. test_upgrade_with_proration
21. test_downgrade_scheduled
22. test_cancel_immediate
23. test_cancel_at_period_end
24. test_reactivate_subscription
25. test_subscription_history
26. test_multiple_subscriptions_same_customer

### Pruebas de Facturacion (10 pruebas)
27. test_create_invoice
28. test_invoice_immutable
29. test_record_payment
30. test_billing_run_monthly
31. test_billing_run_annual
32. test_proration_calculation
33. test_usage_overage_charges
34. test_invoice_with_overage
35. test_failed_payment_handling
36. test_mrr_calculation

### Pruebas de Acceso a Funciones (6 pruebas)
37. test_plan_role_permissions
38. test_sync_role_on_subscribe
39. test_sync_role_on_upgrade
40. test_expire_role_on_cancel
41. test_feature_access_check
42. test_feature_access_denied

## Comportamientos Clave

1. **Las suscripciones son Agreements** - las mismas primitivas que contratos
2. **Las facturas son Transactions inmutables** - no pueden modificarse despues de publicar
3. **El uso son eventos de AuditLog** - consultar con filtros temporales
4. **Acceso a funciones via RBAC** - roles sincronizados al plan de suscripcion
5. **Los cambios de plan crean nuevos Agreements** - historial preservado
6. **La facturacion son Transactions de libro mayor** - contabilidad de doble entrada

## Criterios de Aceptacion

- [ ] Sin nuevos modelos Django creados
- [ ] Las suscripciones usan Agreement con relaciones de party apropiadas
- [ ] Las facturas usan Transactions inmutables
- [ ] El uso se rastrea via eventos de AuditLog
- [ ] El acceso a funciones controlado por RBAC
- [ ] Los cambios de plan preservan historial
- [ ] El prorrateo se calcula correctamente
- [ ] El MRR calculable en cualquier punto en el tiempo
- [ ] Las 42 pruebas pasando
- [ ] README con ejemplos de integracion
```

---

## Ejercicio Practico: Construir Analiticas de Suscripcion

Agregar analiticas a tu servicio de suscripcion.

**Paso 1: Retencion por Cohorte**

```python
def cohort_retention(signup_month: date) -> dict:
    """Calcular retencion por cohorte de registro."""
    cohort_start = signup_month.replace(day=1)
    cohort_end = (cohort_start + relativedelta(months=1))

    # Suscripciones iniciadas en esta cohorte
    cohort = Agreement.objects.filter(
        agreement_type="subscription",
        valid_from__gte=cohort_start,
        valid_from__lt=cohort_end,
    )

    cohort_size = cohort.count()
    retention = {}

    # Verificar retencion para cada mes
    for months_later in range(0, 12):
        check_date = cohort_start + relativedelta(months=months_later)
        still_active = cohort.filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=check_date)
        ).count()

        retention[f"month_{months_later}"] = {
            "active": still_active,
            "rate": (still_active / cohort_size * 100) if cohort_size > 0 else 0,
        }

    return {
        "cohort": cohort_start.isoformat(),
        "cohort_size": cohort_size,
        "retention": retention,
    }
```

**Paso 2: Ingresos por Plan**

```python
def revenue_by_plan(period_start: date, period_end: date) -> dict:
    """Calcular desglose de ingresos por plan."""
    invoices = Transaction.objects.filter(
        transaction_type="invoice",
        effective_at__gte=period_start,
        effective_at__lt=period_end,
        status="posted",
    )

    by_plan = {}
    for invoice in invoices:
        plan_sku = invoice.metadata.get("plan_sku", "unknown")
        amount = invoice.entries.filter(entry_type="credit").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        if plan_sku not in by_plan:
            by_plan[plan_sku] = Decimal("0")
        by_plan[plan_sku] += amount

    return by_plan
```

**Paso 3: Valor de Vida del Cliente**

```python
def calculate_ltv(customer: Party) -> Decimal:
    """Calcular valor de vida para un cliente."""
    # Todas las facturas pagadas por este cliente
    subscriptions = Agreement.objects.filter(
        agreement_type="subscription",
        agreementparty__party=customer,
        agreementparty__role="subscriber",
    )

    total_revenue = Decimal("0")
    for sub in subscriptions:
        invoices = Transaction.objects.filter(
            transaction_type="invoice",
            metadata__subscription_id=str(sub.id),
            status="posted",
        )

        for invoice in invoices:
            paid = Transaction.objects.filter(
                transaction_type="payment",
                metadata__invoice_id=str(invoice.id),
                status="posted",
            ).exists()

            if paid:
                amount = invoice.entries.filter(entry_type="credit").aggregate(
                    total=Sum("amount")
                )["total"] or Decimal("0")
                total_revenue += amount

    return total_revenue
```

---

## Lo Que la IA Se Equivoca Sobre Suscripciones

### Almacenar Plan Actual en Cliente

La IA puede querer agregar un campo `current_plan` al cliente:

```python
# MAL
class Customer(models.Model):
    current_plan = models.ForeignKey(Plan, ...)
    subscription_status = models.CharField(...)
```

**Por que esta mal:** Pierde historial. No puede responder "en que plan estaban en marzo?"

**Solucion:** El Agreement de suscripcion ES la relacion del plan. Consultar con `.current()` o `.as_of()`.

### Facturas Mutables

La IA puede permitir modificaciones de facturas:

```python
# MAL
invoice.amount = new_amount
invoice.save()
```

**Por que esta mal:** Destruye la pista de auditoria. Los registros financieros deben ser inmutables.

**Solucion:** Usar Transactions de libro mayor con publicacion. Publicar reversiones para correcciones.

### Verificar Funciones en Tiempo de Solicitud

La IA puede verificar funciones del plan directamente:

```python
# MAL
if subscription.plan.has_feature("api_access"):
    allow_api_call()
```

**Por que esta mal:** Acopla fuertemente el codigo al modelo de suscripcion. Dificil de probar.

**Solucion:** Usar RBAC. Verificar `user_can_access_feature(user, "api_access")`. Sincronizar roles en cambios de suscripcion.

### Calculos de Uso en Linea

La IA puede calcular uso en linea durante las solicitudes:

```python
# MAL (lento, bloqueante)
def handle_api_request(request):
    usage = count_api_calls_this_month(subscription)  # Consulta DB
    if usage > limit:
        return HttpResponseForbidden()
```

**Por que esta mal:** Lento. Cada llamada API consulta la base de datos.

**Solucion:** Cachear conteos de uso. Actualizar de forma asincrona. Verificar contra limite cacheado.

---

## Por Que Esto Importa

La fundadora de la historia de apertura reconstruyo su sistema de suscripciones con:

1. **Agreements para suscripciones** - historial completo de cambios de plan
2. **Ledger para facturacion** - facturas inmutables, contabilidad apropiada
3. **Audit log para uso** - uso consultable en cualquier punto en el tiempo
4. **RBAC para funciones** - control de acceso desacoplado

Cuando los clientes preguntaban "Por que me cobraron $127.43?", ella podia mostrar:
- Plan base: $99.00
- Excedente de API (2,743 llamadas sobre el limite): $27.43
- Almacenamiento: incluido
- Total: $127.43

Cuando preguntaban "En que plan estaba cuando sucedio eso?", ella podia consultar:

```python
subscription_at_incident = Agreement.objects.filter(
    agreement_type="subscription",
    agreementparty__party=customer,
).as_of(incident_date).first()
```

Sin adivinar. Sin "creo que era." Solo hechos.

---

## Resumen

| Concepto del Dominio | Primitiva | Insight Clave |
|---------------------|-----------|---------------|
| Suscripcion | Agreement | Relacion con limites de tiempo, no un campo de estado |
| Plan | CatalogItem | Funciones y limites en metadata |
| Factura | Transaction | Entrada de libro mayor inmutable |
| Uso | AuditLog | Eventos consultables con filtros temporales |
| Acceso a funciones | RBAC | Roles sincronizados al plan de suscripcion |
| Cambio de plan | Nuevo Agreement | Historial preservado, no sobrescrito |

Las suscripciones son acuerdos. La facturacion son transacciones de libro mayor. El uso son eventos de auditoria. El acceso a funciones es RBAC.

Las mismas primitivas. Dominio de ingresos recurrentes.

---

## Fuentes

- Recurly. (2023). *State of Subscriptions Report*. https://recurly.com/research/state-of-subscriptions/
- Zuora. (2023). *Subscription Economy Index*. https://www.zuora.com/sei/
