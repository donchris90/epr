"""
Module 20 — Asset Management (Code: AST)
Service layer — business logic other modules must call through rather
than querying ast_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.20):
  - Asset records are immutable as to their original as-built
    baseline; all subsequent changes are dated condition/maintenance
    events layered on top, never edits to the baseline itself.
  - Retention release tied to DLP completion requires every defect
    raised during the DLP to be marked resolved AND verified; the
    system blocks the release action otherwise.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.ast.models import Asset, MaintenanceSchedule, DefectsLiabilityRecord, DefectItem


# --- Asset baseline immutability (AST-01, business rule) ------------------------

def update_asset_attributes(asset: Asset, *, name=None, category_attributes=None):
    """
    The ONLY sanctioned way to change an Asset after creation --
    deliberately touches only `name` and `category_attributes`, never
    `baseline_data`, `as_built_record_id`, or `handover_date`. There is
    no function anywhere in this module that accepts those three
    fields after initial creation.
    """
    if name is not None:
        asset.name = name
    if category_attributes is not None:
        asset.category_attributes = category_attributes
    db.session.commit()
    return asset


# --- Maintenance schedule (AST-03) ------------------------------------------------

def complete_maintenance_task(schedule: MaintenanceSchedule, *, completed_at=None):
    """Rolls the schedule forward: completing a task records when, and
    (for a recurring task) advances next_due_date by frequency_days --
    a one-off task (frequency_days is None) simply has no next due
    date afterward."""
    completed_at = completed_at or datetime.now(timezone.utc)
    schedule.last_completed_at = completed_at

    if schedule.frequency_days and schedule.next_due_date:
        from datetime import timedelta

        schedule.next_due_date = schedule.next_due_date + timedelta(days=schedule.frequency_days)
    else:
        schedule.next_due_date = None

    db.session.commit()
    return schedule


def list_overdue_maintenance(tenant_id, *, as_of=None):
    from datetime import date

    as_of = as_of or date.today()
    return MaintenanceSchedule.query.filter(
        MaintenanceSchedule.tenant_id == tenant_id,
        MaintenanceSchedule.next_due_date.isnot(None),
        MaintenanceSchedule.next_due_date < as_of,
    ).all()


# --- Defects Liability Period retention release (AST-06, business rule) --------

def resolve_defect(defect: DefectItem):
    if defect.status != "open":
        raise APIError("Defect is not open", status=409)
    defect.status = "resolved"
    defect.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return defect


def verify_defect(defect: DefectItem, *, verified_by):
    """The distinct verification step -- someone OTHER than whoever
    fixed it confirming the fix actually holds, before it can back a
    retention release. Same reasoning as Module 13's corrective-action
    verification."""
    if defect.status != "resolved":
        raise APIError("Defect must be resolved before it can be verified", status=409)
    defect.status = "verified"
    defect.verified_at = datetime.now(timezone.utc)
    defect.verified_by = verified_by
    db.session.commit()
    return defect


def release_dlp_retention(dlp_record: DefectsLiabilityRecord):
    """
    Business rule: blocks release unless EVERY linked defect is
    verified -- a defect merely "resolved" (fixed but not
    independently confirmed) still blocks release, and a DLP with zero
    defects raised is trivially eligible (nothing to block on).
    """
    if dlp_record.retention_released:
        raise APIError("Retention has already been released for this DLP", status=409)

    unverified = [d for d in dlp_record.defects if d.status != "verified"]
    if unverified:
        raise APIError(
            "Cannot release DLP retention: not all defects are verified",
            status=409,
            detail=f"{len(unverified)} of {len(dlp_record.defects)} defect(s) are not yet verified.",
        )

    dlp_record.retention_released = True
    dlp_record.released_at = datetime.now(timezone.utc)
    db.session.commit()
    return dlp_record


# --- Lifecycle cost (AST-07) -------------------------------------------------------

def get_lifecycle_cost_summary(tenant_id, *, asset_id):
    from app.modules.ast.models import LifecycleCostRecord

    rows = (
        db.session.query(LifecycleCostRecord.cost_type, db.func.coalesce(db.func.sum(LifecycleCostRecord.amount), 0))
        .filter(LifecycleCostRecord.tenant_id == tenant_id, LifecycleCostRecord.asset_id == asset_id)
        .group_by(LifecycleCostRecord.cost_type)
        .all()
    )
    breakdown = {cost_type: Decimal(total) for cost_type, total in rows}
    total = sum(breakdown.values(), Decimal("0"))
    return {"breakdown": breakdown, "total": total}
