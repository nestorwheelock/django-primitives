# Capitulo 5: La Capa de Fundacion

> "Todo gran edificio descansa sobre cimientos que nadie ve."

---

Antes de construir primitivas de negocio, necesitas la infraestructura que las hace funcionar. La capa de Fundacion proporciona cuatro paquetes de los que depende cada otra primitiva: modelos base, configuracion singleton, organizacion de modulos y limites de capas.

Estos no son emocionantes. No resuelven problemas de negocio directamente. Pero sin ellos, cada primitiva reinventaria los mismos patrones—claves primarias UUID, campos de marca de tiempo, gestion de configuracion, limites de importacion—y los obtendria mal de diferentes maneras.

La capa de Fundacion es donde pagas el impuesto aburrido una vez, para no pagarlo nunca mas.

## Los Cuatro Paquetes de Fundacion

| Paquete | Proposito |
|---------|-----------|
| django-basemodels | Patrones comunes de modelo: UUIDs, marcas de tiempo, eliminacion suave |
| django-singleton | Configuracion que existe exactamente una vez |
| django-modules | Organiza modelos relacionados en unidades descubribles |
| django-layers | Aplica limites de importacion entre paquetes |

Cada primitiva en este libro hereda de estas fundaciones. Entenderlas explica por que las primitivas de negocio se ven como se ven.

---

## django-basemodels: Los Patrones Que Siempre Necesitas

Cada modelo de negocio necesita las mismas cosas:

- Una clave primaria que no filtre informacion
- Marcas de tiempo para cuando fue creado y modificado
- Eliminacion suave para que nada desaparezca realmente
- Campos de auditoria para quien hizo que

Escribir estos patrones en cada modelo es tedioso y propenso a errores. Olvidar un campo en un modelo crea inconsistencia que te persigue durante las auditorias.

### UUIDModel

La base mas simple: una clave primaria UUID en lugar de enteros auto-incrementales.

```python
import uuid
from django.db import models


class UUIDModel(models.Model):
    """Modelo base con clave primaria UUID."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    class Meta:
        abstract = True
```

**Por que importan los UUIDs:**

1. **Sin fuga de informacion.** Los IDs secuenciales revelan cuantos registros existen. `/users/1` hasta `/users/47` le dice a los atacantes que hay 47 usuarios. `/users/a1b2c3d4-...` no revela nada.

2. **Sin colision al fusionar.** Cuando fusionas bases de datos—despues de una adquisicion, despues de una recuperacion de desastres—los IDs secuenciales colisionan. Los UUIDs no.

3. **Generacion del lado del cliente.** Puedes crear el ID antes de que exista el registro, habilitando patrones de UI optimista y aplicaciones offline-first.

4. **Sistemas distribuidos.** No se requiere coordinacion. Cualquier nodo puede generar IDs independientemente.

### TimestampedModel

Agrega marcas de tiempo de creacion y modificacion:

```python
class TimestampedModel(UUIDModel):
    """Modelo base con UUID y marcas de tiempo."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

Estas son marcas de tiempo del sistema—cuando la base de datos registro el evento, no cuando sucedio en el mundo real. El Capitulo 7 (Tiempo) explica por que esta distincion importa.

### SoftDeleteModel

Nada deberia desaparecer realmente:

```python
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet que excluye registros eliminados suavemente por defecto."""

    def delete(self):
        """Elimina suavemente todos los registros en el queryset."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Realmente elimina registros. Usar con extrema precaucion."""
        return super().delete()

    def alive(self):
        """Solo registros no eliminados."""
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        """Solo registros eliminados suavemente."""
        return self.filter(deleted_at__isnull=False)

    def with_deleted(self):
        """Todos los registros, incluyendo eliminados suavemente."""
        return self.all()


