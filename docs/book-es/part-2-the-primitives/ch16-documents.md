# Capítulo 16: Documentos

> "El rastro de papel que prueba todo."

---

Los negocios funcionan con documentos. Contratos. Facturas. Recibos. Informes. Políticas. Formularios. Cada acción empresarial significativa produce un documento o requiere uno como entrada.

La primitiva de Documentos captura el almacenamiento de documentos, versionado y ciclo de vida con la precisión que el cumplimiento normativo, la auditoría y la colaboración requieren.

## El Problema que Resuelven los Documentos

La gestión de documentos falla de maneras predecibles:

**Archivos perdidos.** Documentos almacenados en adjuntos de correo electrónico, carpetas locales o unidades en la nube aleatorias no pueden encontrarse cuando se necesitan.

**Sin versionado.** "Final_v2_FINAL_revisado.pdf" no es control de versiones. Cuando surgen disputas, ¿qué versión fue firmada?

**Metadatos faltantes.** Un archivo PDF llamado "contrato.pdf" no te dice nada. ¿Cuándo fue creado? ¿Por quién? ¿Para qué propósito? ¿Sigue siendo válido?

**Enlaces rotos.** Los documentos referenciados por transacciones se vuelven inaccesibles cuando los sistemas de almacenamiento cambian.

**Sin política de retención.** ¿Cuánto tiempo debes guardar este documento? ¿Cuándo puedes eliminarlo? Sin política, o guardas todo para siempre o eliminas cosas que no deberías.

## El Modelo Document

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_basemodels.models import SoftDeleteModel
import hashlib
import uuid


def document_upload_path(instance, filename):
    """Genera ruta de carga: documents/{year}/{month}/{uuid}/{filename}"""
    from django.utils import timezone
    now = timezone.now()
    return f"documents/{now.year}/{now.month:02d}/{instance.id}/{filename}"


class Document(SoftDeleteModel):
    """Un documento gestionado con versionado y metadatos."""

    # Identificador único
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Metadatos del documento
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    DOCUMENT_TYPES = [
        ('contract', 'Contrato'),
        ('invoice', 'Factura'),
        ('receipt', 'Recibo'),
        ('report', 'Informe'),
        ('policy', 'Política'),
        ('form', 'Formulario'),
        ('correspondence', 'Correspondencia'),
        ('certificate', 'Certificado'),
        ('license', 'Licencia'),
        ('other', 'Otro'),
    ]
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='other')

    # Almacenamiento de archivo
    file = models.FileField(upload_to=document_upload_path)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=64)  # SHA-256

    # Enlace a cualquier modelo
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    related_id = models.CharField(max_length=255, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_id')

    # Autoría
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Estado
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('superseded', 'Reemplazado'),
        ('archived', 'Archivado'),
        ('expired', 'Expirado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Versionado
    version = models.PositiveIntegerField(default=1)
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='newer_versions'
    )

    # Validez
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)

    # Retención
    retention_years = models.PositiveIntegerField(default=7)
    can_delete_after = models.DateField(null=True, blank=True)

    # Seguridad
    is_confidential = models.BooleanField(default=False)
    access_level = models.CharField(max_length=50, default='internal')

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['document_type', 'status']),
            models.Index(fields=['related_content_type', 'related_id']),
            models.Index(fields=['file_hash']),
        ]

    def save(self, *args, **kwargs):
        # Calcular hash del archivo si es nuevo
        if self.file and not self.file_hash:
            self.file_hash = self._calculate_hash()

        # Establecer metadatos del archivo
        if self.file:
            self.file_name = self.file.name.split('/')[-1]
            self.file_size = self.file.size

        super().save(*args, **kwargs)

    def _calculate_hash(self):
        """Calcula hash SHA-256 del contenido del archivo."""
        sha256 = hashlib.sha256()
        for chunk in self.file.chunks():
            sha256.update(chunk)
        return sha256.hexdigest()

    def verify_integrity(self):
        """Verifica que el archivo no ha sido modificado."""
        current_hash = self._calculate_hash()
        return current_hash == self.file_hash

    def create_new_version(self, new_file, uploaded_by, **kwargs):
        """Crea una nueva versión de este documento."""
        new_doc = Document.objects.create(
            title=self.title,
            description=kwargs.get('description', self.description),
            document_type=self.document_type,
            file=new_file,
            mime_type=kwargs.get('mime_type', self.mime_type),
            related_content_type=self.related_content_type,
            related_id=self.related_id,
            uploaded_by=uploaded_by,
            version=self.version + 1,
            previous_version=self,
            retention_years=self.retention_years,
            is_confidential=self.is_confidential,
            access_level=self.access_level,
        )

        # Marcar esta versión como reemplazada
        self.status = 'superseded'
        self.save()

        return new_doc

    @property
    def is_expired(self):
        if self.expiration_date:
            from django.utils import timezone
            return self.expiration_date < timezone.now().date()
        return False

    @property
    def version_history(self):
        """Obtiene todas las versiones de este documento."""
        versions = [self]
        current = self.previous_version
        while current:
            versions.append(current)
            current = current.previous_version
        return versions

    def __str__(self):
        return f"{self.title} (v{self.version})"
