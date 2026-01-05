# Dive Plan Extension Specification

**Status**: APPROVED
**Created**: 2025-01-05
**Scope**: Extend existing models to support advance planning and briefing communication

---

## Executive Summary

Extend `ExcursionTypeDive` with briefing content fields and publish lifecycle, add plan snapshot capability to `Dive`. This enables:

1. **Advance Planning**: Define dive details (gas, skills, hazards, route) before excursions
2. **Briefing Communication**: Publish and send briefings to divers/students
3. **Snapshot Freeze**: Lock what was communicated so templates can evolve independently
4. **Audit Trail**: Track who published/locked plans and when

**Approach**: Extend existing models, no new entities. Maintains existing cascade:
`ExcursionType → ExcursionTypeDive → Excursion → Dive`

---

## Policy Decisions (Locked)

1. **Lock requires template published**: YES (unless `force=True` by admin)
2. **Existing templates on migration**: Default to `published` (immediately usable)
3. **Lock idempotency**: Calling `lock_dive_plan()` twice is safe (no-op if already locked)
4. **Re-lock capability**: Explicit `resnapshot_dive_plan()` with reason, audited
5. **Planned fields after lock**: Editable, but triggers `plan_snapshot_outdated` flag

---

## Model Changes

### 1. ExcursionTypeDive Extensions

Add briefing content fields and publish lifecycle to the existing template model.

#### New Fields

```python
class ExcursionTypeDive(BaseModel):
    # ... existing fields ...

    # ─────────────────────────────────────────────────────────────
    # Briefing Content (new)
    # ─────────────────────────────────────────────────────────────

    class GasType(models.TextChoices):
        AIR = "air", "Air"
        EAN32 = "ean32", "EAN32"
        EAN36 = "ean36", "EAN36"
        TRIMIX = "trimix", "Trimix"  # future-proofing

    gas = models.CharField(
        max_length=20,
        choices=GasType.choices,
        blank=True,
        default="",
        help_text="Gas mix for this dive",
    )

    equipment_requirements = models.JSONField(
        default=dict,
        blank=True,
        help_text="Equipment requirements by category",
    )
    # Schema: {"required": ["torch"], "recommended": ["SMB"], "rental_available": ["dive computer"]}

    skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Skills to practice (for training dives)",
    )
    # Example: ["mask clearing", "regulator recovery", "CESA"]

    route = models.TextField(
        blank=True,
        default="",
        help_text="Dive profile, route description, or navigation plan",
    )

    hazards = models.TextField(
        blank=True,
        default="",
        help_text="Known hazards and safety considerations",
    )

    briefing_text = models.TextField(
        blank=True,
        default="",
        help_text="Full briefing content for communication to divers",
    )

    # ─────────────────────────────────────────────────────────────
    # Publish Lifecycle (new)
    # ─────────────────────────────────────────────────────────────

    class PlanStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    status = models.CharField(
        max_length=10,
        choices=PlanStatus.choices,
        default=PlanStatus.DRAFT,
    )

    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",  # No reverse relation needed
    )

    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",  # No reverse relation needed
    )
```

#### Invariants

- Only `published` templates can be used for new excursions (soft enforcement via service layer)
- `retired` templates cannot be re-published (must create new version)
- Transitions: `draft → published → retired` (no backwards)

---

### 2. Dive Extensions

Add plan snapshot capability to freeze communicated briefings.

#### New Fields

```python
class Dive(BaseModel):
    # ... existing fields ...

    # ─────────────────────────────────────────────────────────────
    # Plan Snapshot (new)
    # ─────────────────────────────────────────────────────────────

    plan_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Frozen copy of plan at time of briefing lock",
    )
    # Schema defined in "Plan Snapshot Schema" section below

    plan_locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the plan was locked (briefing sent)",
    )

    plan_locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # ─────────────────────────────────────────────────────────────
    # Provenance (new) - tracks where snapshot came from
    # ─────────────────────────────────────────────────────────────

    plan_template_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of ExcursionTypeDive template used for snapshot",
    )

    plan_template_published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the source template was published",
    )

    # ─────────────────────────────────────────────────────────────
    # Snapshot Outdated Flag (new)
    # ─────────────────────────────────────────────────────────────

    plan_snapshot_outdated = models.BooleanField(
        default=False,
        help_text="True if planned fields changed after lock (needs resend)",
    )
```

