# Capítulo 21: Generación Schema-First

## La Prueba de Reconstrucción

En 2023, un desarrollador borró accidentalmente un paquete completo de Django de un monorepo. Treinta y siete modelos, 80 pruebas, 2,000 líneas de código. Desaparecido.

Tres horas después, el paquete fue reconstruido desde cero. Cada modelo, cada campo, cada prueba. El nuevo código era funcionalmente idéntico al original.

Esto no fue magia. No fue una habilidad extraordinaria de programación. Fue el resultado de una práctica simple: generación schema-first.

El paquete tenía un prompt de reconstrucción. El prompt especificaba cada modelo, cada campo, cada caso de prueba. Cuando el código se perdió, regenerarlo fue simplemente ejecutar el prompt de nuevo.

Este capítulo explica cómo escribir prompts que hacen tu código reproducible.

---

## Por Qué Funciona Schema-First

Cuando le pides a la IA que "cree un modelo para rastrear sesiones de trabajo", obtienes lo que la IA piensa que debería ser un modelo de sesión de trabajo.

Hoy podrías obtener:
```python
class WorkSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
```

Mañana, con el mismo prompt, podrías obtener:
```python
class Session(models.Model):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(null=True)
```

Ambos son razonables. Ninguno es reproducible.

La generación schema-first elimina esta varianza especificando exactamente cuál debe ser la salida:

```markdown
### Modelo WorkSession

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| id | UUIDField | primary_key=True, default=uuid.uuid4 |
| user | ForeignKey | settings.AUTH_USER_MODEL, on_delete=PROTECT |
| started_at | DateTimeField | default=timezone.now |
| stopped_at | DateTimeField | null=True, blank=True |
| duration_seconds | IntegerField | null=True, blank=True |
```

Con este schema, cada regeneración produce el mismo modelo. Los nombres de campos coinciden. Los tipos coinciden. Las restricciones coinciden. Las pruebas que dependen de estos campos continúan funcionando.

---

## La Anatomía de un Prompt de Reconstrucción

Un prompt de reconstrucción es una especificación completa para generar un paquete desde cero. Tiene seis secciones:

### 1. Propósito del Paquete

Un párrafo explicando qué hace este paquete y por qué existe.

```markdown
## Propósito del Paquete

Proporcionar primitivas de seguimiento de tiempo para registrar sesiones de trabajo.
Las sesiones tienen un tiempo de inicio, tiempo de fin opcional, y pueden adjuntarse
a cualquier modelo vía GenericForeignKey. Solo una sesión por usuario puede
estar activa a la vez (iniciar una nueva sesión detiene la anterior).
```

Esto no es texto de marketing. Es la respuesta de una oración a "¿qué hace esto?"

### 2. Dependencias

Lo que este paquete requiere para funcionar.

```markdown
## Dependencias

- Django >= 4.2
- django-basemodels (para UUIDModel)
- django.contrib.contenttypes (para GenericForeignKey)
- django.contrib.auth (para referencia de usuario)
```

Las dependencias son tanto de runtime (lo que debe estar instalado) como conceptuales (qué patrones deben entenderse).

### 3. Estructura de Archivos

Los archivos exactos que deben crearse.

```markdown
## Estructura de Archivos

packages/django-worklog/
├── pyproject.toml
├── README.md
├── src/django_worklog/
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
    ├── test_models.py
    └── test_services.py
```

La IA sabe exactamente qué crear. No se requiere invención.

### 4. Especificación de Modelos

El schema exacto para cada modelo, incluyendo nombres de campos, tipos y restricciones.

