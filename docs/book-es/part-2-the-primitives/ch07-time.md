# Capitulo 7: Tiempo

> "Que sabia el Presidente, y cuando lo supo?"
>
> — Senador Howard Baker, Audiencias de Watergate, 1973

---

Todo sistema que registra hechos sobre el mundo enfrenta el mismo problema: el mundo no espera a tu base de datos.

Una venta sucede el viernes, pero el empleado de entrada de datos esta enfermo hasta el lunes. Un cliente cancela un pedido a las 11:47 PM, pero el proceso por lotes que actualiza el inventario se ejecuta a medianoche. Un doctor realiza un procedimiento el 3 de marzo, pero el sistema de facturacion del hospital no recibe el reclamo hasta el 15 de marzo. El aumento de un empleado se aprueba retroactivo al 1 de enero, pero se registra el 28 de febrero.

En cada caso, hay dos puntos diferentes en el tiempo que importan. Cuando sucedio? Cuando nos enteramos?

La mayoria de los sistemas confunden estos. Tienen una sola marca de tiempo `created_at` que registra cuando se inserto la fila. Esto funciona hasta que no funciona—hasta que alguien hace una pregunta que el sistema no puede responder.

## La Pregunta de Watergate

La pregunta del Senador Howard Baker durante las audiencias de Watergate de 1973 no era solo sobre politica. Era una formulacion precisa del problema de rendicion de cuentas: separar lo que alguien sabia de cuando lo supo.

Esta pregunta aparece en todas partes en los negocios:

- **Los auditores preguntan**: "Cuales eran sus ingresos reportados el 31 de diciembre, antes de la correccion del 15 de enero?"
- **Los reguladores preguntan**: "Cuando se enteraron del defecto del producto?"
- **Los abogados preguntan**: "Cual era el saldo de la cuenta en el momento de la transaccion en disputa?"
- **Los ejecutivos preguntan**: "Que mostraba nuestro pronostico el dia que tomamos la decision de adquisicion?"

Un sistema con solo `created_at` no puede responder estas preguntas. Solo conoce el estado actual. El historial de lo que sabias, cuando lo sabias, se ha ido.

## La Naturaleza Bidimensional del Tiempo

El cientifico informatico Richard Snodgrass paso decadas formalizando este problema. Su trabajo, culminando en las extensiones temporales del estandar SQL 2011, establecio que los datos de negocio inherentemente viven en dos dimensiones de tiempo:

**Tiempo valido** (tambien llamado tiempo de negocio): Cuando el hecho es verdadero en el mundo real. Un contrato es valido del 1 de enero al 31 de diciembre. El salario de un empleado es efectivo desde su fecha de contratacion. El precio de un producto es valido hasta el proximo cambio de precio.

**Tiempo de transaccion** (tambien llamado tiempo del sistema): Cuando el hecho fue registrado en la base de datos. El contrato podria ingresarse el 3 de enero. El registro de salario podria crearse el primer dia del empleado. El precio podria actualizarse tres dias antes de que tome efecto.

Snodgrass llamo a los sistemas que rastrean ambas dimensiones *bitemporales*. La mayoria de los sistemas no lo son. Rastrean solo una dimension—usualmente tiempo de transaccion, oculto en un campo `created_at` que pocos consultan.

## El Costo de Hacerlo Mal

Las consecuencias de los sistemas de tiempo unico van desde inconvenientes hasta catastroficas.

### El Escandalo de Retroactividad de Opciones

Entre 2005 y 2007, mas de 130 empresas que cotizan en bolsa fueron investigadas por retroactivar otorgamientos de opciones sobre acciones. El esquema era simple: los ejecutivos se otorgaban opciones fechadas a un dia cuando el precio de la accion era bajo, haciendo las opciones mas valiosas.

La investigacion del Wall Street Journal, que gano un Premio Pulitzer, uso analisis estadistico para identificar patrones sospechosos. Apple, Broadcom, UnitedHealth y docenas de otras empresas fueron implicadas. La SEC extrajo mas de $700 millones en acuerdos. Varios ejecutivos enfrentaron cargos criminales. El CEO de Brocade fue sentenciado a 21 meses de prision.

