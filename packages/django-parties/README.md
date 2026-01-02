# django-parties

Party Pattern implementation for Django.

This package provides core models for representing real-world entities (people, organizations, and groups) and the relationships between them, plus normalized contact information (addresses, phones, emails, URLs).

## Install

```bash
pip install django-parties
```

## Configure

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_parties",
]
```

Run migrations:

```bash
python manage.py migrate
```

## Quick start

```python
from django_parties.models import Person
from django_parties.selectors import get_person_by_id

person = Person.objects.create(first_name="Jane", last_name="Doe")
same_person = get_person_by_id(person.id)
```

## Design notes

* `Person` is a real-world identity, separate from authentication (`User`).
* Contact info is normalized via `Address`, `Phone`, `Email`, and `PartyURL`.
* Relationships between parties are represented with `PartyRelationship`.

## License

MIT