#### Invariants

- Once `plan_locked_at` is set, `plan_snapshot` is immutable (enforced in service layer)
- Locked dives use `plan_snapshot` as source of truth, not live template
- Re-locking (resnapshot) requires explicit privileged action with audit

---

## Services

### 1. publish_dive_template()

Publish a dive template, making it available for use.

```python
@transaction.atomic
def publish_dive_template(
    *,
    actor,
    dive_template: ExcursionTypeDive,
) -> ExcursionTypeDive:
    """Publish a dive template for use in excursions.

    Args:
        actor: Staff user publishing the template
        dive_template: ExcursionTypeDive to publish

    Returns:
        Updated ExcursionTypeDive

    Raises:
        ValueError: If template is not in draft status
    """
```

**Behavior**:
- Validates template is in `draft` status
- Sets `status = published`, `published_at = now`, `published_by = actor`
- Emits `DIVE_TEMPLATE_PUBLISHED` audit event

### 2. retire_dive_template()

Retire a published template (no longer available for new excursions).

```python
@transaction.atomic
def retire_dive_template(
    *,
    actor,
    dive_template: ExcursionTypeDive,
) -> ExcursionTypeDive:
    """Retire a dive template.

    Args:
        actor: Staff user retiring the template
        dive_template: ExcursionTypeDive to retire

    Returns:
        Updated ExcursionTypeDive

    Raises:
        ValueError: If template is not in published status
    """
```

**Behavior**:
- Validates template is in `published` status
- Sets `status = retired`, `retired_at = now`, `retired_by = actor`
- Does NOT affect existing scheduled dives (their snapshots are independent)
- Emits `DIVE_TEMPLATE_RETIRED` audit event

### 3. lock_dive_plan()

Lock a dive's plan by snapshotting from the template. **Idempotent** - safe to call multiple times.

```python
@transaction.atomic
def lock_dive_plan(
    *,
    actor,
    dive: Dive,
    force: bool = False,
) -> Dive:
    """Lock the dive plan by creating a snapshot.

    Snapshots the current state of the associated ExcursionTypeDive
    template. After locking, template changes don't affect this dive.

    This operation is idempotent - if already locked and force=False,
    returns the dive unchanged.

    Args:
        actor: Staff user locking the plan
        dive: Dive to lock
        force: If True, re-lock even if already locked (for resnapshot)

    Returns:
        Updated Dive with plan_snapshot populated

    Raises:
        ValidationError: If template is not published (unless force=True)
        ValueError: If no template available to snapshot
    """
```

**Behavior**:
- If already locked and `force=False`: return dive unchanged (idempotent)
- Finds matching `ExcursionTypeDive` via sequence matching
- Validates template is `published` (unless `force=True`)
- Builds snapshot JSON using `build_plan_snapshot()` helper
- Sets `plan_snapshot`, `plan_locked_at`, `plan_locked_by`
- Sets provenance: `plan_template_id`, `plan_template_published_at`
- Clears `plan_snapshot_outdated = False`
- Emits `DIVE_PLAN_LOCKED` audit event

### 3a. build_plan_snapshot() (helper)

