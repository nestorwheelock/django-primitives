# Capítulo 17: Notas

> "El contexto que explica todo."

---

Cada registro de negocio necesita contexto. ¿Por qué se canceló este pedido? ¿Qué dijo el cliente por teléfono? ¿Cuál es el historial de esta cuenta? Las notas capturan el contexto humano que los datos estructurados no pueden.

La primitiva de Notas proporciona notas con hilos, buscables y atribuibles que se adjuntan a cualquier registro en tu sistema.

## El Problema que Resuelven las Notas

La toma de notas falla de maneras predecibles:

**Contexto disperso.** El historial del cliente vive en correos electrónicos, notas del CRM, tickets de soporte y la memoria de alguien. Reconstruir el panorama completo requiere arqueología.

**Datos no estructurados.** Un campo de texto llamado "notas" se convierte en un vertedero. La información crítica queda enterrada en muros de texto.

**Atribución faltante.** "El cliente se quejó del envío" - ¿quién escribió esto? ¿Cuándo? ¿Fue antes o después de que arreglamos el problema del envío?

**Sin hilos.** Las notas son planas. No puedes ver conversaciones, seguimientos, o la cadena de eventos.

**Historial perdido.** Cuando las notas pueden ser editadas o eliminadas, el registro histórico se corrompe.

## El Modelo Note

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_basemodels.models import SoftDeleteModel


class Note(SoftDeleteModel):
    """Una nota adjunta a cualquier modelo con soporte de hilos."""

    # A qué está adjunta esta nota
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Contenido de la nota
    content = models.TextField()

    # Datos estructurados opcionales
    NOTE_TYPES = [
        ('general', 'Nota General'),
        ('call', 'Llamada Telefónica'),
        ('meeting', 'Reunión'),
        ('email', 'Resumen de Email'),
        ('task', 'Tarea'),
        ('followup', 'Seguimiento'),
        ('warning', 'Advertencia'),
        ('resolution', 'Resolución'),
    ]
    note_type = models.CharField(max_length=50, choices=NOTE_TYPES, default='general')

    # Prioridad/visibilidad
    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('normal', 'Normal'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    is_pinned = models.BooleanField(default=False)
    is_internal = models.BooleanField(default=True)  # No visible para clientes

    # Autoría (inmutable)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='notes_created'
    )

    # Hilos
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='replies'
    )

    # Marcas de tiempo (de SoftDeleteModel: created_at, updated_at)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id', '-created_at']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['note_type']),
        ]

    @property
    def is_reply(self):
        return self.parent is not None

    @property
    def thread_root(self):
        """Obtiene la nota raíz de este hilo."""
        current = self
        while current.parent:
            current = current.parent
        return current

    @property
    def thread(self):
        """Obtiene todas las notas en este hilo."""
        root = self.thread_root
        return Note.objects.filter(
            models.Q(pk=root.pk) | models.Q(parent=root)
        ).order_by('created_at')

    @property
    def reply_count(self):
        return self.replies.count()

    def add_reply(self, content, created_by, **kwargs):
        """Agrega una respuesta a esta nota."""
        return Note.objects.create(
            target_content_type=self.target_content_type,
            target_id=self.target_id,
            content=content,
            created_by=created_by,
            parent=self,
            note_type=kwargs.get('note_type', 'general'),
            is_internal=kwargs.get('is_internal', self.is_internal),
        )

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.created_by}: {preview}"
```

## QuerySet de Notas

```python
class NoteQuerySet(models.QuerySet):
    """QuerySet con filtros específicos para notas."""

    def for_target(self, target):
        """Notas para un objeto objetivo específico."""
        ct = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=ct,
            target_id=str(target.pk)
        )

    def root_notes(self):
        """Solo notas de nivel superior (no respuestas)."""
        return self.filter(parent__isnull=True)

    def by_type(self, note_type):
        """Filtrar por tipo de nota."""
        return self.filter(note_type=note_type)

    def internal(self):
        """Solo notas internas."""
        return self.filter(is_internal=True)

    def external(self):
        """Solo notas externas/visibles para clientes."""
        return self.filter(is_internal=False)

    def pinned(self):
        """Solo notas fijadas."""
        return self.filter(is_pinned=True)

    def by_author(self, user):
        """Notas de un autor específico."""
        return self.filter(created_by=user)

    def search(self, query):
        """Búsqueda de texto completo en contenido de notas."""
        return self.filter(content__icontains=query)

    def recent(self, days=30):
        """Notas de los últimos N días."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
```

## Menciones y Notificaciones

```python
import re


class NoteMention(models.Model):
    """Rastrea @menciones en notas."""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='mentions')
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='note_mentions'
    )
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['note', 'mentioned_user']


def extract_mentions(content):
    """Extrae menciones @username del contenido."""
    pattern = r'@(\w+)'
    return re.findall(pattern, content)


def process_mentions(note):
    """Crea registros NoteMention para todas las @menciones en una nota."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    usernames = extract_mentions(note.content)

    for username in usernames:
        try:
            user = User.objects.get(username=username)
            NoteMention.objects.get_or_create(
                note=note,
                mentioned_user=user
            )
        except User.DoesNotExist:
            pass
