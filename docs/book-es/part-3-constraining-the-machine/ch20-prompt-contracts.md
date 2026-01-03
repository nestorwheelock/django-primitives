# Capítulo 20: Contratos de Prompt

## El Malentendido de $440 Millones

En 2012, Knight Capital Group desplegó nuevo software de trading que contenía un error. En 45 minutos, el software ejecutó millones de operaciones erróneas. Para cuando alguien entendió lo que estaba pasando, la firma había perdido $440 millones.

El error no era complejo. Durante el despliegue, los técnicos no copiaron una actualización de software a uno de ocho servidores. El código antiguo, inactivo durante años, de repente se activó y comenzó a comprar caro y vender barato en volúmenes enormes.

El análisis posterior reveló algo instructivo: el sistema no tenía un contrato claro sobre lo que el algoritmo de trading tenía permitido hacer. Tenía instrucciones sobre qué hacer, pero no restricciones sobre lo que nunca debía hacer.

Knight Capital solicitó protección por bancarrota cuatro días después.

---

## La Diferencia Entre Instrucciones y Contratos

Las instrucciones le dicen a un sistema qué hacer:
- "Ejecutar operaciones basadas en señales del mercado"
- "Constrúyeme un sistema de facturación"
- "Crear un modelo para rastrear pedidos"

Los contratos le dicen a un sistema qué debe y qué no debe hacer, independientemente de las instrucciones:
- "Nunca ejecutar más de $X en operaciones por minuto"
- "Las facturas son inmutables después de publicarse"
- "Los pedidos siempre deben referenciar una transacción del libro mayor"

Las instrucciones son generativas. Producen salida.

Los contratos son restrictivos. Previenen desastres.

Cuando trabajas con asistentes de codificación de IA, necesitas ambos. La mayoría de las personas solo proporcionan instrucciones.

---

## La Anatomía de un Contrato de Prompt

Un contrato de prompt tiene cuatro secciones. Cada una sirve un propósito diferente.

### Debe Hacer (Restricciones Positivas)

Estos son requisitos no negociables. No son sugerencias ni mejores prácticas. Son leyes.

```markdown
## Debe Hacer

- Usar claves primarias UUID para todos los modelos
- Implementar eliminación suave (campo deleted_at) para objetos de dominio
- Agregar semántica temporal (effective_at, recorded_at) a todos los eventos
- Usar DecimalField para todas las cantidades monetarias
- Heredar modelos de dominio de BaseModel
- Envolver mutaciones en @transaction.atomic
```

Una restricción Debe Hacer es algo por lo que rechazarías código si se viola. Si aceptarías código que usa IDs auto-incrementales "solo esta vez", entonces las claves primarias UUID no son un Debe Hacer. Es una preferencia.

Sé honesto sobre lo que realmente aplicarás.

### No Debe Hacer (Restricciones Negativas)

Estas son operaciones prohibidas. Son más poderosas que las restricciones Debe Hacer porque cierran explícitamente los vacíos legales.

```markdown
## No Debe Hacer

- Nunca usar claves primarias auto-incrementales
- Nunca almacenar moneda como float
- Nunca mutar registros históricos (publicar reversiones en su lugar)
- Nunca eliminar registros de auditoría
- Nunca eliminar permanentemente parties
- Nunca importar de capas arquitectónicas superiores
- Nunca usar datetimes sin zona horaria
```

Las restricciones negativas previenen las soluciones creativas que los sistemas de IA son particularmente buenos encontrando. Si dices "usar Decimal para dinero", una IA podría usar float para "cálculos intermedios". Si dices "nunca usar float para nada relacionado con moneda", el vacío legal se cierra.

### Invariantes (Propiedades del Sistema)

Las invariantes son propiedades que siempre deben ser verdaderas, independientemente de qué operaciones ocurran.

```markdown
## Invariantes

- Las transacciones del libro mayor siempre balancean (débitos = créditos)
- Los acuerdos son solo-agregar (sin ediciones, solo versiones)
- Los parties nunca se eliminan físicamente de la base de datos
- Cada encuentro tiene exactamente un estado actual
- Las entradas del registro de auditoría no pueden modificarse después de la creación
- La suma de entradas en cualquier transacción es igual a cero
```

Las invariantes difieren de las restricciones porque describen todo el sistema, no operaciones individuales. Una restricción dice "no hagas X." Una invariante dice "X siempre debe ser verdadero, sin importar qué."

### Salidas Aceptables (Criterios de Salida)

Estas definen cómo se ve una implementación correcta. Previenen que la IA afirme que algo está "terminado" cuando no cumple tus estándares.