```markdown
## Especificación de Modelos

### Modelo WorkSession

class WorkSession(UUIDModel, BaseModel):
    """
    Una sesión de trabajo con límites de tiempo adjunta a cualquier target.

    Solo una sesión por usuario puede estar activa (iniciada pero no detenida).
    Iniciar una nueva sesión automáticamente detiene cualquier sesión activa.
    """

    # Propietario
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='work_sessions'
    )

    # Target vía GenericFK
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+'
    )
    target_id = models.CharField(max_length=255, blank=True, default='')
    target = GenericForeignKey('target_content_type', 'target_id')

    # Tiempo
    started_at = models.DateTimeField(default=timezone.now)
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Metadatos
    session_type = models.CharField(max_length=50, default='work')
    notes = models.TextField(blank=True, default='')
```

Esto no es pseudo-código. Este es el código real que debe generarse. Nombres de campos, tipos, valores predeterminados, texto de ayuda—todo especificado.

### 5. Funciones de Servicio

Las firmas y comportamientos exactos de las funciones.

```markdown
## Especificación de Servicios

### start_session()

def start_session(
    user,
    target=None,
    session_type: str = 'work',
    notes: str = '',
    stop_active: bool = True,
) -> WorkSession:
    """
    Iniciar una nueva sesión de trabajo para un usuario.

    Args:
        user: El usuario iniciando la sesión
        target: Objeto opcional para adjuntar la sesión (GenericFK)
        session_type: Tipo de sesión (predeterminado 'work')
        notes: Notas opcionales
        stop_active: Si es True, detener cualquier sesión activa primero

    Returns:
        La nueva WorkSession

    Raises:
        ActiveSessionError: Si stop_active=False y el usuario tiene sesión activa
    """
```

Las firmas de funciones son contratos. Si la IA genera firmas diferentes, el código que llama a estas funciones falla.

### 6. Casos de Prueba

Una lista numerada de cada prueba que debe pasar.

```markdown
## Casos de Prueba (31 pruebas)

### Pruebas del Modelo WorkSession (12 pruebas)
1. test_session_creation - Crear con campos requeridos
2. test_session_has_uuid_pk - Clave primaria UUID
3. test_session_user_fk - Foreign key de usuario funciona
4. test_session_target_generic_fk - GenericFK a cualquier modelo
5. test_session_started_at_default - Predeterminado a ahora
6. test_session_stopped_at_nullable - Puede ser null
7. test_session_duration_calculated - Duración calculada al detener
8. test_session_is_active_property - True si no está detenida
9. test_session_ordering - Ordenado por started_at desc
10. test_session_soft_delete - Eliminación suave funciona
11. test_session_target_id_as_string - Almacena UUID como string
12. test_session_str_representation - Formato de string

### Pruebas de Funciones de Servicio (19 pruebas)
13. test_start_session_creates_session
14. test_start_session_with_target
15. test_start_session_stops_active
...
```

Los nombres de las pruebas son específicos. Cada prueba tiene una descripción de una línea. Cuando la IA escribe pruebas, sabe exactamente qué probar.

---

## La Garantía de Reconstrucción

Un prompt de reconstrucción correctamente escrito proporciona una garantía:

1. Eliminar el paquete
2. Ejecutar el prompt
3. Obtener salida idéntica
4. Todas las pruebas pasan

Esto no es aspiracional. Esta es la prueba. Si regenerar el paquete produce salida diferente o rompe pruebas, el prompt está incompleto.

### Probando la Garantía

Cada prompt de reconstrucción debe ser probado:

```bash
# Guardar conteo de pruebas actual
pytest packages/django-worklog/tests/ --collect-only | grep "test" > original.txt

# Eliminar el paquete
rm -rf packages/django-worklog/

# Regenerar desde prompt
# (ejecutar IA con docs/prompts/django-worklog.md)

# Verificar que las pruebas pasan
pytest packages/django-worklog/tests/ -v

# Comparar conteo de pruebas
pytest packages/django-worklog/tests/ --collect-only | grep "test" > regenerated.txt
diff original.txt regenerated.txt
```

Si el diff está vacío y todas las pruebas pasan, el prompt está completo.

---

## El Patrón Completo de Prompt

Aquí está el patrón completo usado para cada paquete primitivo:

```markdown
# Prompt: Reconstruir [nombre-del-paquete]

## Instrucción

Crear un paquete Django llamado `[nombre-del-paquete]` que proporcione [propósito].

## Propósito del Paquete

[1-3 oraciones explicando qué hace este paquete]

## Dependencias

- Django >= 4.2
- [otras dependencias]

## Estructura de Archivos

[diseño exacto de directorios y archivos]

## Especificación de Excepciones

[clases de excepciones personalizadas]

## Especificación de Modelos

[definiciones completas de modelos con todos los campos]

## Especificación de QuerySet

[métodos de QuerySet personalizados si los hay]

## Especificación de Servicios

[todas las firmas de funciones de servicio y docstrings]

## Exportaciones de __init__.py

[lo que el paquete exporta]

## Casos de Prueba (N pruebas)

[lista numerada de cada prueba]

## Comportamientos Clave

[resumen de comportamientos importantes]

## Ejemplos de Uso

[código de ejemplo mostrando cómo usar el paquete]

## Criterios de Aceptación

[lista de verificación para completar]
```

---

## Ejemplo Real: Prompt de django-worklog

Aquí está el prompt de reconstrucción real para django-worklog (abreviado por espacio):

```markdown
# Prompt: Reconstruir django-worklog

## Instrucción

Crear un paquete Django llamado `django-worklog` que proporcione primitivas de
seguimiento de tiempo para registrar sesiones de trabajo con comportamiento de cambio automático.

## Propósito del Paquete

Proporcionar capacidades de seguimiento de tiempo:
- `WorkSession` - Sesión con límites de tiempo con target GenericFK
- `start_session()` - Iniciar una sesión (auto-detiene activa)
- `stop_session()` - Detener sesión activa
- `get_active_session()` - Obtener sesión actual del usuario
- Política de cambio: iniciar nueva sesión detiene la anterior

## Dependencias

- Django >= 4.2
- django-basemodels (para UUIDModel, BaseModel)
- django.contrib.contenttypes
- django.contrib.auth

## Especificación de Modelos

### Modelo WorkSession

class WorkSession(UUIDModel, BaseModel):
    """
    Una sesión de trabajo con límites de tiempo adjunta a cualquier target.
    """

    # Propietario
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='work_sessions'
    )

    # Target vía GenericFK
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    target_id = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey('target_content_type', 'target_id')

    # Tiempo
    started_at = models.DateTimeField(default=timezone.now)
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    @property
    def is_active(self) -> bool:
        return self.stopped_at is None

## Especificación de Servicios

### start_session()

def start_session(user, target=None, session_type='work',
                  stop_active=True) -> WorkSession:
    """Iniciar una nueva sesión, opcionalmente deteniendo cualquier activa."""

### stop_session()

def stop_session(user) -> Optional[WorkSession]:
    """Detener la sesión activa del usuario si existe una."""

### get_active_session()

def get_active_session(user) -> Optional[WorkSession]:
    """Obtener la sesión actualmente activa del usuario, o None."""

## Casos de Prueba (31 pruebas)

### Pruebas de Modelo (12)
1. test_session_creation
2. test_session_uuid_pk
3. test_session_user_fk
4. test_session_target_generic_fk
5. test_session_started_at_default
6. test_session_stopped_at_nullable
7. test_session_duration_calculated
8. test_session_is_active_true
9. test_session_is_active_false
10. test_session_ordering
11. test_session_soft_delete
12. test_session_str

### Pruebas de Servicio (19)
13. test_start_session_creates
14. test_start_session_with_target
15. test_start_session_stops_previous
16. test_start_session_error_when_active
...

## Criterios de Aceptación

- [ ] WorkSession con target GenericFK
- [ ] Política de cambio (iniciar nueva = detener antigua)
- [ ] Duración calculada al detener
- [ ] Las 31 pruebas pasando
- [ ] README con ejemplos
```

