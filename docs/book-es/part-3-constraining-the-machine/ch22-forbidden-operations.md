# Capítulo 22: Operaciones Prohibidas

## El Error Tipográfico de $125 Millones

El 21 de septiembre de 1999, el Mars Climate Orbiter de la NASA se aproximó a Marte después de un viaje de 286 días. Mientras se preparaba para la inserción orbital, la nave espacial encendió sus propulsores. Pero en lugar de entrar en órbita, descendió demasiado bajo en la atmósfera y se desintegró.

La investigación reveló la causa: un módulo de software proporcionaba cálculos de empuje en libras-fuerza por segundo. El software de navegación esperaba newton-segundos. Nadie detectó la discrepancia de unidades. La nave espacial, valuada en $125 millones, se perdió porque un equipo usó unidades imperiales y otro usó métricas.

El error no estaba en las matemáticas. Las matemáticas funcionaban perfectamente—en dos sistemas de unidades diferentes. El error fue que nada en el sistema prohibía mezclar sistemas de unidades. No había ninguna restricción que dijera "todos los valores de empuje deben estar en unidades SI."

La solución no fue "tener más cuidado." La solución fue hacer que mezclar unidades fuera prohibido a nivel del sistema.

Este capítulo trata sobre operaciones prohibidas: las reglas que previenen desastres al hacer ciertas acciones imposibles.

---

## El Poder de "Nunca"

Las instrucciones le dicen a la IA qué hacer. Los contratos especifican límites. Pero las operaciones prohibidas son diferentes. Son prohibiciones absolutas que anulan todo lo demás.

**Instrucción:** "Usar Decimal para cantidades monetarias."
- La IA podría usar float "solo para este cálculo" y redondear al final.
- La IA podría decir "float está bien para propósitos de visualización."
- La IA podría inventar casos borde donde float parece razonable.

**Operación prohibida:** "NUNCA usar float para ningún valor que represente, calcule o muestre dinero, en ningún paso, por ninguna razón."
- Sin excepciones. Sin casos borde. Sin "solo esta vez."
- Si la IA usa float para dinero, ha violado una operación prohibida.
- El código está mal, independientemente de si produce resultados correctos.

Las operaciones prohibidas cierran vacíos legales. Eliminan las soluciones creativas en las que los sistemas de IA sobresalen.

---

## La Lista de Operaciones Prohibidas

Todo sistema de software empresarial tiene operaciones que nunca deberían ocurrir. Aquí está la lista completa para primitivos de grado ERP.

### Integridad de Datos

| Operación Prohibida | Por Qué Está Prohibida | Qué Hacer en Su Lugar |
|--------------------|------------------------|----------------------|
| Claves primarias auto-incrementales | Rompe replicación, fusión, sistemas distribuidos | Claves primarias UUID |
| Float para dinero | Los errores de redondeo se acumulan con el tiempo | DecimalField |
| Eliminar registros de auditoría | Destruye responsabilidad, rompe cumplimiento | Registros solo-agregar |
| Mutar transacciones publicadas | Corrompe historial financiero | Publicar reversiones |
| Editar acuerdos | Destruye historial de contratos | Versionar con nuevo registro |
| Eliminación permanente de objetos de dominio | Pierde referencias históricas | Eliminación suave (deleted_at) |
| Anular campos para simular eliminación | Pérdida de datos sin pista de auditoría | Eliminación suave + mantener datos |
| Cascade delete en FKs críticas | Pérdida de datos no intencional | PROTECT o SET_NULL |

### Tiempo

| Operación Prohibida | Por Qué Está Prohibida | Qué Hacer en Su Lugar |
|--------------------|------------------------|----------------------|
| Datetimes sin zona horaria | Bugs de timezone, fallos de horario de verano | Siempre usar con zona horaria |
| Asumir "ahora" = "cuándo sucedió" | Registros tardíos falsean el historial | Separar effective_at y recorded_at |
| Antedatar recorded_at | Destruye integridad de pista de auditoría | Solo antedatar effective_at |
| Consultar sin contexto temporal | Retorna estado incorrecto para consultas punto-en-tiempo | Usar consultas as_of() |
| Almacenar fechas como strings | Fallos de ordenamiento, comparación, cálculo | DateField o DateTimeField |
| Ignorar tiempo de negocio | Perder el "cuándo realmente sucedió" | Siempre capturar effective_at |

### Identidad

