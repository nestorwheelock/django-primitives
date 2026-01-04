# Tier 5: Value Objects - Deep Review

**Review Date:** 2026-01-02
**Reviewer:** Claude Code (Opus 4.5)
**Packages:** django-money, django-sequence

---

## ⚠️ Classification Issue

**django-sequence is NOT a value object.** It was incorrectly classified in Tier 5.

| Package | Has DB Model | Has Identity | Has State | Correct Classification |
|---------|--------------|--------------|-----------|------------------------|
| django-money | No | No | No (immutable) | ✅ Value Object (Tier 5) |
| django-sequence | Yes (BaseModel) | Yes (UUID) | Yes (current_value) | ❌ Infrastructure (Tier 0 or 2) |

**Recommendation:** Move django-sequence to **Tier 0 (Foundation)** because:
1. It only depends on django-basemodels (Tier 0)
2. ID generation is foundational infrastructure
3. Other domain packages may use it for human-readable IDs
4. It has no domain-specific logic

The review below covers both packages as documented, but the tier structure should be updated.

---

## 1. django-money

### Purpose
Immutable Money value object with currency-aware arithmetic. No database storage - pure domain primitive.

### Architecture
```
Money (dataclass, frozen=True)
├── amount: Decimal (normalized from any numeric input)
├── currency: str (ISO 4217 code)
├── Arithmetic: +, -, *, neg, abs
├── quantized() → banker's rounding to currency decimals
└── is_positive(), is_negative(), is_zero()

CURRENCY_DECIMALS (dict)
├── Standard: USD, EUR, GBP, MXN... → 2 decimals
├── Zero-decimal: JPY, KRW → 0 decimals
└── Crypto: BTC → 8 decimals

Exceptions:
├── CurrencyMismatchError (add/subtract different currencies)
└── MoneyOverflowError (reserved for future use)
```

### What Should NOT Change

1. **dataclass(frozen=True)** - Immutability is critical for value objects
2. **Decimal normalization in __post_init__** - Prevents float precision errors
3. **Currency check in __add__/__sub__** - Prevents currency math errors
4. **ROUND_HALF_EVEN (banker's rounding)** - Industry standard for financial calculations
5. **No database storage** - This is pure domain logic, not a Django model

---

### Opportunity 1: No __truediv__ (division)

**Current State:**
Division is not implemented. `Money / 2` raises TypeError.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add __truediv__ | Allow Money / scalar | More complete API | Division can produce rounding issues |
| B) Keep as-is | Force explicit calculation | Avoids precision pitfalls | Less convenient |

**Risk/Reward:** Low risk, medium reward
**Effort:** S
**Recommendation:** **DEFER** - Division in money is tricky (e.g., $10/3). If needed, caller should handle rounding explicitly. Document the intentional omission.

---

### Opportunity 2: Add __eq__ and __hash__ for dict keys

**Current State:**
dataclass(frozen=True) automatically provides __eq__ and __hash__.

**Risk/Reward:** N/A
**Effort:** N/A
**Recommendation:** **Already Done** - Frozen dataclass provides these automatically

---

### Opportunity 3: Currency code validation

**Current State:**
Any string is accepted as currency. No validation that it's a known code.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add validation in __post_init__ | Raise if unknown currency | Catches typos | Limits extensibility |
| B) Add STRICT_CURRENCIES setting | Opt-in validation | Flexible | Configuration overhead |
| C) Keep as-is | Accept any string | Extensible | Typos allowed |

**Risk/Reward:** Low risk, low reward (typos are rare)
**Effort:** S
**Recommendation:** **DEFER** - Keep flexible; validate in application layer if needed

---

### Opportunity 4: Add comparison operators

**Current State:**
Only equality is supported. No __lt__, __le__, __gt__, __ge__.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add comparison operators | Allow Money < Money | More complete API | Currency mismatch handling needed |
| B) Keep as-is | Compare only amounts explicitly | Clear intent | Less convenient |

**Example:**
```python
def __lt__(self, other: 'Money') -> bool:
    if self.currency != other.currency:
        raise CurrencyMismatchError(...)
    return self.amount < other.amount
```

**Risk/Reward:** Low risk, medium reward
**Effort:** S
**Recommendation:** **ADOPT** - Comparison operators are commonly needed (sorting, max/min)

