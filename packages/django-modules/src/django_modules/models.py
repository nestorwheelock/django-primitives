"""Models for django-modules."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_basemodels.models import BaseModel
from django_modules.conf import get_org_model_string


class Module(BaseModel):
    """A module/feature that can be enabled or disabled.

    Modules are system-wide definitions. Per-org enablement is
    controlled via OrgModuleState.
    """

    key = models.CharField(
        _("key"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_("Unique identifier for this module (e.g., 'pharmacy', 'billing')"),
    )
    name = models.CharField(
        _("name"),
        max_length=200,
        help_text=_("Human-readable name"),
    )
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Description of what this module provides"),
    )
    active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Global default: if True, module is enabled unless org overrides"),
    )

    class Meta:
        verbose_name = _("module")
        verbose_name_plural = _("modules")
        ordering = ["key"]

    def __str__(self):
        status = "active" if self.active else "inactive"
        return f"{self.name} ({self.key}) - {status}"


class OrgModuleState(BaseModel):
    """Per-organization override for module enablement.

    If an OrgModuleState exists for (org, module), it overrides the
    module's global `active` setting. If no OrgModuleState exists,
    the module's global `active` value is used.
    """

    org = models.ForeignKey(
        get_org_model_string(),
        on_delete=models.CASCADE,
        related_name="module_states",
        verbose_name=_("organization"),
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="org_states",
        verbose_name=_("module"),
    )
    enabled = models.BooleanField(
        _("enabled"),
        help_text=_("Override: True to enable, False to disable for this org"),
    )

    class Meta:
        verbose_name = _("organization module state")
        verbose_name_plural = _("organization module states")
        constraints = [
            models.UniqueConstraint(
                fields=["org", "module"],
                name="unique_org_module_state",
            ),
        ]

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"{self.module.key} → {status} for org {self.org_id}"
