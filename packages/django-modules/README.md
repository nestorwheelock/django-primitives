# django-modules

Module enable/disable per organization for Django.

## Install

```bash
pip install django-modules
```

## Quick Start

1. Add `django_modules` to `INSTALLED_APPS`
2. Run migrations: `python manage.py migrate django_modules`
3. Use `is_module_enabled(org, 'module_key')` to check module status

## Versioning

This package follows semantic versioning. See `__version__` in the package root.
