# django-singleton

Singleton settings model pattern for Django.

## Install

```bash
pip install django-singleton
```

## Quick Start

1. Add `django_singleton` to `INSTALLED_APPS`
2. Create a model inheriting from `SingletonModel`
3. Access via `YourModel.get_instance()`

## Versioning

This package follows semantic versioning. See `__version__` in the package root.
