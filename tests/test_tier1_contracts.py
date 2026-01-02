# tests/test_tier1_contracts.py
"""
Contract tests for Tier 1 packages.

These tests catch structural/architectural violations that may not be caught
by unit tests but will cause runtime failures or violate ecosystem conventions.

Catches:
- django-parties: duplicate field names between abstract Party and subclasses
- django-rbac: custom manager bypassing soft-delete
- django-decisioning: missing AppConfig, migrations, non-UUID PKs
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest
from django.db import models


# -----------------------------
# Helpers
# -----------------------------

def module_path(module_name: str) -> Path:
    spec = importlib.util.find_spec(module_name)
    assert spec and spec.origin, f"Cannot find module {module_name}"
    return Path(spec.origin).resolve()


def package_dir(module_name: str) -> Path:
    p = module_path(module_name)
    return p.parent if p.name != "__init__.py" else p.parent


def has_migrations(pkg: str) -> Tuple[bool, str]:
    d = package_dir(pkg)
    mig = d / "migrations"
    if not mig.exists() or not mig.is_dir():
        return False, f"{pkg}: missing migrations/ directory at {mig}"
    py_files = [p for p in mig.glob("*.py") if p.name != "__init__.py"]
    if not py_files:
        return False, f"{pkg}: migrations/ exists but has no migration modules (only __init__.py?)"
    return True, ""


@dataclass
class ClassInfo:
    name: str
    bases: Set[str]
    fields: Set[str]


def _base_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _looks_like_django_field_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr.endswith("Field")
    if isinstance(func, ast.Name):
        return func.id.endswith("Field")
    return False


def parse_models_file(path: Path) -> Dict[str, ClassInfo]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    classes: Dict[str, ClassInfo] = {}

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = set()
        for b in node.bases:
            bn = _base_name(b)
            if bn:
                bases.add(bn)

        fields = set()
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                attr = stmt.targets[0].id
                if _looks_like_django_field_call(stmt.value):
                    fields.add(attr)

        classes[node.name] = ClassInfo(name=node.name, bases=bases, fields=fields)

    return classes


# -----------------------------
# 1) django-parties: duplicate fields
# -----------------------------

def test_parties_no_duplicate_field_names_between_abstract_party_and_subclasses():
    """
    Catches the issue where Party (abstract) defines fields like email/phone/address,
    and Person (or other subclasses) defines fields with the same names again.

    Django does not "override" abstract base fields. It raises FieldError.
    We catch it statically using AST so the test fails even if Django can't import.
    """
    models_py = module_path("django_parties.models")
    classes = parse_models_file(models_py)

    assert "Party" in classes, f"Expected Party class in {models_py}"
    party = classes["Party"]

    assert party.fields, "Party has no detected fields; test may be misconfigured."

    offenders: List[str] = []
    for cname, cinfo in classes.items():
        if cname == "Party":
            continue
        if "Party" in cinfo.bases:
            dupes = sorted(party.fields & cinfo.fields)
            if dupes:
                offenders.append(f"{cname} duplicates fields from Party: {dupes}")

    assert not offenders, (
        "Duplicate field names detected between Party and subclasses. "
        "Django will raise FieldError at import time.\n"
        + "\n".join(offenders)
    )


# -----------------------------
# 2) django-rbac: soft-delete bypass via custom manager
# -----------------------------

@pytest.mark.django_db
def test_rbac_userrole_manager_respects_soft_delete():
    """
    Catches the bug where a model inherits BaseModel (soft delete),
    but overrides `objects = SomeQuerySet.as_manager()` which bypasses
    soft-delete filtering.

    Expected:
      - soft-deleted rows should NOT appear in `.objects.all()`
      - they SHOULD appear in `.all_objects.all()` (if BaseModel provides it)
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django_rbac.models import Role, UserRole

    User = get_user_model()

    # Create required related objects
    user = User.objects.create_user(
        username='contract_test_user',
        password='testpass123'
    )
    group = Group.objects.create(name='Contract Test Group')
    role = Role.objects.create(
        name='Contract Test Role',
        slug='contract-test-role',
        hierarchy_level=20,
        group=group,
    )

    # Create UserRole
    obj = UserRole.objects.create(user=user, role=role)
    pk = obj.pk

    # Soft delete
    obj.delete()

    # If the manager is correct, it should not show up here
    assert not UserRole.objects.filter(pk=pk).exists(), (
        "UserRole.objects is returning soft-deleted rows. "
        "This usually means `objects = <custom manager>` replaced BaseModel's SoftDeleteManager."
    )

    # If BaseModel provides all_objects, ensure the row is still visible
    if hasattr(UserRole, "all_objects"):
        assert UserRole.all_objects.filter(pk=pk).exists(), (
            "Soft-deleted row is missing from all_objects. "
            "Either delete() is hard-deleting or all_objects is misconfigured."
        )