```markdown
## Salidas Aceptables

- Todos los modelos heredan de UUIDModel o base apropiada
- Todas las funciones de servicio usan @transaction.atomic para mutaciones
- Todos los modelos de dominio tienen capacidad de eliminación suave
- La cobertura de pruebas excede el 95%
- Todas las pruebas pasan
- Las migraciones están incluidas y son reversibles
- El README incluye ejemplos de uso
```

Las Salidas Aceptables crean una lista de verificación. Si algún ítem no es verdadero, el trabajo no está completo.

---

## Por Qué los Contratos Funcionan Mejor Que las Instrucciones

Considera dos formas de pedir un sistema de facturación:

### Solo Instrucciones

```
Constrúyeme un sistema de facturación con:
- Clientes y proveedores
- Líneas de items
- Cálculo de impuestos
- Generación de PDF
- Envío de email
```

Esto produce un sistema de facturación. Probablemente funcionará. También probablemente tendrá:
- Números de factura auto-incrementales (falla en replicación)
- Facturas mutables (pesadilla de auditoría)
- Cantidades basadas en float (errores de redondeo)
- Sin pista de auditoría (fallo de cumplimiento)
- Precios obtenidos en vivo de productos (precios históricos perdidos)

La IA hizo exactamente lo que pediste. Pediste características. Obtuviste características.

### Contrato + Instrucciones

```
Constrúyeme un sistema de facturación.

## Debe Hacer
- Los números de factura usan IDs secuenciales de django-sequence
- Las líneas de items capturan instantánea del precio al momento de creación
- Todas las cantidades usan DecimalField con max_digits=19, decimal_places=4
- Las facturas referencian transacciones del libro mayor

## No Debe Hacer
- Nunca permitir modificación de factura después de publicar
- Nunca usar float para cantidades
- Nunca eliminar facturas (solo eliminación suave)
- Nunca recalcular totales de precios de productos en vivo

## Invariantes
- Las facturas publicadas son inmutables
- El total de factura es igual a la suma de líneas de items más impuestos
- Cada factura publicada tiene una transacción en el libro mayor

## Salidas Aceptables
- Todas las pruebas pasan
- Modelos de factura + línea de item con restricciones apropiadas
- La operación de publicar crea entradas en el libro mayor
- La operación de anular crea entradas de reversión
```

Esto produce un sistema de facturación que sobrevive auditorías.

---

## Capas de Contratos: Dónde Viven las Reglas

No todos los contratos pertenecen al mismo lugar. La pila de instrucciones del Capítulo 19 determina dónde vive cada regla.

### CLAUDE.md Global: Reglas Universales

Reglas que aplican a cada proyecto, cada archivo, cada tarea:

```markdown
# Estándares de Desarrollo (Global)

## Calidad de Código
- Cobertura de pruebas > 95%
- Sin comentarios TODO en código de producción
- Sin declaraciones print en código de producción

## Git
- Solo commits convencionales
- Nunca force push a main
- Nunca saltar hooks de pre-commit

## Seguridad
- Sin secretos en código
- Sin concatenación de strings SQL
- Sin eval() o exec()
```

Estas son reglas del sistema operativo. Nunca cambian.

### CLAUDE.md del Proyecto: Reglas del Proyecto

Reglas que aplican a este código base pero podrían diferir en otros proyectos:

```markdown
# Reglas de Django Primitives (Proyecto)

## Arquitectura
- Nunca importar de capas superiores
- La lógica de dominio vive en servicios, no en modelos
- Las vistas son delgadas (llaman servicios)

## Patrones
- Claves primarias UUID para todos los modelos
- Eliminación suave para entidades de dominio
- Semántica temporal para eventos
- GenericForeignKey para targets polimórficos

## Dependencias
- BaseModels es fundación (importar de)
- Parties proporciona identidad (importar de)
- Catalog depende de conceptos de Ledger
```

Estas son configuración del proyecto. Podrían cambiar entre versiones mayores.

### Prompts Por Paquete: Contratos Específicos

Reglas para reconstruir un paquete específico:

```markdown
# Contrato django-ledger

## Debe Hacer
- Transaction tiene múltiples entradas
- Entry tiene account, amount, entry_type
- Las entradas balancean (suma de amounts = 0)
- Las transacciones publicadas son inmutables

## No Debe Hacer
- Nunca permitir IDs de transacción negativos
- Nunca almacenar balance en Account (calcularlo)
- Nunca permitir modificación de entrada después de publicar transacción
- Nunca eliminar transacciones

## Invariantes
- Cada transacción balancea
- Balance de cuenta = suma de entradas en esa cuenta
- Las transacciones publicadas no pueden modificarse
```

Estas son especificaciones de aplicación. Se reescriben completamente cuando el paquete se reconstruye.

---

