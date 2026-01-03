# Capítulo 14: Registro de Trabajo

> "¿Qué hiciste y cuánto tiempo te tomó?"

---

Todo negocio necesita rastrear el trabajo. Horas facturables. Tiempo de proyecto. Completación de tareas. Entrega de servicios. Los detalles varían—los abogados facturan en incrementos de seis minutos, los contratistas facturan por día, los consultores facturan por proyecto—pero la pregunta subyacente es siempre la misma: ¿qué trabajo se hizo, por quién, cuándo y por cuánto tiempo?

El primitivo Worklog captura entradas de trabajo con la precisión que requieren la facturación, la nómina y la gestión de proyectos.

## El Problema que Resuelven los Worklogs

El seguimiento del trabajo falla de maneras predecibles:

**Tiempo impreciso.** "Trabajé en el Proyecto X hoy" no es facturable. "Trabajé en el Proyecto X de 9:00 AM a 11:47 AM" sí lo es. La diferencia es si tus facturas sobreviven al escrutinio.

**Contexto faltante.** Tiempo sin descripción es inútil. "3 horas" no le dice nada al cliente. "3 horas: implementé flujo de autenticación, corregí bug de redirección de login, escribí pruebas unitarias" justifica la factura.

**Sin vinculación.** El trabajo ocurre en el contexto de algo—un proyecto, un ticket, un engagement de cliente, una llamada de servicio. Entradas de tiempo independientes no pueden reconciliarse contra contratos o presupuestos.

**Historial mutable.** Hojas de tiempo que pueden editarse silenciosamente después del hecho crean fallas de auditoría. ¿El empleado realmente trabajó esas horas, o ajustó la hoja de tiempo cuando se dio cuenta de que estaba corto?

**Brechas de aprobación.** Tiempo ingresado pero nunca aprobado existe en el limbo. ¿Es facturable? ¿Se paga? Nadie sabe hasta que alguien lo revisa.

## El Modelo Worklog

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django_basemodels.models import SoftDeleteModel
from decimal import Decimal


class WorklogEntry(SoftDeleteModel):
    """A single work entry with time tracking."""

    # Who did the work
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='worklog_entries'
    )

    # What they worked on (generic - can be project, ticket, client, etc.)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # When the work happened (business time)
    work_date = models.DateField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Duration (can be entered directly or calculated)
    duration_minutes = models.PositiveIntegerField()

    # What was done
    description = models.TextField()
    work_type = models.CharField(max_length=100, blank=True)  # e.g., "development", "meeting", "review"

    # Billing information
    is_billable = models.BooleanField(default=True)
    billing_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    billing_rate_currency = models.CharField(max_length=3, default='USD')

    # Approval workflow
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('billed', 'Billed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='worklog_submissions'
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='worklog_approvals'
    )

    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-work_date', '-started_at']
        indexes = [
            models.Index(fields=['worker', 'work_date']),
            models.Index(fields=['status', 'work_date']),
            models.Index(fields=['target_content_type', 'target_id']),
        ]

    def clean(self):
        super().clean()

        # Validate time range if both are provided
        if self.started_at and self.ended_at:
            if self.ended_at <= self.started_at:
                raise ValidationError("End time must be after start time")

            # Calculate duration from time range
            delta = self.ended_at - self.started_at
            calculated_minutes = int(delta.total_seconds() / 60)

            # If duration_minutes wasn't set, calculate it
            if not self.duration_minutes:
                self.duration_minutes = calculated_minutes

    @property
    def duration_hours(self):
        """Duration in decimal hours."""
        return Decimal(self.duration_minutes) / Decimal(60)

    @property
    def billable_amount(self):
        """Calculate billable amount if rate is set."""
        if self.billing_rate and self.is_billable:
            return self.duration_hours * self.billing_rate
        return Decimal('0.00')

    def submit(self, by_user=None):
        """Submit entry for approval."""
        if self.status != 'draft':
            raise ValidationError("Only draft entries can be submitted")

        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.submitted_by = by_user or self.worker
        self.save()

    def approve(self, by_user):
        """Approve a submitted entry."""
        if self.status != 'submitted':
            raise ValidationError("Only submitted entries can be approved")

        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = by_user
        self.save()

    def reject(self, by_user, reason):
        """Reject a submitted entry."""
        if self.status != 'submitted':
            raise ValidationError("Only submitted entries can be rejected")

        self.status = 'rejected'
        self.rejection_reason = reason
        self.approved_by = by_user  # Track who rejected
        self.approved_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.worker} - {self.work_date} - {self.duration_minutes}min"
