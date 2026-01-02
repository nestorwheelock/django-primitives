# Chapter 12: Worklog

> "What did you do, and how long did it take?"

---

Every business needs to track work. Billable hours. Project time. Task completion. Service delivery. The specifics vary—lawyers bill in six-minute increments, contractors bill by the day, consultants bill by the project—but the underlying question is always the same: what work was done, by whom, when, and for how long?

The Worklog primitive captures work entries with the precision that billing, payroll, and project management require.

## The Problem Worklogs Solve

Work tracking fails in predictable ways:

**Imprecise time.** "I worked on Project X today" isn't billable. "I worked on Project X from 9:00 AM to 11:47 AM" is. The difference is whether your invoices survive scrutiny.

**Missing context.** Time without description is useless. "3 hours" tells the client nothing. "3 hours: implemented authentication flow, fixed login redirect bug, wrote unit tests" justifies the invoice.

**No linkage.** Work happens in the context of something—a project, a ticket, a client engagement, a service call. Standalone time entries can't be reconciled against contracts or budgets.

**Mutable history.** Timesheets that can be silently edited after the fact create audit failures. Did the employee really work those hours, or did they adjust the timesheet when they realized they were short?

**Approval gaps.** Time entered but never approved exists in limbo. Is it billable? Is it paid? Nobody knows until someone reviews it.

## The Worklog Model

```python
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django_basemodels.models import SoftDeleteModel
from decimal import Decimal


class WorklogEntry(SoftDeleteModel):
    """A single work entry with time tracking."""

    # Who did the work
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='worklog_entries'
    )

    # What they worked on (generic - can be project, ticket, client, etc.)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    # When the work happened (business time)
    work_date = models.DateField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Duration (can be entered directly or calculated)
    duration_minutes = models.PositiveIntegerField()

    # What was done
    description = models.TextField()
    work_type = models.CharField(max_length=100, blank=True)  # e.g., "development", "meeting", "review"

    # Billing information
    is_billable = models.BooleanField(default=True)
    billing_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    billing_rate_currency = models.CharField(max_length=3, default='USD')

    # Approval workflow
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('billed', 'Billed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='worklog_submissions'
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='worklog_approvals'
    )

    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-work_date', '-started_at']
        indexes = [
            models.Index(fields=['worker', 'work_date']),
            models.Index(fields=['status', 'work_date']),
            models.Index(fields=['target_content_type', 'target_id']),
        ]

    def clean(self):
        super().clean()

        # Validate time range if both are provided
        if self.started_at and self.ended_at:
            if self.ended_at <= self.started_at:
                raise ValidationError("End time must be after start time")

            # Calculate duration from time range
            delta = self.ended_at - self.started_at
            calculated_minutes = int(delta.total_seconds() / 60)

            # If duration_minutes wasn't set, calculate it
            if not self.duration_minutes:
                self.duration_minutes = calculated_minutes

    @property
    def duration_hours(self):
        """Duration in decimal hours."""
        return Decimal(self.duration_minutes) / Decimal(60)

    @property
    def billable_amount(self):
        """Calculate billable amount if rate is set."""
        if self.billing_rate and self.is_billable:
            return self.duration_hours * self.billing_rate
        return Decimal('0.00')

    def submit(self, by_user=None):
        """Submit entry for approval."""
        if self.status != 'draft':
            raise ValidationError("Only draft entries can be submitted")

        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.submitted_by = by_user or self.worker
        self.save()

    def approve(self, by_user):
        """Approve a submitted entry."""
        if self.status != 'submitted':
            raise ValidationError("Only submitted entries can be approved")

        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = by_user
        self.save()

    def reject(self, by_user, reason):
        """Reject a submitted entry."""
        if self.status != 'submitted':
            raise ValidationError("Only submitted entries can be rejected")

        self.status = 'rejected'
        self.rejection_reason = reason
        self.approved_by = by_user  # Track who rejected
        self.approved_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.worker} - {self.work_date} - {self.duration_minutes}min"
```

## Worklog QuerySet