La falla tecnica subyacente al escandalo era un sistema que permitia establecer fechas `effective_at` sin ningun registro de cuando el otorgamiento fue realmente ingresado al sistema. Las empresas afirmaban que las opciones fueron otorgadas meses antes, y sus sistemas no podian probar lo contrario.

Un sistema bitemporal habria registrado ambas fechas: cuando el otorgamiento tomo efecto (la fecha reclamada) y cuando fue ingresado (la fecha real). La brecha entre ellas habria sido inmediatamente visible—no solo para investigadores anos despues, sino para auditores en tiempo real.

### El Problema de Enron

El fraude contable de Enron dependia fuertemente de la manipulacion de tiempos. La empresa reconocia ingresos en el trimestre actual por acuerdos que realmente no habian cerrado, luego ajustaba los numeros despues. Cuando los auditores preguntaban que sabia la empresa al final del trimestre, la respuesta era turbia porque el sistema no separaba limpiamente el tiempo de negocio del tiempo del sistema.

La Ley Sarbanes-Oxley de 2002, aprobada en respuesta a Enron y escandalos similares, requiere que las empresas publicas mantengan registros financieros precisos que puedan reconstruirse para cualquier punto en el tiempo. La Seccion 802 hace un crimen alterar, destruir u ocultar registros con intencion de obstruir una investigacion.

El cumplimiento no es opcional. La ley requiere que puedas responder la pregunta de Watergate sobre tus datos financieros.

### La Falla del Misil Patriot

El 25 de febrero de 1991, un misil Scud iraqui impacto un cuartel del Ejercito estadounidense en Dhahran, Arabia Saudita, matando a 28 soldados. La bateria de misiles Patriot que deberia haberlo interceptado fallo en rastrear el misil entrante.

La investigacion de la Oficina de Responsabilidad Gubernamental encontro un error de tiempo en el software del sistema. El sistema Patriot rastreaba el tiempo en decimas de segundo usando un entero de 24 bits. Esta representacion introducia un pequeno error de punto flotante—aproximadamente 0.000000095 segundos por decima de segundo. Despues de 100 horas de operacion continua, el error se habia acumulado a 0.34 segundos.

Un misil Scud viaja a aproximadamente 1,676 metros por segundo. En 0.34 segundos, se mueve mas de 500 metros—mas que suficiente para desaparecer de la ventana de rastreo del Patriot.

Este no era un problema bitemporal per se, pero ilustra como los sistemas que tratan el tiempo como una dimension unica y simple pueden fallar catastroficamente. El tiempo es mas complejo que un solo contador. Los sistemas que reconocen esta complejidad son mas robustos que los que no.

## Las Dos Marcas de Tiempo

La solucion es mas simple de lo que el problema podria sugerir. Cada hecho necesita dos marcas de tiempo:

**`effective_at`**: Cuando se volvio verdadero esto en el mundo de negocios? Esta es la fecha que importa para la logica de negocio. Cuando sucedio la venta? Cuando tomo efecto el aumento del empleado? Cuando recibio el paciente el tratamiento?

**`recorded_at`**: Cuando se entero el sistema de esto? Esto es inmutable—registra cuando la fila fue realmente insertada, independientemente de cuando ocurrio el evento subyacente.

```python
class TimeSemanticsMixin(models.Model):
    effective_at = DateTimeField(default=timezone.now)
    recorded_at = DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
```

Eso es todo. Dos campos. Pero las implicaciones son profundas.

### La Retroactividad No Es Fraude

Cuando `effective_at` y `recorded_at` estan separados, la retroactividad se convierte en una operacion normal y transparente. El empleado de entrada de datos que ingresa la venta del viernes el lunes simplemente establece `effective_at` al viernes. El `recorded_at` automaticamente registra que la entrada sucedio el lunes.

No hay engano, ni manipulacion oculta. Cualquiera que consulte los datos puede ver ambas fechas. Los auditores pueden preguntar: "Muestrame todo lo que fue efectivo en Q4 pero registrado en Q1." La respuesta esta facilmente disponible.

