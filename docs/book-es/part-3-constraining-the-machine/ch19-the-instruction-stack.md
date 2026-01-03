# Capítulo 19: El Sistema Operativo de Programación

## Claude No Es un Cerebro. Es un Sistema Operativo Con Aplicaciones.

La mayoría de la confusión sobre la codificación asistida por IA no proviene de la calidad del modelo. Proviene de **malentender cómo se cargan, delimitan y aplican las instrucciones**.

Si tratas a Claude como un desarrollador junior genial que "lee todo lo que le das", obtendrás comportamiento inconsistente, invariantes rotas y confianza alucinada. Si tratas a Claude como un sistema operativo con reglas estrictas de arranque y aplicaciones bajo demanda, se vuelve predecible, seguro y sorprendentemente efectivo.

Este capítulo explica ese modelo mental—y luego lo extiende a algo más poderoso: construir tu propio Sistema Operativo de Programación para software empresarial.

---

## Parte I: La Pila de Instrucciones

Claude no procesa las instrucciones como un solo bloque. Las procesa como una **pila**, cargada en un orden específico, con diferentes garantías de persistencia.

Piensa menos en "prompt" y más en "entorno de ejecución."

### Las Cuatro Capas de Instrucción

```
INICIO DE CONVERSACIÓN
│
├─ 1. CLAUDE.md Global (siempre cargado)
│
├─ 2. CLAUDE.md del Proyecto (auto-cargado en el repo)
│
├─ 3. Tu mensaje (instrucción explícita)
│
└─ 4. Resultados de herramientas (archivos que Claude realmente lee)
```

Cada capa tiene un propósito diferente. Mezclarlas es cómo los equipos accidentalmente se sabotean a sí mismos.

---

### Capa 1: CLAUDE.md Global

**"Cómo Debe Comportarse Claude, Siempre"**

Este archivo es **automático e incondicional**. Claude lo carga para *cada* conversación antes de que digas una palabra.

Eso significa que debe ser:

- Corto
- Estable
- Conductual, no procedimental

**Lo que pertenece aquí:**

- Reglas universales de desarrollo
- Restricciones no negociables
- Estándares de seguridad y calidad

```markdown
# Estándares de Desarrollo

## TDD (Obligatorio)
1. Escribir prueba fallida primero
2. Ejecutar pytest, confirmar fallo
3. Escribir código mínimo para pasar
4. Refactorizar manteniendo verde

## Git
- Commits convencionales: tipo(alcance): descripción
- Nunca force push a main
- Nunca cerrar automáticamente issues de bugs

## Calidad de Código
- >95% cobertura de pruebas
- Sin comentarios TODO en código enviado
```

**Lo que NO pertenece aquí:**

- Especificaciones de proyecto
- Plantillas de archivos
- Descripciones de paquetes
- Flujos de trabajo
- Listas de verificación
- Cualquier cosa que cambie frecuentemente

Si este archivo crece mucho, estás convirtiendo tu sistema operativo en una aplicación, y todo se vuelve frágil.

**Tamaño objetivo: ~50 líneas.**

---

### Capa 2: CLAUDE.md del Proyecto

**"Lo Que Este Código Base Cree"**

Este archivo también se auto-carga, pero solo cuando Claude está trabajando dentro de un directorio de proyecto específico.

Esto es **contexto de proyecto**, no contexto de tarea.

**Lo que pertenece aquí:**

- Reglas arquitectónicas
- Límites de capas
- Patrones compartidos
- Convenciones de nomenclatura
- Filosofía del proyecto

```markdown
# Django Primitives

Monorepo de 18 paquetes Django para aplicaciones ERP/empresariales.

## Regla de Dependencia
Nunca importar desde una capa superior.

## Patrones de Modelos
Todos los modelos usan claves primarias UUID.
Los modelos de dominio agregan eliminación suave.
Los eventos agregan semántica temporal (effective_at/recorded_at).

## Creando Paquetes
Usar los prompts por paquete en docs/prompts/
```

Este archivo debe explicar *cómo piensa el proyecto*, no *qué construir a continuación*.

**Tamaño objetivo: ~100 líneas.**

---

### Capa 3: Tu Mensaje

**"Lo Que Quiero Que Hagas Ahora"**

Esta es la única parte en la que la mayoría de la gente piensa.

Tu mensaje debe:

- Nombrar la tarea
- Referenciar los documentos a cargar
- Evitar repetir reglas ya aplicadas en otro lugar

**Bueno:**

> "Reconstruir django-worklog usando docs/prompts/django-worklog.md"

**Malo:**

> "Aquí están todas las reglas de nuevo, y también la especificación, y también la arquitectura, y también recuerda usar TDD y también..."

La redundancia debilita la aplicación. Claude ya tiene las reglas si las pusiste en el lugar correcto.

---

