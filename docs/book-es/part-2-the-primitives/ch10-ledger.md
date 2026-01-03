# Capítulo 10: Libro Mayor

> "Por cada débito, debe haber un crédito."
>
> — La regla fundamental de la contabilidad, sin cambios desde 1494

---

En 1494, Luca Pacioli publicó *Summa de arithmetica*, que incluía la primera descripción sistemática de la contabilidad por partida doble. El método no era nuevo—los mercaderes venecianos lo habían usado durante siglos—pero la documentación de Pacioli lo hizo enseñable y reproducible.

Quinientos treinta años después, todo sistema financiero serio sigue usando el mismo patrón. No porque nadie haya intentado mejorarlo, sino porque es irreductiblemente correcto. La contabilidad por partida doble no es una preferencia ni una mejor práctica. Es una prueba matemática de que el dinero no desaparece.

## El Problema que Resuelve la Partida Doble

La contabilidad por partida simple registra transacciones como una lista: "Recibí $100 del Cliente A." "Pagué $50 al Proveedor B." "Recibí $75 del Cliente C." En cualquier momento, puedes sumar las entradas y afirmar conocer tu saldo.

Pero los sistemas de partida simple tienen un defecto fatal: no pueden probar su propia corrección.

Si tu saldo calculado no coincide con tu estado de cuenta bancario, ¿dónde está el error? ¿Se omitió una entrada? ¿Se categorizó mal? ¿Se duplicó? El sistema no tiene mecanismo de verificación interno. Cada conciliación requiere comparación contra una fuente externa.

La partida doble resuelve esto requiriendo que cada transacción tenga al menos dos entradas que sumen cero. El dinero viene de algún lugar y va a algún lugar. La restricción de que los débitos igualen los créditos es auto-ejecutable—si los libros no cuadran, definitivamente algo está mal.

La Oficina de Contabilidad General estimó en 2019 que el gobierno federal no podía dar cuenta de $21 mil millones en recursos presupuestarios debido a registros de transacciones inadecuados. Estos no eran fondos perdidos—eran transacciones que no podían rastrearse porque los sistemas no aplicaban la disciplina de partida doble.

## Los Dos Lados de Cada Transacción

Cada transacción comercial tiene al menos dos efectos:

**Venta:** Los ingresos aumentan (crédito), y el efectivo aumenta (débito) o las cuentas por cobrar aumentan (débito).

**Pago:** El efectivo disminuye (crédito), y las cuentas por pagar disminuyen (débito) o los gastos aumentan (débito).

**Reembolso:** Los ingresos disminuyen (débito), y el efectivo disminuye (crédito).

El patrón es universal: para cada flujo de valor, hay una fuente y un destino. La partida doble captura ambos.

```python
class Account(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    owner_id = models.CharField(max_length=255)  # CharField for UUID support
    owner = GenericForeignKey('owner_content_type', 'owner_id')

    account_type = models.CharField(max_length=50)  # asset, liability, equity, revenue, expense
    currency = models.CharField(max_length=3)  # ISO 4217
    name = models.CharField(max_length=255, blank=True)


class Transaction(models.Model):
    description = models.TextField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)  # null = draft
    effective_at = models.DateTimeField(default=timezone.now)
    recorded_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)


class Entry(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=PROTECT, related_name='entries')
    account = models.ForeignKey(Account, on_delete=PROTECT, related_name='entries')
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    entry_type = models.CharField(choices=[('debit', 'Debit'), ('credit', 'Credit')])
    effective_at = models.DateTimeField(default=timezone.now)
    recorded_at = models.DateTimeField(auto_now_add=True)
    reverses = models.ForeignKey('self', null=True, blank=True, on_delete=PROTECT)
```

La estructura es simple: Las Cuentas mantienen valor. Las Transacciones agrupan entradas. Las Entradas mueven valor entre cuentas.

## La Restricción de Balance

El invariante fundamental: dentro de cualquier transacción, la suma de débitos debe igualar la suma de créditos.

