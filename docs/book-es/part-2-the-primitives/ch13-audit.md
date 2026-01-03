# Capítulo 13: Auditoría

> "La ausencia de evidencia no es evidencia de ausencia—pero en un tribunal, bien podría serlo."
>
> — Un abogado explicando por qué importan las pistas de auditoría

---

En 2002, Arthur Andersen LLP se convirtió en la primera firma contable importante en ser condenada por un crimen. El cargo: obstrucción de la justicia por destruir documentos relacionados con Enron.

Arthur Andersen había auditado empresas durante 89 años. Empleaban 85,000 personas en todo el mundo. Dentro de un año de la condena, desaparecieron—no porque ellos mismos manipularan los libros, sino porque destruyeron la pista de auditoría.

La firma tenía una política de retención de documentos. Desafortunadamente, esa política se aplicó con más vigor en las semanas después de que el colapso de Enron se hiciera público. Miles de correos electrónicos fueron eliminados. Miles de documentos en papel fueron triturados. Cuando la SEC vino buscando evidencia, la evidencia había desaparecido.

La lección no es sutil: no solo necesitas hacer lo correcto. Necesitas poder probar que hiciste lo correcto. Una pista de auditoría que puede editarse o eliminarse no es una pista de auditoría. Es una ficción.

## Por Qué los Sistemas Mienten

La mayoría de los sistemas de software mienten sobre su historial. No maliciosamente—simplemente no están diseñados para recordar.

Cuando actualizas un registro:
```python
customer.email = 'new@example.com'
customer.save()
```

El correo antiguo desaparece. No hay registro de que alguna vez existió. Si alguien pregunta "¿cuál era el correo de este cliente el mes pasado?", no tienes respuesta.

Cuando eliminas un registro:
```python
invoice.delete()
```

La factura desaparece. No archivada, no marcada como eliminada—desaparecida. Si un auditor pide ver todas las facturas del Q3, no puedes producir lo que destruiste.

Esto no es un bug. El comportamiento predeterminado de Django es actualizar en su lugar y eliminar físicamente. El framework asume que quieres eficiencia, no historial. Pero para cualquier sistema que maneje dinero, cumplimiento o responsabilidad, esta suposición es catastróficamente incorrecta.

## El Costo del Historial Faltante

En 2017, Equifax reveló una filtración de datos que afectó a 147 millones de personas. Durante la investigación, la empresa luchó por determinar qué datos habían sido accedidos porque su registro era inadecuado. El acuerdo final fue de $700 millones.

El IRS requiere que las empresas retengan registros financieros por al menos 7 años. HIPAA requiere registros de salud por 6 años. Sarbanes-Oxley requiere que las empresas públicas retengan documentos de trabajo de auditoría por 7 años. Si tu sistema no puede probar qué pasó durante ese período, estás en violación.

Pero el cumplimiento es solo el mínimo legal. El costo real es operacional:

- **Depuración**: "¿Por qué esta cuenta tiene saldo negativo?" Sin historial, estás adivinando.
- **Disputas**: "Nunca acepté esos términos." Sin una pista de firmas, podrían tener razón.
- **Soporte**: "¿Qué cambió entre ayer y hoy?" Sin logs, no puedes ayudarles.

## Solo-Adición: El Único Patrón Aceptable

Un log de auditoría tiene una regla: los registros solo pueden crearse, nunca modificarse ni eliminarse.

```python
class AuditLog(models.Model):
    # ... fields ...

    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLogError("Audit logs cannot be modified")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError("Audit logs cannot be deleted")
```

Esto se aplica a nivel de modelo, no por política. Si alguien llama `audit_entry.save()` en una entrada existente, el sistema lanza una excepción. Si alguien llama `audit_entry.delete()`, lo mismo.

No puedes eliminar accidentalmente logs de auditoría. No puedes "corregir" entradas incorrectas. El único camino hacia adelante es crear nuevas entradas que expliquen qué pasó.