```python
from django.db import models
from django.utils import timezone
from datetime import timedelta


class WorklogQuerySet(models.QuerySet):
    """QuerySet with worklog-specific filters."""

    def for_worker(self, user):
        """Entries for a specific worker."""
        return self.filter(worker=user)

    def for_target(self, target):
        """Entries for a specific target object."""
        ct = ContentType.objects.get_for_model(target)
        return self.filter(
            target_content_type=ct,
            target_id=str(target.pk)
        )

    def for_date_range(self, start_date, end_date):
        """Entries within a date range."""
        return self.filter(
            work_date__gte=start_date,
            work_date__lte=end_date
        )

    def this_week(self):
        """Entries from current week."""
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return self.for_date_range(start_of_week, end_of_week)

    def this_month(self):
        """Entries from current month."""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return self.for_date_range(start_of_month, end_of_month)

    def billable(self):
        """Only billable entries."""
        return self.filter(is_billable=True)

    def non_billable(self):
        """Only non-billable entries."""
        return self.filter(is_billable=False)

    def pending_approval(self):
        """Entries awaiting approval."""
        return self.filter(status='submitted')

    def approved(self):
        """Approved entries."""
        return self.filter(status='approved')

    def unbilled(self):
        """Approved but not yet billed."""
        return self.filter(status='approved', is_billable=True)

    def total_minutes(self):
        """Sum of duration_minutes."""
        result = self.aggregate(total=models.Sum('duration_minutes'))
        return result['total'] or 0

    def total_hours(self):
        """Sum of hours as decimal."""
        return Decimal(self.total_minutes()) / Decimal(60)

    def total_billable_amount(self):
        """Sum of billable amounts."""
        total = Decimal('0.00')
        for entry in self.billable().filter(billing_rate__isnull=False):
            total += entry.billable_amount
        return total
```

## Timesheet Aggregation

Individual entries are useful, but timesheets aggregate them:

```python
class Timesheet(SoftDeleteModel):
    """Weekly or monthly timesheet aggregating work entries."""

    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='timesheets'
    )

    period_start = models.DateField()
    period_end = models.DateField()

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='approved_timesheets'
    )

    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['worker', 'period_start', 'period_end']
        ordering = ['-period_start']

    @property
    def entries(self):
        """All worklog entries in this timesheet's period."""
        return WorklogEntry.objects.filter(
            worker=self.worker,
            work_date__gte=self.period_start,
            work_date__lte=self.period_end
        )

    @property
    def total_hours(self):
        """Total hours in this timesheet."""
        return self.entries.total_hours()

    @property
    def billable_hours(self):
        """Billable hours in this timesheet."""
        return self.entries.billable().total_hours()

    def submit(self):
        """Submit timesheet for approval."""
        if self.status != 'open':
            raise ValidationError("Only open timesheets can be submitted")

        # Submit all draft entries in this period
        for entry in self.entries.filter(status='draft'):
            entry.submit()

        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.save()

    def approve(self, by_user):
        """Approve timesheet and all its entries."""
        if self.status != 'submitted':
            raise ValidationError("Only submitted timesheets can be approved")

        # Approve all submitted entries
        for entry in self.entries.filter(status='submitted'):
            entry.approve(by_user)

        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = by_user
        self.save()
```

## Billing Integration

Approved worklog entries feed into the billing system:

```python
from django.db import transaction


def generate_invoice_from_worklog(client, start_date, end_date):
    """Generate invoice from approved worklog entries."""
    from django_ledger.models import Invoice, InvoiceLineItem

    entries = WorklogEntry.objects.filter(
        target=client,  # Assumes client is the target
        status='approved',
        is_billable=True,
        work_date__gte=start_date,
        work_date__lte=end_date
    )

    if not entries.exists():
        return None

    with transaction.atomic():
        invoice = Invoice.objects.create(
            customer=client,
            invoice_date=timezone.now().date()
        )

        for entry in entries:
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"{entry.work_date}: {entry.description}",
                quantity=entry.duration_hours,
                unit_price=entry.billing_rate,
                amount=entry.billable_amount
            )

            # Mark as billed
            entry.status = 'billed'
            entry.save()

        return invoice
```

## Timer Support

For real-time time tracking:

```python
class WorklogTimer(models.Model):
    """Active timer for real-time tracking."""

    worker = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_timer'
    )

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT
    )
    target_id = models.CharField(max_length=255)
    target = GenericForeignKey('target_content_type', 'target_id')

    started_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    work_type = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Active Timer"

    @property
    def elapsed_minutes(self):
        """Minutes elapsed since timer started."""
        delta = timezone.now() - self.started_at
        return int(delta.total_seconds() / 60)

    def stop(self):
        """Stop timer and create worklog entry."""
        entry = WorklogEntry.objects.create(
            worker=self.worker,
            target_content_type=self.target_content_type,
            target_id=self.target_id,
            work_date=self.started_at.date(),
            started_at=self.started_at,
            ended_at=timezone.now(),
            duration_minutes=self.elapsed_minutes,
            description=self.description,
            work_type=self.work_type
        )
        self.delete()
        return entry
```

## Rounding Rules

Different industries have different rounding conventions:

```python
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP


class RoundingRule:
    """Billing time rounding strategies."""

    @staticmethod
    def no_rounding(minutes):
        """Bill exact minutes."""
        return minutes

    @staticmethod
    def round_to_quarter_hour(minutes):
        """Round up to nearest 15 minutes (common for consultants)."""
        return ((minutes + 14) // 15) * 15

    @staticmethod
    def round_to_sixth_hour(minutes):
        """Round up to nearest 6 minutes (legal billing standard)."""
        return ((minutes + 5) // 6) * 6

    @staticmethod
    def round_to_half_hour(minutes):
        """Round up to nearest 30 minutes."""
        return ((minutes + 29) // 30) * 30

    @staticmethod
    def minimum_increment(minutes, minimum=15):
        """Apply minimum billing increment."""
        if minutes == 0:
            return 0
        return max(minutes, minimum)


# Usage
raw_minutes = 37
billable_minutes = RoundingRule.round_to_quarter_hour(raw_minutes)  # Returns 45
```

## Overtime Calculation

```python
def calculate_overtime(worker, week_start, regular_hours=40):
    """Calculate regular and overtime hours for a week."""
    week_end = week_start + timedelta(days=6)

    entries = WorklogEntry.objects.filter(
        worker=worker,
        work_date__gte=week_start,
        work_date__lte=week_end,
        status__in=['approved', 'billed']
    )

    total_hours = entries.total_hours()

    regular = min(total_hours, Decimal(regular_hours))
    overtime = max(total_hours - Decimal(regular_hours), Decimal(0))

    return {
        'total_hours': total_hours,
        'regular_hours': regular,
        'overtime_hours': overtime,
        'entries': entries
    }
```

## Why This Matters Later

The Worklog primitive connects to:

- **Identity** (Chapter 4): Workers are parties. Clients are parties.
- **Agreements** (Chapter 6): Billing rates come from service agreements.
- **Ledger** (Chapter 8): Billable entries become invoice line items.
- **Workflow** (Chapter 9): Approval is a state machine.
- **Audit** (Chapter 11): Every entry, approval, and rejection is logged.

Time tracking seems simple until you need to:
- Prove to a client that 47.5 hours of work was performed
- Calculate overtime across holiday boundaries
- Reconcile timesheets against project budgets
- Generate invoices that survive audit

The Worklog primitive handles the complexity so your application doesn't have to reinvent it.

---

## How to Rebuild This Primitive

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-worklog | `docs/prompts/django-worklog.md` | ~35 tests |

### Using the Prompt

```bash
cat docs/prompts/django-worklog.md | claude

# Request: "Implement WorklogEntry with GenericFK target,
# duration tracking (minutes not hours), and approval workflow.
# Then add Timesheet aggregation."
```

### Key Constraints

- **Duration in minutes**: Integer field, never float hours
- **Billing rate as Decimal**: Never FloatField for money
- **Approval workflow**: draft → submitted → approved → billed
- **GenericFK target**: Time entries attach to any work item

If Claude stores duration as hours or uses Float for rates, that's a constraint violation.

---

## References

- Fair Labor Standards Act (FLSA) timekeeping requirements
- American Bar Association Model Rules for legal billing
- Project Management Institute time tracking standards
- IRS Publication 15-B on employee time records

---

*Status: Draft*