### Capa 4: Resultados de Herramientas

**"Las Únicas Especificaciones Que Realmente Importan"**

Claude **no** lee tu repositorio por defecto.

Solo sabe lo que:

- Pegas
- Le dices explícitamente que lea
- Abre mediante herramientas

Aquí es donde **pertenecen las especificaciones, prompts y documentos de arquitectura**.

Estos archivos pueden ser:

- Largos
- Detallados
- Exhaustivos
- Específicos de la tarea

Porque se cargan **bajo demanda**, no globalmente.

Esto es el equivalente a lanzar una aplicación sobre el SO.

---

### El Error Crítico

La mayoría de los equipos tratan CLAUDE.md como un **prompt maestro**.

Ponen especificaciones, plantillas, flujos de trabajo, ejemplos, arquitectura y listas de verificación en archivos que **siempre se cargan**.

El resultado:

- Miles de líneas de contexto antes de que una tarea siquiera comience
- Claude "siguiendo" algunas reglas e ignorando otras
- Instrucciones conflictivas
- Salida más lenta y menos confiable

Esto no es Claude siendo tonto. Esto es tú arrancando Photoshop dentro del kernel.

---

### El Modelo Mental Correcto

| Concepto | Equivalente en Claude |
|----------|----------------------|
| Sistema operativo | CLAUDE.md Global |
| Configuración de proyecto | CLAUDE.md del Proyecto |
| Aplicación | Documento de prompt / especificación |
| Ejecución de programa | Tu mensaje |
| E/S | Lecturas de herramientas |

No pones toda tu aplicación en el sistema operativo.

Pones **reglas** en el SO. Cargas **apps** cuando las necesitas.

---

## Parte II: Vibe Coding Con Restricciones

La frase "vibe coding" se ha convertido en sinónimo de desarrollo imprudente asistido por IA: pegar requisitos, esperar lo mejor, enviar lo que compile.

Eso no es lo que enseña este libro.

**Vibe coding con restricciones** significa:

- Iteración rápida *dentro de* reglas rígidas
- La IA escribe el código, tú aplicas las invariantes
- La velocidad viene de la eliminación, no de la improvisación

La verdad contraintuitiva: **las restricciones aumentan la velocidad a largo plazo**.

Cuando Claude sabe:

- Cada modelo usa claves primarias UUID
- Cada mutación pasa por una función de servicio
- Cada cambio de estado es solo-agregar
- Cada prueba se escribe antes de la implementación

...deja de inventar. Deja de "ser creativo." Se convierte en un ejecutor preciso de trabajo bien especificado.

El objetivo no es hacer que Claude piense menos. El objetivo es hacer que Claude piense en las cosas correctas.

---

## Parte III: ¿Qué Es un Primitivo?

Un primitivo es una **capacidad no negociable** requerida para construir software empresarial.

No una característica. No un vertical. No una UI con opiniones.

Un primitivo responde la pregunta: *¿Qué necesita cada sistema empresarial, independientemente del dominio?*

### Ejemplos de Primitivos

| Primitivo | Capacidad |
|-----------|-----------|
| Parties | ¿Quiénes son los actores? (personas, organizaciones, grupos) |
| RBAC | ¿Qué puede hacer cada actor? |
| Catalog | ¿Qué puede ordenarse/programarse/rastrearse? |
| Ledger | ¿Qué dinero se movió y por qué? |
| Agreements | ¿Qué se prometió y cuándo? |
| Encounters | ¿Qué interacciones ocurrieron? |

### Ejemplos de NO Primitivos

| No es un Primitivo | Por qué |
|--------------------|---------|
| Notificaciones | Preocupación de infraestructura, no una capacidad de dominio |
| Búsqueda | Preocupación de infraestructura |
| Programación | Compuesto de ledger + agreements + semántica temporal |
| Mitades de toppings de pizza | Configuración específica del dominio, no una capacidad |

La prueba: **Si eliminarlo incapacitaría cada negocio que podrías construir, es un primitivo.**

---

## Parte IV: El Modelo de Primitivos por Niveles

Los primitivos no son iguales. Tienen dependencias. Algunos deben existir antes de que otros tengan sentido.

### Nivel 0: Dados de Django + Postgres

Estos no son tus primitivos. Son tu plataforma.

- Usuarios y autenticación
- Base de datos y migraciones
- Petición/respuesta HTTP
- Interfaz de administración

No los reconstruyes. Construyes sobre ellos.

### Nivel 1: Identidad Base y Tiempo

**Paquetes:** basemodels, parties, rbac, singleton

Estos responden:

- ¿Cómo identificamos las cosas? (UUIDs, eliminación suave)
- ¿Quiénes son los actores? (Patrón Party)
- ¿Qué pueden hacer? (Acceso basado en roles)
- ¿Qué configuración es global? (Singletons)