class SoftDeleteManager(models.Manager):
    """Manager que excluye registros eliminados suavemente por defecto."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteModel(TimestampedModel):
    """Modelo base con soporte de eliminacion suave."""

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Escape cuando necesitas todo

    def delete(self, *args, **kwargs):
        """Elimina suavemente este registro."""
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at', 'updated_at'])

    def hard_delete(self, *args, **kwargs):
        """Realmente elimina este registro. Usar con extrema precaucion."""
        super().delete(*args, **kwargs)

    def restore(self):
        """Restaura un registro eliminado suavemente."""
        self.deleted_at = None
        self.save(update_fields=['deleted_at', 'updated_at'])

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    class Meta:
        abstract = True
```

**Por que eliminacion suave:**

1. **Los rastros de auditoria necesitan historial.** No puedes auditar lo que eliminaste.

2. **La recuperacion es posible.** Las eliminaciones accidentales pueden deshacerse.

3. **Las referencias no se rompen.** Las claves foraneas a registros eliminados aun resuelven.

4. **El cumplimiento lo requiere.** Muchas regulaciones requieren retener registros por anos.

### BaseModel: El Estandar

A partir de v0.2.0, `BaseModel` combina los tres patrones en la clase base estandar para todos los modelos de dominio:

```python
class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """La clase base estandar para todos los modelos de dominio.

    Proporciona:
    - id: Clave primaria UUID (globalmente unica, no adivinable)
    - created_at: Cuando se creo el registro
    - updated_at: Cuando se modifico por ultima vez el registro
    - deleted_at: Marca de tiempo de eliminacion suave (None si activo)
    - objects: Manager que excluye registros eliminados
    - all_objects: Manager que incluye todos los registros
    """
    class Meta:
        abstract = True
```

**Usa BaseModel.** No combines las piezas manualmente. No "elijas el nivel que necesitas." BaseModel es la respuesta para modelos de dominio.

```python
from django_basemodels import BaseModel

class Invoice(BaseModel):
    """Una factura. Obtiene UUID, marcas de tiempo, eliminacion suave automaticamente."""
    number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'billing'
```

**La jerarquia de herencia:**

```
UUIDModel ─────────────┐
TimeStampedModel ──────┼──► BaseModel (usa este)
SoftDeleteModel ───────┘
```

Los mixins individuales aun existen para casos raros donde necesitas solo parte del patron. Pero esos casos son raros. Si estas buscando `TimeStampedModel` solo, preguntate por que no quieres claves primarias UUID y eliminacion suave. Usualmente, si las quieres.

### AuditedModel

Para modelos que necesitan rastrear quien hizo cambios (no solo cuando):

```python
from django.conf import settings


class AuditedModel(BaseModel):
    """Modelo base con soporte completo de auditoria."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(class)s_created',
        null=True, blank=True
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(class)s_updated',
        null=True, blank=True
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(class)s_deleted',
        null=True, blank=True
    )

    class Meta:
        abstract = True
```

La mayoria de los modelos de negocio usan `BaseModel`. Los modelos que necesitan rastreo de actores usan `AuditedModel`.

### El Patron de Capa de Servicio

Los modelos definen estructura. Los servicios aplican reglas de negocio.

Este es un principio fundamental que aplica a todas las primitivas. Cuando un modelo tiene invariantes, reglas de negocio u operaciones de multiples pasos, estas viven en una capa de servicio—no en `model.save()`.

```python
# models.py - define solo estructura
class Agreement(BaseModel):
    terms = models.JSONField()
    current_version = models.PositiveIntegerField(default=1)
    valid_from = models.DateTimeField()  # SIN DEFAULT - el servicio lo proporciona
    valid_to = models.DateTimeField(null=True, blank=True)


# services.py - aplica reglas de negocio
from django.db import transaction

def create_agreement(party_a, party_b, terms, agreed_by, valid_from=None):
    """Crea acuerdo con version inicial."""
    if valid_from is None:
        valid_from = timezone.now()  # El servicio proporciona default conveniente

    with transaction.atomic():
        agreement = Agreement.objects.create(
            party_a=party_a,
            party_b=party_b,
            terms=terms,
            agreed_by=agreed_by,
            valid_from=valid_from,
        )
        AgreementVersion.objects.create(
            agreement=agreement,
            version=1,
            terms=terms,
            reason="Acuerdo inicial",
        )
    return agreement
