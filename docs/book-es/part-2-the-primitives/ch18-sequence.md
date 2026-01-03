# Capítulo 18: Secuencia

> "Números que nunca se saltan, nunca se repiten, y nunca mienten."

---

Algunos números deben ser secuenciales. Números de factura. Números de cheque. Números de pedido. Números de recibo. Reguladores, auditores y contadores todos esperan secuencias sin huecos—números que incrementan exactamente en uno, sin saltos ni duplicados.

La primitiva de Secuencia proporciona numeración sin huecos con la precisión que el cumplimiento normativo requiere.

## El Problema que Resuelven las Secuencias

La numeración secuencial falla de maneras predecibles:

**Huecos por rollbacks.** Una transacción de base de datos asigna el número de factura 1001, luego falla. La siguiente transacción exitosa obtiene 1002. Los auditores preguntan: "¿Dónde está la factura 1001?"

**Duplicados por concurrencia.** Dos solicitudes leen el número actual, ambas lo incrementan, ambas guardan. Ahora tienes dos facturas #1001.

**Explicaciones faltantes.** Cuando existen huecos, no hay registro del porqué. ¿Fue una factura anulada? ¿Un pedido eliminado? ¿Un error del sistema?

**Inconsistencia de formato.** "FAC-001" vs "FAC001" vs "FAC-1" vs "1". Los humanos usan formato inconsistente; los sistemas no deberían.

**Sin aislamiento de espacio de nombres.** Diferentes contextos necesitan diferentes secuencias. Los números de factura no deberían compartir una secuencia con los números de pedido.

## El Modelo SequenceDefinition

```python
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django_basemodels.models import TimestampedModel


class SequenceDefinition(TimestampedModel):
    """Definición de una secuencia sin huecos."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    # Plantilla de formato: {prefix}{number:0{padding}d}{suffix}
    prefix = models.CharField(max_length=50, blank=True)
    suffix = models.CharField(max_length=50, blank=True)
    padding = models.PositiveIntegerField(default=6)  # Número de dígitos

    # Punto de inicio
    start_value = models.PositiveIntegerField(default=1)
    current_value = models.PositiveIntegerField(default=0)

    # Incremento (usualmente 1, pero algunos sistemas usan incrementos mayores)
    increment = models.PositiveIntegerField(default=1)

    # Opcional: Período de reinicio
    RESET_CHOICES = [
        ('never', 'Nunca'),
        ('yearly', 'Anual'),
        ('monthly', 'Mensual'),
        ('daily', 'Diario'),
    ]
    reset_period = models.CharField(max_length=20, choices=RESET_CHOICES, default='never')
    last_reset_at = models.DateTimeField(null=True, blank=True)

    # ¿Incluir fecha en formato?
    include_year = models.BooleanField(default=False)
    include_month = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def format_number(self, value, reference_date=None):
        """Formatea un valor de secuencia según la plantilla."""
        from django.utils import timezone

        if reference_date is None:
            reference_date = timezone.now()

        parts = []

        if self.prefix:
            parts.append(self.prefix)

        if self.include_year:
            parts.append(str(reference_date.year))

        if self.include_month:
            parts.append(f"{reference_date.month:02d}")

        # Número con relleno
        parts.append(f"{value:0{self.padding}d}")

        if self.suffix:
            parts.append(self.suffix)

        return ''.join(parts)

    @transaction.atomic
    def next_value(self):
        """
        Obtiene el siguiente valor en la secuencia.
        Usa SELECT FOR UPDATE para prevenir duplicados.
        """
        from django.utils import timezone

        # Bloquear esta fila para actualización
        seq = SequenceDefinition.objects.select_for_update().get(pk=self.pk)

        # Verificar si se necesita reinicio
        now = timezone.now()
        needs_reset = False

        if seq.reset_period == 'yearly' and seq.last_reset_at:
            if now.year > seq.last_reset_at.year:
                needs_reset = True
        elif seq.reset_period == 'monthly' and seq.last_reset_at:
            if (now.year, now.month) > (seq.last_reset_at.year, seq.last_reset_at.month):
                needs_reset = True
        elif seq.reset_period == 'daily' and seq.last_reset_at:
            if now.date() > seq.last_reset_at.date():
                needs_reset = True

        if needs_reset:
            seq.current_value = seq.start_value - seq.increment
            seq.last_reset_at = now

        # Incrementar
        seq.current_value += seq.increment
        seq.save()

        return seq.current_value

    def next_formatted(self):
        """Obtiene siguiente valor formateado según la plantilla."""
        value = self.next_value()
        return self.format_number(value)

    def preview_next(self):
        """Vista previa del siguiente valor sin consumirlo."""
        return self.format_number(self.current_value + self.increment)

    def __str__(self):
        return f"{self.name}: {self.preview_next()}"
```

