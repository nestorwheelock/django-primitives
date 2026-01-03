# Capitulo 9: Catalogo

> "Antes de poder venderlo, tienes que saber que es."
>
> — Sabiduria del retail

---

El catalogo de Sears, Roebuck and Company de 1888 tenia 322 paginas. Para 1908, habia crecido a mas de 1,000 paginas y pesaba cuatro libras. Se le llamaba "el libro de los deseos" porque los estadounidenses rurales pasaban sus paginas sonando con lo que podrian pedir.

Cada articulo en ese catalogo tenia un numero, una descripcion, un precio y un estado de disponibilidad. Podias pedir el articulo #31C457 y saber exactamente lo que recibirias: un traje de lana peinada para hombre, negro, tallas 34-46, $12.50, se envia en 6-8 semanas.

Esto no era accidental. Sears entendia que el comercio requiere un vocabulario compartido entre comprador y vendedor. El catalogo define lo que puede comprarse. Sin el, cada transaccion se convierte en una negociacion.

## La Primitiva

**Catalogo** responde: Que cosas existen en este sistema que pueden pedirse, programarse o rastrearse?

Esto es distinto del inventario (cuantos tenemos?), precios (cuanto cuesta?) y flujo de trabajo (que pasa despues de ordenar?). El catalogo es pura definicion: una lista de cosas que existen como conceptos abstractos, independientes de cualquier transaccion particular.

El catalogo de una clinica veterinaria incluye examenes de bienestar, paneles de sangre, vacunas y cortes de unas. El catalogo de una pizzeria incluye pizza grande de pepperoni, pizza mediana de queso y pan de ajo. El catalogo de un servicio de suscripcion incluye planes mensuales, planes anuales y funciones adicionales.

El catalogo no sabe quien esta ordenando. No sabe cuando. No sabe cuantos hay en stock. Solo sabe que cosas estan disponibles para ser ordenadas.

## Separacion de Definicion de Instancia

El primer principio del diseno de catalogo: las definiciones no son instancias.

Una "Pizza Grande de Pepperoni" en el catalogo no es lo mismo que la Pizza Grande de Pepperoni que el cliente #4523 ordeno el 15 de marzo a las 7:42 PM. El articulo del catalogo es una plantilla. La linea de pedido es una instancia.

Esta separacion importa por varias razones:

**Los precios cambian.** Una pizza que costaba $18.99 cuando se imprimio el catalogo podria costar $19.99 ahora. Pero el pedido del 15 de marzo aun deberia mostrar $18.99—eso es lo que el cliente acordo pagar. Si tu articulo de catalogo y linea de pedido son el mismo registro, no puedes preservar este historial.

**Los articulos se retiran.** Una clinica descontinua una vacuna particular. El articulo del catalogo se marca como inactivo. Pero los registros historicos que referencian esa vacuna deben permanecer validos. El expediente del paciente aun deberia mostrar que la recibio.

**La disponibilidad varia.** Una firma de consultoria ofrece un "Taller de Planificacion Estrategica." Esta en el catalogo permanentemente, pero solo podria estar disponible en Q3 y Q4. El catalogo define el servicio; la disponibilidad es una preocupacion separada.

**Las configuraciones difieren.** Una "Pizza Grande" es un articulo de catalogo. "Pizza Grande con mitad pepperoni, mitad champiñones, extra queso, salsa ligera" es una instancia con configuracion especifica. El catalogo define lo que es configurable; la instancia captura las elecciones.

```python
class CatalogItem(UUIDModel, BaseModel):
    # Quien ofrece este articulo
    owner_content_type = models.ForeignKey(ContentType, on_delete=CASCADE)
    owner_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    # Que es
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True)  # SKU, codigo de articulo
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)

    # Precio (referencia, no el precio congelado)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')

    # Disponibilidad
    is_available = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_to = models.DateTimeField(null=True, blank=True)

    # Metadatos flexibles
    metadata = models.JSONField(default=dict)
```

Nota el GenericForeignKey para owner. Un articulo de catalogo podria ser ofrecido por un restaurante, una clinica, un proveedor o un departamento. La primitiva de catalogo no asume ningun tipo de party particular.

