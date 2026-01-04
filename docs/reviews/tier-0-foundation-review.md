# Tier 0: Foundation - Deep Review

**Review Date:** 2026-01-02
**Reviewer:** Claude Code (Opus 4.5)
**Packages:** django-basemodels, django-singleton, django-modules, django-layers

---

## 1. django-basemodels

### Purpose
Provides the canonical abstract base classes for all domain models: UUID primary keys, timestamps, and soft-delete.

### Architecture
```
BaseModel = UUIDModel + TimeStampedModel + SoftDeleteModel

Composition hierarchy:
├── UUIDModel          → id: UUID (non-guessable, distributed-safe)
├── TimeStampedModel   → created_at, updated_at (auto-managed)
└── SoftDeleteModel    → deleted_at, objects/all_objects managers
```

### Strengths
- **Excellent composition** - Each concern is a separate mixin; can use individually if needed
- **Manager design is correct** - `objects` excludes deleted, `all_objects` includes all
- **API is intuitive** - `delete()` soft-deletes, `hard_delete()` actually removes, `restore()` recovers
- **Good documentation** - Module docstring explains exactly what you get
- **Lazy imports** - Prevents AppRegistryNotReady errors

### Concerns
1. **No cascade handling** - If you soft-delete a parent, children remain accessible via `objects`. Related objects need explicit handling.
2. **No `deleted_by` tracking** - No audit trail of who deleted. May need django-audit-log integration.
3. **`update_fields` on delete** - Uses `save(update_fields=['deleted_at'])` which won't trigger `updated_at`. Intentional? If so, document it.

### Test Coverage
31 tests passing - covers creation, deletion, restoration, manager queries, edge cases.

### Dependencies
None (uses only Django core). This is correct for Tier 0.

### Recommended Next Action: **ADOPT**
This is production-ready and well-designed. The cascade concern is a documentation/pattern issue, not a code issue.

---

## 2. django-singleton

### Purpose
Enforces exactly one row per model (e.g., site settings, global config).

### Architecture
```python
class SingletonModel(models.Model):
    # Enforces pk=1, provides get_instance(), prevents delete
```

### Strengths
- **Simple, clear contract** - `pk=1` always, `get_instance()` is the only access pattern
- **Race condition handling** - Uses `transaction.atomic()` + IntegrityError catch for concurrent creates
- **Delete protection** - Raises `SingletonDeletionError`, can't accidentally delete settings
- **Corruption detection** - Checks for extra rows (from bulk ops/fixtures) before save