## Asignación de Secuencia

Rastrea qué números fueron asignados a qué:

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class SequenceAllocation(models.Model):
    """Registro de una asignación de número de secuencia."""

    sequence = models.ForeignKey(
        SequenceDefinition,
        on_delete=models.PROTECT,
        related_name='allocations'
    )
    value = models.PositiveIntegerField()
    formatted_value = models.CharField(max_length=100)

    # A qué fue asignado esto
    allocated_to_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    allocated_to_id = models.CharField(max_length=255, blank=True)
    allocated_to = GenericForeignKey('allocated_to_type', 'allocated_to_id')

    allocated_at = models.DateTimeField(auto_now_add=True)
    allocated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True
    )

    # Estado
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('voided', 'Anulado'),
        ('reserved', 'Reservado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='voided_sequences'
    )
    void_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ['sequence', 'value']
        ordering = ['sequence', 'value']
        indexes = [
            models.Index(fields=['formatted_value']),
            models.Index(fields=['allocated_to_type', 'allocated_to_id']),
        ]

    def void(self, by_user, reason):
        """Anula esta asignación."""
        from django.utils import timezone

        if self.status == 'voided':
            raise ValidationError("Ya anulado")

        self.status = 'voided'
        self.voided_at = timezone.now()
        self.voided_by = by_user
        self.void_reason = reason
        self.save()

    def __str__(self):
        return f"{self.formatted_value} ({self.status})"
```

## Asignando Números

```python
from django.db import transaction


def allocate_sequence_number(sequence_name, target=None, allocated_by=None):
    """
    Asigna un número de secuencia, opcionalmente enlazándolo a un objeto objetivo.
    Retorna el número de secuencia formateado.
    """
    with transaction.atomic():
        seq = SequenceDefinition.objects.get(name=sequence_name)
        value = seq.next_value()
        formatted = seq.format_number(value)

        allocation_kwargs = {
            'sequence': seq,
            'value': value,
            'formatted_value': formatted,
            'allocated_by': allocated_by,
        }

        if target:
            allocation_kwargs['allocated_to_type'] = ContentType.objects.get_for_model(target)
            allocation_kwargs['allocated_to_id'] = str(target.pk)

        SequenceAllocation.objects.create(**allocation_kwargs)

        return formatted


# Uso
invoice_number = allocate_sequence_number('invoices', target=invoice, allocated_by=request.user)
# Retorna: "FAC-2024-000042"
```

## Detección de Huecos e Informes

```python
def find_gaps(sequence_name):
    """Encuentra huecos en una secuencia."""
    seq = SequenceDefinition.objects.get(name=sequence_name)
    allocations = SequenceAllocation.objects.filter(
        sequence=seq
    ).order_by('value').values_list('value', flat=True)

    gaps = []
    expected = seq.start_value

    for actual in allocations:
        while expected < actual:
            gaps.append(expected)
            expected += seq.increment
        expected = actual + seq.increment

    return gaps


def sequence_report(sequence_name):
    """Genera un informe sobre el uso de la secuencia."""
    seq = SequenceDefinition.objects.get(name=sequence_name)
    allocations = SequenceAllocation.objects.filter(sequence=seq)

    return {
        'sequence_name': seq.name,
        'current_value': seq.current_value,
        'total_allocated': allocations.count(),
        'active': allocations.filter(status='active').count(),
        'voided': allocations.filter(status='voided').count(),
        'gaps': find_gaps(sequence_name),
        'first_allocation': allocations.order_by('allocated_at').first(),
        'last_allocation': allocations.order_by('-allocated_at').first(),
    }
