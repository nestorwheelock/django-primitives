# Conventions

**Status:** Authoritative
**Scope:** All django-primitives packages

---

## 1. Model Conventions

### BaseModel Usage

All domain models inherit from `BaseModel`:

```python
from django_basemodels.models import BaseModel

class Pet(BaseModel):
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=50)
    # BaseModel provides: id, created_at, updated_at, deleted_at
```

**Never redefine:**
- `id` (use inherited UUID)
- `created_at` / `updated_at` (use inherited timestamps)
- `deleted_at` (use inherited soft delete)

### Primary Keys

```python
# ✅ CORRECT - UUID from BaseModel
class Pet(BaseModel):
    pass  # id is UUID, inherited

# ❌ WRONG - integer PK
class Pet(models.Model):
    id = models.AutoField(primary_key=True)  # NO
```

### Foreign Keys

Always use `on_delete` explicitly:

```python
# ✅ CORRECT - explicit on_delete
owner = models.ForeignKey(Person, on_delete=models.PROTECT)

# ❌ WRONG - implicit or CASCADE for important data
owner = models.ForeignKey(Person, on_delete=models.CASCADE)  # Dangerous for clinical data
```

Preferred `on_delete` choices:
- `PROTECT`: Prevent deletion of referenced object
- `SET_NULL`: Allow deletion, null the reference (requires `null=True`)
- `CASCADE`: Only for true child objects (e.g., order items when order deleted)

---

## 2. Service Layer Pattern

Business logic lives in services, not views or models.

### Service Location

```
package/
├── models.py      # Data structure only
├── services.py    # Write operations (create, update, delete)
├── selectors.py   # Read operations (queries)
└── views.py       # HTTP handling only
```

### Service Pattern

```python
# services.py
class PetService:
    @staticmethod
    def create_pet(owner_id: int, name: str, species: str, **kwargs) -> Pet:
        """Create a pet with validation and side effects."""
        # Validation
        if not name:
            raise ValidationError("Name required")

        # Create
        pet = Pet.objects.create(
            owner_id=owner_id,
            name=name,
            species=species,
            **kwargs
        )

        # Side effects (audit, notifications, etc.)
        # ...

        return pet
```

### Selector Pattern

```python
# selectors.py
def get_pet_by_id(pet_id: UUID) -> Pet | None:
    """Get a pet by ID, or None if not found."""
    return Pet.objects.filter(id=pet_id).first()

def get_pets_for_owner(owner_id: UUID) -> QuerySet[Pet]:
    """Get all pets for an owner."""
    return Pet.objects.filter(owner_id=owner_id)
```

### Views Are Thin

```python
# views.py
class PetCreateView(CreateView):
    def form_valid(self, form):
        # View delegates to service
        pet = PetService.create_pet(
            owner_id=self.request.user.person.id,
            **form.cleaned_data
        )
        return redirect('pet-detail', pk=pet.id)
```

---

## 3. Public API Modules

Each package exposes its API through specific modules:

| Module | Purpose | Pattern |
|--------|---------|---------|
| `selectors.py` | Read operations | `get_X_by_id()`, `get_Xs_for_Y()` |
| `services.py` | Write operations | `XService.create()`, `XService.update()` |
| `protocols.py` | Abstract interfaces | Type hints for cross-package use |

### Cross-Package Access

Other packages and applications access via public API only:

```python
# ✅ CORRECT - use selectors/services
from django_party.selectors import get_person_by_id
from django_party.services import PersonService

# ❌ WRONG - direct model access from outside
from django_party.models import Person
person = Person.objects.filter(...)  # NO - use selectors
```

---

## 4. Naming Conventions

### Models

- PascalCase, singular: `Pet`, `Person`, `Appointment`
- No prefixes: `Pet` not `PetModel` or `TblPet`

### Fields

- snake_case: `first_name`, `created_at`, `is_active`
- Boolean fields: prefix with `is_`, `has_`, `can_`: `is_active`, `has_insurance`
- Foreign keys: name the relationship, not the column: `owner` not `owner_id`

### Services/Selectors

- Services: `{Model}Service` class with static methods
- Selectors: `get_{model}_by_{field}()`, `get_{models}_for_{parent}()`

---

## 5. Error Handling

### Use Django's ValidationError

```python
from django.core.exceptions import ValidationError

def create_appointment(pet_id: UUID, scheduled_at: datetime) -> Appointment:
    if scheduled_at < timezone.now():
        raise ValidationError("Cannot schedule in the past")
    # ...
```

### Custom Exceptions

For domain-specific errors, create explicit exceptions:

```python
# exceptions.py
class InsufficientInventoryError(Exception):
    """Raised when stock is insufficient for consumption."""
    pass

class HierarchyViolationError(Exception):
    """Raised when user attempts to manage higher-level user."""
    pass
```

### Never Swallow Exceptions

```python
# ❌ WRONG
try:
    do_something()
except Exception:
    pass  # Silent failure

# ✅ CORRECT
try:
    do_something()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise
```

---

## 6. Testing Conventions

### Test File Location

```
package/
├── models.py
├── services.py
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_services.py
    └── test_selectors.py
```

### Test Naming

```python
def test_create_pet_with_valid_data_succeeds():
    ...

def test_create_pet_without_name_raises_validation_error():
    ...

def test_soft_delete_excludes_from_default_queryset():
    ...
```

### Coverage Requirement

Minimum 95% coverage for all primitive packages.

---

## 7. Documentation

### Docstrings

All public functions require docstrings:

```python
def get_pets_for_owner(owner_id: UUID) -> QuerySet[Pet]:
    """
    Get all active pets belonging to an owner.

    Args:
        owner_id: UUID of the pet owner

    Returns:
        QuerySet of Pet objects (excludes soft-deleted)
    """
    return Pet.objects.filter(owner_id=owner_id)
```

### Type Hints

All public functions require type hints:

```python
# ✅ CORRECT
def create_pet(owner_id: UUID, name: str, species: str) -> Pet:
    ...

# ❌ WRONG
def create_pet(owner_id, name, species):
    ...
```