```

## Colecciones de Documentos

Agrupa documentos relacionados:

```python
class DocumentCollection(SoftDeleteModel):
    """Una carpeta o colección de documentos relacionados."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children'
    )

    # Enlace a cualquier modelo
    owner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    owner_id = models.CharField(max_length=255, blank=True)
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    documents = models.ManyToManyField(Document, blank=True, related_name='collections')

    class Meta:
        ordering = ['name']

    @property
    def path(self):
        """Ruta completa desde la raíz."""
        parts = [self.name]
        current = self.parent
        while current:
            parts.insert(0, current.name)
            current = current.parent
        return '/'.join(parts)

    @property
    def all_documents(self):
        """Todos los documentos incluyendo los de colecciones hijas."""
        docs = list(self.documents.all())
        for child in self.children.all():
            docs.extend(child.all_documents)
        return docs
```

## Requisitos de Documentos

Define qué documentos son requeridos:

```python
class DocumentRequirement(models.Model):
    """Definición de un documento requerido."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=50)

    # A qué se aplica esto
    applies_to_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    is_required = models.BooleanField(default=True)
    expires_after_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']


class DocumentCompliance(models.Model):
    """Seguimiento del cumplimiento de documentos para una entidad."""

    requirement = models.ForeignKey(DocumentRequirement, on_delete=models.CASCADE)

    # Para qué entidad es esto
    entity_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    entity_id = models.CharField(max_length=255)
    entity = GenericForeignKey('entity_content_type', 'entity_id')

    # El documento que satisface el requisito
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendiente'),
        ('compliant', 'Cumple'),
        ('expired', 'Expirado'),
        ('missing', 'Faltante'),
    ], default='pending')

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        unique_together = ['requirement', 'entity_content_type', 'entity_id']
```

## Control de Acceso a Documentos

```python
class DocumentAccess(models.Model):
    """Permisos de acceso para un documento."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_grants')

    # Quién tiene acceso
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    role = models.CharField(max_length=100, blank=True)  # Para acceso basado en roles

    # Qué acceso
    can_view = models.BooleanField(default=True)
    can_download = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_share = models.BooleanField(default=False)

    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_grants_given'
    )
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['document', 'user']
```

## Por Qué Esto Importa Después

La primitiva de Documentos se conecta con:

- **Identidad** (Capítulo 6): Los documentos tienen propietarios y listas de acceso.
- **Acuerdos** (Capítulo 8): Los contratos son documentos.
- **Auditoría** (Capítulo 13): El acceso a documentos se registra.
- **Flujo de Trabajo** (Capítulo 11): Los documentos fluyen a través de procesos de aprobación.

La gestión de documentos parece simple hasta que necesitas:
- Probar qué versión de un contrato fue firmada
- Demostrar cumplimiento con políticas de retención
- Controlar quién puede ver documentos confidenciales
- Rastrear cada acceso a archivos sensibles

La primitiva de Documentos maneja la complejidad para que tu aplicación no tenga que reinventarla.

---

## Cómo Reconstruir Esta Primitiva

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-documents | `docs/prompts/django-documents.md` | ~30 tests |

### Usando el Prompt

```bash
cat docs/prompts/django-documents.md | claude

# Solicitud: "Implementar modelo Document con historial de versiones,
# GenericFK para adjuntar a cualquier modelo, y metadatos de archivo.
# Agregar DocumentCollection para jerarquía de carpetas."
```

### Restricciones Clave

- **Versiones inmutables**: Los registros de DocumentVersion no pueden ser modificados
- **Hash de contenido**: SHA-256 del contenido del archivo para verificación de integridad
- **Eliminación suave**: Los documentos nunca se eliminan permanentemente
- **Adjunto con GenericFK**: Los documentos se adjuntan a cualquier modelo

Si Claude permite editar versiones de documentos o omite el hash de contenido, eso es una violación de restricción.

---

*Estado: Borrador*