```python
def build_plan_snapshot(*, template: ExcursionTypeDive, dive: Dive) -> dict:
    """Build the snapshot dictionary from template and dive."""
    return {
        "version": 1,
        "template": {
            "id": str(template.id),
            "name": template.name,
            "status": template.status,
            "published_at": template.published_at.isoformat() if template.published_at else None,
        },
        "planning": {
            "sequence": template.sequence,
            "planned_depth_meters": template.planned_depth_meters,
            "planned_duration_minutes": template.planned_duration_minutes,
            "offset_minutes": template.offset_minutes,
        },
        "briefing": {
            "gas": template.gas,
            "equipment_requirements": template.equipment_requirements,
            "skills": template.skills,
            "route": template.route,
            "hazards": template.hazards,
            "briefing_text": template.briefing_text,
        },
        "certification": {
            "min_level_id": str(template.min_certification_level_id) if template.min_certification_level_id else None,
            "min_level_name": template.min_certification_level.name if template.min_certification_level else None,
        },
        "metadata": {
            "locked_at": timezone.now().isoformat(),
        },
    }
```

### 4. resnapshot_dive_plan()

Re-lock with updated template (privileged, audited, rare).

```python
@transaction.atomic
def resnapshot_dive_plan(
    *,
    actor,
    dive: Dive,
    reason: str,
) -> Dive:
    """Re-snapshot an already locked dive plan.

    This is a privileged operation for correcting briefings before
    the dive occurs. Requires explicit reason for audit trail.

    Args:
        actor: Staff user re-snapshotting
        dive: Already-locked Dive to update
        reason: Explanation for the resnapshot (required)

    Returns:
        Updated Dive with new plan_snapshot

    Raises:
        ValueError: If dive is not currently locked
        ValueError: If reason is empty
    """
```

**Behavior**:
- Validates dive IS already locked
- Validates reason is provided
- Overwrites `plan_snapshot` with fresh snapshot from template
- Updates `plan_locked_at`, `plan_locked_by`
- Emits `DIVE_PLAN_RESNAPSHOTTED` audit event with old/new diff and reason

### 5. lock_excursion_plans()

Convenience: Lock all dives in an excursion at once.

```python
@transaction.atomic
def lock_excursion_plans(
    *,
    actor,
    excursion: Excursion,
) -> list[Dive]:
    """Lock plans for all dives in an excursion.

    Typically called when sending briefing to customers.

    Args:
        actor: Staff user locking plans
        excursion: Excursion whose dives to lock

    Returns:
        List of locked Dive instances
    """
```

**Behavior**:
- Iterates `excursion.dives.filter(plan_locked_at__isnull=True)`
- Calls `lock_dive_plan()` for each
- Returns list of locked dives
- Emits `EXCURSION_PLANS_LOCKED` audit event

---

## Audit Events

Add to `Actions` class:

```python
# Dive Template Lifecycle
DIVE_TEMPLATE_PUBLISHED = "dive_template_published"
DIVE_TEMPLATE_RETIRED = "dive_template_retired"

# Dive Plan Locking
DIVE_PLAN_LOCKED = "dive_plan_locked"
DIVE_PLAN_RESNAPSHOTTED = "dive_plan_resnapshotted"
EXCURSION_PLANS_LOCKED = "excursion_plans_locked"
```

---

## Plan Snapshot Schema

The `plan_snapshot` JSON field follows this schema:

```json
{
    "version": 1,
    "template_id": "uuid-string",
    "template_name": "First Tank - Shallow Reef",
    "sequence": 1,

    "planning": {
        "planned_depth_meters": 18,
        "planned_duration_minutes": 45,
        "offset_minutes": 30
    },

    "briefing": {
        "gas": "EAN32",
        "equipment_requirements": ["torch", "SMB"],
        "skills": [],
        "route": "Descend mooring, follow reef wall south, turn at 30 min...",
        "hazards": "Current possible at corner. Watch depth at wall edge.",
        "briefing_text": "Full briefing content here..."
    },

    "certification": {
        "min_certification_level_id": "uuid or null",
        "min_certification_level_name": "Advanced Open Water"
    },

    "metadata": {
        "source_published_at": "2025-01-15T10:00:00Z",
        "snapshot_created_at": "2025-01-15T14:00:00Z"
    }
}
```