## Qué Capturar

Cada entrada del log de auditoría necesita:

**Qué cambió:**
- `target`: El objeto que fue modificado (vía GenericForeignKey)
- `action`: create, update, delete, view, o personalizado
- `old_values`: Valores de campos antes del cambio
- `new_values`: Valores de campos después del cambio
- `changed_fields`: Qué campos fueron modificados

**Quién lo hizo:**
- `actor`: Foreign key al usuario
- `actor_repr`: Representación en string del actor en el momento (en caso de que el usuario sea luego eliminado o renombrado)

**Cuándo ocurrió:**
- `created_at`: Tiempo del sistema cuando se registró el log
- `effective_at`: Tiempo de negocio cuando la acción realmente ocurrió

**Por qué ocurrió:**
- `message`: Descripción legible por humanos
- `metadata`: Contexto adicional (dirección IP, user agent, ID de sesión)

## GenericFK para Cualquier Objetivo

Los logs de auditoría pueden adjuntarse a cualquier modelo. Un cambio de documento, una eliminación de factura, un inicio de sesión de usuario—todos usan la misma infraestructura de auditoría.

```python
class AuditLog(models.Model):
    target_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    target_id = models.CharField(max_length=255)  # CharField for UUID support
    target = GenericForeignKey('target_content_type', 'target_id')
```

Consulta el historial de cualquier objeto:

```python
# All changes to a specific document
logs = AuditLog.objects.for_target(document)

# All deletes across the system
deletes = AuditLog.objects.by_action('delete')

# Everything a specific user did
user_actions = AuditLog.objects.by_actor(user)
```

## El Prompt Completo

Aquí está el prompt completo para generar un paquete de log de auditoría. Copia este prompt, pégalo en tu asistente de IA, y generará primitivos de auditoría de solo-adición correctos.

---

````markdown
# Prompt: Build django-audit-log

## Instruction

Create a Django package called `django-audit-log` that provides immutable audit
logging primitives for tracking changes to any model.

## Package Purpose

Provide append-only audit trail capabilities:
- AuditLog - Immutable log entry with GenericFK target
- log() - Function to create audit log entries
- log_event() - Function for custom event logging
- AuditLogQuerySet for filtering and querying
- Immutability enforcement (no updates/deletes)

## Dependencies

- Django >= 4.2
- django-basemodels (for UUIDModel)
- django.contrib.contenttypes
- django.contrib.auth

## File Structure

```
packages/django-audit-log/
├── pyproject.toml
├── README.md
├── src/django_audit_log/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_models.py
    └── test_services.py
```

## Exceptions Specification

### exceptions.py

```python
class AuditLogError(Exception):
    """Base exception for audit log errors."""
    pass


class ImmutableLogError(AuditLogError):
    """Raised when attempting to modify an immutable audit log entry."""
    def __init__(self, message="Audit log entries are immutable and cannot be modified"):
        super().__init__(message)
```

## Models Specification

### AuditLog Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django_basemodels.models import UUIDModel
from .exceptions import ImmutableLogError


class AuditAction(models.TextChoices):
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    VIEW = 'view', 'View'
    CUSTOM = 'custom', 'Custom'


class AuditLogQuerySet(models.QuerySet):
    """QuerySet for audit log queries."""

    def for_target(self, target):
        """Get audit logs for a specific target object."""
        content_type = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=content_type,
            target_id=str(target.pk)
        )

    def by_action(self, action):
        """Filter by action type."""
        return self.filter(action=action)

    def by_actor(self, actor):
        """Filter by the user who performed the action."""
        return self.filter(actor=actor)

    def in_range(self, start, end):
        """Filter by timestamp range."""
        return self.filter(created_at__gte=start, created_at__lt=end)

    def recent(self, limit=100):
        """Get the most recent entries."""
        return self.order_by('-created_at')[:limit]

    def as_of(self, timestamp):
        """Get entries up to a specific timestamp."""
        return self.filter(created_at__lte=timestamp)


