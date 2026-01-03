# Capitulo 8: Acuerdos

> "La tinta mas palida es mejor que la mejor memoria."
>
> — Proverbio chino

---

Toda transaccion de negocio descansa sobre un acuerdo. Alguien prometio algo a alguien mas, bajo terminos especificos, por un periodo especifico. Cuando surgen disputas—y siempre surgen—la pregunta siempre es la misma: Que se acordo?

Los sistemas que tratan los acuerdos como algo secundario, o peor, como configuracion estatica, eventualmente enfrentan un ajuste de cuentas. Los clientes afirman que se les prometieron terminos diferentes. Los socios insisten en que el contrato decia otra cosa. Los auditores piden prueba de lo que se acordo al momento de la transaccion, no lo que dicen los terminos actuales.

El problema no es que los acuerdos sean complejos. Es que la mayoria de los sistemas los tratan como documentos inmutables en lugar de estructuras de datos vivas y versionadas que evolucionan con el tiempo mientras preservan su historial completo.

## La Primitiva Mas Antigua

Los acuerdos preceden a la escritura. El apreton de manos. El contrato verbal. El juramento presenciado. Pero los primeros registros de negocios escritos son contratos. El Codigo de Hammurabi, tallado en piedra alrededor de 1754 AEC, es en gran parte una codificacion de la ley de contratos: que pasa cuando las partes no cumplen con sus obligaciones.

Luca Pacioli, documentando la contabilidad de partida doble en 1494, asumia los acuerdos como fundamentales. No puedes registrar una venta sin un acuerdo sobre el precio. No puedes registrar una deuda sin un acuerdo sobre los terminos de pago. El libro mayor es un registro de obligaciones cumplidas; los acuerdos definen cuales son esas obligaciones.

Todo sistema ERP, todo sistema de gestion de pedidos, todo servicio de suscripcion es fundamentalmente una maquina para gestionar acuerdos. Sin embargo, la mayoria de los sistemas entierran esta primitiva bajo capas de terminologia especifica del dominio—"pedidos," "contratos," "suscripciones," "polizas"—perdiendo el patron subyacente.

## Los Modos de Falla

### Terminos como Prosa

El error mas comun es almacenar terminos de acuerdos como texto libre. Un contrato se sube como PDF. Los terminos y condiciones se almacenan en un campo de texto. La descripcion de la suscripcion vive en una base de datos de marketing.

Esto funciona hasta que necesitas computar con los terminos. Cual es la politica de cancelacion? Cuantos dias de aviso se requieren para un cambio de precio? Cual es la penalidad por terminacion anticipada? Si la respuesta requiere que un humano lea un documento y lo interprete, no tienes datos—tienes literatura.

En 2019, Disney adquirio 21st Century Fox por $71.3 mil millones. Parte de la integracion involucro reconciliar miles de acuerdos de licencia de contenido, muchos de los cuales existian solo como PDFs escaneados con terminologia inconsistente. El Wall Street Journal reporto que Disney paso meses y recursos significativos simplemente catalogando que derechos habian adquirido y bajo que terminos.

Los terminos que no pueden consultarse no pueden aplicarse programaticamente. Cada decision se convierte en un proceso manual, cada renovacion se convierte en un proyecto de investigacion, y cada disputa se convierte en arqueologia.

### El Problema del Historial que Desaparece

La mayoria de los sistemas sobrescriben los terminos de acuerdos cuando cambian. El plan de suscripcion de un cliente cambia de Basico a Pro. El sistema actualiza un campo. Los terminos viejos desaparecen.

Luego el cliente disputa un cargo de hace dos meses. En que plan estaban? Cual era el precio? Que caracteristicas estaban incluidas? Si tu sistema solo almacena estado actual, estas adivinando.

Este problema se compone en relaciones B2B donde los contratos son negociados, enmendados y extendidos a lo largo de anos. Un proveedor podria afirmar que un termino de pago de 30 dias fue siempre el acuerdo; tu sistema muestra 15 dias pero no tiene registro de cuando cambio eso o quien lo acordo.