---

### Opportunity 5: Add MoneyField for ORM storage

**Current State:**
No Django model field. Users must store amount and currency separately.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add composite MoneyField | Store as JSON or separate columns | Convenient | Increases package scope |
| B) Keep as-is | Let users compose their own | Simple; focused | More work for users |

**Risk/Reward:** Medium effort, high reward (common use case)
**Effort:** M
**Recommendation:** **DEFER** - Out of scope for value object package. Could be separate package or documented pattern.

---

### Opportunity 6: Localized formatting

**Current State:**
No currency symbol or locale-aware formatting.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add format() method | Support locale-aware display | User-friendly output | Adds babel/locale dependency |
| B) Keep as-is | Pure value object | Simple; no deps | Users format themselves |

**Risk/Reward:** Medium risk (dependency), medium reward
**Effort:** M
**Recommendation:** **AVOID** - Keep value object pure. Formatting is presentation concern.

---

## 2. django-sequence

### Purpose
Human-readable, gap-free sequence generator for invoices, orders, tickets, etc. Multi-tenant via org scoping.

### Architecture
```
Sequence (BaseModel)
├── scope: varchar(50) - e.g., 'invoice', 'order'
├── org_content_type, org_id: GenericFK to org (nullable)
├── prefix: varchar(20) - e.g., 'INV-', 'ORD-'
├── current_value: PositiveBigIntegerField
├── pad_width: PositiveSmallIntegerField (default 6)
├── include_year: BooleanField (default True)
├── unique_together: [scope, org_content_type, org_id]
└── formatted_value property: "INV-2026-000001"

Services:
└── next_sequence() → atomic increment with select_for_update()

Exceptions:
├── SequenceNotFoundError (auto_create=False)
└── SequenceLockedError (future: timeout handling)
```

### What Should NOT Change

1. **Extends BaseModel** - Gets UUID, timestamps, soft-delete
2. **GenericFK with CharField for org_id** - Correct for UUID support
3. **select_for_update() in service** - Prevents race conditions
4. **unique_together constraint** - One sequence per scope+org
5. **PositiveBigIntegerField for current_value** - Handles large sequences
6. **formatted_value property** - Clean separation of storage vs display

---

### Opportunity 7: Convert unique_together to UniqueConstraint

**Current State:**
`unique_together = ['scope', 'org_content_type', 'org_id']` - Deprecated syntax.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Use UniqueConstraint | Modern Django syntax | Future-proof | Migration required |
| B) Keep as-is | Works correctly | No change | Deprecated syntax |

**Constraint Example:**
```python
models.UniqueConstraint(
    fields=['scope', 'org_content_type', 'org_id'],
    name='sequence_unique_scope_org'
)
```

**Risk/Reward:** Low risk, low reward (stylistic)
**Effort:** S
**Recommendation:** **ADOPT** - Modernize to UniqueConstraint

---

### Opportunity 8: Add CheckConstraint for pad_width > 0

**Current State:**
`pad_width = PositiveSmallIntegerField(default=6)` - Allows 0, which produces no padding.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add CheckConstraint ≥ 1 | Enforce minimum padding | Prevents degenerate cases | May have valid use for 0 |
| B) Keep as-is | Allow 0 | Flexible | "001" vs "1" ambiguity |

**Constraint Example:**
```python
models.CheckConstraint(
    check=Q(pad_width__gte=1),
    name='sequence_positive_pad_width'
)
```

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - 0 padding is valid if user wants unpadded numbers

---

### Opportunity 9: Add CheckConstraint for prefix format

**Current State:**
`prefix = CharField(max_length=20)` - No format validation.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add regex constraint | Validate alphanumeric + hyphens | Clean sequences | Limits flexibility |
| B) Add clean() validation | Python-level check | Simple | Bypassed by bulk ops |
| C) Keep as-is | Any prefix allowed | Flexible | Invalid chars possible |

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - Keep flexible; let users define their conventions

---

### Opportunity 10: Add reset_sequence() service function

**Current State:**
No way to reset a sequence (e.g., for new fiscal year).

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add reset_sequence() | Allow controlled reset | Supports yearly sequences | Can create duplicate IDs |
| B) Keep as-is | Sequences only increment | Gap-free guarantee | Users need year in prefix |