## La Canasta: Transacciones en Progreso

Entre navegar el catalogo y completar una compra hay un estado transicional: articulos recolectados pero aun no confirmados. Esta es la canasta (tambien llamada carrito, pedido o borrador).

La canasta no es una mera conveniencia de UI. Es un estado critico en el ciclo de vida de la transaccion:

**Estado borrador.** Los articulos pueden agregarse, eliminarse o modificarse. Las cantidades pueden cambiar. La canasta es mutable.

**Estado confirmado.** El cliente confirma su intencion. La canasta se vuelve inmutable. Los precios se congelan. El trabajo se genera. Este es el punto sin retorno.

**Estado cancelado.** El cliente abandona la canasta. No se genera trabajo. La canasta podria retenerse para analitica pero no tiene significado operacional.

```python
class BasketStatus(models.TextChoices):
    DRAFT = 'draft', 'Borrador'
    COMMITTED = 'committed', 'Confirmado'
    CANCELLED = 'cancelled', 'Cancelado'


class Basket(UUIDModel, BaseModel):
    # Para que es esta canasta
    context_content_type = models.ForeignKey(ContentType, null=True, blank=True)
    context_id = models.CharField(max_length=255, blank=True)
    context = GenericForeignKey('context_content_type', 'context_id')

    # Estado
    status = models.CharField(max_length=20, choices=BasketStatus.choices, default=BasketStatus.DRAFT)

    # Superficie de decision
    committed_at = models.DateTimeField(null=True, blank=True)
    committed_by = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)

    # Idempotencia
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
```

El idempotency_key es critico. Cuando un cliente hace doble clic en el boton "Realizar Pedido", necesitas asegurar que solo se cree un pedido. La clave de idempotencia—tipicamente derivada de la sesion o envio del formulario—asegura que solicitudes duplicadas retornen la canasta existente en lugar de crear nuevas.

## El Principio de Instantanea

Cuando un articulo se agrega a una canasta, el precio en ese momento se captura:

```python
class BasketItem(UUIDModel, BaseModel):
    basket = models.ForeignKey(Basket, on_delete=CASCADE, related_name='items')
    catalog_item = models.ForeignKey(CatalogItem, on_delete=PROTECT)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    # Instantanea de precio - congelado al momento de agregar
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')

    # Configuracion y notas
    instructions = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
```

El `unit_price` aqui es una instantanea, no una referencia. Cuando el precio del catalogo cambia, los articulos de canasta existentes retienen su precio original. Cuando la canasta se confirma, el precio se bloquea para siempre.

Esto resuelve varios problemas:

- **Disputas de precio:** "Lo agregue cuando estaba a $15!" Si, y tenemos la instantanea para probarlo.
- **Precios promocionales:** Las ventas flash afectan articulos agregados durante la venta, no antes ni despues.
- **Transacciones de multiples dias:** Pedidos empresariales que toman semanas en finalizarse mantienen precios consistentes a lo largo del proceso.

El campo `metadata` captura configuracion que el catalogo no conoce. Un articulo de canasta de pizza podria incluir `{"half_toppings": ["pepperoni", "mushroom"], "extra_cheese": true}`. Esta configuracion es especifica de la instancia.

## Generacion de Trabajo

Cuando una canasta se confirma, el trabajo comienza. Aqui es donde el catalogo se conecta con la primitiva de flujo de trabajo.

Un pedido de pizza genera trabajo para la cocina. Un pedido de prueba de laboratorio genera trabajo para el flebotomista. Un pedido de suscripcion genera trabajo para el sistema de aprovisionamiento.

```python
class WorkItem(UUIDModel, BaseModel):
    basket_item = models.ForeignKey(BasketItem, on_delete=CASCADE, related_name='work_items')

    work_type = models.CharField(max_length=100)
    spawn_role = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=WorkItemStatus.choices, default='pending')

    assigned_to = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    priority = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['basket_item', 'spawn_role'],
                name='unique_basket_item_spawn_role'
            )
        ]
```

La restriccion unica en `(basket_item, spawn_role)` es crucial. Si la operacion de confirmacion se reintenta (debido a falla de red, doble clic del usuario o reinicio del sistema), no debe crear articulos de trabajo duplicados. La restriccion aplica idempotencia a nivel de base de datos.