```

## Línea de Tiempo de Actividad

Combina notas con eventos del sistema:

```python
class ActivityEntry(models.Model):
    """Una entrada de línea de tiempo (nota o evento del sistema)."""

    # A qué está adjunto esto
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    ENTRY_TYPES = [
        ('note', 'Nota'),
        ('status_change', 'Cambio de Estado'),
        ('assignment', 'Asignación'),
        ('creation', 'Creado'),
        ('update', 'Actualizado'),
        ('attachment', 'Adjunto Agregado'),
        ('email_sent', 'Email Enviado'),
        ('email_received', 'Email Recibido'),
    ]
    entry_type = models.CharField(max_length=50, choices=ENTRY_TYPES)

    # Contenido
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)  # Datos estructurados sobre el evento

    # Para entradas de notas, enlace a la nota real
    note = models.ForeignKey(Note, on_delete=models.SET_NULL, null=True, blank=True)

    # Quién y cuándo
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_content_type', 'target_id', '-created_at']),
        ]

    @classmethod
    def log_status_change(cls, target, old_status, new_status, actor):
        """Registra un evento de cambio de estado."""
        ct = ContentType.objects.get_for_model(target)
        return cls.objects.create(
            target_content_type=ct,
            target_id=str(target.pk),
            entry_type='status_change',
            title=f"Estado cambiado de {old_status} a {new_status}",
            metadata={'old_status': old_status, 'new_status': new_status},
            actor=actor
        )

    @classmethod
    def from_note(cls, note):
        """Crea entrada de actividad desde una nota."""
        return cls.objects.create(
            target_content_type=note.target_content_type,
            target_id=note.target_id,
            entry_type='note',
            title=f"{note.get_note_type_display()} por {note.created_by}",
            note=note,
            actor=note.created_by,
            created_at=note.created_at
        )
```

## Plantillas y Fragmentos

Plantillas de notas predefinidas:

```python
class NoteTemplate(models.Model):
    """Plantillas de notas reutilizables."""

    name = models.CharField(max_length=255)
    content = models.TextField()
    note_type = models.CharField(max_length=50, default='general')

    # Dónde aplica esta plantilla
    applies_to = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    is_shared = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def render(self, context=None):
        """Renderiza plantilla con variables de contexto."""
        from django.template import Template, Context
        template = Template(self.content)
        return template.render(Context(context or {}))
```

## Por Qué Esto Importa Después

La primitiva de Notas se conecta con:

- **Identidad** (Capítulo 6): Las notas son creadas por usuarios, mencionan usuarios.
- **Flujo de Trabajo** (Capítulo 11): Las notas explican transiciones de estado.
- **Auditoría** (Capítulo 13): Las notas son parte del rastro de auditoría.
- **Decisiones** (Capítulo 12): Las notas capturan la justificación de decisiones.

La toma de notas parece simple hasta que necesitas:
- Reconstruir el historial completo de una relación con el cliente
- Probar qué fue comunicado y cuándo
- Buscar en todas las notas menciones de un problema de producto
- Mostrar una línea de tiempo de todo lo que pasó con una cuenta

La primitiva de Notas maneja la complejidad para que tu aplicación no tenga que reinventarla.

---

## Cómo Reconstruir Esta Primitiva

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-notes | `docs/prompts/django-notes.md` | ~25 tests |

### Usando el Prompt

```bash
cat docs/prompts/django-notes.md | claude

# Solicitud: "Implementar modelo Note con target GenericFK,
# controles de visibilidad (público/privado/interno),
# y extracción de @menciones con registros NoteMention."
```

### Restricciones Clave

- **Target GenericFK**: Las notas se adjuntan a cualquier modelo
- **Preservación de eliminación suave**: Las notas eliminadas permanecen para auditoría
- **Procesamiento de menciones**: Extraer @usernames y crear registros NoteMention
- **Soporte de hilos**: Las notas pueden responder a otras notas via FK parent

Si Claude elimina permanentemente notas u omite la extracción de menciones, eso es una violación de restricción.

---

*Estado: Borrador*
