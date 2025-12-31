# django-primitives

Reusable Django packages extracted from production patterns.

---

## What This Is

A collection of standalone, pip-installable Django packages that implement common architectural patterns:

- **django-basemodels**: UUID PKs, timestamps, soft delete
- **django-party**: Party pattern (Person, Organization, relationships)
- **django-rbac**: Role-based access control with hierarchy
- **django-audit**: Append-only audit trails

See [docs/extraction/ROADMAP.md](docs/extraction/ROADMAP.md) for the full extraction plan.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [CONTRACT.md](docs/architecture/CONTRACT.md) | Architectural rules (what must be true) |
| [DEPENDENCIES.md](docs/architecture/DEPENDENCIES.md) | Layer boundaries and import rules |
| [CONVENTIONS.md](docs/architecture/CONVENTIONS.md) | Coding patterns and standards |
| [DECISIONS.md](docs/architecture/DECISIONS.md) | Resolved contradictions and ADRs |
| [TDD_CYCLE.md](docs/process/TDD_CYCLE.md) | 26-step development process |
| [ROADMAP.md](docs/extraction/ROADMAP.md) | Package extraction plan |

---

## Project Structure

```
django-primitives/
├── docs/
│   ├── architecture/     # Canonical contracts and rules
│   │   ├── CONTRACT.md
│   │   ├── DEPENDENCIES.md
│   │   ├── CONVENTIONS.md
│   │   └── DECISIONS.md
│   ├── extraction/       # Package extraction plan
│   │   ├── ROADMAP.md
│   │   ├── PACKAGE_TEMPLATE.md
│   │   └── BOUNDARY_TESTS.md
│   ├── process/          # Development process
│   │   └── TDD_CYCLE.md
│   └── archive/          # Historical docs (read-only)
│       └── vetfriendly-planning/
├── scripts/              # Enforcement scripts
│   ├── check_all.py
│   ├── check_dependencies.py
│   └── check_basemodel.py
└── src/                  # Package source (future)
    ├── django_basemodels/
    ├── django_party/
    └── ...
```

---

## Quick Start

### Run Boundary Checks

```bash
python scripts/check_all.py
```

### Development Process

Every task follows the [26-step TDD cycle](docs/process/TDD_CYCLE.md):

1. **Planning** (Steps 1-6): Validate docs, review code, ask questions
2. **TDD** (Steps 7-10): Write failing tests, make them pass
3. **Quality** (Steps 11-14): Refactor, document, verify coverage
4. **Git** (Steps 15-18): Commit with conventional format
5. **Review** (Steps 19-23): Code review, fix issues
6. **Ship** (Steps 24-26): Push, deploy staging, deploy production (manual)

---

## Key Principles

From [CONTRACT.md](docs/architecture/CONTRACT.md):

1. **Party Pattern**: Person/Organization/Group are foundational
2. **User vs Person**: Authentication is separate from identity
3. **RBAC Hierarchy**: Users can only manage lower-level users
4. **BaseModel**: All domain models use UUID, timestamps, soft delete
5. **Separation**: Clinical != Operational != Inventory != Accounting
6. **Explicit Triggers**: Side effects happen at defined points only

---

## Extraction Tiers

### Tier 1: Foundation (Extract First)

| Package | Purpose |
|---------|---------|
| django-basemodels | UUID PKs, timestamps, soft delete |
| django-party | Party pattern |
| django-rbac | Role hierarchy |
| django-audit | Audit trails |

### Tier 2: Domain (After Tier 1)

| Package | Purpose |
|---------|---------|
| django-catalog | Orderable item definitions |
| django-workitems | Task spawning |
| django-encounters | Clinical pipelines |
| django-worklog | Time tracking |

### Tier 3: Infrastructure

| Package | Purpose |
|---------|---------|
| django-modules | Dynamic feature config |
| django-singleton | Settings pattern |
| django-layers | Import enforcement |

---

## Origin

These patterns were extracted from [VetFriendly](../vetfriendly/), a veterinary practice management system. The original planning documents are archived in [docs/archive/vetfriendly-planning/](docs/archive/vetfriendly-planning/).

---

## License

MIT
