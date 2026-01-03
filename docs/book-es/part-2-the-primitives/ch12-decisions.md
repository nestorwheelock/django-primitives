# Capítulo 12: Decisiones

> "No es la especie más fuerte la que sobrevive, ni la más inteligente. Es la que mejor se adapta al cambio."
>
> — Frecuentemente mal atribuido a Darwin, pero el punto se mantiene: las decisiones deben ser rastreables para sobrevivir al escrutinio.

---

El 2 de diciembre de 2001, Enron se declaró en bancarrota. En su pico, Enron era la séptima empresa más grande de Estados Unidos. En semanas, no valía nada. Los accionistas perdieron $74 mil millones. Los empleados perdieron sus ahorros de jubilación.

El escándalo reveló un problema fundamental: se habían tomado decisiones—miles de millones de dólares en decisiones—pero nadie podía reconstruir quién las tomó, qué información tenían, o por qué eligieron como lo hicieron. El rastro de decisiones era una ficción. Arthur Andersen, el auditor de Enron, destruyó documentos. Los ejecutivos alegaron ignorancia. La junta directiva alegó que fueron engañados.

La Ley Sarbanes-Oxley de 2002 surgió directamente de este fracaso. La Sección 404 requiere que las empresas públicas mantengan "controles internos" suficientes para asegurar la confiabilidad de los informes financieros. En la práctica, esto significa: debes poder probar quién decidió qué, cuándo y con qué información.

Pero SOX aplica a empresas públicas. El principio aplica en todas partes. Cada aprobación de préstamo, cada denegación de reclamo de seguro, cada decisión de tratamiento médico—todas estas son decisiones que pueden ser cuestionadas después. Cuando lo sean, necesitas más que logs. Necesitas un registro de decisión.

## La Anatomía de una Decisión

Una decisión no es un evento. Es un registro estructurado de:

1. **Qué** se estaba decidiendo (el objetivo)
2. **Quién** tomó la decisión (el actor)
3. **Qué información** estaba disponible (el contexto y evidencia)
4. **Qué resultado** se eligió (aprobado, rechazado, diferido)
5. **Por qué** se eligió ese resultado (la justificación)
6. **Cuándo** se tomó la decisión (tiempo de negocio) y se registró (tiempo del sistema)

La mayoría de los sistemas capturan solo el resultado. El préstamo fue aprobado. El reclamo fue denegado. Pero sin el contexto y la justificación, no puedes responder las preguntas que importan:

- ¿Fue la decisión correcta dada la información disponible?
- ¿Se habría tomado una decisión diferente con mejor información?
- ¿Siguió la decisión la política?
- ¿Puede reproducirse la decisión?

## Decisiones vs. Acciones

Las decisiones y las acciones son cosas diferentes:

**Decisión**: "Basándome en el reporte crediticio, apruebo esta solicitud de préstamo."

**Acción**: El préstamo se desembolsa a la cuenta del cliente.

Muchos sistemas confunden estas. El préstamo se desembolsa, y ese hecho se registra. Pero la decisión de aprobar el préstamo—el razonamiento, la evidencia considerada, la persona que aprobó—se pierde en un cambio de campo de estado.

Cuando algo sale mal, necesitas ambas:
- El rastro de decisiones: ¿Quién aprobó esto? ¿Qué sabían?
- El rastro de acciones: ¿Qué pasó realmente? ¿Cuándo?

El primitivo de encuentros (Capítulo 11) maneja acciones—transiciones de estado a través de un flujo de trabajo. El primitivo de decisiones maneja las decisiones que disparan esas transiciones.

## El Patrón IdempotencyKey

Las decisiones frecuentemente disparan acciones irreversibles. Aprobar un pago, y el dinero se mueve. Denegar un reclamo, y el cliente es notificado. Si tu sistema falla a mitad de operación y reintenta, no quieres aprobar dos veces o denegar dos veces.

El patrón IdempotencyKey previene el procesamiento duplicado:

```python
class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    status = models.CharField(choices=['in_flight', 'completed', 'failed'])
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    result_data = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
```