La operacion de confirmacion misma se envuelve en una transaccion:

```python
@transaction.atomic
def commit_basket(basket, committed_by, work_types=None):
    basket.refresh_from_db()  # Obtener estado mas reciente

    if basket.is_committed:
        return basket  # Ya confirmada, retornar como esta (idempotente)

    if basket.total_items == 0:
        raise BasketEmptyError(basket.pk)

    basket.status = BasketStatus.COMMITTED
    basket.committed_at = timezone.now()
    basket.committed_by = committed_by
    basket.save()

    # Generar articulos de trabajo
    if work_types:
        for item in basket.items.all():
            for work_type in work_types:
                WorkItem.objects.get_or_create(
                    basket_item=item,
                    spawn_role=work_type,
                    defaults={'work_type': work_type, 'status': 'pending'}
                )

    return basket
```

La llamada `get_or_create`, combinada con la restriccion unica, asegura que llamar `commit_basket` dos veces produzca resultados identicos. Este es el patron de idempotencia en accion.

## Dispensacion y Cumplimiento

Algunos articulos de canasta representan bienes fisicos que deben dispensarse. Medicamentos, suministros, productos—cosas que se cuentan y rastrean.

```python
class DispenseLog(UUIDModel, BaseModel):
    basket_item = models.ForeignKey(BasketItem, on_delete=CASCADE, related_name='dispense_logs')

    quantity_dispensed = models.DecimalField(max_digits=10, decimal_places=2)

    dispensed_by = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)
    dispensed_at = models.DateTimeField(default=timezone.now)

    # Rastreo de lote
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
```

El DispenseLog es solo de agregacion. Cada evento de dispensacion crea un nuevo registro. Puedes consultar el total dispensado sumando los logs:

```python
total_dispensed = basket_item.dispense_logs.aggregate(
    total=Sum('quantity_dispensed')
)['total'] or 0
```

Este patron maneja dispensacion parcial (10 tabletas ordenadas, 5 dispensadas hoy, 5 manana), sobrellenado (el cliente recibio 12 en lugar de 10, registrado para precision), y rastreo de lotes (la FDA requiere saber que numero de lote se dispenso a que paciente).

## Estructura del Paquete

La primitiva de catalogo, como todos los paquetes de django-primitives, sigue una estructura consistente. Esto no es solo organizacion—es un contrato que habilita reproducibilidad.

```
packages/django-catalog/
├── pyproject.toml           # Metadatos del paquete y dependencias
├── README.md                # Documentacion de uso
├── src/
│   └── django_catalog/
│       ├── __init__.py      # Exporta API publica
│       ├── apps.py          # Configuracion de app Django
│       ├── models.py        # CatalogItem, Basket, BasketItem, WorkItem, DispenseLog
│       ├── services.py      # create_basket, add_item, commit_basket, cancel_basket
│       ├── exceptions.py    # BasketAlreadyCommittedError, BasketEmptyError, etc.
│       └── migrations/
│           └── 0001_initial.py
└── tests/
    ├── conftest.py          # Fixtures de Pytest
    ├── settings.py          # Configuracion de Django para pruebas
    ├── models.py            # Modelos de prueba (Organization, etc.)
    ├── test_models.py       # Pruebas de modelos
    └── test_services.py     # Pruebas de funciones de servicio
```

Esta estructura se replica en los 18 paquetes. Cuando entiendes uno, los entiendes todos.

## Practica: Construyendo un Catalogo con IA

### Ejercicio 1: Catalogo Sin Restricciones

Pide a una IA:

```
Construye un sistema de e-commerce Django con productos y carrito de compras.
Incluye funcionalidad de agregar al carrito y checkout.
```

Examina el resultado. Tipicamente:

- Productos y articulos del carrito estan estrechamente acoplados
- Sin instantanea de precio al momento de agregar
- El checkout modifica el carrito en lugar de confirmarlo
- Sin proteccion de idempotencia
- Sin concepto de generacion de trabajo
- Toda la logica de negocio en vistas

Esto funciona para un tutorial pero falla en produccion.

