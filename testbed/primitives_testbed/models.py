"""Models for primitives_testbed.

This module defines only the custom User model that integrates with django-rbac.
All other models come from the django-primitives packages.
"""

from django.contrib.auth.models import AbstractUser

from django_rbac.mixins import RBACUserMixin


class User(RBACUserMixin, AbstractUser):
    """Custom user model with RBAC integration.

    Inherits from:
    - RBACUserMixin: Provides hierarchy_level, can_manage(), get_manageable_roles()
    - AbstractUser: Provides username, email, password, etc.
    """

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        swappable = "AUTH_USER_MODEL"