El principio legal es claro: los acuerdos son vinculantes basados en lo que se acordo en el momento, no lo que dicen los terminos actuales. Los sistemas que no pueden reconstruir terminos historicos fallan en este requisito basico.

### El Problema de "Quien Acordo?"

Un vendedor ofrece a un cliente un descuento especial. El cliente acepta. Un ano despues, cuando el descuento expira y al cliente se le cobra precio completo, se quejan.

Quien autorizo ese descuento? Cuando? Estaba dentro de su autoridad? Hay algun registro de la aceptacion del cliente?

Sin rastreo explicito de firmantes, estas preguntas son irrespondibles. El acuerdo existe como un hecho en el sistema, pero el rastro de decisiones esta ausente. No puedes probar quien acordo que, o cuando, o con que autoridad.

Sarbanes-Oxley, entre otras regulaciones, requiere que las empresas mantengan registros de quien autorizo transacciones significativas. Un acuerdo sin una superficie de decision—quien hizo este acuerdo, con que autoridad, con que evidencia—es una responsabilidad de cumplimiento.

## Las Dos Partes, Siempre

Todo acuerdo tiene al menos dos partes. Esto parece obvio, pero muchos sistemas fallan en modelarlo correctamente.

Considera un servicio de suscripcion. El modelo ingenuo: un User tiene un campo subscription_plan. Pero esto oculta el acuerdo. Con quien es la suscripcion? La empresa que ofrece el servicio es una parte del acuerdo. Tambien lo es el cliente. El acuerdo existe entre ellos.

Por que importa esto? Porque las partes tienen diferentes derechos y obligaciones. El proveedor del servicio acuerda proporcionar acceso. El cliente acuerda pagar. Los terminos definen que pasa si alguna de las partes no cumple.

Cuando modelas al proveedor del servicio como implicito—solo "el sistema"—pierdes la capacidad de manejar escenarios multi-proveedor, relaciones de revendedor, o adquisiciones donde la parte proveedora cambia.

```python
from django_basemodels import BaseModel
from django.db.models import Q, F

class Agreement(BaseModel):
    """Acuerdo entre dos partes. Hereda UUID, timestamps, eliminacion suave."""

    # Ambas partes son explicitas
    party_a_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    party_a_id = models.CharField(max_length=255)
    party_a = GenericForeignKey('party_a_content_type', 'party_a_id')

    party_b_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    party_b_id = models.CharField(max_length=255)
    party_b = GenericForeignKey('party_b_content_type', 'party_b_id')

    # Los terminos son datos estructurados, no prosa
    terms = models.JSONField()

    # Periodo de validez - valid_from NO tiene DEFAULT (el servicio lo proporciona)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)

    # Contador de version - sincronizado por la capa de servicio
    current_version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            # Django 6.0+: usar 'condition', no 'check'
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')),
                name='agreements_valid_to_after_valid_from'
            ),
        ]
```

El patron GenericForeignKey permite que cualquiera de las partes sea cualquier modelo: una Person, una Organization, o cualquier otra entidad. Esta flexibilidad maneja el espectro completo de acuerdos desde suscripciones de consumidor hasta contratos empresariales y consorcios multipartitos.

## Terminos como Datos

La decision de diseno critica es almacenar terminos como datos estructurados, no prosa.

Compara:

**Version prosa:**
```
"El cliente acuerda pagar $49.99 por mes por el plan Pro,
facturado el 15 de cada mes. El servicio incluye llamadas
API ilimitadas y soporte 24/7. Cualquiera de las partes puede terminar con
30 dias de aviso por escrito."
```

**Version datos:**
```json
{
  "plan": "pro",
  "price_cents": 4999,
  "currency": "USD",
  "billing_cycle": "monthly",
  "billing_day": 15,
  "features": ["unlimited_api", "24_7_support"],
  "termination_notice_days": 30
}
```

La version de datos puede computarse. Puedes consultar todos los acuerdos con `termination_notice_days < 30`. Puedes calcular ingresos mensuales totales sumando `price_cents`. Puedes enviar avisos automaticamente basados en `termination_notice_days`.

La version prosa requiere interpretacion humana para cada operacion.