| Operación Prohibida | Por Qué Está Prohibida | Qué Hacer en Su Lugar |
|--------------------|------------------------|----------------------|
| Eliminación permanente de parties | Deja huérfanas todas las referencias históricas | Eliminación suave |
| Asumir un usuario = una persona | Cuentas compartidas, acceso basado en roles | Separar User y Party |
| Almacenar roles en tabla de usuario | Cambios de rol se convierten en vacíos de auditoría | Modelo Role separado con límites de tiempo |
| Saltar límites de tiempo en relaciones | No se puede consultar "¿quién estaba conectado cuándo?" | valid_from, valid_to en relaciones |
| Embeber identidad en objetos de negocio | Datos duplicados, problemas de sincronización | Referenciar Parties por FK |
| Eliminar usuario sin preservar historial | Pierde información del actor en registros de auditoría | Capturar actor_repr al momento del evento |

### Arquitectura

| Operación Prohibida | Por Qué Está Prohibida | Qué Hacer en Su Lugar |
|--------------------|------------------------|----------------------|
| Importar de capas superiores | Crea dependencias circulares | Jerarquía de capas estricta |
| Lógica de negocio en modelos | Difícil de probar, difícil de cambiar | Capa de servicios |
| Lógica de negocio en vistas | No testeable, duplicada | Capa de servicios |
| Inventar nuevos primitivos | Duplicación, inconsistencia | Componer primitivos existentes |
| Saltar la capa de servicios | Acceso directo a modelos evita reglas | Todas las mutaciones a través de servicios |
| GenericForeignKey sin string owner_id | Problemas de compatibilidad con UUID | CharField para target_id |

### Operaciones

| Operación Prohibida | Por Qué Está Prohibida | Qué Hacer en Su Lugar |
|--------------------|------------------------|----------------------|
| Force push a main | Pierde historial, rompe colaboración | Push regular o rebase cuidadosamente |
| Saltar hooks de pre-commit | Evita puertas de calidad | Arreglar problemas, luego commit |
| Commitear secretos al código | Vulnerabilidad de seguridad | Variables de entorno |
| Concatenación de strings SQL | Vulnerabilidad de inyección SQL | Consultas parametrizadas |
| eval() o exec() en entrada de usuario | Vulnerabilidad de inyección de código | Nunca evaluar entrada no confiable |
| Deshabilitar SSL en producción | Ataques man-in-the-middle | Siempre usar TLS |

---

## Mecanismos de Aplicación

Las operaciones prohibidas solo son útiles si se aplican. Hay cinco niveles de aplicación, del más débil al más fuerte.

### Nivel 1: Prompt (Más Débil)

Poner la operación prohibida en CLAUDE.md o el prompt de la tarea:

```markdown
## No Debe Hacer
- Nunca usar float para dinero
- Nunca eliminar registros de auditoría
- Nunca mutar transacciones publicadas
```

**Fortaleza:** Fácil de agregar. La IA lo lee al inicio de la sesión.
**Debilidad:** La IA puede "olvidar" en sesiones largas. Sin aplicación en runtime.

### Nivel 2: Código

Aplicar en el código del modelo o servicio:

```python
class AuditLog(models.Model):
    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLogError(
                "Las entradas del registro de auditoría no pueden modificarse después de la creación."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLogError(
            "Las entradas del registro de auditoría no pueden eliminarse."
        )
```

**Fortaleza:** Falla en runtime. Funciona incluso si se olvida el prompt.
**Debilidad:** Puede evitarse con SQL directo o `Model.objects.filter().delete()`.

### Nivel 3: Base de Datos

Aplicar con restricciones y triggers de base de datos:

```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=~models.Q(amount=Decimal('0')),
            name='ledger_entry_non_zero'
        ),
    ]
```

Para inmutabilidad, usar triggers de PostgreSQL:

```sql
CREATE OR REPLACE FUNCTION prevent_audit_log_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Las entradas del registro de auditoría son inmutables';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update_audit_log
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_update();
```

**Fortaleza:** Sobrevive SQL directo, bypass del ORM, cualquier cliente.
**Debilidad:** Requiere acceso a base de datos para configurar. Complejidad de migraciones.

### Nivel 4: Pruebas

Escribir pruebas que demuestren que las operaciones prohibidas fallan:

```python
class TestForbiddenOperations:
    """Pruebas que verifican que las operaciones prohibidas están bloqueadas."""

    def test_cannot_update_audit_log(self):
        """Actualizar entradas del registro de auditoría está prohibido."""
        log = AuditLog.objects.create(
            target=document,
            action='create',
            actor=user
        )

        log.message = "Intentando modificar"
        with pytest.raises(ImmutableLogError):
            log.save()

    def test_cannot_delete_audit_log(self):
        """Eliminar entradas del registro de auditoría está prohibido."""
        log = AuditLog.objects.create(
            target=document,
            action='create',
            actor=user
        )

        with pytest.raises(ImmutableLogError):
            log.delete()

    def test_cannot_bulk_delete_audit_logs(self):
        """La eliminación masiva de registros de auditoría está prohibida."""
        AuditLog.objects.create(target=document, action='create')
        AuditLog.objects.create(target=document, action='update')

        # Esto debería ser bloqueado por el trigger de base de datos
        with pytest.raises(Exception):  # DatabaseError o personalizado
            AuditLog.objects.all().delete()

    def test_cannot_use_float_for_money(self):
        """Los campos de dinero deben ser Decimal, nunca float."""
        # Esta prueba documenta el requisito
        amount_field = Transaction._meta.get_field('amount')
        assert isinstance(amount_field, models.DecimalField)
        assert not isinstance(amount_field, models.FloatField)
```

**Fortaleza:** Documenta requisitos. Captura regresiones. Corre en CI.
**Debilidad:** Solo captura violaciones en tiempo de prueba, no en tiempo de desarrollo.

### Nivel 5: Análisis Estático (Más Fuerte)

Usar linters y verificadores de tipos para capturar violaciones antes del runtime:

```python
# mypy.ini
[mypy]
disallow_any_explicit = True

# Plugin personalizado de mypy para tipos de dinero
from decimal import Decimal
Money = Decimal  # Alias de tipo

def calculate_total(amounts: list[Money]) -> Money:
    return sum(amounts, Decimal('0'))

# Esto sería capturado por el verificador de tipos:
# calculate_total([1.5, 2.5])  # Error: esperaba Money, obtuvo float
```

Para violaciones de capas:

```yaml
# layers.yaml
layers:
  - name: infrastructure
    packages:
      - django_basemodels
      - django_singleton

  - name: domain
    packages:
      - django_parties
      - django_catalog
    allowed_imports:
      - infrastructure

  - name: application
    packages:
      - vetfriendly
    allowed_imports:
      - domain
      - infrastructure
```

```bash
# Verificar violaciones de capas
python -m django_layers check
```

**Fortaleza:** Captura violaciones antes de que el código corra. Se integra con IDE.
**Debilidad:** Requiere configuración. No todas las violaciones son detectables estáticamente.

---

## El Patrón de Prueba Negativa

Para cada operación prohibida, escribe una prueba que demuestre que falla:

```python
# tests/test_forbidden_operations.py

"""
Pruebas para operaciones prohibidas.

Estas pruebas documentan lo que el sistema NUNCA debe hacer.
Cada prueba debería fallar si la operación prohibida se permite.
"""

import pytest
from decimal import Decimal
from django.db import models

from django_audit_log.models import AuditLog
from django_audit_log.exceptions import ImmutableLogError
from django_ledger.models import Transaction, Entry
from django_ledger.exceptions import ImmutableTransactionError


class TestAuditLogForbiddenOperations:
    """Los registros de auditoría son inmutables."""

    def test_update_forbidden(self, audit_log):
        """No se puede modificar un registro de auditoría después de la creación."""
        audit_log.message = "Modificado"
        with pytest.raises(ImmutableLogError):
            audit_log.save()

    def test_delete_forbidden(self, audit_log):
        """No se puede eliminar un registro de auditoría."""
        with pytest.raises(ImmutableLogError):
            audit_log.delete()


class TestTransactionForbiddenOperations:
    """Las transacciones publicadas son inmutables."""

    def test_update_posted_transaction_forbidden(self, posted_transaction):
        """No se puede modificar una transacción publicada."""
        posted_transaction.memo = "Modificado"
        with pytest.raises(ImmutableTransactionError):
            posted_transaction.save()

    def test_delete_posted_transaction_forbidden(self, posted_transaction):
        """No se puede eliminar una transacción publicada."""
        with pytest.raises(ImmutableTransactionError):
            posted_transaction.delete()

    def test_modify_entries_after_post_forbidden(self, posted_transaction):
        """No se puede agregar o modificar entradas después de publicar."""
        with pytest.raises(ImmutableTransactionError):
            Entry.objects.create(
                transaction=posted_transaction,
                account=some_account,
                amount=Decimal('100'),
                entry_type='debit'
            )


class TestMoneyForbiddenOperations:
    """El dinero nunca debe usar float."""

    def test_amount_is_decimal_field(self):
        """El monto de Transaction debe ser DecimalField."""
        field = Transaction._meta.get_field('amount')
        assert isinstance(field, models.DecimalField), \
            "Los campos de dinero deben usar DecimalField, no FloatField"

    def test_entry_amount_is_decimal_field(self):
        """El monto de Entry debe ser DecimalField."""
        field = Entry._meta.get_field('amount')
        assert isinstance(field, models.DecimalField), \
            "Los campos de dinero deben usar DecimalField, no FloatField"
```