```python
@transaction.atomic
def record_transaction(description, entries, effective_at=None, metadata=None):
    # Validate balance
    debits = sum(e['amount'] for e in entries if e['entry_type'] == 'debit')
    credits = sum(e['amount'] for e in entries if e['entry_type'] == 'credit')

    if debits != credits:
        raise UnbalancedTransactionError(
            f"Transaction unbalanced: debits={debits}, credits={credits}"
        )

    tx = Transaction.objects.create(
        description=description,
        effective_at=effective_at or timezone.now(),
        metadata=metadata or {},
    )

    for entry_data in entries:
        Entry.objects.create(
            transaction=tx,
            account=entry_data['account'],
            amount=entry_data['amount'],
            entry_type=entry_data['entry_type'],
            effective_at=tx.effective_at,
        )

    tx.posted_at = timezone.now()
    tx.save()

    return tx
```

Esta restricción no es opcional. Todo sistema financiero que la omita eventualmente produce libros que no concilian.

## Inmutabilidad Después del Registro

Una vez que una transacción está registrada, no puede modificarse. Esto no es una limitación técnica—es un requisito contable. Los auditores necesitan saber que los libros que les muestras son los mismos libros que existían en la fecha de auditoría.

```python
class Entry(models.Model):
    # ...

    def save(self, *args, **kwargs):
        if self.pk and self.transaction.is_posted:
            raise ImmutableEntryError(
                f"Cannot modify entry {self.pk} - transaction is posted. "
                "Create a reversal instead."
            )
        super().save(*args, **kwargs)
```

Si cometiste un error, no editas la transacción. Creas una reversión—una nueva transacción que deshace el efecto de la original:

```python
@transaction.atomic
def reverse_entry(entry, reason, effective_at=None):
    opposite_type = 'credit' if entry.entry_type == 'debit' else 'debit'

    tx = Transaction.objects.create(
        description=f"Reversal: {reason}",
        effective_at=effective_at or timezone.now(),
        metadata={'reverses_entry_id': entry.pk, 'reason': reason},
    )

    Entry.objects.create(
        transaction=tx,
        account=entry.account,
        amount=entry.amount,
        entry_type=opposite_type,
        effective_at=tx.effective_at,
        reverses=entry,
    )

    tx.posted_at = timezone.now()
    tx.save()

    return tx
```

Después de una reversión, el saldo de la cuenta vuelve a donde estaba. Pero el historial se preserva: la transacción original, la reversión, y la razón de la reversión están todas en el registro permanente.

## Los Saldos se Calculan, No se Almacenan

Un error común es almacenar un campo "balance" en las cuentas y actualizarlo con cada transacción. Esto crea problemas de sincronización: ¿qué pasa si dos transacciones actualizan el saldo simultáneamente? ¿Qué pasa si una transacción se revierte pero la actualización del saldo falla?

El enfoque correcto: los saldos siempre se calculan a partir de las entradas.

```python
def get_balance(account, as_of=None):
    entries = Entry.objects.filter(
        account=account,
        transaction__posted_at__isnull=False,
    )

    if as_of:
        entries = entries.filter(effective_at__lte=as_of)

    debit_sum = entries.filter(entry_type='debit').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

    credit_sum = entries.filter(entry_type='credit').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')

    return debit_sum - credit_sum
```

Para cuentas de activos (efectivo, cuentas por cobrar), saldo = débitos - créditos. Un saldo positivo significa que tienes activos.

Para cuentas de pasivos (cuentas por pagar, préstamos), el saldo es típicamente negativo (los créditos exceden los débitos), lo que significa que debes dinero.

La fórmula es consistente. La interpretación depende del tipo de cuenta.

## Moneda: Nunca Float

La moneda es el dominio donde la aritmética de punto flotante falla más espectacularmente.

En Python:
```python
>>> 0.1 + 0.2
0.30000000000000004
```

Esto no es un bug—es cómo funciona el punto flotante binario. Pero cuando estás calculando facturas, los errores de redondeo se acumulan. Después de miles de transacciones, tus libros no cuadran, y no sabes por qué.

La solución es trivial: usa `DecimalField` con al menos 4 decimales. Cantidades de moneda como $100.25 se almacenan como `Decimal('100.2500')`.

Para sistemas multimoneda, almacena cantidades en la unidad más pequeña (centavos para USD, peniques para GBP) y rastrea la moneda por separado:

```python
amount = models.DecimalField(max_digits=19, decimal_places=4)
currency = models.CharField(max_length=3)  # ISO 4217 code
```

Nunca almacenes moneda como float. Nunca realices aritmética sobre valores de moneda float. Esta restricción es absoluta.

## GenericFK para Cuentas Polimórficas

Las cuentas pertenecen a partes. Pero las partes pueden ser personas, organizaciones, departamentos, o cualquier otra entidad. El modelo Account usa GenericForeignKey para soportar cualquier tipo de propietario:

```python
class Account(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=PROTECT)
    owner_id = models.CharField(max_length=255)  # CharField for UUID support
    owner = GenericForeignKey('owner_content_type', 'owner_id')
```

Nota: `owner_id` es CharField, no IntegerField. Esto soporta claves primarias UUID, que son estándar en los primitivos.

Con GenericFK, puedes consultar cuentas para cualquier tipo de parte:

```python
# Accounts for a customer
customer_accounts = Account.objects.for_owner(customer)

# Accounts for an organization
org_accounts = Account.objects.for_owner(organization)

# Accounts of a specific type
receivables = Account.objects.by_type('receivable')
```

## El Prompt Completo

Aquí está el prompt completo para generar un paquete de libro mayor de partida doble. Aliméntalo a una IA, y generará primitivos contables correctos.

---

```markdown
# Prompt: Build django-ledger

## Instruction

Create a Django package called `django-ledger` that provides double-entry
accounting primitives with immutable posted entries.

## Package Purpose

Provide lightweight, immutable double-entry accounting:
- Account model with polymorphic owners via GenericFK
- Transaction model grouping balanced entries
- Entry model that is immutable once posted
- Balance calculation and entry reversal services

## File Structure

packages/django-ledger/
├── pyproject.toml
├── README.md
├── src/django_ledger/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── exceptions.py
│   └── migrations/
│       └── 0001_initial.py
└── tests/
    ├── conftest.py
    ├── settings.py
    ├── models.py
    ├── test_models.py
    └── test_services.py

## Exceptions Specification

### exceptions.py

class LedgerError(Exception):
    """Base exception for ledger errors."""
    pass

class UnbalancedTransactionError(LedgerError):
    """Raised when transaction entries don't balance."""
    pass

class ImmutableEntryError(LedgerError):
    """Raised when attempting to modify a posted entry."""
    pass

## Models Specification

### Account Model

- owner via GenericForeignKey (owner_content_type, owner_id)
- owner_id is CharField(max_length=255) for UUID support
- account_type: CharField(max_length=50) - receivable, payable, revenue, expense, etc.
- currency: CharField(max_length=3) - ISO 4217
- name: CharField(max_length=255, blank=True)
- created_at, updated_at timestamps

QuerySet methods:
- for_owner(owner) - filter by owner
- by_type(account_type) - filter by type
- by_currency(currency) - filter by currency

### Transaction Model

- description: TextField(blank=True)
- posted_at: DateTimeField(null=True, blank=True) - null means draft
- effective_at: DateTimeField(default=timezone.now) - business timestamp
- recorded_at: DateTimeField(auto_now_add=True) - system timestamp
- metadata: JSONField(default=dict)

Property:
- is_posted: returns True if posted_at is not None

### Entry Model

- transaction: ForeignKey(Transaction, on_delete=PROTECT)
- account: ForeignKey(Account, on_delete=PROTECT)
- amount: DecimalField(max_digits=19, decimal_places=4)
- entry_type: CharField with choices ('debit', 'credit')
- description: CharField(max_length=500, blank=True)
- effective_at: DateTimeField(default=timezone.now)
- recorded_at: DateTimeField(auto_now_add=True)
- reverses: ForeignKey('self', null=True, blank=True) - for reversal entries
- metadata: JSONField(default=dict)

CRITICAL: Override save() to prevent modification of posted entries:
- If self.pk exists AND self.transaction.is_posted, raise ImmutableEntryError

## Service Functions

### record_transaction(description, entries, effective_at=None, metadata=None)

1. Validate: sum(debits) must equal sum(credits)
2. If not balanced, raise UnbalancedTransactionError
3. Create Transaction
4. Create all Entry records
5. Set posted_at = timezone.now()
6. Return the posted Transaction

Use @transaction.atomic decorator.

### get_balance(account, as_of=None)

1. Filter entries for account where transaction.posted_at is not None
2. If as_of provided, filter effective_at <= as_of
3. Sum debits, sum credits
4. Return debits - credits as Decimal

### reverse_entry(entry, reason, effective_at=None)

1. Determine opposite entry_type
2. Create new Transaction with description "Reversal: {reason}"
3. Create Entry with opposite type, same amount, reverses=entry
4. Post the transaction
5. Return the reversal Transaction

Use @transaction.atomic decorator.

## Test Cases (48 tests minimum)

### Account Model (7 tests)
- test_account_has_owner_generic_fk
- test_account_owner_id_is_charfield (for UUID support)
- test_account_has_account_type
- test_account_has_currency
- test_account_has_name_optional
- test_account_name_defaults_to_empty
- test_account_has_timestamps

### Transaction Model (8 tests)
- test_transaction_has_description
- test_transaction_description_is_optional
- test_transaction_has_posted_at_nullable
- test_transaction_is_posted_property
- test_transaction_has_effective_at
- test_transaction_effective_at_defaults_to_now
- test_transaction_has_recorded_at
- test_transaction_has_metadata

### Entry Model (10 tests)
- test_entry_has_transaction_fk
- test_entry_has_account_fk
- test_entry_has_amount_decimal
- test_entry_has_entry_type (debit/credit)
- test_entry_has_description
- test_entry_has_effective_at
- test_entry_has_recorded_at
- test_entry_has_reverses_fk
- test_entry_reversal_entries_related_name
- test_entry_has_metadata

### Entry Immutability (2 tests)
- test_entry_can_be_modified_before_posting
- test_entry_immutable_after_posting (raises ImmutableEntryError)

### Account QuerySet (3 tests)
- test_for_owner_returns_accounts
- test_by_type_filters_accounts
- test_by_currency_filters_accounts

### record_transaction Service (7 tests)
- test_record_transaction_creates_transaction
- test_record_transaction_creates_entries
- test_record_transaction_posts_transaction
- test_record_transaction_enforces_balance (raises UnbalancedTransactionError)
- test_record_transaction_multiple_entries (3+ entries)
- test_record_transaction_with_metadata
- test_record_transaction_with_effective_at

### get_balance Service (5 tests)
- test_get_balance_returns_zero_for_empty
- test_get_balance_calculates_debit_minus_credit
- test_get_balance_credit_account (negative balance)
- test_get_balance_multiple_transactions
- test_get_balance_as_of_timestamp

### reverse_entry Service (5 tests)
- test_reverse_entry_creates_new_transaction
- test_reverse_entry_creates_opposite_entry
- test_reverse_entry_links_to_original (reverses FK)
- test_reverse_entry_nets_to_zero
- test_reverse_entry_includes_reason

### Integration (1 test)
- test_complete_sales_cycle (sale → payment → refund)

## Key Behaviors

1. Double-entry balance: debits MUST equal credits
2. Immutable posted entries: cannot modify after posting
3. Reversal pattern: create opposite entry instead of delete
4. GenericFK owners: accounts owned by any model
5. Balance = debits - credits (consistent formula)
6. Currency as Decimal, NEVER float

## Usage Example

from decimal import Decimal
from django_ledger import Account, record_transaction, get_balance, reverse_entry

# Create accounts
receivable = Account.objects.create(
    owner=customer, account_type='receivable', currency='USD'
)
revenue = Account.objects.create(
    owner=org, account_type='revenue', currency='USD'
)

# Record sale
tx = record_transaction(
    description="Invoice #123",
    entries=[
        {'account': receivable, 'amount': Decimal('100.00'), 'entry_type': 'debit'},
        {'account': revenue, 'amount': Decimal('100.00'), 'entry_type': 'credit'},
    ]
)

# Check balance
balance = get_balance(receivable)  # Decimal('100.00')

# Reverse if needed
reversal = reverse_entry(tx.entries.first(), reason="Customer refund")
balance = get_balance(receivable)  # Decimal('0')

## Acceptance Criteria

- [ ] Account model with GenericFK owner
- [ ] Transaction model with posted_at for immutability
- [ ] Entry model with immutability enforcement
- [ ] record_transaction enforces balance
- [ ] get_balance calculates debits - credits
- [ ] reverse_entry creates opposite entry
- [ ] All 48 tests passing
- [ ] No float currency, only Decimal
```