class AuditLog(UUIDModel):
    """
    Immutable audit log entry.

    Once created, entries cannot be modified or deleted.
    """

    # Target via GenericFK (the object being audited)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name='+'
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Action
    action = models.CharField(
        max_length=20,
        choices=AuditAction.choices,
        db_index=True
    )
    event_type = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Custom event type for action=custom"
    )

    # Actor (who performed the action)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    actor_repr = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="String representation of actor at time of action"
    )

    # Change data
    old_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field values before change"
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field values after change"
    )
    changed_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="List of field names that changed"
    )

    # Context
    message = models.TextField(
        blank=True,
        default='',
        help_text="Human-readable description of the action"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context (IP, user agent, etc)"
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the action actually occurred (for backdating)"
    )

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        app_label = 'django_audit_log'
        verbose_name = 'audit log'
        verbose_name_plural = 'audit logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        # Enforce immutability
        if self.pk:
            raise ImmutableLogError()

        # Ensure target_id is string
        self.target_id = str(self.target_id)

        # Capture actor representation
        if self.actor and not self.actor_repr:
            self.actor_repr = str(self.actor)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError("Audit log entries cannot be deleted")

    def __str__(self):
        action_str = self.event_type if self.action == 'custom' else self.action
        return f"{action_str} on {self.target_content_type.model}:{self.target_id}"
```

## Services Specification

### services.py

```python
from typing import Any, Dict, List, Optional
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models import AuditLog, AuditAction


def log(
    target,
    action: str,
    actor=None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    changed_fields: Optional[List[str]] = None,
    message: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    effective_at=None,
) -> AuditLog:
    """
    Create an audit log entry for a model change.

    Args:
        target: The model instance being audited
        action: One of 'create', 'update', 'delete', 'view', 'custom'
        actor: User who performed the action (optional)
        old_values: Dictionary of field values before change
        new_values: Dictionary of field values after change
        changed_fields: List of field names that changed
        message: Human-readable description
        metadata: Additional context (IP, user agent, etc)
        effective_at: When the action actually occurred (for backdating)

    Returns:
        AuditLog instance
    """
    return AuditLog.objects.create(
        target=target,
        action=action,
        actor=actor,
        old_values=old_values or {},
        new_values=new_values or {},
        changed_fields=changed_fields or [],
        message=message,
        metadata=metadata or {},
        effective_at=effective_at or timezone.now(),
    )


def log_create(target, actor=None, message: str = '', metadata: Optional[Dict] = None) -> AuditLog:
    """
    Log a create action.

    Args:
        target: The created model instance
        actor: User who created it
        message: Optional description
        metadata: Additional context

    Returns:
        AuditLog instance
    """
    # Capture all field values as new_values
    new_values = {}
    for field in target._meta.fields:
        if field.name in ('id', 'pk'):
            continue
        value = getattr(target, field.name)
        new_values[field.name] = _serialize_value(value)

    return log(
        target=target,
        action=AuditAction.CREATE,
        actor=actor,
        new_values=new_values,
        changed_fields=list(new_values.keys()),
        message=message or f"Created {target._meta.model_name}",
        metadata=metadata,
    )


def log_update(
    target,
    old_values: Dict[str, Any],
    actor=None,
    message: str = '',
    metadata: Optional[Dict] = None
) -> AuditLog:
    """
    Log an update action.

    Args:
        target: The updated model instance
        old_values: Field values before the update
        actor: User who made the update
        message: Optional description
        metadata: Additional context

    Returns:
        AuditLog instance
    """
    # Calculate changed fields and new values
    new_values = {}
    changed_fields = []

    for field_name, old_value in old_values.items():
        current_value = getattr(target, field_name, None)
        new_value = _serialize_value(current_value)

        if _serialize_value(old_value) != new_value:
            changed_fields.append(field_name)
            new_values[field_name] = new_value

    return log(
        target=target,
        action=AuditAction.UPDATE,
        actor=actor,
        old_values={k: _serialize_value(v) for k, v in old_values.items()},
        new_values=new_values,
        changed_fields=changed_fields,
        message=message or f"Updated {target._meta.model_name}",
        metadata=metadata,
    )