Esto no significa que eliminas la prosa completamente. Los acuerdos legales a menudo requieren texto legible por humanos para ejecutabilidad. Pero los terminos autoritativos—aquellos sobre los que el sistema actua—deben ser datos estructurados. La prosa es documentacion; el JSON es verdad.

## El Patron Proyeccion + Libro Mayor

Los acuerdos usan un patron que aparece a lo largo del software de negocios: **proyeccion + libro mayor**.

- **Agreement** almacena estado actual (la proyeccion). Su campo `terms` refleja los terminos mas recientes. Su campo `current_version` te dice cuantas enmiendas han ocurrido.

- **AgreementVersion** almacena historial inmutable (el libro mayor). Cada enmienda crea un nuevo registro de version. Estos registros nunca se modifican despues de crearse.

Cuando los terminos de un acuerdo cambian, no editas el acuerdo. Creas una nueva version y actualizas la proyeccion.

```python
class AgreementVersion(BaseModel):
    """Historial de versiones inmutable. Nunca se modifica despues de crearse."""

    agreement = models.ForeignKey(Agreement, on_delete=CASCADE, related_name='versions')
    version = models.PositiveIntegerField()
    terms = models.JSONField()
    created_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)
    reason = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['agreement', 'version'],
                name='unique_agreement_version'
            ),
        ]
        ordering = ['-version']
```

**El invariante:** `Agreement.current_version == max(AgreementVersion.version)`

Este invariante es mantenido por la capa de servicio, no el modelo. Mas sobre eso en breve.

Ahora tienes historial completo. La version 1 es el acuerdo original. La version 2 es la primera enmienda. La version 3 es la segunda. Cada version captura:

- Cuales eran los terminos
- Cuando se hizo el cambio (via `created_at` de BaseModel)
- Quien lo autorizo
- Por que se cambio

Para responder "Cuales eran los terminos el 15 de marzo?", consultas la version mas reciente donde `created_at <= 15 de marzo`. La respuesta es inequivoca y auditable.

Este patron tambien soporta rollbacks. Si una enmienda se hizo por error, creas una nueva version que restaura los terminos anteriores. La version erronea permanece en el historial—nunca destruyes datos—pero los terminos efectivos actuales son correctos.

## La Superficie de Decision

Todo acuerdo representa una decision. Alguien lo autorizo. Esa decision debe registrarse.

```python
class Agreement(models.Model):
    # ... campos de party ...

    # Superficie de decision
    agreed_at = models.DateTimeField()  # Cuando se hizo el acuerdo
    agreed_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)  # Quien lo autorizo

    # Validez
    valid_from = models.DateTimeField()  # Cuando toman efecto los terminos
    valid_to = models.DateTimeField(null=True, blank=True)  # Cuando expiran los terminos
```

Nota la distincion entre `agreed_at` y `valid_from`. Un acuerdo podria firmarse en diciembre pero tomar efecto en enero. La decision sucedio en `agreed_at`; los terminos aplican desde `valid_from`.

Para acuerdos complejos que requieren multiples firmantes—como contratos de sociedad o acuerdos de licencia multipartitos—extiendes esto con un modelo Signatory:

```python
class Signatory(models.Model):
    agreement_version = models.ForeignKey(AgreementVersion, on_delete=CASCADE)
    party = GenericForeignKey()
    signed_at = models.DateTimeField()
    signature_metadata = models.JSONField()  # Direccion IP, dispositivo, metodo
```

Ahora puedes rastrear exactamente quien firmo que version de que acuerdo, cuando y como.

## Consultas Temporales

Los campos `valid_from` y `valid_to` habilitan consultas temporales esenciales para operaciones de negocio.

**Acuerdos actuales:**
```python
Agreement.objects.filter(
    valid_from__lte=now(),
).filter(
    Q(valid_to__isnull=True) | Q(valid_to__gt=now())
)
```

**Acuerdos validos en una fecha especifica:**
```python
Agreement.objects.as_of(specific_date)
```

**Acuerdos para una parte especifica:**
```python
Agreement.objects.for_party(customer)
```