```

## QuerySet de Worklog

```python
from django.db import models
from django.utils import timezone
from datetime import timedelta


class WorklogQuerySet(models.QuerySet):
    """QuerySet with worklog-specific filters."""

    def for_worker(self, user):
        """Entries for a specific worker."""
        return self.filter(worker=user)

    def for_target(self, target):
        """Entries for a specific target object."""
        ct = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=ct,
            target_id=str(target.pk)
        )

    def for_date_range(self, start_date, end_date):
        """Entries within a date range."""
        return self.filter(
            work_date__gte=start_date,
            work_date__lte=end_date
        )

    def this_week(self):
        """Entries from current week."""
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return self.for_date_range(start_of_week, end_of_week)

    def this_month(self):
        """Entries from current month."""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return self.for_date_range(start_of_month, end_of_month)

    def billable(self):
        """Only billable entries."""
        return self.filter(is_billable=True)

    def non_billable(self):
        """Only non-billable entries."""
        return self.filter(is_billable=False)

    def pending_approval(self):
        """Entries awaiting approval."""
        return self.filter(status='submitted')

    def approved(self):
        """Approved entries."""
        return self.filter(status='approved')

    def unbilled(self):
        """Approved but not yet billed."""
        return self.filter(status='approved', is_billable=True)

    def total_minutes(self):
        """Sum of duration_minutes."""
        result = self.aggregate(total=models.Sum('duration_minutes'))
        return result['total'] or 0

    def total_hours(self):
        """Sum of hours as decimal."""
        return Decimal(self.total_minutes()) / Decimal(60)

    def total_billable_amount(self):
        """Sum of billable amounts."""
        total = Decimal('0.00')
        for entry in self.billable().filter(billing_rate__isnull=False):
            total += entry.billable_amount
        return total
```

## Agregación de Hojas de Tiempo

Las entradas individuales son útiles, pero las hojas de tiempo las agregan:

```python
class Timesheet(SoftDeleteModel):
    """Weekly or monthly timesheet aggregating work entries."""

    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='timesheets'
    )

    period_start = models.DateField()
    period_end = models.DateField()

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='approved_timesheets'
    )

    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['worker', 'period_start', 'period_end']
        ordering = ['-period_start']

    @property
    def entries(self):
        """All worklog entries in this timesheet's period."""
        return WorklogEntry.objects.filter(
            worker=self.worker,
            work_date__gte=self.period_start,
            work_date__lte=self.period_end
        )

    @property
    def total_hours(self):
        """Total hours in this timesheet."""
        return self.entries.total_hours()

    @property
    def billable_hours(self):
        """Billable hours in this timesheet."""
        return self.entries.billable().total_hours()

    def submit(self):
        """Submit timesheet for approval."""
        if self.status != 'open':
            raise ValidationError("Only open timesheets can be submitted")

        # Submit all draft entries in this period
        for entry in self.entries.filter(status='draft'):
            entry.submit()

        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.save()

    def approve(self, by_user):
        """Approve timesheet and all its entries."""
        if self.status != 'submitted':
            raise ValidationError("Only submitted timesheets can be approved")

        # Approve all submitted entries
        for entry in self.entries.filter(status='submitted'):
            entry.approve(by_user)

        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = by_user
        self.save()
```

## Integración con Facturación

Las entradas de worklog aprobadas alimentan el sistema de facturación:

```python
from django.db import transaction


def generate_invoice_from_worklog(client, start_date, end_date):
    """Generate invoice from approved worklog entries."""
    from django_ledger.models import Invoice, InvoiceLineItem

    entries = WorklogEntry.objects.filter(
        target=client,  # Assumes client is the target
        status='approved',
        is_billable=True,
        work_date__gte=start_date,
        work_date__lte=end_date
    )

    if not entries.exists():
        return None

    with transaction.atomic():
        invoice = Invoice.objects.create(
            customer=client,
            invoice_date=timezone.now().date()
        )

        for entry in entries:
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"{entry.work_date}: {entry.description}",
                quantity=entry.duration_hours,
                unit_price=entry.billing_rate,
                amount=entry.billable_amount
            )

            # Mark as billed
            entry.status = 'billed'
            entry.save()

        return invoice