def test_rbac_has_migrations():
    """All packages with models must ship migrations."""
    ok, msg = has_migrations("django_rbac")
    assert ok, (
        f"{msg}. "
        "Packages must ship migrations - downstream projects shouldn't generate schema."
    )


@pytest.mark.django_db
def test_rbac_role_manager_respects_soft_delete():
    """Same check for Role model."""
    from django.contrib.auth.models import Group
    from django_rbac.models import Role

    group = Group.objects.create(name='Role Soft Delete Test')
    obj = Role.objects.create(
        name='Soft Delete Test Role',
        slug='soft-delete-test-role',
        hierarchy_level=20,
        group=group,
    )
    pk = obj.pk

    obj.delete()

    assert not Role.objects.filter(pk=pk).exists(), (
        "Role.objects is returning soft-deleted rows."
    )

    if hasattr(Role, "all_objects"):
        assert Role.all_objects.filter(pk=pk).exists(), (
            "Soft-deleted Role missing from all_objects."
        )


# -----------------------------
# 3) django-decisioning: app config / migrations / PK policy
# -----------------------------

def test_decisioning_has_app_config():
    """All packages must have apps.py for explicit configuration."""
    pkg_dir = package_dir("django_decisioning")
    apps_py = pkg_dir / "apps.py"
    assert apps_py.exists(), (
        f"django-decisioning missing apps.py at {apps_py}. "
        "All packages need AppConfig for explicit default_auto_field."
    )


def test_decisioning_has_migrations():
    """All packages with models must ship migrations."""
    ok, msg = has_migrations("django_decisioning")
    assert ok, (
        f"{msg}. "
        "Packages must ship migrations - downstream projects shouldn't generate schema."
    )


def test_decisioning_models_pk_policy_is_documented():
    """
    django-decisioning uses integer PKs (system package exception).

    This test verifies the exception is documented via allow-plain-model marker.
    Models without the marker using non-UUID PKs would fail.
    """
    from django_decisioning import models as decisioning_models

    models_path = module_path("django_decisioning.models")
    source = models_path.read_text()

    model_classes = [
        getattr(decisioning_models, name)
        for name in dir(decisioning_models)
        if isinstance(getattr(decisioning_models, name), type)
        and issubclass(getattr(decisioning_models, name), models.Model)
        and getattr(decisioning_models, name)._meta.abstract is False
        and getattr(decisioning_models, name).__module__ == decisioning_models.__name__
    ]

    for m in model_classes:
        pk = m._meta.pk
        if not isinstance(pk, models.UUIDField):
            # Check for allow-plain-model marker before the class definition
            class_pattern = f"class {m.__name__}"
            class_pos = source.find(class_pattern)
            if class_pos == -1:
                pytest.fail(f"Could not find {m.__name__} in source")

            # Look for marker in the 200 chars before class definition
            preceding = source[max(0, class_pos - 200):class_pos]
            if "allow-plain-model" not in preceding:
                pytest.fail(
                    f"{m.__name__} uses {pk.__class__.__name__} PK but lacks "
                    "'# PRIMITIVES: allow-plain-model' marker. "
                    "Either use BaseModel (UUID PK) or document the exception."
                )


# -----------------------------
# 4) django-parties: Party subclass soft-delete
# -----------------------------

@pytest.mark.django_db
def test_parties_person_manager_respects_soft_delete():
    """Verify Person soft-delete works correctly."""
    from django_parties.models import Person

    obj = Person.objects.create(first_name='Test', last_name='User')
    pk = obj.pk

    obj.delete()

    assert not Person.objects.filter(pk=pk).exists(), (
        "Person.objects is returning soft-deleted rows."
    )

    if hasattr(Person, "all_objects"):
        assert Person.all_objects.filter(pk=pk).exists(), (
            "Soft-deleted Person missing from all_objects."
        )


@pytest.mark.django_db
def test_parties_organization_manager_respects_soft_delete():
    """Verify Organization soft-delete works correctly."""
    from django_parties.models import Organization

    obj = Organization.objects.create(name='Test Org')
    pk = obj.pk

    obj.delete()

    assert not Organization.objects.filter(pk=pk).exists(), (
        "Organization.objects is returning soft-deleted rows."
    )