Contrasta esto con un sistema de marca de tiempo unica donde alguien cambia la fecha `created_at` al viernes. Ahora el rastro de auditoria esta comprometido. El sistema miente sobre cuando aprendio la informacion. Este es el patron que habilito el escandalo de retroactividad de opciones.

### Consultas "As Of"

Con ambas marcas de tiempo, puedes responder preguntas que los sistemas de marca de tiempo unica no pueden:

**"Cual era el estado de esta cuenta el 31 de diciembre?"**

Esta es la consulta de tiempo valido. Quieres todos los hechos donde `effective_at <= 31 de diciembre`, independientemente de cuando fueron registrados.

**"Que sabiamos sobre esta cuenta el 31 de diciembre?"**

Esta es la consulta de tiempo de transaccion. Quieres todos los hechos donde `recorded_at <= 31 de diciembre`, independientemente de cuando tomaron efecto.

**"Que creiamos que era el estado de la cuenta el 31 de diciembre, a partir de nuestro cierre del 15 de enero?"**

Esta es la consulta bitemporal. Quieres todos los hechos donde `effective_at <= 31 de diciembre` Y `recorded_at <= 15 de enero`. Esto responde preguntas como: "Que mostraba nuestro cierre de fin de ano antes de las correcciones que hicimos en febrero?"

## Fechas Efectivas para Rangos

Algunos hechos no son puntos en el tiempo—son validos por un rango. Una suscripcion esta activa del 1 de marzo al 31 de marzo. Una poliza de seguro te cubre desde hoy hasta el proximo ano. El salario de un empleado es lo que es hasta el proximo aumento.

Para estos, necesitas periodos de validez:

```python
class EffectiveDatedMixin(TimeSemanticsMixin):
    valid_from = DateTimeField()  # SIN DEFAULT - el llamador debe especificar
    valid_to = DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
```

Nota que esto hereda de `TimeSemanticsMixin`. Aun tienes `effective_at` y `recorded_at` para el hecho del periodo de validez en si. Pero ahora tambien tienes `valid_from` y `valid_to` definiendo cuando aplica el hecho.

El campo `valid_to` es nullable. Un valor `NULL` significa "hasta nuevo aviso"—el hecho permanece valido indefinidamente hasta que algo explicitamente lo reemplace.

### Defaults: Modelo vs Servicio

Nota la diferencia entre `effective_at` y `valid_from`:

- **`effective_at` tiene un default** (`default=timezone.now`). Para eventos puntuales, "ahora" es usualmente correcto—la mayoria de los eventos se registran cuando suceden. El default es una conveniencia sensata.

- **`valid_from` NO tiene default**. Para periodos de validez, no hay default sensato. Cuando comienza este acuerdo? Cuando toma efecto esta asignacion? El llamador debe decidir.

Esto refleja un principio de diseno: **los modelos aplican correccion; los servicios proporcionan conveniencia.**

Si una funcion de servicio quiere defaultear `valid_from` a ahora, puede:

```python
def create_agreement(party_a, party_b, terms, valid_from=None, **kwargs):
    """El servicio proporciona default conveniente."""
    if valid_from is None:
        valid_from = timezone.now()

    return Agreement.objects.create(
        party_a=party_a,
        party_b=party_b,
        terms=terms,
        valid_from=valid_from,  # Requerido por el modelo
        **kwargs
    )
```

El modelo fuerza la pregunta: "Cuando se vuelve efectivo esto?" El servicio puede responder "ahora" como conveniencia, pero la pregunta siempre se hace explicitamente.

### El Patron Cerrar-Luego-Abrir

Al actualizar un registro con fecha efectiva, nunca modifiques el registro existente. En su lugar:

1. Establece el `valid_to` del registro viejo al punto de transicion
2. Crea un nuevo registro con `valid_from` en el punto de transicion

Esto preserva el historial. Siempre puedes reconstruir lo que era verdad en cualquier punto en el tiempo porque nunca destruiste el estado anterior.

```python
# El empleado recibe un aumento efectivo el 1 de abril
# Registro de salario actual: valid_from=1 de enero, valid_to=None

# Paso 1: Cerrar el registro actual
old_salary.valid_to = april_1st
old_salary.save()

# Paso 2: Crear el nuevo registro
new_salary = Salary.objects.create(
    employee=employee,
    amount=new_amount,
    valid_from=april_1st,
    valid_to=None
)
```