### Ejercicio 2: Catalogo Restringido

Ahora pide con restricciones explicitas:

```
Construye un sistema de catalogo y canasta Django usando estas restricciones:

1. Modelo CatalogItem con GenericFK owner
   - name, code, description, category
   - unit_price como DecimalField, currency como CharField(3)
   - is_available, available_from, available_to
   - metadata como JSONField

2. Modelo Basket con flujo de trabajo de estado
   - status: draft → committed O cancelled
   - committed_at, committed_by para superficie de decision
   - idempotency_key (unique, nullable) para prevencion de duplicados
   - context via GenericFK (para que es esta canasta)

3. Modelo BasketItem con instantanea de precio
   - FK a Basket y CatalogItem
   - unit_price capturado AL MOMENTO DE AGREGAR (instantanea, no referencia)
   - quantity como DecimalField
   - instructions y metadata para configuracion

4. Modelo WorkItem con restriccion unica
   - FK a BasketItem
   - work_type, spawn_role
   - status: pending → in_progress → completed
   - UniqueConstraint en (basket_item, spawn_role) para idempotencia

5. Funciones de servicio:
   - create_basket(context, idempotency_key) - creacion idempotente
   - add_item(basket, catalog_item, quantity) - toma instantanea de precio
   - commit_basket(basket, committed_by, work_types) - atomico, idempotente
   - cancel_basket(basket) - solo funciona en borrador

6. Excepciones:
   - BasketAlreadyCommittedError - lanzada en modificacion despues de confirmar
   - BasketEmptyError - lanzada al confirmar sin articulos
   - ItemNotAvailableError - lanzada al agregar articulo no disponible

Escribe pruebas primero usando TDD. Minimo 50 pruebas cubriendo modelos y servicios.
```

Las restricciones fuerzan implementacion correcta de instantaneas, idempotencia y generacion de trabajo.

### Ejercicio 3: Flujo de Pedido de Clinica

Prueba el patron con un escenario del mundo real:

```
Usando las primitivas de catalogo, implementa un flujo de pedido de clinica veterinaria:

Escenario: Un paciente (mascota) visita para un examen de bienestar. El veterinario ordena:
- 1x Examen de Bienestar ($75)
- 1x Vacuna de Rabia ($25)
- 1x Prueba de Dirofilaria ($45)

Implementa:
1. Crear articulos de catalogo para la clinica (owner = organizacion clinica)
2. Crear una canasta para la visita del paciente (context = encuentro)
3. Agregar articulos a la canasta con instantaneas de precio
4. Confirmar canasta, generando articulos de trabajo para:
   - rol "perform" (veterinario realiza examen/procedimientos)
   - rol "dispense" (tecnico dispensa vacuna)
   - rol "lab" (laboratorio procesa prueba de dirofilaria)

Escribe pruebas verificando:
- Articulos de catalogo se crean con owner correcto
- Articulos de canasta toman instantanea de precios al momento de agregar
- Confirmar crea exactamente 3 articulos de trabajo por articulo de canasta (9 total)
- Llamar confirmar dos veces retorna la misma canasta (idempotente)
- Articulos de trabajo tienen roles y estados correctos
- Valor total de canasta se calcula correctamente
```

Este ejercicio integra el catalogo con identidad (parties), tiempo (timestamps) y flujo de trabajo (articulos de trabajo).

## El Contrato de Prompt para Catalogo

Incluye estas restricciones cuando trabajes con codigo relacionado a catalogo:

```markdown
## Restricciones de Primitiva de Catalogo

### Debe Hacer
- CatalogItem tiene GenericFK owner (no hardcodeado a User/Organization)
- BasketItem toma instantanea de unit_price al momento de agregar (no referencia a catalogo)
- Basket tiene flujo de trabajo de estado: draft → committed O cancelled
- commit_basket es atomico e idempotente
- WorkItem tiene UniqueConstraint en (basket_item, spawn_role)
- Todos los precios usan DecimalField, nunca Float

### No Debe
- Nunca modificar canastas confirmadas (lanzar BasketAlreadyCommittedError)
- Nunca eliminar articulos de canasta (cancelar canasta en su lugar)
- Nunca referenciar precio de catalogo despues de agregar a canasta
- Nunca generar articulos de trabajo duplicados (usar get_or_create con restriccion unica)
- Nunca poner logica de flujo de trabajo en modelo CatalogItem

### Invariantes
- CatalogItem define lo que puede ordenarse (plantilla)
- BasketItem es lo que realmente se ordeno (instancia)
- Los precios se congelan al crear BasketItem (instantanea)
- La confirmacion de Basket es irreversible (historial solo de agregacion)
- Los articulos de trabajo existen solo para canastas confirmadas
```

