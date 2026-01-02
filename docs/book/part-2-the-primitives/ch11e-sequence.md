# Chapter 11e: Sequence

> "Numbers that never skip, never repeat, and never lie."

---

Some numbers must be sequential. Invoice numbers. Check numbers. Order numbers. Receipt numbers. Regulators, auditors, and accountants all expect gapless sequences—numbers that increment by exactly one, with no skips and no duplicates.

The Sequence primitive provides gapless numbering with the precision that compliance requires.

## The Problem Sequences Solve

Sequential numbering fails in predictable ways:

**Gaps from rollbacks.** A database transaction allocates invoice number 1001, then fails. The next successful transaction gets 1002. Auditors ask: "Where is invoice 1001?"

**Duplicates from concurrency.** Two requests read the current number, both increment it, both save. Now you have two invoice #1001.

**Missing explanations.** When gaps exist, there's no record of why. Was it a voided invoice? A deleted order? A system bug?

**Format inconsistency.** "INV-001" vs "INV001" vs "INV-1" vs "1". Humans use inconsistent formatting; systems should not.

**No namespace isolation.** Different contexts need different sequences. Invoice numbers shouldn't share a sequence with order numbers.

## The Sequence Model

```python
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django_basemodels.models import TimestampedModel


class SequenceDefinition(TimestampedModel):
    """Definition of a gapless sequence."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    # Format template: {prefix}{number:0{padding}d}{suffix}
    prefix = models.CharField(max_length=50, blank=True)
    suffix = models.CharField(max_length=50, blank=True)
    padding = models.PositiveIntegerField(default=6)  # Number of digits

    # Starting point
    start_value = models.PositiveIntegerField(default=1)
    current_value = models.PositiveIntegerField(default=0)

    # Increment (usually 1, but some systems use larger increments)
    increment = models.PositiveIntegerField(default=1)

    # Optional: Reset period
    RESET_CHOICES = [
        ('never', 'Never'),
        ('yearly', 'Yearly'),
        ('monthly', 'Monthly'),
        ('daily', 'Daily'),
    ]
    reset_period = models.CharField(max_length=20, choices=RESET_CHOICES, default='never')
    last_reset_at = models.DateTimeField(null=True, blank=True)

    # Include date in format?
    include_year = models.BooleanField(default=False)
    include_month = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def format_number(self, value, reference_date=None):
        """Format a sequence value according to the template."""
        from django.utils import timezone

        if reference_date is None:
            reference_date = timezone.now()

        parts = []

        if self.prefix:
            parts.append(self.prefix)

        if self.include_year:
            parts.append(str(reference_date.year))

        if self.include_month:
            parts.append(f"{reference_date.month:02d}")

        # Padded number
        parts.append(f"{value:0{self.padding}d}")

        if self.suffix:
            parts.append(self.suffix)

        return ''.join(parts)

    @transaction.atomic
    def next_value(self):
        """
        Get the next value in sequence.
        Uses SELECT FOR UPDATE to prevent duplicates.
        """
        from django.utils import timezone

        # Lock this row for update
        seq = SequenceDefinition.objects.select_for_update().get(pk=self.pk)

        # Check if reset is needed
        now = timezone.now()
        needs_reset = False

        if seq.reset_period == 'yearly' and seq.last_reset_at:
            if now.year > seq.last_reset_at.year:
                needs_reset = True
        elif seq.reset_period == 'monthly' and seq.last_reset_at:
            if (now.year, now.month) > (seq.last_reset_at.year, seq.last_reset_at.month):
                needs_reset = True
        elif seq.reset_period == 'daily' and seq.last_reset_at:
            if now.date() > seq.last_reset_at.date():
                needs_reset = True

        if needs_reset:
            seq.current_value = seq.start_value - seq.increment
            seq.last_reset_at = now

        # Increment
        seq.current_value += seq.increment
        seq.save()

        return seq.current_value

    def next_formatted(self):
        """Get next value formatted according to template."""
        value = self.next_value()
        return self.format_number(value)

    def preview_next(self):
        """Preview the next value without consuming it."""
        return self.format_number(self.current_value + self.increment)

    def __str__(self):
        return f"{self.name}: {self.preview_next()}"
```

## Sequence Allocation

Track which numbers were allocated to what:

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class SequenceAllocation(models.Model):
    """Record of a sequence number allocation."""

    sequence = models.ForeignKey(
        SequenceDefinition,
        on_delete=models.PROTECT,
        related_name='allocations'
    )
    value = models.PositiveIntegerField()
    formatted_value = models.CharField(max_length=100)

    # What this was allocated to
    allocated_to_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    allocated_to_id = models.CharField(max_length=255, blank=True)
    allocated_to = GenericForeignKey('allocated_to_type', 'allocated_to_id')

    allocated_at = models.DateTimeField(auto_now_add=True)
    allocated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True
    )

    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('voided', 'Voided'),
        ('reserved', 'Reserved'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='voided_sequences'
    )
    void_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ['sequence', 'value']
        ordering = ['sequence', 'value']
        indexes = [
            models.Index(fields=['formatted_value']),
            models.Index(fields=['allocated_to_type', 'allocated_to_id']),
        ]

    def void(self, by_user, reason):
        """Void this allocation."""
        from django.utils import timezone

        if self.status == 'voided':
            raise ValidationError("Already voided")

        self.status = 'voided'
        self.voided_at = timezone.now()
        self.voided_by = by_user
        self.void_reason = reason
        self.save()

    def __str__(self):
        return f"{self.formatted_value} ({self.status})"
