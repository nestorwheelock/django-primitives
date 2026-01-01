"""Concrete test models for testing abstract mixins and querysets."""
from django.db import models
from django_decisioning.mixins import TimeSemanticsMixin, EffectiveDatedMixin
from django_decisioning.querysets import EventAsOfQuerySet, EffectiveDatedQuerySet


class TimeSemanticTestModel(TimeSemanticsMixin):
    """Concrete model for testing TimeSemanticsMixin."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'


class EventTestModel(TimeSemanticsMixin):
    """Concrete model for testing EventAsOfQuerySet."""
    name = models.CharField(max_length=100)

    objects = EventAsOfQuerySet.as_manager()

    class Meta:
        app_label = 'tests'


class EffectiveDatedTestModel(EffectiveDatedMixin):
    """Concrete model for testing EffectiveDatedMixin and EffectiveDatedQuerySet."""
    name = models.CharField(max_length=100)

    objects = EffectiveDatedQuerySet.as_manager()

    class Meta:
        app_label = 'tests'