Todo lo demás depende de que estos existan.

### Nivel 2: Superficies de Decisión

**Paquetes:** decisioning, agreements, audit-log

Estos responden:

- ¿Cuándo sucedió algo realmente vs. cuándo se registró?
- ¿Qué se prometió y por quién?
- ¿Cuál es la pista de auditoría inmutable?

La lógica de negocio vive aquí. Estos paquetes aplican **semántica temporal** e **idempotencia**.

### Nivel 3: Dinero y Obligaciones

**Paquetes:** money, ledger, sequence

Estos responden:

- ¿Cómo representamos la moneda correctamente?
- ¿Cómo rastreamos transacciones financieras?
- ¿Cómo generamos identificadores secuenciales?

Contabilidad de partida doble. Sin punto flotante. Sin saldos mutables.

### Nivel 4: Capas de Composición

**Paquetes:** catalog, worklog, encounters, documents, notes

Estos responden:

- ¿Qué puede ordenarse? (Catalog)
- ¿Qué trabajo se hizo? (Worklog)
- ¿Qué interacciones ocurrieron? (Encounters)
- ¿Qué archivos están adjuntos? (Documents)
- ¿Qué comentarios existen? (Notes)

Estos paquetes *componen* los niveles inferiores en superficies de dominio utilizables.

### Primitivos de Borde

**Paquetes:** geo

Opcional. No todos los negocios necesitan conciencia de ubicación. Pero cuando la necesitas, necesitas:

- Coordenadas con precisión adecuada
- Límites de área de servicio
- Cálculos de distancia

Los primitivos de borde son primitivos reales—solo tienen aplicabilidad más estrecha.

---

## Parte V: El Mapa de Dependencias

```
                    ┌─────────────────┐
                    │   Aplicaciones  │
                    │  (Pizza, Vet,   │
                    │   Dive, Rental) │
                    └────────┬────────┘
                             │ usa
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Catalog │         │Encounter│         │ Worklog │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        └─────────┬─────────┴─────────┬─────────┘
                  │                   │
                  ▼                   ▼
            ┌──────────┐        ┌──────────┐
            │  Ledger  │        │Agreements│
            └────┬─────┘        └────┬─────┘
                 │                   │
                 └─────────┬─────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Decisioning │
                    │(tiempo,idem)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
         ┌────────┐   ┌────────┐   ┌────────┐
         │ Parties│   │  RBAC  │   │  Audit │
         └───┬────┘   └───┬────┘   └───┬────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │ BaseModels │
                   │ (UUID, ts) │
                   └────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │  Django +  │
                   │  Postgres  │
                   └────────────┘
```

Este mapa es un **mapa de desarrollo**, no un diseño de sistema de archivos.

Las dependencias fluyen *conceptualmente*. No puedes construir Catalog sin entender Ledger. No puedes construir Ledger sin entender Decisioning. No puedes construir Decisioning sin entender Parties.

Pero cada paquete permanece **instalable independientemente**. Un proyecto que solo necesita Parties no instala Catalog. La dependencia es conceptual, no de tiempo de ejecución.

---

## Parte VI: Un Sistema, Muchos Dominios

Los primitivos no cambian. Los dominios sí.

### Pedidos de Pizza

| Concepto del Dominio | Primitivo Usado |
|----------------------|-----------------|
| Cliente | parties.Person |
| Pizzería | parties.Organization |
| Elementos del menú | catalog.CatalogItem |
| Pedido | catalog.Basket → catalog.Order |
| Pago | ledger.Transaction |
| Zona de entrega | geo.ServiceArea |
| Asignación de repartidor | worklog.WorkSession |

¿Mitades de toppings? Configuración de catálogo. ¿Porciones? Configuración de catálogo. ¿Ofertas combo? Agreements + reglas de precios del catálogo.

No se requieren nuevos primitivos.

### Clínica Veterinaria

| Concepto del Dominio | Primitivo Usado |
|----------------------|-----------------|
| Dueño de mascota | parties.Person |
| Paciente (mascota) | parties.Person (sí, realmente) |
| Clínica | parties.Organization |
| Cita | encounters.Encounter |
| Servicios prestados | catalog.BasketItem |
| Factura | ledger.Transaction |
| Notas médicas | notes.Note |
| Resultados de laboratorio | documents.Document |

¿Calendarios de vacunación? Agreements. ¿Protocolos de tratamiento? Catalog + máquina de estados de encounters.

No se requieren nuevos primitivos.

### Operaciones de Buceo

| Concepto del Dominio | Primitivo Usado |
|----------------------|-----------------|
| Buceador | parties.Person |
| Tienda de buceo | parties.Organization |
| Bote | catalog.CatalogItem (tipo de recurso) |
| Reserva de viaje | catalog.Basket → encounters.Encounter |
| Exención | agreements.Agreement |
| Pago | ledger.Transaction |
| Sitio de buceo | geo.Place |
| Registro de buceo | worklog.WorkSession + notes.Note |