```

## Allocating Numbers

```python
from django.db import transaction


def allocate_sequence_number(sequence_name, target=None, allocated_by=None):
    """
    Allocate a sequence number, optionally linking it to a target object.
    Returns the formatted sequence number.
    """
    with transaction.atomic():
        seq = SequenceDefinition.objects.get(name=sequence_name)
        value = seq.next_value()
        formatted = seq.format_number(value)

        allocation_kwargs = {
            'sequence': seq,
            'value': value,
            'formatted_value': formatted,
            'allocated_by': allocated_by,
        }

        if target:
            allocation_kwargs['allocated_to_type'] = ContentType.objects.get_for_model(target)
            allocation_kwargs['allocated_to_id'] = str(target.pk)

        SequenceAllocation.objects.create(**allocation_kwargs)

        return formatted


# Usage
invoice_number = allocate_sequence_number('invoices', target=invoice, allocated_by=request.user)
# Returns: "INV-2024-000042"
```

## Gap Detection and Reporting

```python
def find_gaps(sequence_name):
    """Find gaps in a sequence."""
    seq = SequenceDefinition.objects.get(name=sequence_name)
    allocations = SequenceAllocation.objects.filter(
        sequence=seq
    ).order_by('value').values_list('value', flat=True)

    gaps = []
    expected = seq.start_value

    for actual in allocations:
        while expected < actual:
            gaps.append(expected)
            expected += seq.increment
        expected = actual + seq.increment

    return gaps


def sequence_report(sequence_name):
    """Generate a report on sequence usage."""
    seq = SequenceDefinition.objects.get(name=sequence_name)
    allocations = SequenceAllocation.objects.filter(sequence=seq)

    return {
        'sequence_name': seq.name,
        'current_value': seq.current_value,
        'total_allocated': allocations.count(),
        'active': allocations.filter(status='active').count(),
        'voided': allocations.filter(status='voided').count(),
        'gaps': find_gaps(sequence_name),
        'first_allocation': allocations.order_by('allocated_at').first(),
        'last_allocation': allocations.order_by('-allocated_at').first(),
    }
```

## Multi-Tenant Sequences

For SaaS applications where each tenant needs their own sequences:

```python
class TenantSequence(TimestampedModel):
    """Tenant-specific sequence."""

    tenant_id = models.CharField(max_length=255)
    sequence_type = models.CharField(max_length=100)  # 'invoice', 'order', etc.

    prefix = models.CharField(max_length=50, blank=True)
    current_value = models.PositiveIntegerField(default=0)
    padding = models.PositiveIntegerField(default=6)

    class Meta:
        unique_together = ['tenant_id', 'sequence_type']

    @classmethod
    @transaction.atomic
    def next_for_tenant(cls, tenant_id, sequence_type):
        """Get next number for a tenant's sequence."""
        seq, created = cls.objects.select_for_update().get_or_create(
            tenant_id=tenant_id,
            sequence_type=sequence_type,
            defaults={'current_value': 0}
        )

        seq.current_value += 1
        seq.save()

        if seq.prefix:
            return f"{seq.prefix}{seq.current_value:0{seq.padding}d}"
        return f"{seq.current_value:0{seq.padding}d}"
```

## Model Integration

Add sequence numbers to models automatically:

```python
class SequencedModelMixin(models.Model):
    """Mixin for models that need a sequence number."""

    sequence_number = models.CharField(max_length=100, unique=True, blank=True)

    SEQUENCE_NAME = None  # Override in subclass

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.sequence_number and self.SEQUENCE_NAME:
            self.sequence_number = allocate_sequence_number(
                self.SEQUENCE_NAME,
                target=self
            )
        super().save(*args, **kwargs)


# Usage
class Invoice(SequencedModelMixin, SoftDeleteModel):
    SEQUENCE_NAME = 'invoices'

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    # ... other fields ...
```

## Why This Matters Later

The Sequence primitive connects to:

- **Ledger** (Chapter 8): Transaction numbers, check numbers.
- **Agreements** (Chapter 6): Contract numbers.
- **Audit** (Chapter 11): Sequence allocations are logged.
- **Documents** (Chapter 11c): Document reference numbers.

Sequential numbering seems simple until you need to:
- Prove to an auditor that no invoice numbers are missing
- Explain why invoice #1047 was voided
- Reset sequences at year-end while preserving history
- Support multiple tenants with isolated sequences

The Sequence primitive handles the complexity so your application doesn't have to reinvent it.

---

## References

- IRS Publication 583: Record retention requirements for sequential numbering
- Sarbanes-Oxley Act Section 802: Document retention and integrity
- Generally Accepted Accounting Principles (GAAP): Invoice numbering standards

---

*Status: Draft*