def log_delete(target, actor=None, message: str = '', metadata: Optional[Dict] = None) -> AuditLog:
    """
    Log a delete action.

    Args:
        target: The model instance being deleted
        actor: User who deleted it
        message: Optional description
        metadata: Additional context

    Returns:
        AuditLog instance
    """
    # Capture all field values as old_values
    old_values = {}
    for field in target._meta.fields:
        if field.name in ('id', 'pk'):
            continue
        value = getattr(target, field.name)
        old_values[field.name] = _serialize_value(value)

    return log(
        target=target,
        action=AuditAction.DELETE,
        actor=actor,
        old_values=old_values,
        message=message or f"Deleted {target._meta.model_name}",
        metadata=metadata,
    )


def log_event(
    target,
    event_type: str,
    actor=None,
    message: str = '',
    metadata: Optional[Dict] = None,
    effective_at=None,
) -> AuditLog:
    """
    Log a custom event.

    Args:
        target: The model instance the event relates to
        event_type: Custom event type identifier
        actor: User who triggered the event
        message: Human-readable description
        metadata: Additional context
        effective_at: When the event occurred

    Returns:
        AuditLog instance
    """
    return log(
        target=target,
        action=AuditAction.CUSTOM,
        actor=actor,
        message=message or event_type,
        metadata=metadata or {},
        effective_at=effective_at,
    )


def _serialize_value(value) -> Any:
    """Serialize a value for JSON storage."""
    if value is None:
        return None
    if hasattr(value, 'pk'):
        return str(value.pk)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)
```

## Test Cases (23 tests)

### AuditLog Model Tests (10 tests)
1. `test_audit_log_creation` - Create with required fields
2. `test_audit_log_has_uuid_pk` - UUID primary key
3. `test_audit_log_target_generic_fk` - GenericFK works
4. `test_audit_log_action_choices` - All action types work
5. `test_audit_log_immutable_save` - Cannot update after create
6. `test_audit_log_immutable_delete` - Cannot delete
7. `test_audit_log_actor_optional` - Actor is nullable
8. `test_audit_log_actor_repr_captured` - String representation saved
9. `test_audit_log_ordering` - Ordered by created_at desc
10. `test_audit_log_str_representation` - String format

### AuditLogQuerySet Tests (6 tests)
1. `test_for_target_filters_by_object` - Filters to specific object
2. `test_by_action_filters` - Filters by action type
3. `test_by_actor_filters` - Filters by user
4. `test_in_range_filters` - Date range filter
5. `test_recent_limits_results` - Limited recent entries
6. `test_as_of_filters_by_timestamp` - Historical query

### Service Function Tests (7 tests)
1. `test_log_creates_entry` - Basic log() works
2. `test_log_create_captures_values` - log_create() captures fields
3. `test_log_update_calculates_diff` - log_update() finds changes
4. `test_log_update_tracks_changed_fields` - Changed fields list
5. `test_log_delete_captures_old_values` - log_delete() captures fields
6. `test_log_event_custom_type` - log_event() works
7. `test_log_with_metadata` - Metadata stored

## Key Behaviors

1. Immutability: Entries cannot be modified or deleted after creation
2. GenericFK Target: Attach audit logs to any model
3. Change Tracking: old_values, new_values, changed_fields
4. Actor Capture: Store user and string representation
5. Effective Dating: effective_at for backdating support

## Usage Examples

```python
from django_audit_log import (
    AuditLog, log, log_create, log_update, log_delete, log_event
)

# Log a create
document = Document.objects.create(title='Report', content='...')
log_create(document, actor=request.user)

