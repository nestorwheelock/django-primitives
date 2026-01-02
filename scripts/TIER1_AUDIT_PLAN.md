# Tier 1 Audit Plan

## Packages in Scope

**Tier 1 (Identity + Infrastructure):**
- django-parties (identity spine)
- django-rbac (role-based access)
- django-decisioning (decisions + idempotency)
- django-audit-log (append-only forensics)

**Tier 2 (Domain):**
- django-catalog
- django-encounters
- django-worklog
- django-ledger
- django-geo

**Tier 3 (Content):**
- django-documents
- django-notes
- django-agreements

**Tier 4 (Value Objects):**
- django-money
- django-sequence

---

## Audit Categories

### A) Structural Compliance (MUST)

| Check | Domain | System | Utility |
|-------|--------|--------|---------|
| Inherits BaseModel | Required | Forbidden | Ignored |
| No UUIDModel direct use | Required | N/A | Ignored |
| No manual timestamps | Required | Allowed | Ignored |
| No manual id field | Required | Allowed | Ignored |
| Soft-delete manager intact | Required | N/A | Ignored |

### B) Dependency Sanity (MUST)

- [ ] No circular dependencies between packages
- [ ] Version floors: `django-basemodels>=0.2.0` where needed
- [ ] No upward tier imports (Tier 1 cannot import Tier 2)
- [ ] No importing consuming app code inside primitives

### C) Migration Sanity (MUST)

- [ ] UUIDField for id where BaseModel is used
- [ ] No AutoField/BigAutoField in domain packages
- [ ] Migration dependencies are correct (no broken graph)
- [ ] No testapp migrations in production code

### D) GenericForeignKey Patterns (MUST)

- [ ] object_id fields use CharField(max_length=255) not PositiveIntegerField
- [ ] ContentType FKs use on_delete=PROTECT or CASCADE appropriately

### E) ForeignKey Policies (RECOMMENDED)

- [ ] Domain data uses PROTECT (not CASCADE) for audit trail
- [ ] Soft-delete models don't cascade hard deletes
- [ ] AUTH_USER_MODEL used instead of direct User import

### F) Package Hygiene (RECOMMENDED)

- [ ] `__version__` matches pyproject.toml version
- [ ] `app_label` in Meta matches package name
- [ ] Models exported in `__init__.py` with lazy imports
- [ ] `tests/` directory exists with test files
- [ ] README.md exists

### G) Pattern Compliance (PER PACKAGE TYPE)

**Ledger-ish (agreements, ledger, encounters, sequence):**
- [ ] services.py exists
- [ ] Direct .save() calls minimal outside services

**Append-only (audit-log, decisioning):**
- [ ] No update/delete methods exposed
- [ ] Immutability enforced

**Temporal (rbac, encounters):**
- [ ] valid_from/valid_to OR effective_at/recorded_at pattern used

---

## Output Format

### Console Summary (per package)
```
Package              Kind      Violations  Models  Migrations  Deps
django-parties       domain    0           10      3           2
django-catalog       domain    2           5       5           4
```

### JSON Report Structure
```json
{
  "timestamp": "2026-01-02T...",
  "packages": {
    "django-parties": {
      "kind": "domain",
      "violations": [],
      "models": ["Party", "Person", "Organization"],
      "dependencies": ["django-basemodels"],
      "migrations": ["0001_initial", "0002_..."]
    }
  },
  "summary": {
    "total_packages": 14,
    "total_violations": 5,
    "by_category": {}
  }
}
```

---

## Scripts to Create

1. `scripts/audit_models.py` - EXISTS, needs expansion
2. `scripts/audit_deps.py` - NEW: dependency graph + cycle detection
3. `scripts/audit_migrations.py` - NEW: migration sanity checks
4. `scripts/audit_tier1.py` - NEW: orchestrator that runs all audits

---

## Execution Plan

```bash
mkdir -p out
python scripts/audit_tier1.py --root . --json out/tier1_audit.json | tee out/tier1_audit.txt
zip -r out/tier1-audit.zip out/
```

---

## Fix Order (after audit)

1. django-parties (identity spine - everything depends on it)
2. django-rbac (identity layer)
3. django-catalog (most referenced domain package)
4. django-encounters (workflow engine)
5. django-ledger (accounting correctness)
6. django-worklog (simpler domain)
7. django-geo (simpler domain)
8. django-documents (content)
9. django-notes (content)
10. django-agreements (content)
11. django-money (value object)
12. django-sequence (value object)
13. django-decisioning (infrastructure - append-only)
14. django-audit-log (infrastructure - append-only)