Antes de realizar una operación:
1. Crea un IdempotencyKey con status='in_flight'
2. Si la creación falla (restricción única), verifica la clave existente
3. Si la clave existente está completada, retorna el resultado en caché
4. Si la clave existente está en vuelo, la operación ya está corriendo—espera o falla
5. Si la clave existente falló, elimínala y reintenta

Después de la operación:
1. Marca la clave como completada con el resultado
2. O márcala como fallida con el mensaje de error

Este patrón convierte cualquier función en una operación idempotente:

```python
@idempotent(key_func=lambda order_id, **kw: f"process_order:{order_id}")
def process_order(order_id, items):
    # Only runs once per order_id, even with retries
    order = Order.objects.get(id=order_id)
    order.process(items)
    return order
```

## Semántica de Tiempo para Decisiones

Las decisiones tienen la misma semántica de tiempo que todos los hechos de negocio (Capítulo 7):

**effective_at** — Cuándo se tomó realmente la decisión (tiempo de negocio). Una decisión tomada ayer pero registrada hoy tiene effective_at = ayer.

**recorded_at** — Cuándo se registró la decisión en el sistema (tiempo del sistema). Siempre se establece automáticamente a ahora. No puede cambiarse.

Esto permite antedatar sin corrupción. Si un gerente aprobó un préstamo por teléfono a las 2 PM pero el ingreso de datos ocurrió a las 5 PM, el registro de decisión muestra:
- effective_at: 2 PM (cuándo se tomó la decisión)
- recorded_at: 5 PM (cuándo lo registramos)

Los auditores pueden ver ambos: cuándo pasaron las cosas y cuándo supimos de ellas.

## Fechado Efectivo para Reglas

Algunas decisiones se gobiernan por reglas que cambian con el tiempo. Una política de aprobación de préstamos en enero podría diferir de la política en marzo. Para auditar correctamente una decisión, necesitas saber qué versión de las reglas estaba vigente.

El EffectiveDatedMixin proporciona períodos de validez:

```python
class ApprovalThreshold(EffectiveDatedMixin, models.Model):
    loan_type = models.CharField(max_length=50)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    objects = EffectiveDatedQuerySet.as_manager()
```

Consulta las reglas que estaban vigentes en el momento de la decisión:

```python
# What threshold was in effect when this decision was made?
threshold = ApprovalThreshold.objects.as_of(decision.effective_at).get(
    loan_type='personal'
)
```

Esto hace las decisiones reproducibles. Dado el timestamp effective_at de la decisión, puedes recuperar las reglas exactas que aplicaban.

## GenericFK para Objetivos Polimórficos

Las decisiones pueden tomarse sobre cualquier cosa: solicitudes de préstamo, reclamos de seguro, solicitudes de compra, tratamientos médicos. El modelo Decision usa GenericForeignKey para referenciar cualquier modelo:

```python
class Decision(UUIDModel, BaseModel, TimeSemanticsMixin):
    target_content_type = models.ForeignKey(ContentType, on_delete=CASCADE)
    target_id = models.CharField(max_length=255)  # CharField for UUID support
    target = GenericForeignKey('target_content_type', 'target_id')

    decision_type = models.CharField(max_length=100)
    outcome = models.CharField(choices=DecisionOutcome.choices)
    reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    context = models.JSONField(default=dict)
    evidence = models.JSONField(default=dict)
```

El mismo framework de decisiones maneja:

```python
# Loan approval
Decision.objects.create(
    target=loan_application,
    decision_type='credit_approval',
    outcome='approved',
    reason='Credit score exceeds threshold',
    context={'credit_score': 720, 'threshold': 650}
)

# Insurance claim
Decision.objects.create(
    target=claim,
    decision_type='claim_review',
    outcome='rejected',
    reason='Pre-existing condition exclusion',
    context={'condition': 'diabetes', 'policy_exclusion': 'section 4.2'}
)

# Purchase request
Decision.objects.create(
    target=purchase_request,
    decision_type='budget_approval',
    outcome='deferred',
    reason='Requires VP approval for amounts over $10,000',
    context={'amount': 15000, 'approval_limit': 10000}
)
```