```

**Por que servicios?**

1. **Operaciones atomicas.** Crear un acuerdo requiere crear un registro de version tambien. El servicio envuelve ambos en una transaccion.

2. **Aplicacion de invariantes.** El servicio asegura que `Agreement.current_version` siempre iguale `max(AgreementVersion.version)`.

3. **Defaults convenientes.** El modelo requiere `valid_from`—sin default. El servicio puede defaultearlo a "ahora" como conveniencia. El modelo aplica correccion; el servicio proporciona conveniencia.

4. **Seguridad de concurrencia.** Los servicios usan `select_for_update()` al incrementar contadores de version.

Este patron aparece a lo largo de las primitivas. El Capitulo 8 (Acuerdos) lo muestra en detalle completo.

---

## django-singleton: Configuracion Que Existe Una Vez

Algunas cosas deberian existir exactamente una vez: configuraciones del sitio, feature flags, limites de tasa, el plan de facturacion actual. Estas son configuraciones, no colecciones.

El enfoque ingenuo es un modelo regular con logica de negocio asegurando que solo exista un registro. Esto falla bajo acceso concurrente—dos solicitudes pueden cada una verificar "existe un registro?" y ambas crear uno.

### El Patron Singleton

```python
from django.db import models
from django.core.cache import cache


class SingletonModel(models.Model):
    """Un modelo que solo puede tener una instancia."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Fuerza la clave primaria a siempre ser 1
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalida cache al guardar
        cache.delete(self._cache_key())

    def delete(self, *args, **kwargs):
        # Previene eliminacion
        raise ValueError("Las instancias singleton no pueden ser eliminadas")

    @classmethod
    def _cache_key(cls):
        return f'singleton_{cls.__name__}'

    @classmethod
    def load(cls):
        """Carga la instancia singleton, creando si es necesario."""
        cache_key = cls._cache_key()
        instance = cache.get(cache_key)

        if instance is None:
            instance, _ = cls.objects.get_or_create(pk=1)
            cache.set(cache_key, instance, timeout=3600)

        return instance
```

### Ejemplo de Uso

```python
class SiteSettings(SingletonModel):
    """Configuracion global del sitio."""

    site_name = models.CharField(max_length=255, default="Mi Sitio")
    maintenance_mode = models.BooleanField(default=False)
    max_upload_size_mb = models.IntegerField(default=10)
    feature_new_checkout = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Configuracion del Sitio"
        verbose_name_plural = "Configuracion del Sitio"


# Uso
settings = SiteSettings.load()
if settings.maintenance_mode:
    return HttpResponse("Sitio en mantenimiento", status=503)
```

### Por Que No Django Settings?

El `settings.py` de Django requiere un reinicio para cambiar. Los modelos singleton pueden cambiarse en tiempo de ejecucion a traves de la interfaz de admin o llamadas API.

Usa Django settings para:
- Conexiones de base de datos
- Claves secretas
- Apps instaladas
- Configuracion de middleware

Usa modelos singleton para:
- Feature flags
- Limites de tasa
- Texto de visualizacion
- Reglas de negocio que cambian sin deployments

---

## django-modules: Organizando Modelos Relacionados

A medida que tu aplicacion crece, tendras docenas de modelos. Algunos pertenecen juntos—comparten conceptos, se referencian entre si, son mantenidos por el mismo equipo. Los modulos hacen estas relaciones explicitas.

### El Registro de Modulos

```python
from django.apps import apps


class ModuleRegistry:
    """Registro de todos los modulos de la aplicacion."""

    _modules = {}

    @classmethod
    def register(cls, name, models, description=""):
        """Registra un modulo con sus modelos."""
        cls._modules[name] = {
            'models': models,
            'description': description,
        }

    @classmethod
    def get_module(cls, name):
        """Obtiene un modulo registrado por nombre."""
        return cls._modules.get(name)

    @classmethod
    def all_modules(cls):
        """Obtiene todos los modulos registrados."""
        return dict(cls._modules)

    @classmethod
    def models_for_module(cls, name):
        """Obtiene todos los modelos en un modulo."""
        module = cls.get_module(name)
        if module:
            return [apps.get_model(m) for m in module['models']]
        return []


# Registro en apps.py
class IdentityConfig(AppConfig):
    name = 'django_parties'

    def ready(self):
        ModuleRegistry.register(
            'identity',
            models=[
                'django_parties.Party',
                'django_parties.Person',
                'django_parties.Organization',
                'django_rbac.Role',
                'django_rbac.Permission',
            ],
            description='Primitivas de identidad y control de acceso'
        )
```

### Por Que Importan los Modulos

1. **Documentacion.** "Que modelos estan involucrados en identidad?" tiene una respuesta clara.

2. **Permisos.** Otorga acceso a modulos completos, no modelos individuales.

3. **Exportar/Importar.** Volcar y restaurar datos relacionados juntos.

4. **Pruebas.** Prueba modulos en aislamiento con limites claros.

5. **Incorporacion.** Los nuevos desarrolladores entienden la estructura del sistema.

---

## django-layers: Aplicando Limites

El paquete de fundacion mas importante te previene de cometer errores arquitectonicos. Las capas definen que puede importar que.

### La Regla de Dependencia

Del CLAUDE.md del proyecto:

> **Regla de Dependencia:** Nunca importes desde una capa superior. La Fundacion no tiene dependencias. Cada capa solo importa de capas debajo de ella.

Esto no es una sugerencia. Esta aplicado por codigo.

### Configuracion de Capas

```yaml
# layers.yaml
layers:
  - name: foundation
    packages:
      - django_basemodels
      - django_singleton
      - django_modules
      - django_layers
    allowed_imports: []  # Fundacion no importa nada de nuestro codigo

  - name: identity
    packages:
      - django_parties
      - django_rbac
    allowed_imports:
      - foundation

  - name: infrastructure
    packages:
      - django_decisioning
      - django_audit_log
    allowed_imports:
      - foundation
      - identity

  - name: domain
    packages:
      - django_catalog
      - django_encounters
      - django_worklog
      - django_geo
      - django_ledger
    allowed_imports:
      - foundation
      - identity
      - infrastructure

  - name: content
    packages:
      - django_documents
      - django_notes
      - django_agreements
    allowed_imports:
      - foundation
      - identity
      - infrastructure
      - domain

  - name: value_objects
    packages:
      - django_money
      - django_sequence
    allowed_imports:
      - foundation  # Los objetos de valor son mayormente independientes
```

### El Verificador de Capas

```python
import ast
import sys
from pathlib import Path
import yaml


def load_layer_config(path='layers.yaml'):
    """Carga configuracion de capas desde archivo YAML."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_layer_for_package(package_name, config):
    """Encuentra a que capa pertenece un paquete."""
    for layer in config['layers']:
        if package_name in layer['packages']:
            return layer['name']
    return None