---

## Práctica: Genera Tu Libro Mayor

Copia el prompt de arriba y pégalo en tu asistente de IA. La IA generará:

1. La estructura completa del paquete
2. Modelos con todas las restricciones
3. Funciones de servicio con validación adecuada
4. Clases de excepciones
5. Casos de prueba cubriendo todos los comportamientos

Después de la generación, ejecuta las pruebas:

```bash
cd packages/django-ledger
pip install -e .
pytest tests/ -v
```

Las 48 pruebas deberían pasar. Si alguna falla, revisa la prueba fallida para entender qué restricción se violó, luego pide a la IA que la corrija.

### Ejercicio: Agregar Conversión de Moneda

Extiende el libro mayor con soporte multimoneda:

```
Extend django-ledger to support multicurrency transactions:

1. Add ExchangeRate model:
   - from_currency, to_currency (both CharField(3))
   - rate (DecimalField, max_digits=12, decimal_places=6)
   - effective_from, effective_to for temporal validity

2. Add convert_amount(amount, from_currency, to_currency, as_of) function:
   - Look up rate valid at as_of timestamp
   - Return amount * rate as Decimal
   - Raise CurrencyConversionError if no rate found

3. Modify record_transaction to validate all entries use same currency
   (multicurrency transactions require explicit conversion entries)

Write tests for:
- Exchange rate lookup by date
- Currency conversion calculation
- Rejecting mismatched currencies in single transaction
```

