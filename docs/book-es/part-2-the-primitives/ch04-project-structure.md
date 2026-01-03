# Capitulo 4: Estructura del Proyecto

Antes de sumergirnos en las primitivas, necesitas un lugar donde ponerlas.

Este interludio te muestra como estructurar un proyecto que usa django-primitives. Toma 10 minutos configurarlo y te ahorrara horas de confusion mas adelante.

---

## La Estructura del Monorepo

Todos los paquetes de django-primitives viven en un solo repositorio. Tu aplicacion tendra una estructura similar:

```
your-project/
├── packages/                      # Primitivas reutilizables
│   ├── django-basemodels/         # Fundacion (UUIDModel, BaseModel)
│   ├── django-parties/            # Identidad (Person, Organization)
│   ├── django-rbac/               # Control de acceso (Roles, Permissions)
│   ├── django-catalog/            # Productos y servicios
│   ├── django-ledger/             # Transacciones financieras
│   ├── django-encounters/         # Maquinas de estado de flujo de trabajo
│   ├── django-decisioning/        # Semantica temporal, decisiones
│   ├── django-audit-log/          # Registro de eventos inmutable
│   ├── django-agreements/         # Contratos y terminos
│   ├── django-documents/          # Adjuntos de archivos
│   ├── django-notes/              # Anotaciones de texto
│   ├── django-money/              # Manejo de divisas
│   └── django-sequence/           # IDs secuenciales
│
├── apps/                          # Tus aplicaciones de dominio
│   └── yourapp/                   # Compone primitivas
│       ├── models.py              # Vacio o minimo
│       ├── services.py            # Logica de negocio
│       ├── views.py               # Endpoints de API/UI
│       └── tests/                 # Pruebas de integracion
│
├── pyproject.toml                 # Configuracion del proyecto raiz
├── CLAUDE.md                      # Instrucciones para IA
└── layers.yaml                    # Reglas de limites de importacion
```

---

## Por Que Esta Estructura?

### 1. Las Primitivas Son Paquetes

Cada primitiva es un paquete instalable por separado:

```toml
# En el pyproject.toml de tu aplicacion
dependencies = [
    "django-basemodels",
    "django-parties",
    "django-catalog",
    "django-ledger",
]
```

Esto significa:
- Puedes actualizar primitivas independientemente
- Puedes usar primitivas en multiples proyectos
- Las dependencias son explicitas, no implicitas

### 2. Las Aplicaciones Componen, No Crean

El codigo de tu aplicacion (en `apps/`) debe:
- Importar desde paquetes
- Componer primitivas en flujos de trabajo de dominio
- Agregar servicios especificos del dominio

El codigo de tu aplicacion NO debe:
- Crear nuevos modelos de Django (con raras excepciones)
- Duplicar funcionalidad de los paquetes
- Modificar primitivas directamente

### 3. Los Limites de Capas Son Aplicados

El archivo `layers.yaml` define que puede importar que:

```yaml
# layers.yaml
layers:
  - name: infrastructure
    packages:
      - django_basemodels
      - django_singleton
      - django_sequence

  - name: foundation
    packages:
      - django_parties
      - django_rbac
    allowed_imports:
      - infrastructure

  - name: domain
    packages:
      - django_catalog
      - django_encounters
      - django_agreements
      - django_ledger
      - django_decisioning
      - django_documents
      - django_notes
      - django_money
      - django_audit_log
    allowed_imports:
      - infrastructure
      - foundation

  - name: application
    packages:
      - apps.*
    allowed_imports:
      - infrastructure
      - foundation
      - domain
```

Ejecuta `python -m django_layers check` para verificar que los limites no se violen.

---

## Estructura del Paquete

Cada paquete de primitiva sigue la misma estructura:

```
packages/django-parties/
├── pyproject.toml               # Metadatos del paquete
├── README.md                    # Documentacion de uso
├── src/
│   └── django_parties/
│       ├── __init__.py          # Exportaciones publicas
│       ├── apps.py              # Configuracion de la app Django
│       ├── models.py            # Modelos de Django
│       ├── services.py          # Funciones de servicio
│       ├── querysets.py         # Metodos de QuerySet personalizados
│       ├── mixins.py            # Mixins de modelo reutilizables
│       ├── exceptions.py        # Excepciones personalizadas
│       └── migrations/
│           ├── __init__.py
│           └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py              # Fixtures de Pytest
    ├── settings.py              # Configuracion de Django para pruebas
    ├── test_models.py           # Pruebas de modelos
    └── test_services.py         # Pruebas de servicios
```