---

## Test Cases

### ExcursionTypeDive Lifecycle Tests

```python
class TestPublishDiveTemplate:
    def test_publishes_draft_template(self, draft_template, staff_user):
        """publish_dive_template changes status from draft to published."""

    def test_sets_published_at_and_by(self, draft_template, staff_user):
        """publish_dive_template sets audit fields."""

    def test_rejects_already_published(self, published_template, staff_user):
        """publish_dive_template raises if not draft."""

    def test_rejects_retired_template(self, retired_template, staff_user):
        """publish_dive_template raises if retired."""

    def test_emits_published_audit_event(self, draft_template, staff_user):
        """publish_dive_template emits DIVE_TEMPLATE_PUBLISHED."""


class TestRetireDiveTemplate:
    def test_retires_published_template(self, published_template, staff_user):
        """retire_dive_template changes status to retired."""

    def test_sets_retired_at_and_by(self, published_template, staff_user):
        """retire_dive_template sets audit fields."""

    def test_rejects_draft_template(self, draft_template, staff_user):
        """retire_dive_template raises if not published."""

    def test_rejects_already_retired(self, retired_template, staff_user):
        """retire_dive_template raises if already retired."""

    def test_emits_retired_audit_event(self, published_template, staff_user):
        """retire_dive_template emits DIVE_TEMPLATE_RETIRED."""
```

### Dive Plan Locking Tests

```python
class TestLockDivePlan:
    def test_creates_plan_snapshot(self, dive_with_template, staff_user):
        """lock_dive_plan populates plan_snapshot from template."""

    def test_sets_locked_at_and_by(self, dive_with_template, staff_user):
        """lock_dive_plan sets audit fields."""

    def test_sets_provenance_fields(self, dive_with_template, staff_user):
        """lock_dive_plan sets plan_template_id and plan_template_published_at."""

    def test_snapshot_contains_template_fields(self, dive_with_template, staff_user):
        """plan_snapshot includes all briefing content."""

    def test_snapshot_independent_of_template_changes(self, locked_dive, staff_user):
        """Modifying template after lock doesn't change snapshot."""

    def test_idempotent_when_already_locked(self, locked_dive, staff_user):
        """lock_dive_plan called twice returns dive unchanged (no error)."""

    def test_force_relocks_already_locked_dive(self, locked_dive, staff_user):
        """lock_dive_plan with force=True updates existing snapshot."""

    def test_rejects_unpublished_template(self, dive_with_draft_template, staff_user):
        """lock_dive_plan raises if template not published."""

    def test_force_allows_unpublished_template(self, dive_with_draft_template, staff_user):
        """lock_dive_plan with force=True allows unpublished template."""

    def test_rejects_dive_without_template(self, standalone_dive, staff_user):
        """lock_dive_plan raises if no template available."""

    def test_clears_snapshot_outdated_flag(self, dive_with_outdated_flag, staff_user):
        """lock_dive_plan clears plan_snapshot_outdated."""

    def test_emits_locked_audit_event(self, dive_with_template, staff_user):
        """lock_dive_plan emits DIVE_PLAN_LOCKED."""


class TestResnapshotDivePlan:
    def test_updates_snapshot_on_locked_dive(self, locked_dive, staff_user):
        """resnapshot_dive_plan replaces snapshot."""

    def test_requires_reason(self, locked_dive, staff_user):
        """resnapshot_dive_plan raises if reason empty."""

    def test_rejects_unlocked_dive(self, dive_with_template, staff_user):
        """resnapshot_dive_plan raises if not locked."""

    def test_audit_contains_old_and_new(self, locked_dive, staff_user):
        """resnapshot audit event includes diff and reason."""

    def test_emits_resnapshotted_audit_event(self, locked_dive, staff_user):
        """resnapshot_dive_plan emits DIVE_PLAN_RESNAPSHOTTED."""


class TestLockExcursionPlans:
    def test_locks_all_unlocked_dives(self, excursion_with_dives, staff_user):
        """lock_excursion_plans locks all dives."""

    def test_skips_already_locked_dives(self, excursion_with_mixed_dives, staff_user):
        """lock_excursion_plans doesn't relock locked dives."""

    def test_returns_list_of_locked_dives(self, excursion_with_dives, staff_user):
        """lock_excursion_plans returns locked dive list."""

    def test_emits_excursion_locked_audit_event(self, excursion_with_dives, staff_user):
        """lock_excursion_plans emits EXCURSION_PLANS_LOCKED."""
```