Despues de esto, tienes dos registros: uno valido del 1 de enero al 1 de abril, otro valido desde el 1 de abril en adelante. Consulta "as of 15 de marzo" y obtienes el salario viejo. Consulta "as of 15 de abril" y obtienes el nuevo. Consulta "actual" y obtienes el que tiene `valid_from <= now` y `valid_to IS NULL OR valid_to > now`.

## La Realidad Regulatoria

La semantica temporal no es solo sobre arquitectura limpia. Es legalmente requerida en muchas industrias.

### Servicios Financieros

La Autoridad Reguladora de la Industria Financiera (FINRA) requiere que los broker-dealers mantengan registros "de manera que permita que los registros se recreen por fecha." La Regla 4511 especifica que los registros deben preservarse en formato no borrable y no reescribible por periodos de retencion especificados.

La Regla 1.31 de la Comision de Comercio de Futuros de Commodities (CFTC) requiere que los registros sean "facilmente accesibles" y capaces de reproducir la informacion para cualquier fecha historica. Las firmas deben poder responder: "Cual era la posicion en esta fecha?"

### Salud

La Ley de Portabilidad y Responsabilidad del Seguro de Salud (HIPAA) requiere que las entidades cubiertas mantengan un rastro de auditoria de quien accedio a que informacion de salud protegida y cuando. Pero tambien requiere que los registros medicos reflejen la fecha real del servicio, no solo cuando se creo el registro.

Una nota del doctor ingresada el 15 de marzo sobre un examen del 10 de marzo debe indicar claramente ambas fechas. La fecha del tratamiento afecta decisiones medicas y facturacion; la fecha de entrada afecta el rastro de auditoria.

### Impuestos y Contabilidad

El IRS requiere que los negocios mantengan registros suficientes para fundamentar ingresos y deducciones. Para contribuyentes de base devengada, esto significa poder determinar cuando se gano el ingreso o se incurrio en gastos, independientemente de cuando fueron registrados.

Los Principios de Contabilidad Generalmente Aceptados (GAAP) requieren que las transacciones se registren en el periodo en que ocurrieron. Una entrada de ajuste hecha en febrero para una transaccion de diciembre debe indicar claramente que afecta las finanzas de diciembre.

## El Registro de Decision

Algunos eventos no son solo hechos—son decisiones. Un prestamo se aprueba. Un reclamo de seguro se paga. Un descuento se autoriza. Un reembolso se emite.

Las decisiones necesitan mas que marcas de tiempo. Necesitan evidencia de lo que se sabia en el momento en que se tomo la decision. Esto protege contra el fraude y los errores honestos.

```python
class Decision(TimeSemanticsMixin):
    # Quien tomo la decision
    actor_user = ForeignKey(AUTH_USER_MODEL, on_delete=PROTECT)
    on_behalf_of_user = ForeignKey(AUTH_USER_MODEL, null=True, blank=True)

    # Sobre que fue la decision
    target_type = ForeignKey(ContentType, on_delete=PROTECT)
    target_id = CharField(max_length=255)

    # Que se decidio
    action = CharField(max_length=50)

    # Evidencia: instantanea del estado al momento de la decision
    snapshot = JSONField()

    # Resultado de la decision
    outcome = JSONField(default=dict)

    # Cuando la decision se volvio irreversible
    finalized_at = DateTimeField(null=True, blank=True)
```

El campo `snapshot` es critico. Captura el estado del mundo en el momento en que se tomo la decision. Si los datos subyacentes cambian despues—la direccion del cliente se actualiza, el precio del producto cambia, el saldo de la cuenta se corrige—la instantanea preserva lo que se sabia al momento de la decision.

Esta es proteccion de auditoria. Cuando un regulador pregunta "Por que aprobaron este prestamo?", puedes mostrar exactamente que informacion vio el aprobador. Los cambios hechos despues de la decision son irrelevantes para si la decision estaba justificada en el momento en que se tomo.

## Idempotencia y Tiempo