Estas pruebas sirven tres propósitos:

1. **Documentación**: Cualquiera que lea las pruebas entiende qué está prohibido.
2. **Regresión**: Si alguien accidentalmente permite una operación prohibida, la prueba falla.
3. **Aplicación**: CI bloquea merges que violan operaciones prohibidas.

---

## Hoja de Referencia de Operaciones Prohibidas

Copia esto en tu CLAUDE.md:

```markdown
# Operaciones Prohibidas

## NUNCA (sin excepciones)

### Integridad de Datos
- NUNCA usar claves primarias auto-incrementales (usar UUID)
- NUNCA usar float para dinero (usar Decimal)
- NUNCA eliminar registros de auditoría (solo-agregar)
- NUNCA mutar transacciones publicadas (publicar reversiones)
- NUNCA eliminar permanentemente objetos de dominio (eliminación suave)

### Tiempo
- NUNCA usar datetimes sin zona horaria (siempre con zona horaria)
- NUNCA asumir ahora = cuándo sucedió (usar effective_at)
- NUNCA antedatar recorded_at (solo antedatar effective_at)

### Identidad
- NUNCA eliminar permanentemente parties (eliminación suave)
- NUNCA almacenar roles en tabla de usuario (modelo Role separado)
- NUNCA saltar límites de tiempo en relaciones (valid_from/valid_to)

### Arquitectura
- NUNCA importar de capas superiores (jerarquía estricta)
- NUNCA poner lógica de negocio en modelos (usar servicios)
- NUNCA inventar nuevos primitivos (componer existentes)

### Seguridad
- NUNCA commitear secretos al código (usar env vars)
- NUNCA usar concatenación de strings SQL (parametrizar)
- NUNCA usar eval() en entrada de usuario (nunca)
```

---

## Manejando Casos Borde

A veces alguien preguntará: "Pero ¿qué pasa si realmente necesito..."

### "¿Pero qué pasa si necesito eliminar datos de prueba?"

```python
# La limpieza de pruebas es diferente de la eliminación en producción
# Usar SQL directo o fixtures especiales de prueba

# En tests/conftest.py
@pytest.fixture(autouse=True)
def reset_database(db):
    """Limpiar base de datos entre pruebas."""
    yield
    # El test runner de Django maneja esto
```

### "¿Pero qué pasa si necesito corregir un error de transacción?"

```python
# Publicar una reversión, luego publicar la transacción correcta
def fix_transaction_error(wrong_transaction, correct_amount):
    """Corregir una transacción revirtiendo y republicando."""
    # Revertir la transacción incorrecta
    reverse(wrong_transaction)

    # Crear nueva transacción correcta
    return Transaction.objects.create(
        amount=correct_amount,
        memo=f"Corrección para {wrong_transaction.id}",
        relates_to=wrong_transaction,
    )
```

### "¿Pero qué pasa si el registro de auditoría tiene datos incorrectos?"

```python
# Publicar un evento de corrección, no modificar el original
def correct_audit_error(original_log, correction_note):
    """Documentar que una entrada del registro de auditoría era incorrecta."""
    return AuditLog.objects.create(
        target=original_log.target,
        action='correction',
        message=f"Corrección al registro {original_log.id}: {correction_note}",
        metadata={
            'corrects': str(original_log.id),
            'original_message': original_log.message,
        }
    )
```

El patrón es siempre el mismo: **no modificar, agregar correcciones**.

---

## Ejercicio Práctico: La Auditoría de Operaciones Prohibidas