### Snapshot Schema Tests

```python
class TestPlanSnapshotSchema:
    def test_snapshot_has_version(self, locked_dive):
        """Snapshot includes version field."""

    def test_snapshot_has_template_identity(self, locked_dive):
        """Snapshot includes template_id and template_name."""

    def test_snapshot_has_planning_fields(self, locked_dive):
        """Snapshot includes depth, duration, offset."""

    def test_snapshot_has_briefing_fields(self, locked_dive):
        """Snapshot includes gas, equipment, skills, route, hazards."""

    def test_snapshot_has_certification_fields(self, locked_dive):
        """Snapshot includes min certification if set."""

    def test_snapshot_has_metadata(self, locked_dive):
        """Snapshot includes source_published_at and snapshot_created_at."""
```

---

## TDD Implementation Phases

### Phase A: Write Failing Tests First
- [ ] Create test file: `tests/test_dive_plan_lifecycle.py`
- [ ] Create test file: `tests/test_dive_plan_locking.py`
- [ ] Run tests, confirm they fail (services don't exist)

### Phase B: Model Extensions + Migrations
- [ ] Add briefing fields to ExcursionTypeDive
- [ ] Add lifecycle fields to ExcursionTypeDive
- [ ] Add snapshot fields to Dive
- [ ] Run `makemigrations`, verify migration file
- [ ] Run `migrate`
- [ ] **STOP: Verify schema correct before proceeding**

### Phase C: Implement Services
- [ ] `publish_dive_template()`
- [ ] `retire_dive_template()`
- [ ] `lock_dive_plan()`
- [ ] `resnapshot_dive_plan()`
- [ ] `lock_excursion_plans()`

### Phase D: Wire Audit Events
- [ ] Add actions to `Actions` class
- [ ] Emit events in services

### Phase E: Run Tests Until Green
- [ ] All lifecycle tests pass
- [ ] All locking tests pass
- [ ] All schema tests pass

---

## Migration Notes

### Backwards Compatibility

- All new fields have defaults or are nullable
- Existing `ExcursionTypeDive` records get `status = "draft"` (or could default to `"published"` if you want existing templates usable immediately)
- Existing `Dive` records have `plan_snapshot = null` (unlocked)

### Recommended Default for Existing Data

```python
# In migration
ExcursionTypeDive.objects.filter(status="").update(status="published")
```

This makes existing templates immediately usable without requiring manual publishing.

---

## Open Questions

1. **Default status for existing templates**: `draft` (requires manual publish) or `published` (immediately usable)?
   **Recommendation**: `published` for existing, `draft` for new

2. **Required briefing fields**: Should some fields (e.g., `hazards`) be required before publishing?
   **Recommendation**: No hard requirements initially, enforce via admin UI hints

3. **Snapshot on excursion create vs explicit lock**: Auto-snapshot when excursion is created, or require explicit lock action?
   **Recommendation**: Explicit lock (gives staff time to adjust)

---

## Approval

- [ ] Model extensions reviewed
- [ ] Service signatures approved
- [ ] Audit events approved
- [ ] Test cases reviewed
- [ ] Migration strategy approved

**Approved by**: _________________ **Date**: _________