```

## Secuencias Multi-Inquilino

Para aplicaciones SaaS donde cada inquilino necesita sus propias secuencias:

```python
class TenantSequence(TimestampedModel):
    """Secuencia específica de inquilino."""

    tenant_id = models.CharField(max_length=255)
    sequence_type = models.CharField(max_length=100)  # 'invoice', 'order', etc.

    prefix = models.CharField(max_length=50, blank=True)
    current_value = models.PositiveIntegerField(default=0)
    padding = models.PositiveIntegerField(default=6)

    class Meta:
        unique_together = ['tenant_id', 'sequence_type']

    @classmethod
    @transaction.atomic
    def next_for_tenant(cls, tenant_id, sequence_type):
        """Obtiene el siguiente número para la secuencia de un inquilino."""
        seq, created = cls.objects.select_for_update().get_or_create(
            tenant_id=tenant_id,
            sequence_type=sequence_type,
            defaults={'current_value': 0}
        )

        seq.current_value += 1
        seq.save()

        if seq.prefix:
            return f"{seq.prefix}{seq.current_value:0{seq.padding}d}"
        return f"{seq.current_value:0{seq.padding}d}"
```

## Integración con Modelos

Agrega números de secuencia a modelos automáticamente:

```python
class SequencedModelMixin(models.Model):
    """Mixin para modelos que necesitan un número de secuencia."""

    sequence_number = models.CharField(max_length=100, unique=True, blank=True)

    SEQUENCE_NAME = None  # Sobrescribir en subclase

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.sequence_number and self.SEQUENCE_NAME:
            self.sequence_number = allocate_sequence_number(
                self.SEQUENCE_NAME,
                target=self
            )
        super().save(*args, **kwargs)


# Uso
class Invoice(SequencedModelMixin, SoftDeleteModel):
    SEQUENCE_NAME = 'invoices'

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    # ... otros campos ...
```

## Por Qué Esto Importa Después

La primitiva de Secuencia se conecta con:

- **Libro Mayor** (Capítulo 10): Números de transacción, números de cheque.
- **Acuerdos** (Capítulo 8): Números de contrato.
- **Auditoría** (Capítulo 13): Las asignaciones de secuencia se registran.
- **Documentos** (Capítulo 16): Números de referencia de documentos.

La numeración secuencial parece simple hasta que necesitas:
- Probar a un auditor que no faltan números de factura
- Explicar por qué la factura #1047 fue anulada
- Reiniciar secuencias a fin de año mientras preservas el historial
- Soportar múltiples inquilinos con secuencias aisladas

La primitiva de Secuencia maneja la complejidad para que tu aplicación no tenga que reinventarla.

---

## Cómo Reconstruir Esta Primitiva

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-sequence | `docs/prompts/django-sequence.md` | ~25 tests |

### Usando el Prompt

```bash
cat docs/prompts/django-sequence.md | claude

# Solicitud: "Implementar SequenceDefinition con patrones de formato configurables,
# luego SequenceAllocation para rastrear cada número asignado.
# Usar select_for_update() para concurrencia."
```

### Restricciones Clave

- **Incremento atómico**: Usar `select_for_update()` para prevenir condiciones de carrera
- **Rastreo de asignaciones**: Cada número se registra con quién/qué/cuándo
- **Soporte de anulación**: Los números pueden ser anulados pero los registros de asignación persisten
- **Detección de huecos**: Puede identificar números faltantes en una secuencia

Si Claude permite acceso concurrente sin bloqueo u omite el rastreo de asignaciones, eso es una violación de restricción.

---

## Referencias

- Publicación 583 del IRS: Requisitos de retención de registros para numeración secuencial
- Ley Sarbanes-Oxley Sección 802: Retención e integridad de documentos
- Principios de Contabilidad Generalmente Aceptados (PCGA): Estándares de numeración de facturas

---

*Estado: Borrador*