### Concerns
1. **No caching** - Every `get_instance()` hits the database. For high-traffic settings access, this could be expensive. Consider adding `@cached_property` or explicit cache layer.
2. **No BaseModel inheritance** - Uses plain `models.Model`. This is intentional (singletons don't need UUID/soft-delete), but breaks the "everything uses BaseModel" pattern. Document this exception explicitly.
3. **No migration from pk=1** - If you want to change the singleton instance, there's no `update_instance()` method - you have to manually update the existing row.

### Test Coverage
15 tests passing - covers creation, re-access, race conditions, delete blocking.

### Dependencies
None. Correct for Tier 0.

### Recommended Next Action: **ADOPT**
Solid pattern implementation. The caching concern is a performance optimization that can be added later if needed. The no-BaseModel design is correct for this use case.

---

## 3. django-modules

### Purpose
Per-organization feature toggle system. Enable/disable modules (features) at the org level.

### Architecture
```
Module (global definition)
    ├── key: "pharmacy", "billing", etc.
    ├── active: global default (True/False)
    └── OrgModuleState (per-org override)
         ├── org: FK to org model
         ├── enabled: True/False override
         └── If no OrgModuleState exists, uses Module.active
```

### Strengths
- **Clean override pattern** - Global default + per-org override is the right design
- **Uses BaseModel** - Gets UUID, timestamps, soft-delete
- **Configurable org model** - Uses `get_org_model_string()` to allow flexible org FK
- **Public API is minimal** - Just `is_module_enabled()`, `require_module()`, `list_enabled_modules()`

### Concerns
1. **N+1 risk** - `is_module_enabled()` likely does 2 queries (Module + OrgModuleState). For permission checks in loops, this adds up fast. Consider prefetch/cache pattern.
2. **No bulk check API** - `list_enabled_modules()` returns a set, but there's no `are_modules_enabled(org, [list])` for batch checking.
3. **Soft-delete interaction** - If an org is soft-deleted, their OrgModuleState rows still exist. Is this intentional? Probably fine (settings preserved for restore).
4. **Depends on django-basemodels** - This is a Tier 0 package importing from Tier 0. This is allowed but creates a dependency order: django-basemodels must be installed first.

### Test Coverage
57 tests passing - extensive coverage of enable/disable logic.

### Dependencies
- `django-basemodels` (Tier 0) - allowed

### Recommended Next Action: **ADOPT**
Good feature toggle design. The N+1 concern is addressable with caching at the service layer. Consider adding a `@cache_module_state` decorator for high-frequency checks.

---

## 4. django-layers

### Purpose
Static analysis tool to enforce import boundaries between packages in a monorepo. Prevents higher tiers from being imported by lower tiers.

### Architecture
```
layers.yaml (config)
    ├── layers: [{name, packages, level}]
    ├── ignore: paths to skip
    └── allow: explicit import exceptions

checker.py → scanner.py → resolver.py
    ↓
Violation[] with file, line, from/to package, reason
```

### Strengths
- **AST-based scanning** - Parses actual imports, not regex matching
- **YAML config** - Declarative layer definitions, easy to read and maintain
- **Explicit allowlist** - Can permit specific cross-tier imports when needed
- **CLI integration** - Runs in CI via `python -m django_layers.cli check`
- **Actionable output** - Reports file:line, from→to package, and why it's a violation

### Concerns
1. **No runtime enforcement** - This is static analysis only. If someone imports at runtime via `importlib`, it won't be caught. This is fine for most cases, but document the limitation.
2. **Duplicates ci_quality_gate.py** - We now have TWO tier checking systems: django-layers (full YAML config) and ci_quality_gate.py (hardcoded tiers). Should consolidate.
3. **yaml dependency** - Requires `pyyaml`. Tier 0 packages should have minimal deps. Not a blocker, but worth noting.
4. **Test fixtures are internal** - `tests/fixtures/packages/` contains fake packages. Good for testing, but ensure they don't get scanned in CI.

### Test Coverage
64 tests passing - covers config parsing, violation detection, ignore paths.

### Dependencies
- `pyyaml` (third-party)
- No django-primitives deps - correct for Tier 0

### Recommended Next Action: **ADOPT**
Essential for maintaining architecture integrity. The duplication with ci_quality_gate.py should be resolved - either have ci_quality_gate.py call django-layers, or consolidate the tier definitions into layers.yaml only.

---

## Tier 0 Summary

| Package | Status | Key Strength | Key Concern |
|---------|--------|--------------|-------------|
| django-basemodels | **ADOPT** | Clean composition, intuitive API | Cascade handling undocumented |
| django-singleton | **ADOPT** | Race-safe, delete-protected | No caching (perf for high-traffic) |
| django-modules | **ADOPT** | Clean override pattern | N+1 query risk |
| django-layers | **ADOPT** | Essential architecture guard | Duplicate tier definitions |

---

## Overall Tier 0 Assessment

**Verdict: Production-ready foundation.**

All four packages are well-designed with appropriate separation of concerns. Minor concerns are documentation/optimization issues, not architectural flaws.

### Action Items

1. **django-basemodels**: Document cascade behavior for soft-delete
2. **django-singleton**: Consider caching for high-traffic deployments
3. **django-modules**: Add bulk check API or caching decorator
4. **django-layers**: Consolidate with ci_quality_gate.py tier definitions

### Installation Order

Due to internal dependencies:
```
1. django-basemodels (no deps)
2. django-singleton (no deps)
3. django-layers (no django-primitives deps)
4. django-modules (depends on django-basemodels)
```