Con este prompt, el paquete puede ser reconstruido en cualquier momento. La IA no inventa. Ejecuta.

---

## Por Qué las Tablas Funcionan Mejor Que la Prosa

Nota cómo la especificación de modelos usa formato estructurado, no prosa:

**Prosa (más difícil de seguir):**
```markdown
El modelo WorkSession debe tener un campo user que es una foreign key
a AUTH_USER_MODEL con PROTECT en delete. También debe tener campos
para rastrear tiempos de inicio y fin, con el tiempo de fin siendo nullable.
La duración debe almacenarse en segundos como un entero.
```

**Estructurado (preciso):**
```markdown
### Modelo WorkSession

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| user | ForeignKey | AUTH_USER_MODEL, on_delete=PROTECT |
| started_at | DateTimeField | default=timezone.now |
| stopped_at | DateTimeField | null=True, blank=True |
| duration_seconds | IntegerField | null=True, blank=True |
```

Las tablas eliminan la ambigüedad. La IA no puede malinterpretar "debe tener campos para rastrear" porque cada campo está explícitamente nombrado y tipado.

---

## El Sistema de Numeración de Casos de Prueba

Nota cómo los casos de prueba están numerados, no solo nombrados:

```markdown
## Casos de Prueba (31 pruebas)

### Pruebas de Modelo (12)
1. test_session_creation
2. test_session_uuid_pk
...

### Pruebas de Servicio (19)
13. test_start_session_creates
14. test_start_session_with_target
...
```

La numeración sirve tres propósitos:

1. **Conteo**: Sabes exactamente cuántas pruebas deben existir. Si la IA genera 29 pruebas, algo falta.

2. **Ordenamiento**: La IA escribe pruebas en un orden predecible. La revisión de código se vuelve más fácil cuando sabes dónde debe aparecer cada prueba.

3. **Referencia**: Puedes referirte a pruebas específicas por número. "La prueba 14 está fallando" es más claro que "la prueba para iniciar con target."

---

## Manejando Casos Borde en Prompts

Schema-first no significa sin casos borde. Significa que los casos borde están explícitamente especificados:

```markdown
## Casos Borde

### ¿Qué pasa si el usuario inicia sesión cuando una está activa?
- Si stop_active=True: Detener sesión existente, iniciar nueva
- Si stop_active=False: Lanzar ActiveSessionError

### ¿Qué pasa si stop_session se llama sin sesión activa?
- Retornar None (no es un error)
- Registrar una advertencia

### ¿Qué pasa si el target se elimina?
- GenericFK queda huérfano (target retorna None)
- La sesión permanece válida
- Usar target_content_type y target_id para referencia histórica
```

Cada "qué pasa si" que puedas pensar va en el prompt. La IA no decide el comportamiento de casos borde. Tú lo haces.

---

## Ejercicio Práctico: Escribe un Prompt de Reconstrucción

Toma un modelo existente en tu código base. Escribe un prompt de reconstrucción para él.

**Paso 1: Documenta el Propósito**
¿Qué hace este modelo? ¿Por qué existe?

**Paso 2: Documenta el Schema**
Cada campo, tipo y restricción. Usa una tabla.

**Paso 3: Documenta los Comportamientos**
¿Qué métodos tiene? ¿Cuáles son los casos borde?

**Paso 4: Documenta las Pruebas**
Numera cada prueba. Una línea cada una.

**Paso 5: Prueba el Prompt**
¿Puede una IA regenerar el modelo solo con este prompt? Si no, ¿qué falta?

---

## Lo Que la IA Se Equivoca Sobre los Schemas

### Sobre-Ingeniería

Dada libertad, la IA agrega campos que no pediste:
```python
class WorkSession(models.Model):
    # Tus campos especificados
    user = models.ForeignKey(...)
    started_at = models.DateTimeField(...)

    # Adiciones de IA (no solicitadas)
    created_by = models.ForeignKey(...)  # Redundante con user
    status = models.CharField(...)        # Sobre-ingeniería
    priority = models.IntegerField(...)   # No necesario
    tags = models.ManyToManyField(...)    # Inflación de características
```