Este ejercicio extiende el libro mayor mientras mantiene sus invariantes centrales.

## Lo Que la IA Hace Mal

Sin restricciones explícitas, el código contable generado por IA típicamente:

1. **Usa FloatField para cantidades** — El problema de 0.1 + 0.2 corrompe tus libros.

2. **Permite editar transacciones registradas** — Alguien "corrige" una entrada antigua en lugar de crear una reversión. La pista de auditoría se rompe.

3. **Omite validación de balance** — Las transacciones desbalanceadas se aceptan silenciosamente. Tus libros no concilian.

4. **Almacena el balance como campo** — Condiciones de carrera y fallas de sincronización corrompen el balance. No conoces el número real.

5. **Usa IntegerField para owner_id** — Se rompe cuando las partes tienen claves primarias UUID.

6. **Carece del patrón de reversión** — Se permiten eliminaciones, destruyendo el historial de auditoría.

La solución siempre son restricciones explícitas. El prompt de arriba previene todos estos errores.

## Por Qué Esto Importa Después

El libro mayor es la base financiera:

- **Catálogo**: Cuando una cesta se confirma, las entradas del libro mayor registran la venta.

- **Acuerdos**: Los calendarios de pago y la facturación derivan de los términos del acuerdo y crean entradas del libro mayor.

- **Auditoría**: Cada entrada del libro mayor es evidencia permanente de lo que sucedió.

- **Reportes**: Los estados financieros se calculan a partir de las entradas del libro mayor, no de resúmenes almacenados.

Si el libro mayor está mal, tus datos financieros no son confiables. Si está bien, tienes libros en los que los auditores confiarán.

---

## Cómo Reconstruir Este Primitivo

| Paquete | Archivo de Prompt | Cantidad de Pruebas |
|---------|-------------------|---------------------|
| django-ledger | `docs/prompts/django-ledger.md` | 48 pruebas |

### Usando el Prompt

```bash
cat docs/prompts/django-ledger.md | claude

# Request: "Implement Account model with GenericFK owner,
# then Transaction with posted_at for immutability,
# then Entry with debit/credit types."
```

### Restricciones Clave

- **DecimalField para todas las cantidades**: Nunca uses FloatField para dinero
- **Entradas registradas inmutables**: No se pueden modificar después de que `posted_at` esté establecido
- **Aplicación de balance**: `record_transaction` debe validar débitos = créditos
- **Patrón de reversión**: Las correcciones crean entradas opuestas, nunca eliminan

Si Claude permite editar una entrada registrada o almacena cantidades como Float, eso es una violación de restricción.

---

## Fuentes y Referencias

1. **Pacioli, Luca** (1494). *Summa de arithmetica, geometria, proportioni et proportionalita*. La primera descripción publicada de la contabilidad por partida doble.

2. **Government Accountability Office** (2019). "Financial Management: Federal Agencies Need to Address Long-Standing Deficiencies." GAO-19-572T. El hallazgo de la discrepancia de $21 mil millones.

3. **Aritmética de Punto Flotante** — Goldberg, David. "What Every Computer Scientist Should Know About Floating-Point Arithmetic," *ACM Computing Surveys*, Marzo 1991. La explicación autorizada de por qué 0.1 + 0.2 ≠ 0.3.

4. **ISO 4217** — Estándar internacional para códigos de moneda. USD, EUR, GBP, etc.

5. **Django DecimalField** — Documentación de Django sobre el uso de Decimal para cálculos monetarios precisos.

---

*Estado: Completo*