Estas consultas son fundamentales para:

- Facturacion: Que acuerdos estan activos este ciclo de facturacion?
- Cumplimiento: Que terminos aplicaban cuando ocurrio esta transaccion?
- Renovaciones: Que acuerdos expiran en los proximos 30 dias?
- Disputas: A que acordo el cliente al momento de este evento?

Un `valid_to` nullable significa "hasta nuevo aviso"—el acuerdo continua indefinidamente hasta que se termina explicitamente. Esto maneja suscripciones mes a mes y contratos evergreen.

## Alcance y Contexto

Los acuerdos a menudo se relacionan con algo mas—un pedido, un servicio, un activo. El campo scope captura esto:

```python
class Agreement(models.Model):
    # ... otros campos ...

    scope_type = models.CharField(max_length=50)  # 'order', 'subscription', 'consent'
    scope_ref_content_type = models.ForeignKey(ContentType, null=True, blank=True)
    scope_ref_id = models.CharField(max_length=255, blank=True)
    scope_ref = GenericForeignKey('scope_ref_content_type', 'scope_ref_id')
```

Esto permite que los acuerdos se vinculen a cualquier objeto de dominio:

- Un acuerdo de nivel de servicio (SLA) vinculado a un contrato de soporte
- Terminos de venta vinculados a un pedido especifico
- Consentimiento para procesamiento de datos vinculado a una cuenta de usuario
- Una garantia vinculada a un producto comprado

El `scope_type` proporciona un filtro rapido sin requerir un join, mientras que `scope_ref` proporciona el vinculo completo.

## La Capa de Servicio

Los modelos definen estructura. Los servicios aplican reglas de negocio.

Para acuerdos, la capa de servicio mantiene el invariante de proyeccion + libro mayor y proporciona operaciones atomicas:

```python
# services.py
from django.db import transaction
from django.utils import timezone

class AgreementError(Exception):
    """Excepcion base para operaciones de acuerdos."""
    pass

class InvalidTerminationError(AgreementError):
    """Se lanza cuando la fecha de terminacion es invalida."""
    pass


def create_agreement(
    party_a,
    party_b,
    scope_type,
    terms,
    agreed_by,
    valid_from=None,  # Default conveniente
    agreed_at=None,
    valid_to=None,
    scope_ref=None,
):
    """Crea acuerdo con version inicial."""
    if valid_from is None:
        valid_from = timezone.now()
    if agreed_at is None:
        agreed_at = timezone.now()

    # Validar fechas
    if valid_to and valid_to <= valid_from:
        raise AgreementError("valid_to debe ser posterior a valid_from")

    with transaction.atomic():
        agreement = Agreement.objects.create(
            party_a=party_a,
            party_b=party_b,
            scope_type=scope_type,
            terms=terms,
            agreed_by=agreed_by,
            agreed_at=agreed_at,
            valid_from=valid_from,
            valid_to=valid_to,
            scope_ref=scope_ref,
            current_version=1,
        )

        AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms=terms,
            created_by=agreed_by,
            reason="Acuerdo inicial",
        )

    return agreement


def amend_agreement(agreement, new_terms, reason, amended_by):
    """Enmienda terminos del acuerdo, creando nueva version."""
    with transaction.atomic():
        # Bloquea la fila para incremento seguro de version
        agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

        new_version = agreement.current_version + 1

        # Crea entrada de libro mayor (inmutable)
        AgreementVersion.objects.create(
            agreement=agreement,
            version=new_version,
            terms=new_terms,
            created_by=amended_by,
            reason=reason,
        )

        # Actualiza proyeccion
        agreement.terms = new_terms
        agreement.current_version = new_version
        agreement.save()

    return agreement


def terminate_agreement(agreement, terminated_by, valid_to=None, reason="Terminado"):
    """Termina acuerdo estableciendo valid_to."""
    if valid_to is None:
        valid_to = timezone.now()

    if valid_to <= agreement.valid_from:
        raise InvalidTerminationError("La fecha de terminacion debe ser posterior a valid_from")

    with transaction.atomic():
        agreement = Agreement.objects.select_for_update().get(pk=agreement.pk)

        new_version = agreement.current_version + 1

        AgreementVersion.objects.create(
            agreement=agreement,
            version=new_version,
            terms=agreement.terms,
            created_by=terminated_by,
            reason=reason,
        )

        agreement.valid_to = valid_to
        agreement.current_version = new_version
        agreement.save()

    return agreement
```