```

## Soporte de Temporizador

Para seguimiento de tiempo en tiempo real:

```python
class WorklogTimer(models.Model):
    """Active timer for real-time tracking."""

    worker = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_timer'
    )

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    started_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    work_type = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Active Timer"

    @property
    def elapsed_minutes(self):
        """Minutes elapsed since timer started."""
        delta = timezone.now() - self.started_at
        return int(delta.total_seconds() / 60)

    def stop(self):
        """Stop timer and create worklog entry."""
        entry = WorklogEntry.objects.create(
            worker=self.worker,
            target_content_type=self.target_content_type,
            target_id=self.target_id,
            work_date=self.started_at.date(),
            started_at=self.started_at,
            ended_at=timezone.now(),
            duration_minutes=self.elapsed_minutes,
            description=self.description,
            work_type=self.work_type
        )
        self.delete()
        return entry
```

## Reglas de Redondeo

Diferentes industrias tienen diferentes convenciones de redondeo:

```python
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP


class RoundingRule:
    """Billing time rounding strategies."""

    @staticmethod
    def no_rounding(minutes):
        """Bill exact minutes."""
        return minutes

    @staticmethod
    def round_to_quarter_hour(minutes):
        """Round up to nearest 15 minutes (common for consultants)."""
        return ((minutes + 14) // 15) * 15

    @staticmethod
    def round_to_sixth_hour(minutes):
        """Round up to nearest 6 minutes (legal billing standard)."""
        return ((minutes + 5) // 6) * 6

    @staticmethod
    def round_to_half_hour(minutes):
        """Round up to nearest 30 minutes."""
        return ((minutes + 29) // 30) * 30

    @staticmethod
    def minimum_increment(minutes, minimum=15):
        """Apply minimum billing increment."""
        if minutes == 0:
            return 0
        return max(minutes, minimum)


# Usage
raw_minutes = 37
billable_minutes = RoundingRule.round_to_quarter_hour(raw_minutes)  # Returns 45
```

## Cálculo de Horas Extra

```python
def calculate_overtime(worker, week_start, regular_hours=40):
    """Calculate regular and overtime hours for a week."""
    week_end = week_start + timedelta(days=6)

    entries = WorklogEntry.objects.filter(
        worker=worker,
        work_date__gte=week_start,
        work_date__lte=week_end,
        status__in=['approved', 'billed']
    )

    total_hours = entries.total_hours()

    regular = min(total_hours, Decimal(regular_hours))
    overtime = max(total_hours - Decimal(regular_hours), Decimal(0))

    return {
        'total_hours': total_hours,
        'regular_hours': regular,
        'overtime_hours': overtime,
        'entries': entries
    }
```

## Por Qué Esto Importa Después

El primitivo Worklog se conecta con:

- **Identidad** (Capítulo 6): Los trabajadores son partes. Los clientes son partes.
- **Acuerdos** (Capítulo 8): Las tarifas de facturación vienen de acuerdos de servicio.
- **Libro Mayor** (Capítulo 10): Las entradas facturables se convierten en líneas de factura.
- **Flujo de Trabajo** (Capítulo 11): La aprobación es una máquina de estados.
- **Auditoría** (Capítulo 13): Cada entrada, aprobación y rechazo se registra.

El seguimiento de tiempo parece simple hasta que necesitas:
- Probar a un cliente que se realizaron 47.5 horas de trabajo
- Calcular horas extra a través de límites de días festivos
- Reconciliar hojas de tiempo contra presupuestos de proyecto
- Generar facturas que sobrevivan a auditorías

El primitivo Worklog maneja la complejidad para que tu aplicación no tenga que reinventarla.

---

## Cómo Reconstruir Este Primitivo

| Paquete | Archivo de Prompt | Cantidad de Pruebas |
|---------|-------------------|---------------------|
| django-worklog | `docs/prompts/django-worklog.md` | ~35 pruebas |

### Usando el Prompt

```bash
cat docs/prompts/django-worklog.md | claude

# Request: "Implement WorklogEntry with GenericFK target,
# duration tracking (minutes not hours), and approval workflow.
# Then add Timesheet aggregation."
```

### Restricciones Clave

- **Duración en minutos**: Campo entero, nunca horas float
- **Tarifa de facturación como Decimal**: Nunca FloatField para dinero
- **Flujo de trabajo de aprobación**: draft → submitted → approved → billed
- **Objetivo GenericFK**: Las entradas de tiempo se adjuntan a cualquier elemento de trabajo

Si Claude almacena la duración como horas o usa Float para tarifas, eso es una violación de restricción.

---

## Referencias

- Requisitos de registro de tiempo de la Fair Labor Standards Act (FLSA)
- Reglas del American Bar Association para facturación legal
- Estándares de seguimiento de tiempo del Project Management Institute
- Publicación 15-B del IRS sobre registros de tiempo de empleados

---

*Estado: Borrador*