### pyproject.toml

```toml
[project]
name = "django-parties"
version = "0.1.0"
description = "Primitivas de identidad para aplicaciones Django"
requires-python = ">=3.11"
dependencies = [
    "Django>=4.2",
    "django-basemodels",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-django>=4.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/django_parties"]
```

### __init__.py

Solo exportaciones explicitas:

```python
# src/django_parties/__init__.py

from django_parties.models import Party, Person, Organization, Group
from django_parties.services import create_person, create_organization

__all__ = [
    # Models
    "Party",
    "Person",
    "Organization",
    "Group",
    # Services
    "create_person",
    "create_organization",
]
```

### apps.py

Configuracion de la aplicacion Django:

```python
# src/django_parties/apps.py

from django.apps import AppConfig

class DjangoPartiesConfig(AppConfig):
    name = "django_parties"
    verbose_name = "Parties"
    default_auto_field = "django.db.models.UUIDField"
```

---

## Configurando Tu CLAUDE.md

El archivo `CLAUDE.md` en la raiz de tu proyecto le dice a los asistentes de IA como trabajar con tu base de codigo:

```markdown
# Proyecto: [Nombre de Tu Proyecto]

## Primitivas en Uso

Este proyecto usa django-primitives. Todos los modelos de dominio vienen de paquetes:
- django-parties (Person, Organization, Group, PartyRelationship)
- django-catalog (Category, CatalogItem, Basket, WorkItem)
- django-ledger (Account, Transaction, Entry)
- django-encounters (EncounterDefinition, Encounter, EncounterTransition)
- django-decisioning (Decision, IdempotencyKey)
- django-audit-log (AuditLog)
- django-agreements (Agreement, AgreementParty)

## Debe Hacer

- Usar claves primarias UUID para todos los modelos
- Usar DecimalField para dinero (nunca float)
- Heredar de UUIDModel o BaseModel
- Envolver mutaciones en @transaction.atomic
- Agregar semantica temporal (effective_at, recorded_at) a eventos
- Implementar eliminacion suave (deleted_at) para entidades de dominio

## No Debe Hacer

- Nunca crear nuevos modelos de Django (componer primitivas existentes)
- Nunca importar desde capas superiores
- Nunca usar claves primarias auto-incrementales
- Nunca eliminar registros de auditoria
- Nunca mutar transacciones publicadas

## Arquitectura

- Capa de aplicacion: apps/yourapp/
- Capa de dominio: packages/django-*
- Capa de fundacion: django-parties, django-rbac
- Capa de infraestructura: django-basemodels

## Comandos

- Ejecutar pruebas: `pytest`
- Verificar capas: `python -m django_layers check`
- Ejecutar servidor de desarrollo: `python manage.py runserver`
```

---

## Instalando Paquetes para Desarrollo

Durante el desarrollo, instala los paquetes en modo editable:

```bash
# Desde la raiz del proyecto
pip install -e packages/django-basemodels
pip install -e packages/django-parties
pip install -e packages/django-catalog
# ... etc
```

O usa un archivo de requirements:

```
# requirements-dev.txt
-e packages/django-basemodels
-e packages/django-parties
-e packages/django-catalog
-e packages/django-ledger
-e packages/django-encounters
-e packages/django-decisioning
-e packages/django-audit-log
-e packages/django-agreements
-e packages/django-documents
-e packages/django-notes
-e packages/django-money
-e packages/django-sequence
```

Luego:

```bash
pip install -r requirements-dev.txt
```

---

## Configuracion de Django

Tu configuracion de Django debe incluir todas las primitivas:

```python
# settings.py

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",

    # Primitivas (el orden importa para las migraciones)
    "django_basemodels",
    "django_parties",
    "django_rbac",
    "django_catalog",
    "django_ledger",
    "django_encounters",
    "django_decisioning",
    "django_audit_log",
    "django_agreements",
    "django_documents",
    "django_notes",
    "django_money",
    "django_sequence",

    # Tus aplicaciones
    "apps.yourapp",
]

# Configuracion del modelo de Party
PARTY_PERSON_MODEL = "django_parties.Person"
PARTY_ORGANIZATION_MODEL = "django_parties.Organization"
```

---

## Tu Primera Composicion

Asi es como se ve el codigo de tu aplicacion cuando compone primitivas:

```python
# apps/yourapp/services.py

from django.db import transaction
from django_parties.models import Person, Organization
from django_catalog.models import CatalogItem, Basket, BasketItem
from django_ledger.services import post_transaction
from django_agreements.models import Agreement
from django_audit_log.services import log_event

@transaction.atomic
def process_order(customer: Person, items: list, payment_method: str):
    """
    Procesa un pedido usando primitivas.

    Sin modelos nuevos. Solo composicion.
    """
    # Crear canasta (Catalog)
    basket = Basket.objects.create(
        owner=customer,
        status="draft",
    )

    for item_data in items:
        catalog_item = CatalogItem.objects.get(sku=item_data["sku"])
        BasketItem.objects.create(
            basket=basket,
            catalog_item=catalog_item,
            quantity=item_data["quantity"],
            unit_price_snapshot=catalog_item.unit_price,
        )

    # Confirmar canasta (dispara transaccion de libro mayor)
    basket.status = "committed"
    basket.save()

    # Crear acuerdo de venta (Agreements)
    agreement = Agreement.objects.create(
        agreement_type="sale",
        metadata={
            "basket_id": str(basket.id),
            "payment_method": payment_method,
        }
    )

    # Registrar el evento (Audit)
    log_event(
        target=agreement,
        event_type="order_placed",
        actor=customer,
        metadata={
            "item_count": basket.items.count(),
            "total": str(basket.total),
        }
    )

    return agreement
```

Observa:
- No se crean modelos nuevos
- Todos los objetos de dominio vienen de paquetes
- Los servicios componen primitivas
- El registro de auditoria es automatico

---

## Pruebas

Las pruebas viven en cada paquete:

```python
# packages/django-parties/tests/test_models.py

import pytest
from django_parties.models import Person

@pytest.mark.django_db
class TestPerson:
    def test_create_person(self):
        person = Person.objects.create(
            full_name="Jane Doe",
            email="jane@example.com",
        )

        assert person.id is not None
        assert person.full_name == "Jane Doe"

    def test_person_soft_delete(self):
        person = Person.objects.create(full_name="To Delete")
        person.soft_delete()

        assert person.deleted_at is not None
        assert Person.objects.active().count() == 0
```

Ejecutar todas las pruebas:

```bash
pytest
```

Ejecutar pruebas de un paquete:

```bash
pytest packages/django-parties/tests/
```

---

## Agregando un Nuevo Paquete

Cuando necesites una nueva primitiva (raro), sigue este patron:

**1. Crear la estructura del paquete:**

```bash
mkdir -p packages/django-newprimitive/src/django_newprimitive
mkdir -p packages/django-newprimitive/tests
```

**2. Copiar pyproject.toml y adaptar:**

```bash
cp packages/django-parties/pyproject.toml packages/django-newprimitive/
# Editar nombre, descripcion, dependencias
```

**3. Agregar a layers.yaml:**

```yaml
- name: domain
  packages:
    - django_newprimitive  # Agregar aqui
```

**4. Escribir pruebas primero (TDD):**

```python
# packages/django-newprimitive/tests/test_models.py

@pytest.mark.django_db
def test_new_model_creation():
    # Escribir prueba fallida primero
    pass
```

**5. Implementar la primitiva:**

```python
# packages/django-newprimitive/src/django_newprimitive/models.py

from django_basemodels.models import UUIDModel, BaseModel

class NewPrimitive(UUIDModel, BaseModel):
    # Implementacion
    pass
```

---

## Referencia Rapida

| Tarea | Comando |
|-------|---------|
| Ejecutar todas las pruebas | `pytest` |
| Ejecutar pruebas de paquete | `pytest packages/django-parties/` |
| Verificar limites de capas | `python -m django_layers check` |
| Crear migraciones | `python manage.py makemigrations` |
| Aplicar migraciones | `python manage.py migrate` |
| Instalar paquete (dev) | `pip install -e packages/django-xxx` |

---

## Resumen

| Concepto | Proposito |
|----------|-----------|
| Monorepo | Todas las primitivas en un repositorio |
| Paquetes | Componentes reutilizables e instalables |
| Aplicaciones | Componen primitivas, agregan logica de dominio |
| layers.yaml | Aplica limites de importacion |
| CLAUDE.md | Instrucciones de IA para tu proyecto |
| TDD | Pruebas primero para todas las primitivas |

Con esta estructura en su lugar, estas listo para aprender las primitivas mismas. El Capitulo 5 cubre la Capa de Fundacion, seguido del Capitulo 6: Identidad—la primitiva de dominio mas fundamental.