## El Prompt Completo

Aquí está el prompt completo para generar un paquete de decisiones. Copia este prompt, pégalo en tu asistente de IA, y generará primitivos correctos de seguimiento de decisiones.

---

````markdown
# Prompt: Build django-decisioning

## Instruction

Create a Django package called `django-decisioning` that provides time semantics,
idempotency patterns, and decision tracking primitives.

## Package Purpose

Provide infrastructure for time-aware operations and decision tracking:
- TimeSemanticsMixin - Add effective_at/recorded_at to any model
- EffectiveDatedMixin - Add valid_from/valid_to for temporal validity
- IdempotencyKey - Track idempotent operation status
- @idempotent decorator - Make functions idempotent
- Decision - Track decisions with GenericFK target
- QuerySets for temporal queries (as_of, current, etc.)

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel, BaseModel)
- django.contrib.contenttypes

## File Structure

```
packages/django-decisioning/
├── pyproject.toml
├── README.md
├── src/django_decisioning/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── mixins.py
│   ├── querysets.py
│   ├── decorators.py
│   ├── utils.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── test_models.py
    ├── test_mixins.py
    ├── test_querysets.py
    ├── test_decorators.py
    └── test_utils.py
```

## Exceptions Specification

### exceptions.py

```python
class DecisioningError(Exception):
    """Base exception for decisioning errors."""
    pass


class IdempotencyError(DecisioningError):
    """Base exception for idempotency errors."""
    pass


class OperationInFlightError(IdempotencyError):
    """Raised when operation is already in progress."""
    def __init__(self, key: str, started_at):
        self.key = key
        self.started_at = started_at
        super().__init__(
            f"Operation with key '{key}' is already in flight (started at {started_at})"
        )


class DuplicateOperationError(IdempotencyError):
    """Raised when operation was already completed."""
    def __init__(self, key: str, completed_at, result):
        self.key = key
        self.completed_at = completed_at
        self.result = result
        super().__init__(
            f"Operation with key '{key}' already completed at {completed_at}"
        )
```

## QuerySets Specification

### querysets.py

```python
from django.db import models
from django.utils import timezone


class EventAsOfQuerySet(models.QuerySet):
    """QuerySet for event-sourced models with effective_at/recorded_at."""

    def as_of(self, timestamp):
        """Get records effective as of a timestamp."""
        return self.filter(effective_at__lte=timestamp)

    def recorded_before(self, timestamp):
        """Get records recorded before a timestamp."""
        return self.filter(recorded_at__lte=timestamp)

    def recorded_after(self, timestamp):
        """Get records recorded after a timestamp."""
        return self.filter(recorded_at__gt=timestamp)

    def effective_between(self, start, end):
        """Get records effective within a range."""
        return self.filter(effective_at__gte=start, effective_at__lt=end)


class EffectiveDatedQuerySet(models.QuerySet):
    """QuerySet for models with valid_from/valid_to fields."""

    def current(self):
        """Get currently valid records."""
        return self.as_of(timezone.now())

    def as_of(self, timestamp):
        """Get records valid at a specific timestamp."""
        return self.filter(
            valid_from__lte=timestamp
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=timestamp)
        )

    def expired(self):
        """Get records that have expired."""
        now = timezone.now()
        return self.filter(valid_to__lte=now)

    def future(self):
        """Get records not yet valid."""
        now = timezone.now()
        return self.filter(valid_from__gt=now)

    def overlapping(self, start, end):
        """Get records that overlap with a time range."""
        return self.filter(
            valid_from__lt=end
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=start)
        )
```

## Mixins Specification

### mixins.py