Revisa tu código base por violaciones de operaciones prohibidas.

**Paso 1: Verificar Float para Dinero**

```bash
grep -r "FloatField" --include="*.py" | grep -i "price\|amount\|cost\|fee\|total"
```

**Paso 2: Verificar Eliminaciones Permanentes**

```bash
grep -r "\.delete()" --include="*.py" | grep -v "soft_delete\|test"
```

**Paso 3: Verificar Datetimes Sin Zona Horaria**

```bash
grep -r "datetime.now()" --include="*.py"
grep -r "datetime.utcnow()" --include="*.py"
# Debería usar timezone.now() en su lugar
```

**Paso 4: Verificar Auto-Incremento**

```bash
grep -r "AutoField\|BigAutoField" --include="*.py" | grep -v "django/db"
```

**Paso 5: Verificar Violaciones de Capas**

```bash
# En una app de capa superior, verificar importaciones de capas inferiores
grep -r "from django_" --include="*.py" apps/vetfriendly/
```

Documenta cada violación encontrada. Crea tickets para arreglarlas.

---

## Lo Que la IA Se Equivoca Sobre las Operaciones Prohibidas

### Solicitudes de Excepción

La IA puede argumentar que una restricción no debería aplicar:

> "En este caso, usar float está bien porque solo estamos mostrando el valor y no haciendo cálculos."

**Respuesta:** La restricción es absoluta. Sin excepciones. Si hay un contexto de visualización donde float parece bien hoy, habrá un contexto de cálculo mañana donde causa bugs.

### Cumplimiento Parcial

La IA puede aplicar algunas restricciones pero no otras:

```python
class Transaction(models.Model):
    amount = models.DecimalField(...)  # ¡Correcto!

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)  # ¡Incorrecto! Debería estar prohibido
```

**Respuesta:** Usar la lista completa de operaciones prohibidas. Verificar cada ítem.

### Soluciones Alternativas

La IA puede encontrar formas creativas de evitar restricciones:

> "Dijiste nunca eliminar registros. Así que puse todos los campos en None y mantuve la fila."

**Respuesta:** Agregar prohibiciones explícitas para soluciones alternativas:
```markdown
- NUNCA eliminar registros
- NUNCA anular campos para simular eliminación
- NUNCA mover registros a tablas de "archivo"
- NUNCA poner flags is_deleted sin preservar datos originales
```

---

## Por Qué Esto Importa Después

Las operaciones prohibidas son los rieles de seguridad de tu sistema.

Sin ellas:
- Alguien usará float para dinero "solo esta vez"
- Alguien eliminará un registro de auditoría "para limpiar datos de prueba"
- Alguien modificará una transacción publicada "porque el cliente lo pidió"

Con ellas:
- El sistema previene estas acciones en múltiples niveles
- Las violaciones se capturan en pruebas, en código, en la base de datos
- Los nuevos desarrolladores no pueden romper invariantes accidentalmente

En la Parte IV, compondremos primitivos para construir aplicaciones reales. Cada composición respetará las operaciones prohibidas de este capítulo. Los rieles de seguridad permanecen en su lugar, sin importar qué tan compleja se vuelva la aplicación.

---

## Resumen

| Concepto | Propósito |
|----------|-----------|
| Operaciones prohibidas | Prohibiciones absolutas que anulan todas las otras reglas |
| Aplicación por prompt | Reglas de CLAUDE.md (más débil) |
| Aplicación por código | Overrides de save/delete del modelo |
| Aplicación por base de datos | Restricciones y triggers |
| Aplicación por pruebas | Pruebas negativas que demuestran que las violaciones fallan |
| Análisis estático | Linters y verificadores de tipos (más fuerte) |
| Patrón de prueba negativa | Cada operación prohibida tiene una prueba |
| Sin excepciones | Las restricciones son absolutas, sin casos borde |

El Mars Climate Orbiter se perdió porque nada en el sistema prohibía mezclar sistemas de unidades.

Tu software empresarial no debería sufrir el mismo destino. Haz las operaciones peligrosas imposibles, y las operaciones seguras fáciles.

---

## Fuentes

- Stephenson, A. G. et al. (1999). *Mars Climate Orbiter Mishap Investigation Board Phase I Report*. NASA.
- NASA. (1999). "Mars Climate Orbiter Failure Board Releases Report." Press Release 99-134.