# Log an update
old_values = {'title': document.title, 'status': document.status}
document.title = 'Updated Report'
document.status = 'published'
document.save()
log_update(document, old_values, actor=request.user)

# Log a delete
log_delete(document, actor=request.user)
document.delete()

# Log a custom event
log_event(
    target=document,
    event_type='downloaded',
    actor=request.user,
    message='User downloaded the document',
    metadata={'ip': '192.168.1.1', 'format': 'pdf'}
)

# Query audit logs
logs = AuditLog.objects.for_target(document)
create_logs = AuditLog.objects.by_action('create')
user_logs = AuditLog.objects.by_actor(request.user)
recent = AuditLog.objects.recent(limit=50)
```

## Acceptance Criteria

- [ ] AuditLog model with GenericFK target
- [ ] Immutability enforcement (no save/delete after create)
- [ ] log(), log_create(), log_update(), log_delete(), log_event()
- [ ] AuditLogQuerySet with filtering methods
- [ ] Change tracking (old_values, new_values, changed_fields)
- [ ] All 23 tests passing
- [ ] README with usage examples
````

---

## Práctica: Genera Tu Paquete de Log de Auditoría

Copia el prompt de arriba y pégalo en tu asistente de IA. La IA generará:

1. La estructura completa del paquete
2. Modelo AuditLog inmutable con GenericFK
3. Funciones de servicio para todos los tipos de acciones
4. Métodos QuerySet para filtrado
5. 23 casos de prueba cubriendo todos los comportamientos

Después de la generación, ejecuta las pruebas:

```bash
cd packages/django-audit-log
pip install -e .
pytest tests/ -v
```

Las 23 pruebas deberían pasar.

### Ejercicio: Agregar Middleware de Metadatos de Solicitud

Crea middleware que automáticamente capture contexto de la solicitud:

```
Create Django middleware that adds audit context to every request:

1. AuditContextMiddleware that captures:
   - IP address (with X-Forwarded-For handling)
   - User agent
   - Session ID
   - Request path
   - Request method

2. Store in thread-local or context variable

3. Modify log() to automatically include this metadata if available

4. Ensure metadata is cleared after request completes
```

### Ejercicio: Reconstruir Estado del Objeto

Usa el log de auditoría para reconstruir un objeto en un punto en el tiempo:

```
Write a function reconstruct_state(target, as_of) that:

1. Finds the object's creation log
2. Applies all updates in order up to as_of timestamp
3. Returns a dictionary of field values at that moment