```python
from django.db import models
from django.utils import timezone


class TimeSemanticsMixin(models.Model):
    """
    Mixin for event-sourced models with clear time semantics.

    effective_at: When the event actually happened (business time)
    recorded_at: When we recorded the event (system time)
    """
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this event actually occurred (business time)"
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was created (system time)"
    )

    class Meta:
        abstract = True


class EffectiveDatedMixin(models.Model):
    """
    Mixin for models with temporal validity periods.

    valid_from: When this record becomes valid
    valid_to: When this record expires (null = indefinite)
    """
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this record becomes valid"
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this record expires (null = indefinite)"
    )

    class Meta:
        abstract = True

    @property
    def is_active(self) -> bool:
        """Check if this record is currently valid."""
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now >= self.valid_to:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if this record has expired."""
        if not self.valid_to:
            return False
        return timezone.now() >= self.valid_to

    @property
    def is_future(self) -> bool:
        """Check if this record is not yet valid."""
        return timezone.now() < self.valid_from
```

## Models Specification

### IdempotencyKey Model

```python
from django.db import models
from django_basemodels.models import UUIDModel

class IdempotencyStatus(models.TextChoices):
    IN_FLIGHT = 'in_flight', 'In Flight'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class IdempotencyKey(UUIDModel):
    """Track idempotent operation status."""
    key = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=IdempotencyStatus.choices,
        default=IdempotencyStatus.IN_FLIGHT
    )

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Result storage
    result_type = models.CharField(max_length=255, blank=True, default='')
    result_id = models.CharField(max_length=255, blank=True, default='')
    result_data = models.JSONField(default=dict, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True, default='')

    # Expiry for cleanup
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'django_decisioning'
        verbose_name = 'idempotency key'
        verbose_name_plural = 'idempotency keys'
        indexes = [
            models.Index(fields=['status', 'started_at']),
            models.Index(fields=['expires_at']),
        ]

    def mark_completed(self, result=None, result_type='', result_id=''):
        """Mark operation as completed."""
        from django.utils import timezone
        self.status = IdempotencyStatus.COMPLETED
        self.completed_at = timezone.now()
        if result:
            self.result_data = result if isinstance(result, dict) else {'value': result}
        self.result_type = result_type
        self.result_id = str(result_id) if result_id else ''
        self.save()

    def mark_failed(self, error_message: str):
        """Mark operation as failed."""
        from django.utils import timezone
        self.status = IdempotencyStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()

    def __str__(self):
        return f"{self.key} ({self.status})"
```

### Decision Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django_basemodels.models import UUIDModel, BaseModel
from .mixins import TimeSemanticsMixin


class DecisionOutcome(models.TextChoices):
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    PENDING = 'pending', 'Pending'
    DEFERRED = 'deferred', 'Deferred'
    ESCALATED = 'escalated', 'Escalated'


class Decision(UUIDModel, BaseModel, TimeSemanticsMixin):
    """Track a decision made about a target entity."""

    # Target via GenericFK
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+'
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Decision details
    decision_type = models.CharField(max_length=100)
    outcome = models.CharField(
        max_length=20,
        choices=DecisionOutcome.choices,
        default=DecisionOutcome.PENDING
    )
    reason = models.TextField(blank=True, default='')

    # Decision maker
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decisions_made'
    )

    # Context and evidence
    context = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=dict, blank=True)

    # Linked idempotency key (optional)
    idempotency_key = models.ForeignKey(
        IdempotencyKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decisions'
    )

    class Meta:
        app_label = 'django_decisioning'
        verbose_name = 'decision'
        verbose_name_plural = 'decisions'
        ordering = ['-effective_at', '-recorded_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['decision_type']),
            models.Index(fields=['outcome']),
        ]

    def save(self, *args, **kwargs):
        self.target_id = str(self.target_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.decision_type}: {self.outcome}"
```

## Decorators Specification

### decorators.py

```python
import functools
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import IdempotencyKey, IdempotencyStatus
from .exceptions import OperationInFlightError, DuplicateOperationError