**Solución:** Sé explícito de que el schema es exhaustivo. "El modelo tiene SOLO estos campos. No agregar campos adicionales."

### Creatividad en Nombres de Campos

Dados conceptos similares, la IA usa nombres inconsistentes:
```python
# En WorkSession
started_at = models.DateTimeField()

# En un modelo diferente, misma sesión
begin_time = models.DateTimeField()
```

**Solución:** Incluir una sección de convenciones de nomenclatura:
```markdown
## Convenciones de Nomenclatura
- Campos datetime: [verbo]_at (started_at, stopped_at, created_at)
- Campos boolean: is_[adjetivo] (is_active, is_deleted)
- Foreign keys: [modelo_relacionado] (user, organization)
```

### Deriva de Valores Predeterminados

Dados prompts en diferentes momentos, la IA usa diferentes valores predeterminados:
```python
# Primera generación
session_type = models.CharField(max_length=50, default='work')

# Segunda generación
session_type = models.CharField(max_length=100, default='general')
```

**Solución:** Especificar cada valor predeterminado explícitamente. Nunca dejar valores predeterminados a interpretación.

---

## Por Qué Esto Importa Después

La generación schema-first es la base del desarrollo reproducible asistido por IA.

Sin schema-first:
- Cada regeneración es diferente
- Las pruebas fallan cuando el código se regenera
- Las migraciones entran en conflicto entre versiones
- Los miembros del equipo generan código incompatible

Con schema-first:
- El código es reproducible
- Las pruebas son estables
- Las migraciones son predecibles
- Cualquiera puede regenerar el mismo paquete

En el próximo capítulo, exploraremos el lado opuesto: operaciones prohibidas. Si schema-first le dice a la IA qué construir, las operaciones prohibidas le dicen a la IA qué nunca hacer.

---

## Resumen

| Concepto | Propósito |
|----------|-----------|
| Schema-first | Especificar salida exacta antes de la generación |
| Prompt de reconstrucción | Especificación completa para regenerar un paquete |
| Especificación de modelos | Campos exactos, tipos, restricciones |
| Especificación de servicios | Firmas exactas de funciones |
| Casos de prueba | Lista numerada de pruebas requeridas |
| Garantía de reconstrucción | Eliminar, regenerar, las pruebas pasan |
| Tablas sobre prosa | Eliminar ambigüedad |
| Documentación de casos borde | Manejo explícito de casos especiales |

El objetivo no es restringir a la IA. El objetivo es hacer la salida de la IA predecible.

Cuando puedes eliminar un paquete y regenerarlo idénticamente, has escapado de la trampa del código irreproducible.

---

## La Colección de Prompts

Los prompts de reconstrucción completos para todos los primitivos están en la Parte II de este libro:

| Paquete | Capítulo | Conteo de Pruebas |
|---------|----------|-------------------|
| django-parties | Capítulo 6: Identidad | 44 pruebas |
| django-rbac | Capítulo 6: Identidad | 30 pruebas |
| django-agreements | Capítulo 8: Acuerdos | 47 pruebas |
| django-catalog | Capítulo 9: Catálogo | 83 pruebas |
| django-ledger | Capítulo 10: Libro Mayor | 48 pruebas |
| django-money | Capítulo 10: Libro Mayor | 63 pruebas |
| django-encounters | Capítulo 11: Flujo de Trabajo | 80 pruebas |
| django-decisioning | Capítulo 12: Decisiones | 78 pruebas |
| django-audit-log | Capítulo 13: Auditoría | 23 pruebas |

Cada prompt sigue el patrón de este capítulo. Cada paquete puede ser reconstruido desde su prompt.

Ese es el poder de la generación schema-first.