**Por que servicios en lugar de model.save()?**

1. **Invariantes atomicos.** Crear un acuerdo requiere crear una version. Enmendar requiere actualizar tanto proyeccion como libro mayor. Estos deben suceder juntos o no suceder.

2. **Seguridad de concurrencia.** `select_for_update()` previene que dos enmiendas simultaneas creen el mismo numero de version.

3. **Validacion en contexto.** La fecha de terminacion debe ser posterior a `valid_from`. Esta verificacion pertenece en la operacion, no en `model.clean()`.

4. **Defaults convenientes.** El modelo no tiene default para `valid_from`—es requerido. El servicio proporciona `timezone.now()` como default sensato.

## Practica: Construyendo Acuerdos con IA

Ahora ponemos la primitiva en practica. Estos ejercicios demuestran como dirigir a una IA para generar codigo consciente de acuerdos correctamente.

### Ejercicio 1: Acuerdo Sin Restricciones

Pide a una IA:

```
Construye un modelo Django para rastrear suscripciones de clientes.
Incluye el nombre del plan, precio y fecha de inicio.
```

Examina lo que obtienes. Tipicamente:

- Un solo modelo con campos mutables
- Sin historial de versiones
- Sin relaciones de partes (el cliente podria estar, pero el proveedor es implicito)
- Sin consultas temporales
- Precio como valor almacenado, no una referencia computada

La IA produce algo que funciona para el camino feliz pero falla en cada caso extremo.

### Ejercicio 2: Acuerdo Restringido

Ahora pide con restricciones explicitas:

```
Construye una app Django para acuerdos de suscripcion usando estas restricciones:

1. Modelo Agreement heredando de BaseModel (UUID, timestamps, eliminacion suave)
   - DOS partes explicitas via GenericForeignKey
   - party_a_id y party_b_id son CharField (no IntegerField) para soporte UUID

2. Terminos almacenados como JSONField, no prosa
   - Debe soportar: plan_id, price_cents, currency, billing_cycle
   - Nunca almacenar precio como float

3. Patron Proyeccion + Libro Mayor
   - Agreement tiene terms (proyeccion actual) y contador current_version
   - AgreementVersion almacena historial inmutable (el libro mayor)
   - Invariante: Agreement.current_version == max(AgreementVersion.version)

4. Capa de servicio para todas las escrituras
   - create_agreement(): Crea acuerdo + version inicial atomicamente
   - amend_agreement(): Crea nueva version, actualiza proyeccion
   - terminate_agreement(): Establece valid_to, crea version de terminacion
   - Usar select_for_update() para incremento seguro de version

5. Validez temporal
   - valid_from (REQUERIDO, sin default en modelo - servicio proporciona conveniencia)
   - valid_to (nullable significa indefinido)
   - CheckConstraint: valid_to > valid_from (usar 'condition' para Django 6.0+)
   - Metodos de QuerySet: current(), as_of(timestamp), for_party(party)

6. Los acuerdos nunca se eliminan duramente (eliminacion suave de BaseModel)

Escribe pruebas primero usando TDD.
```

La salida deberia coincidir con el patron de este capitulo. Si alguna restriccion se viola, el suite de pruebas lo capturara.

### Ejercicio 3: Ciclo de Vida de Suscripcion

Prueba tu comprension implementando un flujo de suscripcion completo usando la capa de servicio:

```
Usando el modelo Agreement y servicios del Ejercicio 2, implementa:

1. create_subscription(customer, provider, plan_terms, started_by)
   - Llama a create_agreement() con scope_type='subscription'
   - valid_from defaultea a ahora (via servicio), valid_to es None
   - Retorna el Agreement

2. upgrade_subscription(agreement, new_plan_terms, upgraded_by, reason)
   - Llama a amend_agreement() con los nuevos terminos
   - Incrementa current_version via select_for_update()
   - Actualiza proyeccion, crea entrada inmutable de libro mayor
   - Retorna el Agreement actualizado

3. cancel_subscription(agreement, cancelled_by, cancellation_date, reason)
   - Llama a terminate_agreement()
   - Establece valid_to a cancellation_date
   - Crea version de terminacion en libro mayor
   - Retorna el Agreement actualizado

4. get_terms_as_of(agreement, timestamp)
   - Retorna la instantanea de terminos de la version mas reciente donde created_at <= timestamp
   - Retorna None si no existia version en ese momento

Escribe pruebas cubriendo:
- Crear una suscripcion (verificar Agreement + AgreementVersion creados atomicamente)
- Actualizar dos veces (version 1 → 2 → 3, proyeccion coincide con la mas reciente)
- Consultar terminos en varios puntos del historial (usar version created_at)
- Cancelar y confirmar que is_active retorna False
- Rechazar fecha de terminacion invalida (debe ser posterior a valid_from)
- Concurrencia: dos enmiendas simultaneas no corrompen version
```

Este ejercicio forza a la IA a implementar el patron completo de proyeccion + libro mayor con capa de servicio correctamente.

## El Contrato de Prompt para Acuerdos

Al usar IA para trabajar con acuerdos en tu base de codigo, aplica estas reglas:

```markdown
## Restricciones de Primitiva de Acuerdos

### Debe Hacer
- Heredar de BaseModel (UUID, timestamps, eliminacion suave)
- Usar GenericForeignKey para ambas partes (soporta cualquier tipo de modelo)
- Almacenar terminos como JSONField con datos estructurados, computables
- Usar patron Proyeccion + Libro Mayor (Agreement + AgreementVersion)
- Rastrear superficie de decision (agreed_at, agreed_by para cada acuerdo)
- Implementar consultas temporales (current(), as_of(), for_party())
- Usar valid_from/valid_to para validez temporal
- Agregar CheckConstraint: valid_to > valid_from (usar 'condition' para Django 6.0+)
- Escribir todas las mutaciones a traves de capa de servicio (create, amend, terminate)
- Usar select_for_update() al incrementar contadores de version

### No Debe
- Nunca editar terminos de acuerdo directamente (usar servicio amend_agreement)
- Nunca eliminar acuerdos duramente (eliminacion suave de BaseModel)
- Nunca poner logica de negocio en model.save() (usar servicios)
- Nunca almacenar terminos como prosa en TextField
- Nunca usar Float para cantidades monetarias en terminos
- Nunca asumir que las partes son siempre modelo User (usar GenericFK)
- Nunca modificar registros AgreementVersion despues de crearse
- Nunca agregar default para valid_from en modelo (servicio proporciona conveniencia)

### Invariantes
- Agreement.current_version == max(AgreementVersion.version)
- Todo Agreement tiene al menos un AgreementVersion (el original)
- Los numeros de version son estrictamente crecientes por acuerdo
- valid_to debe ser > valid_from cuando ambos estan establecidos
- Los registros AgreementVersion son inmutables despues de crearse
```

Incluye esto en el CLAUDE.md de tu proyecto o cargalo cuando trabajes en features relacionadas con acuerdos.

## Lo Que la IA Hace Mal

Sin restricciones explicitas, el codigo de acuerdos generado por IA tipicamente:

1. **Omite BaseModel** — Agrega manualmente UUID, timestamps o campos de eliminacion suave. O peor, usa IDs auto-incrementales.

2. **Modela solo una parte** — El cliente tiene una `subscription`, pero con quien es la suscripcion? El proveedor es implicito, rompiendose cuando agregas revendedores o escenarios multi-proveedor.

3. **Pone logica en save()** — Reglas de negocio en `model.save()` en lugar de funciones de servicio. Sin atomicidad, sin seguridad de concurrencia.

4. **Usa campos mutables** — Los cambios de plan actualizan el registro de suscripcion. El historial se pierde. Sin patron proyeccion + libro mayor.