## Aplicación: Cómo los Contratos Se Convierten en Código

Un contrato que no se aplica es una sugerencia. La aplicación ocurre en cuatro niveles.

### Nivel 1: Aplicación por Prompt

La IA lee el contrato y lo sigue. Esta es la aplicación más débil porque depende de que la IA entienda y recuerde.

Para fortalecer la aplicación por prompt:
- Poner reglas críticas en el CLAUDE.md global (siempre cargado)
- Repetir restricciones críticas al inicio de cada tarea
- Usar restricciones negativas explícitas ("nunca") no solo positivas ("preferir")

### Nivel 2: Aplicación por Código

El código generado aplica el contrato a través de restricciones del modelo Django:

```python
class Invoice(BaseModel):
    """Una factura que se vuelve inmutable una vez publicada."""

    status = models.CharField(max_length=20, choices=InvoiceStatus.choices)
    posted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            original = Invoice.objects.get(pk=self.pk)
            if original.status == 'posted':
                raise ImmutableInvoiceError(
                    "Las facturas publicadas no pueden modificarse. Publica una reversión en su lugar."
                )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == 'posted':
            raise ImmutableInvoiceError(
                "Las facturas publicadas no pueden eliminarse. Publica una anulación en su lugar."
            )
        # Eliminación suave para facturas no publicadas
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])
```

La aplicación por código es más fuerte que la aplicación por prompt porque falla en tiempo de ejecución, incluso si la IA "olvida" la regla en una sesión posterior.

### Nivel 3: Aplicación por Base de Datos

La base de datos aplica el contrato a través de restricciones y triggers:

```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=~models.Q(amount=0),
            name='ledger_entry_non_zero_amount'
        ),
        models.CheckConstraint(
            check=models.Q(entry_type__in=['debit', 'credit']),
            name='ledger_entry_valid_type'
        ),
    ]
```

Para invariantes financieras críticas, los triggers de PostgreSQL proporcionan la aplicación más fuerte:

```sql
CREATE OR REPLACE FUNCTION check_transaction_balance()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT SUM(amount) FROM ledger_entry
        WHERE transaction_id = NEW.transaction_id) != 0 THEN
        RAISE EXCEPTION 'La transacción no balancea';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

La aplicación por base de datos sobrevive incluso a la manipulación directa de SQL.

### Nivel 4: Aplicación por Pruebas

Las pruebas verifican que los contratos se mantienen. Cada operación prohibida debe tener una prueba que demuestre que falla:

```python
def test_posted_invoice_immutable():
    """Las facturas publicadas no pueden modificarse."""
    invoice = Invoice.objects.create(
        customer=customer,
        status='posted',
        posted_at=timezone.now()
    )

    invoice.total = Decimal('999.99')
    with pytest.raises(ImmutableInvoiceError):
        invoice.save()

def test_posted_invoice_not_deletable():
    """Las facturas publicadas no pueden eliminarse."""
    invoice = Invoice.objects.create(
        customer=customer,
        status='posted',
        posted_at=timezone.now()
    )

    with pytest.raises(ImmutableInvoiceError):
        invoice.delete()

def test_transaction_must_balance():
    """Las transacciones con entradas desbalanceadas fallan."""
    with pytest.raises(ValidationError):
        Transaction.objects.create(
            entries=[
                Entry(account=cash, amount=Decimal('100'), entry_type='debit'),
                Entry(account=revenue, amount=Decimal('99'), entry_type='credit'),
            ]
        )
```

La aplicación por pruebas es la última red de seguridad. Cuando todo lo demás falla, las pruebas capturan violaciones antes del despliegue.

---

## La Plantilla de Contrato

Usa esta plantilla para cada paquete primitivo:

```markdown
# Contrato: [Nombre del Paquete]

## Propósito
[Una oración: qué problema resuelve este paquete]

## Dependencias
[Paquetes de los que depende, tanto runtime como conceptuales]

## Debe Hacer
- [ ] [Restricción positiva 1]
- [ ] [Restricción positiva 2]
- [ ] [Restricción positiva 3]

## No Debe Hacer
- [ ] Nunca [operación prohibida 1]
- [ ] Nunca [operación prohibida 2]
- [ ] Nunca [operación prohibida 3]

## Invariantes
- [ ] [Propiedad del sistema que siempre debe ser verdadera 1]
- [ ] [Propiedad del sistema que siempre debe ser verdadera 2]

## Especificación de Modelos
[Campos exactos, tipos, restricciones para cada modelo]

## Funciones de Servicio
[Firmas exactas de funciones y comportamientos]

## Casos de Prueba
[Lista numerada de pruebas que deben pasar]