Las fallas de red y los reintentos crean complejidad temporal. Un cliente hace clic en "Enviar" en un formulario de pago. La solicitud llega a tu servidor, el pago se procesa, pero la respuesta se pierde. El cliente hace clic en "Enviar" de nuevo. Sin proteccion, pagan dos veces.

La solucion es idempotencia—asegurar que solicitudes repetidas con la misma clave produzcan el mismo efecto que una sola solicitud.

```python
class IdempotencyKey(models.Model):
    scope = CharField(max_length=100)
    key = CharField(max_length=255)
    state = CharField(choices=State.choices)
    created_at = DateTimeField(auto_now_add=True)
    locked_at = DateTimeField(null=True)
    response_snapshot = JSONField(null=True)

    class Meta:
        unique_together = ['scope', 'key']
```

La primera solicitud crea un `IdempotencyKey` en estado `PROCESSING`. Ejecuta la operacion y almacena el resultado en `response_snapshot`. Cualquier solicitud subsecuente con la misma clave retorna la respuesta en cache sin re-ejecutar la operacion.

Esta es otra forma de semantica temporal: rastrear cuando ocurrio una operacion por primera vez para que los duplicados posteriores puedan detectarse y manejarse correctamente.

## Construyendolo Correctamente

El patron para sistemas conscientes del tiempo es sencillo:

1. **Usa TimeSemanticsMixin para todos los hechos de negocio.** Cada tabla que registra algo que sucedio debe tener `effective_at` y `recorded_at`.

2. **Usa EffectiveDatedMixin para cosas con periodos de validez.** Suscripciones, acuerdos, asignaciones de rol, precios—cualquier cosa que es valida por un rango de tiempo.

3. **Nunca modifiques el historial.** Cuando algo cambia, cierra el registro viejo y abre uno nuevo. Nunca actualices `effective_at` o `valid_from` en registros existentes.

4. **Haz `recorded_at` inmutable.** Es `auto_now_add=True` y nunca se actualiza. Este es tu rastro de auditoria.

5. **Captura instantaneas para decisiones.** Cuando se toma una decision, almacena la evidencia que la justifico. No confies en poder reconstruirla despues.

6. **Usa consultas "as of" por defecto.** Tu base de codigo debe hacer facil preguntar "que era verdad en el momento X" e incomodo preguntar "que es verdad ahora" sin especificar que significa "ahora".

### La Restriccion para IA

Al usar IA para generar codigo, la restriccion es explicita:

```
Todo modelo que registra hechos de negocio debe heredar de TimeSemanticsMixin.
Todo modelo con periodos de validez debe tener valid_from (SIN default) y valid_to (nullable).
Toda consulta que recupera datos de negocio debe especificar "as of" a menos que explicitamente busque estado actual.
recorded_at nunca debe modificarse despues de la insercion inicial.
Los registros historicos nunca deben actualizarse o eliminarse.
Las funciones de servicio pueden proporcionar defaults convenientes; los modelos no deben.
```

Una IA a la que se le dan estas restricciones generara codigo bitemporal por defecto. Una IA sin ellas generara sistemas que no pueden responder la pregunta de Watergate.

## Lo Que la IA Hace Mal

Sin restricciones explicitas, el codigo generado por IA tipicamente:

1. **Usa una sola marca de tiempo** llamada `created_at` que confunde tiempo de negocio y tiempo del sistema

2. **Actualiza registros in situ** en lugar de cerrar y abrir nuevas versiones

3. **Elimina datos viejos** durante operaciones de "limpieza", destruyendo rastros de auditoria

4. **Ignora la retroactividad** rechazando fechas en el pasado en lugar de registrarlas con `recorded_at` apropiado

5. **Consulta "estado actual"** sin considerar que "actual" es un punto en el tiempo, no una verdad absoluta

6. **Agrega defaults donde no pertenecen** — `valid_from = DateTimeField(default=timezone.now)` oculta omisiones accidentales en lugar de forzar decisiones explicitas

7. **Pone logica de tiempo en modelos** — Validacion como "valid_to debe ser despues de valid_from" pertenece a funciones de servicio o restricciones de base de datos, no en `model.save()`

