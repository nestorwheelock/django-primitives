# django-audit-log

Generic, B2B-grade audit logging for Django applications.

Answers: **"Who did what, when, and where?"**

## Features

- UUID primary keys
- Immutable logs (append-only, no updates/deletes)
- Actor tracking with string snapshots
- Before/after change diffs (JSON)
- Request context (IP, user agent, request ID)
- Sensitivity classification (normal/high/critical)
- Zero domain assumptions

## Installation

```bash
pip install django-audit-log
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_audit_log',
]
```

```bash
python manage.py migrate django_audit_log
```

## Quick Start

```python
from django_audit_log import log, log_event

# Log a model operation
log(
    action='create',
    obj=my_instance,
    actor=request.user,
    request=request,
)

# Log with changes
log(
    action='update',
    obj=customer,
    actor=request.user,
    changes={'email': {'old': 'a@b.com', 'new': 'x@y.com'}},
)

# Log a non-model event
log_event(
    action='login',
    actor=user,
    metadata={'method': 'oauth'},
)
```

## Optional Middleware

Automatically capture request context:

```python
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_audit_log.middleware.AuditContextMiddleware',
    ...
]
```

## Documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) for:
- Full API reference
- Integration patterns
- Known gotchas
- Compliance notes

## License

Proprietary