def idempotent(
    key_func=None,
    expires_in: timedelta = None,
    raise_on_duplicate: bool = False
):
    """
    Decorator to make a function idempotent.

    Args:
        key_func: Function to generate idempotency key from args/kwargs.
                  If None, uses first positional arg as key.
        expires_in: How long until the idempotency key expires.
        raise_on_duplicate: If True, raise error on duplicate. If False, return cached result.

    Usage:
        @idempotent(key_func=lambda order_id, **kw: f"process_order:{order_id}")
        def process_order(order_id, items):
            # This will only run once per order_id
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate idempotency key
            if key_func:
                key = key_func(*args, **kwargs)
            elif args:
                key = f"{func.__module__}.{func.__name__}:{args[0]}"
            else:
                raise ValueError("Cannot generate idempotency key - provide key_func or positional arg")

            # Check for existing operation
            try:
                existing = IdempotencyKey.objects.get(key=key)

                if existing.status == IdempotencyStatus.IN_FLIGHT:
                    raise OperationInFlightError(key, existing.started_at)

                if existing.status == IdempotencyStatus.COMPLETED:
                    if raise_on_duplicate:
                        raise DuplicateOperationError(
                            key, existing.completed_at, existing.result_data
                        )
                    # Return cached result
                    return existing.result_data.get('value', existing.result_data)

                # Failed - allow retry by falling through to create new
                existing.delete()

            except IdempotencyKey.DoesNotExist:
                pass

            # Create new idempotency key
            expires_at = None
            if expires_in:
                expires_at = timezone.now() + expires_in

            idem_key = IdempotencyKey.objects.create(
                key=key,
                status=IdempotencyStatus.IN_FLIGHT,
                expires_at=expires_at
            )

            try:
                with transaction.atomic():
                    result = func(*args, **kwargs)

                    # Store result
                    result_type = ''
                    result_id = ''
                    if hasattr(result, '__class__'):
                        result_type = f"{result.__class__.__module__}.{result.__class__.__name__}"
                    if hasattr(result, 'pk'):
                        result_id = str(result.pk)

                    idem_key.mark_completed(
                        result={'value': result} if not isinstance(result, dict) else result,
                        result_type=result_type,
                        result_id=result_id
                    )

                    return result

            except Exception as e:
                idem_key.mark_failed(str(e))
                raise

        return wrapper
    return decorator
```

## Utils Specification

### utils.py

```python
from django.contrib.contenttypes.models import ContentType


def get_target_ref(obj):
    """
    Get a serializable reference to any Django model instance.

    Args:
        obj: Django model instance

    Returns:
        Dict with content_type and object_id
    """
    content_type = ContentType.objects.get_for_model(obj)
    return {
        'content_type_id': content_type.id,
        'app_label': content_type.app_label,
        'model': content_type.model,
        'object_id': str(obj.pk)
    }


def resolve_target_ref(ref):
    """
    Resolve a target reference back to a model instance.

    Args:
        ref: Dict from get_target_ref()

    Returns:
        Django model instance or None
    """
    try:
        if 'content_type_id' in ref:
            content_type = ContentType.objects.get(id=ref['content_type_id'])
        else:
            content_type = ContentType.objects.get(
                app_label=ref['app_label'],
                model=ref['model']
            )
        return content_type.get_object_for_this_type(pk=ref['object_id'])
    except Exception:
        return None
```

## Test Cases (78 tests)

### IdempotencyKey Model Tests (12 tests)
1. `test_idempotency_key_creation` - Create with required fields
2. `test_idempotency_key_has_uuid_pk` - UUID primary key
3. `test_idempotency_key_unique_key` - Unique constraint
4. `test_idempotency_key_status_choices` - All status values work
5. `test_idempotency_key_started_at_auto` - Auto-set on create
6. `test_idempotency_key_mark_completed` - Transition to completed
7. `test_idempotency_key_mark_completed_with_result` - Store result
8. `test_idempotency_key_mark_failed` - Transition to failed
9. `test_idempotency_key_result_data_json` - JSONField works
10. `test_idempotency_key_expires_at_optional` - Nullable
11. `test_idempotency_key_str_representation` - String format
12. `test_idempotency_key_indexes` - Indexes exist

### Decision Model Tests (10 tests)
1. `test_decision_creation` - Create with required fields
2. `test_decision_has_uuid_pk` - UUID primary key
3. `test_decision_has_time_semantics` - effective_at, recorded_at
4. `test_decision_target_generic_fk` - GenericFK works
5. `test_decision_outcome_choices` - All outcomes work
6. `test_decision_decided_by_optional` - Nullable
7. `test_decision_context_json` - JSONField works
8. `test_decision_evidence_json` - JSONField works
9. `test_decision_soft_delete` - Soft delete works
10. `test_decision_ordering` - Ordered by effective_at desc

### TimeSemanticsMixin Tests (8 tests)
1. `test_effective_at_defaults_to_now` - Default value
2. `test_effective_at_can_be_backdated` - Custom value
3. `test_recorded_at_auto_set` - Auto on create
4. `test_recorded_at_not_editable` - Cannot change
5. `test_effective_before_recorded` - Backdating works
6. `test_effective_equals_recorded` - Same time works
7. `test_mixin_is_abstract` - Cannot instantiate
8. `test_multiple_inheritance` - Works with other mixins

### EffectiveDatedMixin Tests (10 tests)
1. `test_valid_from_defaults_to_now` - Default value
2. `test_valid_to_nullable` - Can be indefinite
3. `test_is_active_when_valid` - True for current
4. `test_is_active_false_when_expired` - False for expired
5. `test_is_active_false_when_future` - False for future
6. `test_is_expired_when_past_valid_to` - Expired check
7. `test_is_expired_false_when_indefinite` - No end date
8. `test_is_future_when_valid_from_ahead` - Future check
9. `test_is_future_false_when_started` - Not future
10. `test_mixin_is_abstract` - Cannot instantiate

### EventAsOfQuerySet Tests (8 tests)
1. `test_as_of_returns_effective_before` - Filter by effective_at
2. `test_as_of_excludes_future` - Future excluded
3. `test_recorded_before_filters` - Filter by recorded_at
4. `test_recorded_after_filters` - Filter by recorded_at
5. `test_effective_between_range` - Range query
6. `test_as_of_empty_when_none_exist` - Empty result
7. `test_as_of_multiple_records` - Multiple matches
8. `test_chained_queries` - Methods chainable

### EffectiveDatedQuerySet Tests (10 tests)
1. `test_current_returns_active` - Currently valid only
2. `test_current_excludes_expired` - Expired excluded
3. `test_current_excludes_future` - Future excluded
4. `test_as_of_historical` - Historical query
5. `test_expired_returns_only_expired` - Expired filter
6. `test_future_returns_only_future` - Future filter
7. `test_overlapping_finds_intersecting` - Overlap detection
8. `test_overlapping_excludes_non_intersecting` - Non-overlap excluded
9. `test_current_with_indefinite` - Null valid_to
10. `test_chained_queries` - Methods chainable

### @idempotent Decorator Tests (12 tests)
1. `test_first_call_executes_function` - Function runs
2. `test_second_call_returns_cached` - Cached result
3. `test_in_flight_raises_error` - Concurrent protection
4. `test_failed_allows_retry` - Retry after failure
5. `test_custom_key_func` - Custom key generation
6. `test_default_key_from_args` - Auto key from args
7. `test_raise_on_duplicate_true` - Raises instead of cache
8. `test_expires_in_sets_expiry` - Expiry timestamp
9. `test_result_stored_in_key` - Result persistence
10. `test_exception_marks_failed` - Error handling
11. `test_atomic_transaction` - Transaction wrapper
12. `test_model_result_stored` - Model PK stored

### Utils Tests (8 tests)
1. `test_get_target_ref_returns_dict` - Returns reference
2. `test_get_target_ref_includes_content_type` - Has CT info
3. `test_get_target_ref_includes_object_id` - Has object ID
4. `test_resolve_target_ref_returns_object` - Resolves to instance
5. `test_resolve_target_ref_by_id` - Resolve by CT ID
6. `test_resolve_target_ref_by_label` - Resolve by app/model
7. `test_resolve_target_ref_returns_none_missing` - Missing object
8. `test_roundtrip_get_resolve` - Full roundtrip

## Key Behaviors

1. Time Semantics: effective_at (business time) vs recorded_at (system time)
2. Effective Dating: valid_from/valid_to for temporal validity
3. Idempotency: Prevent duplicate operations with key tracking
4. Decision Tracking: Record decisions about any entity
5. Temporal Queries: as_of(), current(), expired(), future()

## Usage Examples

```python
from datetime import timedelta
from django_decisioning import (
    TimeSemanticsMixin, EffectiveDatedMixin,
    EventAsOfQuerySet, EffectiveDatedQuerySet,
    idempotent, Decision, DecisionOutcome,
    get_target_ref, resolve_target_ref
)

# Model with time semantics
class PaymentEvent(TimeSemanticsMixin, models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    objects = EventAsOfQuerySet.as_manager()

# Model with effective dating
class PriceOverride(EffectiveDatedMixin, models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    objects = EffectiveDatedQuerySet.as_manager()

# Idempotent function
@idempotent(
    key_func=lambda order_id, **kw: f"process_order:{order_id}",
    expires_in=timedelta(hours=24)
)
def process_order(order_id, items):
    # Only runs once per order_id
    order = Order.objects.get(id=order_id)
    order.process(items)
    return order

# Record a decision
decision = Decision.objects.create(
    target=loan_application,
    decision_type='credit_approval',
    outcome=DecisionOutcome.APPROVED,
    reason='Credit score meets threshold',
    decided_by=request.user,
    context={'credit_score': 720},
    evidence={'report_id': 'CR-123'}
)

# Query by time
events = PaymentEvent.objects.as_of(last_month)
active_prices = PriceOverride.objects.current()
historical = PriceOverride.objects.as_of(audit_date)
```

## Acceptance Criteria

- [ ] TimeSemanticsMixin with effective_at/recorded_at
- [ ] EffectiveDatedMixin with valid_from/valid_to
- [ ] IdempotencyKey model with status tracking
- [ ] @idempotent decorator with key generation
- [ ] Decision model with GenericFK target
- [ ] EventAsOfQuerySet and EffectiveDatedQuerySet
- [ ] All 78 tests passing
- [ ] README with usage examples
````

---

## Práctica: Genera Tu Paquete de Decisiones

Copia el prompt de arriba y pégalo en tu asistente de IA. La IA generará:

1. La estructura completa del paquete
2. Mixins de semántica temporal y fechado efectivo
3. Infraestructura de idempotencia
4. Modelo Decision con GenericFK
5. QuerySets para consultas temporales
6. 78 casos de prueba cubriendo todos los comportamientos

Después de la generación, ejecuta las pruebas:

```bash
cd packages/django-decisioning
pip install -e .
pytest tests/ -v
```

Las 78 pruebas deberían pasar.

### Ejercicio: Construir un Flujo de Trabajo de Aprobación

Combina decisiones con encuentros:

```
Create an approval workflow for purchase requests:

1. PurchaseRequest model with amount, justification, requested_by
2. EncounterDefinition with states: submitted, pending_review, approved, rejected
3. Decision records at each transition with context snapshot

When a request is approved:
- Record Decision with outcome='approved', context={amount, budget_remaining}
- Transition encounter to 'approved'
- Use @idempotent to prevent double-approval

When a request is rejected:
- Record Decision with outcome='rejected', reason='...'
- Transition encounter to 'rejected'
```

### Ejercicio: Auditar Historial de Decisiones

Escribe una función que reconstruya el rastro de decisiones para cualquier objetivo:

```
def get_decision_trail(target) -> List[Dict]:
    """
    Return chronological list of all decisions about a target.

    Each entry should include:
    - decision_type
    - outcome
    - decided_by (user's name or "System")
    - effective_at
    - reason
    - context (what information was available)
    """
```

## Lo Que la IA Hace Mal

Sin restricciones explícitas, el seguimiento de decisiones generado por IA típicamente:

1. **Almacena decisiones como cambios de estado** — El préstamo fue aprobado. Pero ¿quién lo aprobó? ¿Cuándo? ¿Basándose en qué? Desconocido.

2. **No captura contexto** — El resultado de la decisión se registra pero no la información que estaba disponible en el momento.

3. **Confunde decisión y acción** — "Aprobado" significa tanto la decisión como el desembolso. No puedes saber cuál falló si algo sale mal.

4. **Sin idempotencia** — Reintentar una operación fallida puede aprobar dos veces, cobrar dos veces, desembolsar dos veces.

5. **Usa IntegerField para target_id** — Se rompe con claves primarias UUID.

6. **Sin semántica de tiempo** — ¿Cuándo se tomó la decisión vs. cuándo se registró? La distinción se pierde.

7. **Carece de fechado efectivo para reglas** — No puedes determinar qué versión de la política de aprobación estaba vigente.

El prompt de arriba previene todos estos errores.

## Por Qué Esto Importa Después

El primitivo de decisiones une todo:

- **Encuentros**: Las transiciones de estado son disparadas por decisiones. Cada transición debería tener un registro de decisión correspondiente.

- **Libro Mayor**: Las transacciones financieras son el resultado de decisiones. La decisión de aprobar una venta lleva a entradas del libro mayor.

- **Acuerdos**: Firmar un acuerdo es una decisión. Los cambios de versión son decisiones.

- **Auditoría**: Cada decisión es evidencia de auditoría. El log de auditoría captura eventos del sistema; las decisiones capturan elecciones humanas.

Cuando los reguladores preguntan "¿quién aprobó esto?" y "¿qué sabían?", tienes respuestas. Cuando algo sale mal y necesitas entender por qué, tienes el rastro de decisiones. Cuando ocurren reintentos, la idempotencia previene desastres.

Si las decisiones están mal, tu sistema es una caja negra. Si están bien, tienes un registro listo para tribunales de cada elección.

---

## Cómo Reconstruir Este Primitivo

| Paquete | Archivo de Prompt | Cantidad de Pruebas |
|---------|-------------------|---------------------|
| django-decisioning | `docs/prompts/django-decisioning.md` | ~78 pruebas |

### Usando el Prompt

```bash
cat docs/prompts/django-decisioning.md | claude

# Request: "Implement TimeSemanticsMixin with effective_at/recorded_at,
# then EffectiveDatedMixin with valid_from/valid_to,
# then IdempotencyKey model and @idempotent decorator."
```

### Restricciones Clave

- **Siempre dos timestamps**: `effective_at` (cuándo ocurrió) y `recorded_at` (cuándo se registró)
- **recorded_at inmutable**: Se establece una vez en la creación, nunca cambia
- **Aplicación de idempotencia**: Las operaciones duplicadas retornan resultados en caché
- **Captura de contexto**: Las decisiones almacenan instantánea de información disponible en el momento de la decisión

Si Claude almacena solo un único timestamp o permite que `recorded_at` se modifique, eso es una violación de restricción.

---

## Fuentes y Referencias

1. **Escándalo Enron** — Powers, William C., Jr. "Report of Investigation by the Special Investigative Committee of the Board of Directors of Enron Corp." 1 de Febrero, 2002. El relato definitivo de las fallas en la toma de decisiones.

2. **Ley Sarbanes-Oxley** — Public Law 107-204, 30 de Julio, 2002. Sección 404 sobre controles internos y Sección 302 sobre certificación ejecutiva de informes financieros.

3. **Idempotencia en Sistemas Distribuidos** — Helland, Pat. "Idempotence Is Not a Medical Condition." *ACM Queue*, 2012. El tratamiento autorizado de operaciones idempotentes.

4. **Registro de Decisiones** — Kleppmann, Martin. *Designing Data-Intensive Applications*. O'Reilly, 2017. Capítulo 11 sobre event sourcing y captura de decisiones.

5. **Datos Temporales** — Snodgrass, Richard T. *Developing Time-Oriented Database Applications in SQL*. Morgan Kaufmann, 2000. El fundamento académico para tiempo de negocio vs. tiempo del sistema.

---

*Estado: Completo*