5. **Agrega defaults a valid_from** — `default=timezone.now` en el modelo. Esto oculta omisiones accidentales en lugar de forzar fechas explicitas.

6. **Ignora validez temporal** — Sin valid_from/valid_to significa que no puedes consultar estado historico o manejar acuerdos con fecha futura.

7. **Usa FloatField para dinero** — `"price": 49.99` almacenado como float introduce errores de redondeo.

8. **Usa check= en CheckConstraint** — Django 6.0 cambio la API a `condition=`. El codigo viejo falla silenciosamente.

9. **Sin manejo de concurrencia** — Dos enmiendas simultaneas crean numeros de version duplicados.

La solucion es siempre restricciones explicitas. Dile a la IA exactamente que patron seguir—BaseModel, capa de servicio, proyeccion + libro mayor, select_for_update—y lo seguira consistentemente.

## Por Que Esto Importa Despues

Los acuerdos son la fundacion para:

- **Facturacion**: Suscripciones, facturas y calendarios de pago se derivan todos de terminos de acuerdos.

- **Catalogos**: Cuando se hace un pedido, los terminos en ese momento—precios, descuentos, promesas de entrega—se convierten en parte de un acuerdo implicito.

- **Flujos de trabajo**: Los acuerdos de nivel de servicio definen tiempos de respuesta y rutas de escalamiento para encuentros.

- **Auditoria**: Toda transaccion financiera deberia rastrear al acuerdo que la autorizo.

Si manejas mal los acuerdos, todo sistema que depende de "lo que se prometio" se vuelve poco confiable. Si los manejas bien, tienes una fundacion solida para gestion de suscripciones, negociaciones de contratos y reportes de cumplimiento.

---

## Como Reconstruir Esta Primitiva

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-agreements | `docs/PRIMITIVE_PROMPT.md` | ~47 tests |

### Usando el Prompt

```bash
cat docs/PRIMITIVE_PROMPT.md | claude

# Solicitud: "Crea paquete django-agreements con:
# - Modelo Agreement heredando BaseModel
# - AgreementVersion para historial inmutable
# - Capa de servicio: create_agreement, amend_agreement, terminate_agreement
# - Patron proyeccion + libro mayor"
```

### Restricciones Clave

- **Heredar de BaseModel**: UUID, timestamps, eliminacion suave incorporados
- **Patron Proyeccion + Libro Mayor**: Agreement.terms es proyeccion, AgreementVersion es libro mayor
- **Capa de servicio requerida**: Todas las escrituras pasan por funciones create/amend/terminate
- **Invariante aplicado por servicios**: Agreement.current_version == max(AgreementVersion.version)
- **Sin defaults para valid_from**: Modelo lo requiere, servicio proporciona conveniencia
- **Seguro de concurrencia**: select_for_update() al incrementar versiones
- **Compatible con Django 6.0**: CheckConstraint usa `condition=` no `check=`

Si Claude pone logica de negocio en model.save() o agrega defaults a valid_from, eso es una violacion de restriccion.

---

## Fuentes y Referencias

1. **Codigo de Hammurabi** — Escrito circa 1754 AEC, el codigo legal escrito mas antiguo conocido, abordando principalmente relaciones contractuales. Museo Britanico, Londres.

2. **Pacioli, Luca** (1494). *Summa de arithmetica, geometria, proportioni et proportionalita*. La seccion sobre contabilidad de partida doble asume contratos como fundacion de transacciones comerciales.

3. **Integracion Disney-Fox** — "Disney's Fox Deal: A $71.3 Billion Bet," *Wall Street Journal*, 20 de marzo de 2019. El desafio de reconciliacion de licencias de contenido fue discutido en reportes de integracion subsecuentes.

4. **Ley Sarbanes-Oxley** — Ley Publica 107-204 (2002), Seccion 302 y 404 sobre controles internos y documentacion de cadenas de autorizacion.

5. **Patron GenericForeignKey** — Documentacion de Django sobre el framework contenttypes. Este patron habilita relaciones polimorficas esenciales para partes de acuerdos flexibles.

---

*Estado: Completo*