¿Seguimiento de certificaciones? Agreements con valid_from/valid_to. ¿Alquiler de equipo? Elementos de catálogo con reglas de disponibilidad.

No se requieren nuevos primitivos.

### El Patrón

Cada negocio vertical es una **composición** de los mismos primitivos con diferente:

- Configuración
- Flujos de trabajo
- UI
- Reglas de negocio

Los primitivos proporcionan capacidades. La aplicación proporciona decisiones.

---

## Parte VII: Por Qué la Corrección Supera a la Creatividad

Seis principios que hacen el sistema confiable:

### 1. Idempotencia

Cada operación que puede reintentarse debe producir el mismo resultado.

```python
@idempotent(key_func=lambda basket_id, **_: f"commit:{basket_id}")
def commit_basket(basket_id):
    # Seguro llamar dos veces
```

Fallos de red, doble clic del usuario, colas de reintentos—ninguno de estos corrompe el estado.

### 2. Semántica Temporal

Dos marcas de tiempo, siempre:

```python
effective_at = models.DateTimeField()  # Cuándo sucedió en realidad
recorded_at = models.DateTimeField()   # Cuándo nos enteramos
```

Una visita al veterinario el lunes registrada el martes: `effective_at = Lunes`, `recorded_at = Martes`.

Antedatar no es fraude. Es **precisión**.

### 3. Instantáneas Sobre Estado Vivo

Cuando se coloca un pedido, copia el precio. No referencias el catálogo.

```python
class OrderLine(models.Model):
    unit_price_snapshot = models.DecimalField()  # Congelado al momento del pedido
    # NO: price = catalog_item.current_price
```

Los precios cambian. Los pedidos no deben.

### 4. Reversiones Sobre Ediciones

¿Transacción incorrecta? No la edites. Publica una reversión.

```python
# Incorrecto:
transaction.amount = corrected_amount
transaction.save()

# Correcto:
Transaction.objects.create(
    amount=-original_amount,
    reverses=original_transaction
)
Transaction.objects.create(
    amount=corrected_amount
)
```

El historial es inmutable. La pista de auditoría es sagrada.

### 5. Solo-Agregar Donde Importa

Los registros de auditoría no pueden editarse ni eliminarse:

```python
def save(self, *args, **kwargs):
    if self.pk:
        raise ImmutableLogError()
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise ImmutableLogError("Los registros de auditoría no pueden eliminarse")
```

Algunas tablas son libros mayores. Trátalas así.

### 6. Eliminación Suave para Objetos de Dominio

Nada se elimina verdaderamente. Todo se marca:

```python
deleted_at = models.DateTimeField(null=True, blank=True)

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
```

"Eliminado" significa "oculto de consultas normales." Los datos permanecen para auditoría, recuperación y cumplimiento legal.

---

## Parte VIII: Por Qué Este Es un SO ERP Personal

Esto no es un pitch de SaaS. Esto no es un framework para que otros adopten. Esto no es marketing de código abierto.

Este es un **sistema operativo personal** para construir software empresarial.

El objetivo:

- Construir los primitivos una vez
- Probarlos exhaustivamente (815 pruebas en 18 paquetes)
- Reutilizarlos para cada negocio futuro

El proyecto del próximo año—sea lo que sea—comienza con:

```python
INSTALLED_APPS = [
    'django_basemodels',
    'django_parties',
    'django_rbac',
    'django_catalog',
    'django_ledger',
    # ... ya construido, ya probado
]
```

Los primitivos son aburridos. Los primitivos son correctos. Los primitivos no necesitan ser reconstruidos.

Todo el esfuerzo futuro va hacia **decisiones específicas del dominio**, no infraestructura.

Ese es el sistema operativo. Todo lo demás son solo aplicaciones.

---

## Resumen

| Principio | Implementación |
|-----------|----------------|
| Higiene de instrucciones | CLAUDE.md para reglas, prompts para especificaciones |
| Las restricciones habilitan la velocidad | Patrones rígidos, iteración rápida dentro de ellos |
| Los primitivos son capacidades | 14 core + 1 de borde, no características |
| Las dependencias son conceptuales | Modelo por niveles, paquetes independientes |
| Los dominios son composiciones | Mismos primitivos, diferente configuración |
| La corrección supera a la creatividad | Idempotencia, semántica temporal, inmutabilidad |

El lector que entiende este capítulo ve el sistema operativo.

Todo lo que sigue—Catalog, Ledger, Agreements, Encounters—es solo instalar aplicaciones.

---

*Próximo capítulo: El Primitivo Catalog—Pedidos, Carritos y el Flujo de Trabajo Que Ejecuta Todo*