Handle edge cases:
- Object didn't exist at as_of
- Object was deleted before as_of
- No audit logs exist for object
```

## Lo Que la IA Hace Mal

Sin restricciones explícitas, el logging de auditoría generado por IA típicamente:

1. **Permite actualizaciones** — Alguien "corrige" una entrada del log. La corrección destruye la evidencia original.

2. **Permite eliminaciones** — Los logs pueden purgarse, ya sea intencionalmente o por accidente. Arthur Andersen estaría orgulloso.

3. **No captura old_values** — Registra que algo cambió, pero no de qué cambió.

4. **No tiene instantánea del actor** — Almacena una foreign key al usuario, pero si el usuario es eliminado, el actor se pierde.

5. **Usa IntegerField para target_id** — Se rompe con claves primarias UUID.

6. **No tiene effective_at** — No puede distinguir entre cuándo algo pasó y cuándo se registró.

7. **Almacena solo mensaje** — Una descripción en string en lugar de datos estructurados de antes/después. Inútil para análisis programático.

El prompt de arriba previene todos estos errores.

## Auditoría vs. Decisiones vs. Transiciones

Estos tres primitivos capturan diferentes tipos de datos históricos:

**Log de Auditoría**: Qué cambió en el sistema, cuándo y por quién. Cambios de campo de bajo nivel. "El campo de email cambió de X a Y."

**Decisiones** (Capítulo 12): Elecciones humanas con contexto. "El préstamo fue aprobado porque el puntaje crediticio excedió 650."

**Transiciones** (Capítulo 11): Cambios de estado en flujos de trabajo. "El encuentro pasó de 'checked_in' a 'in_progress'."

Los tres son de solo-adición. Los tres capturan quién y cuándo. Pero sirven propósitos diferentes:

- Los logs de auditoría responden: "¿Qué cambió?"
- Las decisiones responden: "¿Por qué se hizo esta elección?"
- Las transiciones responden: "¿En qué etapa está este proceso?"

En un sistema completo, podrías tener los tres para un solo evento. Cuando un préstamo es aprobado:
- Una Decision registra la aprobación con contexto y razonamiento
- Una EncounterTransition mueve el préstamo de "pending" a "approved"
- Un AuditLog registra que el campo de estado cambió de "pending" a "approved"

La redundancia es intencional. Cada uno sirve a una audiencia diferente: los auditores quieren el log de auditoría, los analistas de negocio quieren decisiones, los equipos de operaciones quieren transiciones.

## Por Qué Esto Importa Después

El log de auditoría es la memoria del sistema:

- **Cumplimiento**: Los reguladores piden pruebas. El log de auditoría las proporciona.

- **Depuración**: Cuando algo sale mal, el log de auditoría muestra qué llevó a la falla.

- **Disputas**: Cuando un cliente afirma que no hizo un cambio, el log de auditoría muestra quién lo hizo.

- **Recuperación**: Cuando necesitas deshacer un error, el log de auditoría muestra cuál era el estado original.

- **Analíticas**: El log de auditoría es un historial completo de la actividad del sistema—útil para entender patrones.

Si la auditoría está mal, estás volando a ciegas. Si está bien, tienes un registro permanente y a prueba de manipulaciones de todo lo que pasó.

---

## Cómo Reconstruir Este Primitivo

| Paquete | Archivo de Prompt | Cantidad de Pruebas |
|---------|-------------------|---------------------|
| django-audit-log | `docs/prompts/django-audit-log.md` | ~23 pruebas |

### Usando el Prompt

```bash
cat docs/prompts/django-audit-log.md | claude

# Request: "Implement AuditLog model with GenericFK target,
# immutability enforcement, and actor snapshot.
# Then add log(), log_create(), log_update(), log_delete() service functions."
```

### Restricciones Clave

- **Entradas inmutables**: No se pueden actualizar ni eliminar después de la creación (lanza `ImmutableLogError`)
- **Instantánea del actor**: Almacena string `actor_repr` en caso de que el usuario sea eliminado después
- **Seguimiento de cambios**: `old_values`, `new_values`, `changed_fields` para reconstrucción
- **Objetivo GenericFK**: Los logs de auditoría pueden adjuntarse a cualquier modelo

Si Claude permite editar o eliminar entradas de auditoría, eso es una violación de restricción. Arthur Andersen fue condenado por menos.

---

## Fuentes y Referencias

1. **Condena de Arthur Andersen** — United States v. Arthur Andersen LLP, 544 U.S. 696 (2005). La Corte Suprema finalmente revocó la condena, pero para entonces la firma ya había colapsado.

2. **Acuerdo de Equifax** — Federal Trade Commission. "Equifax Data Breach Settlement." Julio 2019. El acuerdo de $700 millones por protección de datos y logging inadecuados.

3. **Retención de Registros del IRS** — IRS Publication 583. "Starting a Business and Keeping Records." El requisito de retención de 7 años para registros fiscales.

4. **Requisitos de HIPAA** — 45 CFR § 164.530(j). El requisito de retención de 6 años para documentación relacionada con HIPAA.

5. **Sección 802 de Sarbanes-Oxley** — 18 U.S.C. § 1519. Sanciones penales por alterar, destruir o falsificar registros en investigaciones federales.

---

*Estado: Completo*