def get_allowed_imports(layer_name, config):
    """Obtiene lista de paquetes de los que esta capa puede importar."""
    allowed_packages = set()
    for layer in config['layers']:
        if layer['name'] == layer_name:
            for allowed_layer in layer['allowed_imports']:
                for l in config['layers']:
                    if l['name'] == allowed_layer:
                        allowed_packages.update(l['packages'])
            break
    return allowed_packages


def check_imports(file_path, config):
    """Verifica si los imports de un archivo violan limites de capas."""
    violations = []

    with open(file_path) as f:
        tree = ast.parse(f.read())

    # Determina a que paquete pertenece este archivo
    package_name = None
    for part in Path(file_path).parts:
        if part.startswith('django_'):
            package_name = part
            break

    if not package_name:
        return violations

    current_layer = get_layer_for_package(package_name, config)
    if not current_layer:
        return violations

    allowed = get_allowed_imports(current_layer, config)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_pkg = alias.name.split('.')[0]
                if imported_pkg.startswith('django_'):
                    if imported_pkg not in allowed and imported_pkg != package_name:
                        violations.append({
                            'file': file_path,
                            'line': node.lineno,
                            'import': alias.name,
                            'message': f'{package_name} no puede importar de {imported_pkg}'
                        })

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_pkg = node.module.split('.')[0]
                if imported_pkg.startswith('django_'):
                    if imported_pkg not in allowed and imported_pkg != package_name:
                        violations.append({
                            'file': file_path,
                            'line': node.lineno,
                            'import': node.module,
                            'message': f'{package_name} no puede importar de {imported_pkg}'
                        })

    return violations


def check_all_layers(packages_dir='packages', config_path='layers.yaml'):
    """Verifica todos los paquetes por violaciones de capas."""
    config = load_layer_config(config_path)
    all_violations = []

    for py_file in Path(packages_dir).rglob('*.py'):
        violations = check_imports(str(py_file), config)
        all_violations.extend(violations)

    return all_violations


