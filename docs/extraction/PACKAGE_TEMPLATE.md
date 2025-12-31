# Package Template

Standard layout for all django-primitives packages.

---

## Directory Structure

```
django-{name}/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/
│   └── django_{name}/
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py
│       ├── services.py
│       ├── selectors.py
│       ├── protocols.py      # Optional: abstract interfaces
│       ├── exceptions.py     # Optional: custom exceptions
│       ├── admin.py          # Optional: admin integration
│       ├── migrations/
│       │   └── __init__.py
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_models.py
│           ├── test_services.py
│           └── test_selectors.py
└── docs/
    └── usage.md
```

---

## pyproject.toml Template

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-{name}"
version = "0.1.0"
description = "{One-line description}"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Framework :: Django :: 4.2",
    "Framework :: Django :: 5.0",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "django>=4.2",
    # Add django-basemodels if this package depends on it
    # "django-basemodels>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-django>=4.5",
    "pytest-cov>=4.0",
    "black>=23.0",
    "ruff>=0.1.0",
]

[project.urls]
Homepage = "https://github.com/yourorg/django-{name}"
Documentation = "https://github.com/yourorg/django-{name}#readme"
Repository = "https://github.com/yourorg/django-{name}"

[tool.hatch.build.targets.wheel]
packages = ["src/django_{name}"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
python_files = ["test_*.py"]
addopts = "--cov=django_{name} --cov-report=term-missing --cov-fail-under=95"

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.black]
line-length = 100
```

---

## apps.py Template

```python
from django.apps import AppConfig


class Django{Name}Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_{name}"
    verbose_name = "{Human Readable Name}"
```

---

## __init__.py Template

```python
"""
django-{name}: {One-line description}
"""

__version__ = "0.1.0"

# Public API exports
from django_{name}.models import {MainModel}
from django_{name}.services import {MainService}
from django_{name}.selectors import {main_selectors}

__all__ = [
    "{MainModel}",
    "{MainService}",
    "{main_selectors}",
]
```

---

## README.md Template

```markdown
# django-{name}

{One-line description}

## Installation

```bash
pip install django-{name}
```

## Configuration

Add to INSTALLED_APPS:

```python
INSTALLED_APPS = [
    ...
    "django_{name}",
]
```

Run migrations:

```bash
python manage.py migrate django_{name}
```

## Usage

```python
from django_{name}.models import {MainModel}
from django_{name}.services import {MainService}

# Example usage
instance = {MainService}.create(...)
```

## Requirements

- Python 3.11+
- Django 4.2+

## License

MIT
```

---

## Test Settings (tests/settings.py)

```python
SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_{name}",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

---

## conftest.py Template

```python
import pytest
from django.conf import settings


@pytest.fixture(scope="session")
def django_db_setup():
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }


@pytest.fixture
def sample_data():
    """Create sample data for tests."""
    # Return test fixtures
    pass
```

---

## Checklist for New Package

- [ ] Create repo from template
- [ ] Update package name in all files
- [ ] Write models with docstrings
- [ ] Write services with type hints
- [ ] Write selectors with type hints
- [ ] Write tests (95%+ coverage)
- [ ] Write README with usage examples
- [ ] Run linting (ruff, black)
- [ ] Run tests locally
- [ ] Set up CI (GitHub Actions)
- [ ] Publish to PyPI (or private index)