La solucion es la misma de siempre: restricciones explicitas. Dile a la IA que significa la semantica temporal en tu dominio. Dile que cada hecho necesita dos marcas de tiempo. Dile que el historial es inmutable. Dile que los servicios proporcionan conveniencia, los modelos aplican correccion. La IA seguira estas reglas consistentemente—mas consistentemente que desarrolladores humanos que podrian tomar atajos bajo presion de plazos.

## Por Que Esto Importa Despues

La semantica temporal es la fundacion para:

- **El Libro Mayor**: Cada asiento contable tiene fechas efectivas y fechas de registro. Debes poder reconstruir lo que mostraban los libros en cualquier punto en el tiempo.

- **Acuerdos**: Los contratos tienen periodos efectivos. Los cambios de version crean nuevos registros con nuevas fechas de validez. Debes poder mostrar que terminos aplicaban cuando.

- **Documentos**: Los adjuntos y evidencia son inmutables una vez creados. Su relacion con eventos de negocio se rastrea temporalmente.

- **Flujos de trabajo**: Las maquinas de estado rastrean transiciones a lo largo del tiempo. Debes poder reconstruir la secuencia de eventos y cuando ocurrio cada transicion.

Si manejas mal el tiempo, todo sistema que depende de consultas temporales estara comprometido. Si lo manejas bien, puedes responder cualquier pregunta sobre que sucedio, cuando sucedio, y cuando te enteraste.

---

## Como Reconstruir Esta Primitiva

La semantica temporal es manejada por `django-decisioning` que proporciona rastreo bitemporal:

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-decisioning | `docs/prompts/django-decisioning.md` | ~50 tests |

### Usando el Prompt

```bash
cat docs/prompts/django-decisioning.md | claude

# Solicitud: "Comienza con el mixin temporal que proporciona
# campos effective_at y recorded_at, luego agrega el metodo de queryset as_of()."
```

### Restricciones Clave

- **Siempre dos marcas de tiempo**: `effective_at` (cuando sucedio) y `recorded_at` (cuando se registro)
- **recorded_at inmutable**: Se establece una vez en creacion, nunca cambia
- **Metodo as_of()**: Consulta estado en cualquier punto en el tiempo
- **Metodo current()**: Filtra a registros actualmente efectivos

Si Claude almacena solo una marca de tiempo unica o permite que `recorded_at` sea modificado, eso es una violacion de restriccion.

---

## Fuentes y Referencias

1. **Snodgrass, R.T.** (1999). *Developing Time-Oriented Database Applications in SQL*. Morgan Kaufmann.

2. **Estandar SQL:2011** - ISO/IEC 9075:2011, especificamente Parte 2 (Foundation) que introdujo soporte de tablas temporales.

3. **Audiencias de Watergate** - La famosa pregunta de Baker fue planteada el 28 de junio de 1973. *The New York Times*, 29 de junio de 1973.

4. **Retroactividad de Opciones** - "The Perfect Payday," *Wall Street Journal*, 18 de marzo de 2006. La investigacion que inicio el escandalo, que despues gano el Premio Pulitzer al Servicio Publico de 2007.

5. **Acciones de la SEC sobre Retroactividad de Opciones** - Comunicados de Litigio de la SEC, 2006-2007. Apple llego a un acuerdo por $14 millones (2007), ejecutivos de Brocade fueron acusados criminalmente.

6. **Falla del Misil Patriot** - "Patriot Missile Defense: Software Problem Led to System Failure at Dhahran, Saudi Arabia," Reporte GAO GAO/IMTEC-92-26, febrero 1992.

7. **Ley Sarbanes-Oxley** - Ley Publica 107-204, 116 Stat. 745, promulgada el 30 de julio de 2002. La Seccion 802 aborda retencion de registros y penalidades.

8. **Regla 4511 de FINRA** - Libros y Registros, requiriendo mantenimiento de registros en formato recuperable por periodos de retencion especificados.

9. **Regla 1.31 de CFTC** - Requisitos de mantenimiento de registros regulatorios y reportes para comercio de futuros de commodities.

10. **Regla de Seguridad de HIPAA** - 45 CFR Part 164, Subpart C, requiriendo controles de auditoria para informacion de salud protegida electronica.

---

*Estado: Completo*
