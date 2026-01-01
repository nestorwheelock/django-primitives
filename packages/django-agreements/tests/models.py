"""Test models for django-agreements tests."""

from django.db import models


class Organization(models.Model):
    """Test organization model (party in agreements)."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name


class Customer(models.Model):
    """Test customer model (party in agreements)."""

    name = models.CharField(max_length=100)
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='customers',
    )

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.name


class ServiceContract(models.Model):
    """Test service contract model (scope reference)."""

    title = models.CharField(max_length=200)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='contracts',
    )

    class Meta:
        app_label = 'tests'

    def __str__(self):
        return self.title