if __name__ == '__main__':
    violations = check_all_layers()
    if violations:
        print("Violaciones de capas encontradas:")
        for v in violations:
            print(f"  {v['file']}:{v['line']} - {v['message']}")
        sys.exit(1)
    else:
        print("No se encontraron violaciones de capas.")
        sys.exit(0)
```

### Ejecutando la Verificacion

```bash
# Verificar limites de capas
python -m django_layers check

# En pipeline CI/CD
python -m django_layers check || exit 1
```

### Por Que Importan las Capas

Sin limites aplicados:

1. **Emergen dependencias circulares.** Identidad importa de Ledger importa de Identidad.

2. **Los cambios cascadean.** Modificar un paquete de bajo nivel rompe todo arriba.

3. **Las pruebas se vuelven imposibles.** No puedes probar Identidad sin tambien cargar Ledger, Catalog y todo lo demas.

4. **Los modelos mentales se rompen.** Los desarrolladores no pueden razonar sobre el sistema en piezas.

Con limites aplicados:

1. **Dependencias claras.** Sabes exactamente que necesita cada paquete.

2. **Pruebas aisladas.** Prueba cada capa independientemente.

3. **Refactorizacion segura.** Los cambios en capas superiores no pueden romper capas inferiores.

4. **Arquitectura comprensible.** Los nuevos desarrolladores captan la estructura rapidamente.

---

## Relacion con los Built-ins de Django

La capa de Fundacion no reemplaza las apps integradas de Django. Las extiende.

### Lo Que Proporciona Django

| App de Django | Proposito |
|---------------|-----------|
| django.contrib.auth | Modelo de usuario, autenticacion, permisos basicos |
| django.contrib.contenttypes | Claves foraneas genericas, metadatos de modelo |
| django.contrib.sessions | Gestion de sesiones |
| django.contrib.admin | Interfaz de administracion |

### Lo Que Agrega Fundacion

| Paquete de Fundacion | Extiende Django Como |
|---------------------|----------------------|
| django-basemodels | Proporciona clases base abstractas de las que heredan los modelos Django |
| django-singleton | Proporciona un patron que Django no tiene nativamente |
| django-modules | Organiza apps de Django en agrupaciones logicas |
| django-layers | Aplica reglas de importacion entre apps de Django |

### Los Puntos de Integracion

```python
# django-basemodels usa el sistema de modelos de Django
from django.db import models

class UUIDModel(models.Model):  # Hereda de Django
    ...

# django-singleton usa el framework de cache de Django
from django.core.cache import cache

# AuditedModel referencia el modelo de usuario de Django
from django.conf import settings

class AuditedModel(SoftDeleteModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Usa la configuracion de modelo de usuario de Django
        ...
    )
```

### Integracion de AUTH_USER_MODEL

Cada primitiva que rastrea "quien hizo esto" referencia el modelo de usuario de Django a traves de `settings.AUTH_USER_MODEL`. Esto funciona ya sea que uses el `User` predeterminado de Django, un modelo de usuario personalizado, o un sistema de autenticacion de terceros.

```python
# En settings.py
AUTH_USER_MODEL = 'myapp.CustomUser'

# En primitivas
from django.conf import settings

class Decision(models.Model):
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
```

A las primitivas no les importa como se ve tu modelo de usuario. Solo necesitan algo a que apuntar.

---

## Instalacion y Configuracion

### 1. Instalar los Paquetes de Fundacion

```bash
pip install django-basemodels django-singleton django-modules django-layers
```

O en desarrollo:

```bash
pip install -e packages/django-basemodels
pip install -e packages/django-singleton
pip install -e packages/django-modules
pip install -e packages/django-layers
```

### 2. Agregar a INSTALLED_APPS

```python
INSTALLED_APPS = [
    # Built-ins de Django primero
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Capa de fundacion
    'django_basemodels',
    'django_singleton',
    'django_modules',
    'django_layers',

    # Tus otras primitivas y apps...
]
```

### 3. Crear layers.yaml

```yaml
# layers.yaml en la raiz del proyecto
layers:
  - name: foundation
    packages:
      - django_basemodels
      - django_singleton
      - django_modules
      - django_layers
    allowed_imports: []

  # Agregar otras capas a medida que agregas paquetes...
