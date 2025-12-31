"""Test models for django-rbac tests."""

from django.db import models
from django.contrib.auth.models import AbstractUser

from django_rbac.mixins import RBACUserMixin


class User(RBACUserMixin, AbstractUser):
    """Test user model with RBAC mixin."""

    class Meta:
        app_label = 'tests'
