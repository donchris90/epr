"""
Module 9 — Equipment & Fleet Management (Code: EQP)
Service layer — business logic other modules must call through rather
than querying eqp_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.9):
  - An Operator Assignment is blocked if the operator's certification
    has expired -- unconditionally; the SRS does not describe an
    override path here the way it does for budget/compliance checks
    elsewhere, so none is implemented.
  - Cost per Hour recalculates automatically whenever a contributing
    record changes -- satisfied by never storing it: every call to
    calculate_cost_per_hour reads current data and computes fresh.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.eqp.models import (
    Equipment,
    OperatorAssignment,
    MaintenanceRecord,
    RepairHistory,
    DowntimeEvent,
    UtilizationRecord,
    EquipmentTransfer,
)


# --- Operator assignment (EQP-04, business rule) ----------------------------

def assign_operator(tenant_id, *, equipment_id, operator_id, shift_start, certification_valid_until=None, shift_end=None):
    """
    Business rule: blocked, unconditionally, if the operator's
    certification has expired. `certification_valid_until` is supplied
    by the caller because EQP does not own Module 11's competency data
    (bounded-context discipline, SRS 3.3).
    """
    today = shift_start.date() if hasattr(shift_start, "date") else date.today()
    if certification_valid_until and certification_valid_until < today:
        raise APIError(
            "Operator certification has expired",
            status=409,
            detail=f"Certification expired {certification_valid_until}; assignment cannot proceed.",
        )

    assignment = OperatorAssignment(
        tenant_id=tenant_id,
        equipment_id=equipment_id,
        operator_id=operator_id,
        shift_start=shift_start,
        shift_end=shift_end,
        certification_valid_until=certification_valid_until,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


# --- Availability & Utilization (EQP-09) ------------------------------------

def calculate_availability_utilization(equipment: Equipment, *, period_start: date, period_end: date) -> dict:
    """
    Availability = uptime / total scheduled time.
    Utilization  = productive hours / available (uptime) hours.

    Uptime = total scheduled time minus ALL downtime in the period
    (every DowntimeEvent reason classification represents time the
    equipment was NOT available for use, including its own scheduled
    maintenance -- "available" and "in scheduled maintenance" are not
    the same thing).
    """
    utilization_records = UtilizationRecord.query.filter(
        UtilizationRecord.equipment_id == equipment.id,
        UtilizationRecord.record_date >= period_start,
        UtilizationRecord.record_date <= period_end,
    ).all()

    total_scheduled = sum((r.hours_scheduled for r in utilization_records), Decimal("0"))
    productive_hours = sum((r.hours_operated for r in utilization_records), Decimal("0"))

    period_start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    period_end_dt = datetime.combine(period_end, datetime.max.time(), tzinfo=timezone.utc)

    downtime_events = DowntimeEvent.query.filter(
        DowntimeEvent.equipment_id == equipment.id,
        DowntimeEvent.started_at <= period_end_dt,
        db.or_(DowntimeEvent.ended_at.is_(None), DowntimeEvent.ended_at >= period_start_dt),
    ).all()

    downtime_hours = Decimal("0")
    for event in downtime_events:
        # Clip to the period boundary -- an event spanning outside the
        # window should only count the portion that falls within it.
        start = max(event.started_at, period_start_dt)
        end = min(event.ended_at or period_end_dt, period_end_dt)
        if end > start:
            downtime_hours += Decimal((end - start).total_seconds()) / Decimal("3600")

    uptime_hours = max(total_scheduled - downtime_hours, Decimal("0"))

    availability = (uptime_hours / total_scheduled) if total_scheduled > 0 else None
    utilization = (productive_hours / uptime_hours) if uptime_hours > 0 else None

    return {
        "total_scheduled_hours": total_scheduled,
        "downtime_hours": downtime_hours,
        "uptime_hours": uptime_hours,
        "productive_hours": productive_hours,
        "availability_pct": (availability * 100) if availability is not None else None,
        "utilization_pct": (utilization * 100) if utilization is not None else None,
    }


# --- Cost per Hour (EQP-10, business rule) -----------------------------------

def calculate_cost_per_hour(
    equipment: Equipment,
    *,
    period_start: date,
    period_end: date,
    fuel_normal_cost=None,
    fuel_variance_cost=None,
    operator_cost=None,
) -> dict:
    """
    Cost per Hour = (fuel + maintenance + depreciation + operator) / hours operated.

    `fuel_normal_cost` / `fuel_variance_cost` and `operator_cost` are
    supplied by the caller because EQP does not own Module 10 (Fuel) or
    Module 11 (Workforce) data -- same pattern as the
    operator-certification check above. Fuel is deliberately split into
    two parameters rather than one blended figure: Module 10's own
    business rule (SRS 4.10) requires fuel variance to appear as a
    distinct cost line here, never folded into normal consumption --
    see app.modules.fuel.services.fuel_cost_breakdown, which is what a
    caller composing this call would use to get both figures.
    Maintenance and depreciation are computed from this module's own
    data, so they need no external input.
    """
    # MaintenanceRecord.completed_at / RepairHistory.repaired_at are
    # DateTime columns; comparing against a bare Date for period_end
    # implicitly compares against midnight of that date, silently
    # excluding anything completed later that same day. Extend to the
    # end of the day explicitly.
    from datetime import datetime, time

    period_end_dt = datetime.combine(period_end, time.max)

    maintenance_cost = (
        db.session.query(db.func.coalesce(db.func.sum(MaintenanceRecord.cost), 0))
        .filter(
            MaintenanceRecord.equipment_id == equipment.id,
            MaintenanceRecord.completed_at.isnot(None),
            MaintenanceRecord.completed_at >= period_start,
            MaintenanceRecord.completed_at <= period_end_dt,
        )
        .scalar()
    )
    repair_cost = (
        db.session.query(db.func.coalesce(db.func.sum(RepairHistory.cost), 0))
        .filter(
            RepairHistory.equipment_id == equipment.id,
            RepairHistory.repaired_at.isnot(None),
            RepairHistory.repaired_at >= period_start,
            RepairHistory.repaired_at <= period_end_dt,
        )
        .scalar()
    )

    utilization = calculate_availability_utilization(equipment, period_start=period_start, period_end=period_end)
    hours_operated = utilization["productive_hours"]

    period_days = (period_end - period_start).days + 1
    annual_dep = equipment.annual_depreciation
    depreciation_cost = (Decimal(annual_dep) * Decimal(period_days) / Decimal("365")) if annual_dep else Decimal("0")

    fuel_normal_cost = Decimal(str(fuel_normal_cost or 0))
    fuel_variance_cost = Decimal(str(fuel_variance_cost or 0))

    total_cost = (
        Decimal(maintenance_cost)
        + Decimal(repair_cost)
        + depreciation_cost
        + fuel_normal_cost
        + fuel_variance_cost
        + Decimal(str(operator_cost or 0))
    )

    cost_per_hour = (total_cost / hours_operated) if hours_operated > 0 else None

    return {
        "maintenance_cost": Decimal(maintenance_cost),
        "repair_cost": Decimal(repair_cost),
        "depreciation_cost": depreciation_cost,
        "fuel_normal_cost": fuel_normal_cost,
        "fuel_variance_cost": fuel_variance_cost,
        "operator_cost": Decimal(str(operator_cost or 0)),
        "total_cost": total_cost,
        "hours_operated": hours_operated,
        "cost_per_hour": cost_per_hour,
    }


# --- Idle equipment (EQP-11) ---------------------------------------------------

def find_idle_equipment(tenant_id, *, threshold_days: int = 7, as_of: date = None):
    """Flags equipment with no logged productive hours in the last
    `threshold_days` -- the "show me all idle excavators" AI Assistant
    use case named directly in the SRS."""
    as_of = as_of or date.today()
    from datetime import timedelta

    horizon = as_of - timedelta(days=threshold_days)

    idle = []
    for equipment in Equipment.query.filter_by(tenant_id=tenant_id, status="active").all():
        recent_hours = (
            db.session.query(db.func.coalesce(db.func.sum(UtilizationRecord.hours_operated), 0))
            .filter(
                UtilizationRecord.equipment_id == equipment.id,
                UtilizationRecord.record_date >= horizon,
                UtilizationRecord.record_date <= as_of,
            )
            .scalar()
        )
        if Decimal(recent_hours) == 0:
            idle.append(equipment)

    return idle


# --- Equipment transfers (EQP-12) -----------------------------------------------

def approve_transfer(transfer: EquipmentTransfer, *, approved_by, cutover_date=None):
    if transfer.status != "pending":
        raise APIError("Transfer is not pending", status=409)

    transfer.status = "approved"
    transfer.approved_by = approved_by
    transfer.approved_at = datetime.now(timezone.utc)
    transfer.cutover_date = cutover_date or date.today()

    # Cost allocation cutover: equipment's current_project_id switches
    # exactly at the cutover date -- for a same-day approval this takes
    # effect immediately; a future-dated cutover is intentionally left
    # for a scheduler to apply on that date rather than jumped forward
    # now (this module has no Celery task wired up yet -- TODO).
    if transfer.cutover_date <= date.today():
        transfer.equipment.current_project_id = transfer.to_project_id

    db.session.commit()
    return transfer