```

### 4. Agregar Verificacion de Capas a CI

```yaml
# .github/workflows/ci.yml
- name: Verificar limites de capas
  run: python -m django_layers check
```

---

## Por Que Esto Importa Despues

La capa de Fundacion es invisible en aplicaciones funcionando. No piensas en claves primarias UUID cuando consultas facturas. No piensas en eliminacion suave cuando muestras una lista de clientes. La fundacion simplemente funciona.

Esa invisibilidad es el punto.

Cada primitiva en la Parte II hereda de `BaseModel`. Cada primitiva respeta los limites de capas. Cada primitiva puede probarse en aislamiento porque la arquitectura es limpia.

Cuando veas `class Invoice(BaseModel)` en el Capitulo 10, sabras:
- Tiene una clave primaria UUID
- Tiene marcas de tiempo created_at y updated_at
- Llamar delete() establece deleted_at en lugar de eliminar la fila
- Las consultas por defecto excluyen registros eliminados suavemente
- Puedes acceder a registros eliminados a traves de `all_objects`

Cuando veas un archivo `services.py`, sabras:
- Las reglas de negocio viven ahi, no en `model.save()`
- Las operaciones de multiples pasos son atomicas
- Los invariantes se aplican
- Los defaults convenientes se proporcionan

Sabes todo esto porque la capa de Fundacion lo definio una vez, correctamente.

Las fundaciones aburridas habilitan la logica de negocio interesante. Construyelas bien, y nunca piensas en ellas de nuevo.

---

## Como Reconstruir Estas Primitivas

Los paquetes de Fundacion pueden reconstruirse desde cero usando prompts restringidos. Cada paquete tiene una especificacion detallada en `docs/prompts/`:

| Paquete | Archivo de Prompt | Cantidad de Tests |
|---------|-------------------|-------------------|
| django-basemodels | `docs/prompts/django-basemodels.md` | 30 tests |
| django-singleton | `docs/prompts/django-singleton.md` | ~15 tests |
| django-modules | `docs/prompts/django-modules.md` | ~20 tests |
| django-layers | `docs/prompts/django-layers.md` | ~25 tests |

### Usando los Prompts

Cada archivo de prompt contiene:

1. **Instruccion** - Que construir y por que
2. **Estructura de Archivos** - Disposicion exacta de directorios
3. **Especificacion de Modelos** - Campos, metodos, comportamientos
4. **Casos de Prueba** - Tests numerados para implementar primero (TDD)
5. **Errores Conocidos** - Errores comunes a evitar
6. **Criterios de Aceptacion** - Definicion de terminado

### Flujo de Trabajo de Ejemplo

Para reconstruir `django-basemodels`:

```bash
# Paso 1: Dale a Claude el prompt
cat docs/prompts/django-basemodels.md | claude

# Paso 2: Solicita enfoque TDD
"Comienza con los tests de TimeStampedModel. Escribe tests fallidos primero,
luego implementa codigo minimo para pasar."

# Paso 3: Verifica restricciones
# - Solo modelos abstractos (sin migraciones)
# - SoftDeleteManager es el manager por defecto
# - El gotcha de QuerySet.delete() esta documentado
```

### Restriccion Clave

Los prompts aplican la regla **SIN MIGRACIONES DE BASE DE DATOS** para modelos base abstractos. Si Claude genera archivos de migracion para estos paquetes, eso es una violacion de restriccion—los modelos abstractos no crean tablas.

---

## Referencias

- Documentacion de Modelos de Django: https://docs.djangoproject.com/en/stable/topics/db/models/
- Clases base abstractas de Django: https://docs.djangoproject.com/en/stable/topics/db/models/#abstract-base-classes
- Especificacion UUID: RFC 4122
- El Patron Singleton: Gamma, Helm, Johnson, Vlissides. *Design Patterns*. Addison-Wesley, 1994.
- Arquitectura Hexagonal: Cockburn, Alistair. "Hexagonal Architecture." 2005.
- Arquitectura Limpia: Martin, Robert C. *Clean Architecture*. Prentice Hall, 2017.

---

*Estado: Borrador*