**Risk/Reward:** Medium risk (ID conflicts), medium reward
**Effort:** S
**Recommendation:** **DEFER** - Current design uses year in formatted output. Reset is dangerous for ID uniqueness.

---

### Opportunity 11: Year rollover handling

**Current State:**
`formatted_value` uses `date.today().year` which changes at midnight Jan 1.

**Issue:** Sequence "INV-2025-000100" → "INV-2026-000101" creates a gap in 2025 numbers.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Store year_started field | Track which year sequence started | Consistent numbering | Schema change |
| B) Reset per year | Start over each year | Clean yearly sequences | Complexity; ID conflicts |
| C) Keep as-is | Continuous counter with year prefix | Simple; gap-free | "Gap" at year boundary |

**Risk/Reward:** Medium effort, unclear reward
**Effort:** M
**Recommendation:** **DEFER** - Current behavior is correct for most use cases. Year change at midnight is expected.

---

### Opportunity 12: Add index for prefix queries

**Current State:**
No index on `prefix`. Queries like "find all invoice sequences" would use the composite index on scope.

**Options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A) Add db_index on prefix | Fast prefix queries | Useful for admin | Minor overhead |
| B) Keep as-is | Use scope-based queries | Simple | Prefix queries slower |

**Risk/Reward:** Low risk, low reward
**Effort:** S
**Recommendation:** **DEFER** - Query by scope, not prefix. Prefix is display concern.

---

## Tier 5 Summary

### django-money

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 1. Add __truediv__ | DEFER | S | N/A |
| 2. __eq__ and __hash__ | Already Done | N/A | N/A |
| 3. Currency validation | DEFER | S | N/A |
| 4. Comparison operators | **ADOPT** | S | N/A |
| 5. MoneyField for ORM | DEFER | M | N/A |
| 6. Localized formatting | AVOID | M | N/A |

### django-sequence

| Opportunity | Action | Effort | DB Constraint? |
|-------------|--------|--------|----------------|
| 7. unique_together → UniqueConstraint | **ADOPT** | S | Yes - style |
| 8. pad_width CheckConstraint | DEFER | S | Yes |
| 9. prefix format validation | DEFER | S | No |
| 10. reset_sequence() function | DEFER | S | No |
| 11. Year rollover handling | DEFER | M | No |
| 12. Index on prefix | DEFER | S | Yes - Index |

---

## Immediate Action Items (ADOPT)

### High Priority (API Completeness)

1. **django-money:** Add comparison operators (__lt__, __le__, __gt__, __ge__)

### Medium Priority (Modernization)

2. **django-sequence:** Convert unique_together to UniqueConstraint

---

## Overall Tier 5 Assessment

**Verdict: Production-ready, well-designed value object patterns.**

Both packages implement their patterns correctly with appropriate design choices:
- Money is pure value object (no DB) with immutability
- Sequence is DB-backed with proper concurrency handling

**Key Architectural Strengths:**

**django-money:**
- frozen dataclass ensures immutability
- Decimal normalization prevents float precision issues
- Currency mismatch protection on arithmetic
- Banker's rounding for financial accuracy
- No database entanglement - pure domain logic

**django-sequence:**
- BaseModel inheritance for UUID, timestamps
- GenericFK with CharField for multi-tenant org support
- select_for_update() prevents race conditions
- Formatted output separates storage from display
- Auto-create pattern for convenience

**Key Pattern: Value Object (Money)**
- No identity (no pk/id)
- Immutable (frozen=True)
- Equality by value (dataclass provides)
- Pure functions that return new instances
- Should be documented as the standard for domain primitives

**Key Pattern: Atomic Counter (Sequence)**
- Row-level locking with select_for_update()
- Transaction boundary for consistency
- Separation of raw value (current_value) and formatted output
- Should be documented as the standard for gap-free sequences

**What NOT to change:**
- Money immutability (frozen=True)
- Decimal normalization in __post_init__
- Currency mismatch exceptions
- select_for_update() pattern in next_sequence()
- unique_together constraint (but modernize syntax)

**Documentation Needs:**
- Document why __truediv__ is omitted (precision concerns)
- Document year rollover behavior at sequence boundary
- Add usage patterns for common scenarios (invoices, tickets)