## Lo Que la IA Hace Mal

Sin restricciones explicitas, el codigo de catalogo generado por IA tipicamente:

1. **Referencia precios en vivo** — El carrito enlaza a productos y lee current_price. Los cambios de precio afectan carritos viejos.

2. **Usa checkout mutable** — El boton "checkout" actualiza un campo de estado. El carrito puede modificarse despues del checkout en algunos casos extremos.

3. **Ignora idempotencia** — Hacer doble clic en "Realizar Pedido" crea pedidos duplicados.

4. **Hardcodea tipos de party** — Los productos pertenecen a "la tienda" implicitamente. Sin soporte para escenarios multi-proveedor.

5. **Mezcla definicion e instancia** — Las variantes de producto son productos separados en lugar de configuracion en articulos de canasta.

6. **Carece de generacion de trabajo** — La finalizacion del pedido no dispara ningun proceso de backend. El cumplimiento es un sistema separado, desconectado.

La solucion es restricciones explicitas. Define el patron, y la IA lo sigue.

## Por Que Esto Importa Despues

La primitiva de catalogo es el motor de transacciones:

- **Libro Mayor**: Cada confirmacion de canasta deberia crear asientos de libro mayor—reconocimiento de ingresos cuando se prestan servicios.

- **Acuerdos**: Acuerdos especiales de precios (descuentos, tarifas de contrato) afectan como se computan y toman instantaneas de precios.

- **Flujos de trabajo**: Los articulos de trabajo generados desde canastas impulsan la maquina de estado de encuentros.

- **Auditoria**: Cada confirmacion de canasta es una decision que deberia registrarse con contexto completo.

Si manejas mal el catalogo, las transacciones se vuelven caoticas. Si lo manejas bien, tienes una fundacion solida para cualquier sistema donde las cosas se ordenan, programan o cumplen.

---

## Como Reconstruir Esta Primitiva

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-catalog | `docs/prompts/django-catalog.md` | ~60 tests |

### Usando el Prompt

```bash
cat docs/prompts/django-catalog.md | claude

# Solicitud: "Comienza con los modelos CatalogItem y Category,
# luego implementa Basket con commit() para bloqueo de precios."
```

### Restricciones Clave

- **Instantaneas de precio en BasketItem**: `unit_price_snapshot` captura precio al momento de agregar
- **Basket.commit() bloquea todo**: Las canastas confirmadas son inmutables
- **Generacion de trabajo**: Las canastas confirmadas pueden generar articulos de trabajo
- **Operaciones idempotentes**: Agregar-al-carrito maneja duplicados elegantemente

Si Claude almacena precios solo en CatalogItem sin tomar instantanea a BasketItem, eso es una violacion de restriccion.

---

## Fuentes y Referencias

1. **Historia del Catalogo Sears** — "Sears, Roebuck & Co. Catalogs," Museo Nacional de Historia Estadounidense, Institucion Smithsonian. El "libro grande" de 1908 excedio 1,000 paginas.

2. **Idempotencia en Sistemas Distribuidos** — Helland, Pat. "Idempotence Is Not a Medical Condition," *ACM Queue*, abril 2012. Paper fundamental sobre operaciones idempotentes.

3. **Propiedades ACID** — Haerder, T. y Reuter, A. "Principles of Transaction-Oriented Database Recovery," *ACM Computing Surveys*, diciembre 1983. La garantia de atomicidad subyacente a commit_basket.

4. **Requisitos de Rastreo de Lotes de la FDA** — 21 CFR Part 820.65 requiere trazabilidad de componentes y productos. DispenseLog implementa este patron para productos regulados.

---

*Estado: Completo*