## Salidas Aceptables
- [ ] Todas las pruebas pasan
- [ ] Cobertura > 95%
- [ ] Migraciones incluidas
- [ ] README con ejemplos
```

---

## Ejercicio Práctico: Escribe un Contrato

Toma una característica que planeas construir. Antes de escribir cualquier código, escribe su contrato.

**Paso 1: Define Debe Hacer**

¿Cuáles son los requisitos no negociables? Si la implementación no tiene estos, está mal.

**Paso 2: Define No Debe Hacer**

¿Qué haría peligrosa esta implementación? ¿Qué atajos podría tomar una IA que causarían problemas después?

**Paso 3: Define Invariantes**

¿Qué propiedades siempre deben ser verdaderas? Si una operación viola estas, el sistema está corrupto.

**Paso 4: Define Salidas Aceptables**

¿Cómo sabrás que está terminado? ¿Cuáles son los entregables concretos?

**Paso 5: Prueba Tu Contrato**

Dale tu contrato a una IA sin instrucciones adicionales. ¿La salida cumple tus estándares? Si no, tu contrato tiene vacíos.

---

## Lo Que la IA Se Equivoca Sobre los Contratos

Los sistemas de IA son excelentes siguiendo instrucciones. Son menos confiables manteniendo restricciones a través de sesiones largas o múltiples archivos.

### Deriva de Contrato

En una sesión larga, la IA puede "olvidar" restricciones anteriores y volver a los valores predeterminados:
- La sesión comienza con "nunca usar auto-incremento"
- Tres horas después, la IA genera `id = models.AutoField()`
- ¿Por qué? Limitaciones de la ventana de contexto, o la restricción se declaró una vez y nunca se reforzó

**Solución:** Poner restricciones críticas en archivos siempre cargados (CLAUDE.md), y repetirlas al comenzar tareas relacionadas.

### Soluciones Creativas

La IA encuentra soluciones inesperadas que técnicamente satisfacen restricciones pero violan su intención:
- Restricción: "Nunca eliminar registros"
- Solución de IA: `UPDATE table SET all_fields = NULL WHERE id = X`
- Técnicamente no es una declaración DELETE. Los datos se fueron.

**Solución:** Usar restricciones negativas explícitas. "Nunca eliminar registros Y nunca anular campos para simular eliminación Y nunca mover registros a tablas de archivo."

### Violaciones Confiadas

La IA puede explicar con confianza por qué una restricción no aplica en este caso:
- Restricción: "Nunca usar float para dinero"
- IA: "Para este cálculo intermedio, float está bien porque redondeamos al final"
- Esto está mal, pero suena razonable

**Solución:** Hacer las restricciones absolutas. "Nunca usar float para dinero, en ningún cálculo, en ningún paso, por ninguna razón."

---

## Por Qué Esto Importa Después

El pensamiento de contratos cambia cómo abordas el desarrollo asistido por IA.

Sin contratos, escribes prompts y esperas lo mejor. Capturas bugs en revisión, en pruebas, en producción. Cada bug te enseña algo que deberías haber especificado.

Con contratos, especificas restricciones por adelantado. Los bugs se hacen visibles antes de que se escriba el código. La IA tiene límites claros. Tu proceso de revisión se convierte en "¿esto coincide con el contrato?" en lugar de "¿esto parece razonable?"

En el próximo capítulo, veremos cómo los contratos se combinan con la generación schema-first para crear paquetes generados por IA verdaderamente reproducibles.

---

## Resumen

| Concepto | Propósito |
|----------|-----------|
| Debe Hacer | Requisitos no negociables |
| No Debe Hacer | Operaciones explícitamente prohibidas |
| Invariantes | Propiedades del sistema que siempre deben mantenerse |
| Salidas Aceptables | Criterios de salida para completar |
| Aplicación por prompt | La IA sigue reglas del contexto |
| Aplicación por código | Excepciones de runtime en violaciones |
| Aplicación por base de datos | Restricciones que sobreviven SQL directo |
| Aplicación por pruebas | Verificación automatizada de contratos |

El objetivo no es restringir la creatividad de la IA. El objetivo es canalizar esa creatividad dentro de límites seguros.

Knight Capital no tenía restricciones. Tenían características. Enviaron rápido. Luego enviaron $440 millones por la puerta en 45 minutos.

Las restricciones no son el enemigo de la productividad. Son la precondición para la seguridad.

---

## Fuentes

- SEC. (2013). *In the Matter of Knight Capital Americas LLC: Administrative Proceeding File No. 3-15570*. https://www.sec.gov/litigation/admin/2013/34-70694.pdf
- Patterson, S. (2012). "Knight Capital Says Trading Glitch Cost It $440 Million." *The Wall Street Journal*.
