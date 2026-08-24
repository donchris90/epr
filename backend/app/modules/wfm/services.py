"""
Module 11 — Workforce Management (Code: WFM)
Service layer — business logic other modules must call through rather
than querying wfm_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.11):
  - Medical Record field-level access restriction is enforced in
    routes.py (a permission gate, not a service-layer concern) --
    see the module docstring in models.py.
  - Payroll cannot be finalized while any linked timesheet remains in
    "pending_approval" status.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.wfm.models import (
    Employee,
    CasualWorker,
    AttendanceRecord,
    Timesheet,
    LeaveRequest,
    Certification,
    PayrollRun,
    PayrollLine,
    StatutoryDeductionRule,
)


# --- Employees (WFM-01) --------------------------------------------------------

def update_employee(employee: Employee, **fields):
    """Real, previously genuinely missing -- only create_employee (via
    the route directly) and list existed; no way to correct a
    mistake or change role/trade/pay_grade/monthly_rate without this."""
    for key, value in fields.items():
        if value is not None and hasattr(employee, key):
            setattr(employee, key, value)
    db.session.commit()
    return employee


def terminate_employee(employee: Employee):
    """Real, explicit terminate -- distinct from a soft-delete (this
    model has none): a terminated employee's real history (timesheets,
    payroll lines, certifications) stays intact and queryable, they're
    simply no longer active. Uses the real, existing "inactive" status
    (WORKER_STATUSES has no separate "terminated" value) rather than
    adding a new one -- for this model, terminated and inactive are
    the same real state."""
    if employee.status == "inactive":
        raise APIError("Employee is already terminated", status=409)
    employee.status = "inactive"
    db.session.commit()
    return employee


def reactivate_employee(employee: Employee):
    if employee.status != "inactive":
        raise APIError("Only a terminated employee can be reactivated", status=409, detail=f"Current status is '{employee.status}'")
    employee.status = "active"
    db.session.commit()
    return employee


def assign_project(employee: Employee, *, project_id: str):
    """Real assign/transfer -- assigned_project_ids is a real,
    already-existing JSONB list (see models.py); this was previously
    only ever set at creation, with no way to add or change it
    afterward. Idempotent -- assigning a project already on the list
    is a real no-op, not a duplicate entry."""
    current = list(employee.assigned_project_ids or [])
    if project_id not in current:
        current.append(project_id)
    employee.assigned_project_ids = current
    db.session.commit()
    return employee


def transfer_project(employee: Employee, *, from_project_id: str, to_project_id: str):
    """Real transfer -- removes the real, specific old assignment and
    adds the new one in a single, atomic update, rather than two
    separate calls that could leave an inconsistent intermediate
    state if one failed."""
    current = list(employee.assigned_project_ids or [])
    if from_project_id in current:
        current.remove(from_project_id)
    if to_project_id not in current:
        current.append(to_project_id)
    employee.assigned_project_ids = current
    db.session.commit()
    return employee


# --- Timesheets (WFM-04) -----------------------------------------------------

def generate_timesheet(
    tenant_id,
    *,
    employee_id=None,
    casual_worker_id=None,
    project_id=None,
    activity_id=None,
    period_start,
    period_end,
    pay_basis,
    hours_or_units,
    rate_applied,
):
    if bool(employee_id) == bool(casual_worker_id):
        raise APIError("Exactly one of employee_id or casual_worker_id is required", status=400)

    hours_or_units = Decimal(str(hours_or_units))
    rate_applied = Decimal(str(rate_applied))
    gross_amount = hours_or_units * rate_applied

    timesheet = Timesheet(
        tenant_id=tenant_id,
        employee_id=employee_id,
        casual_worker_id=casual_worker_id,
        project_id=project_id,
        activity_id=activity_id,
        period_start=period_start,
        period_end=period_end,
        pay_basis=pay_basis,
        hours_or_units=hours_or_units,
        rate_applied=rate_applied,
        gross_amount=gross_amount,
    )
    db.session.add(timesheet)
    db.session.commit()
    return timesheet


def approve_timesheet(timesheet: Timesheet, *, approver_id):
    if timesheet.status != "pending_approval":
        raise APIError("Timesheet is not pending approval", status=409, detail=f"Current status is '{timesheet.status}'")

    timesheet.status = "approved"
    timesheet.approved_by = approver_id
    timesheet.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return timesheet


def reject_timesheet(timesheet: Timesheet, *, approver_id):
    if timesheet.status != "pending_approval":
        raise APIError("Timesheet is not pending approval", status=409)

    timesheet.status = "rejected"
    timesheet.approved_by = approver_id
    timesheet.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return timesheet


def return_timesheet_for_correction(timesheet: Timesheet, *, approver_id):
    """Real, distinct from reject: "rejected" is a terminal state (see
    reject_timesheet above -- nothing in this codebase transitions a
    timesheet out of it); "returned" is meant to be corrected and
    resubmitted, matching this batch's own explicit distinction
    between the two as separate required actions."""
    if timesheet.status != "pending_approval":
        raise APIError("Timesheet is not pending approval", status=409, detail=f"Current status is '{timesheet.status}'")

    timesheet.status = "returned"
    timesheet.approved_by = approver_id
    timesheet.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return timesheet


def resubmit_timesheet(timesheet: Timesheet):
    """Real reverse of return_timesheet_for_correction -- a returned
    timesheet, once corrected (via update_timesheet below), goes back
    to pending_approval for a real, fresh approval decision."""
    if timesheet.status != "returned":
        raise APIError("Timesheet is not in returned status", status=409, detail=f"Current status is '{timesheet.status}'")

    timesheet.status = "pending_approval"
    timesheet.approved_by = None
    timesheet.approved_at = None
    db.session.commit()
    return timesheet


def lock_timesheet(timesheet: Timesheet):
    """Real, explicit lock -- once approved, a timesheet can be locked
    to signal it's genuinely final and ready for payroll (locked
    timesheets are consumed by generate_payroll_run exactly like
    approved ones -- see that function's own docstring on the real
    bug this closes). Deliberately one-way in this batch: no
    unlock action exists, matching "lock" as a real, meaningful
    commitment rather than a togglable flag."""
    if timesheet.status != "approved":
        raise APIError("Only an approved timesheet can be locked", status=409, detail=f"Current status is '{timesheet.status}'")

    timesheet.status = "locked"
    db.session.commit()
    return timesheet


def update_timesheet(timesheet: Timesheet, *, hours_or_units=None, rate_applied=None):
    """Real edit capability -- previously genuinely missing (only
    generate_timesheet existed, no way to correct a mistake without
    creating a duplicate). Deliberately restricted to pending_approval
    or returned -- an approved/locked/rejected timesheet is a real
    decision already made and shouldn't silently change under it."""
    if timesheet.status not in ("pending_approval", "returned"):
        raise APIError(
            "Only a pending or returned timesheet can be edited", status=409, detail=f"Current status is '{timesheet.status}'"
        )

    if hours_or_units is not None:
        timesheet.hours_or_units = hours_or_units
    if rate_applied is not None:
        timesheet.rate_applied = rate_applied
    timesheet.gross_amount = timesheet.hours_or_units * timesheet.rate_applied
    db.session.commit()
    return timesheet


# --- Leave (WFM-05) -----------------------------------------------------------

def decide_leave_request(leave: LeaveRequest, *, decision: str, approver_id):
    if leave.status != "pending":
        raise APIError("Leave request already decided", status=409)
    if decision not in ("approved", "rejected"):
        raise APIError("Invalid decision", status=400)

    leave.status = decision
    leave.approved_by = approver_id
    leave.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return leave


def cancel_leave_request(leave: LeaveRequest):
    """Real, previously genuinely missing -- a pending OR already-
    approved request can be cancelled (an approved leave someone no
    longer needs is a real, ordinary case, not just a pending one)."""
    if leave.status not in ("pending", "approved"):
        raise APIError("Only a pending or approved leave request can be cancelled", status=409, detail=f"Current status is '{leave.status}'")
    leave.status = "cancelled"
    db.session.commit()
    return leave


def list_leave_requests(tenant_id, *, employee_id=None, status=None):
    """Real, previously genuinely missing -- no way to list leave
    requests at all existed (only create and decide), so there was no
    real way to build a leave calendar or a balance view."""
    query = LeaveRequest.query.filter_by(tenant_id=tenant_id)
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(LeaveRequest.start_date.desc()).all()


def get_leave_balance(tenant_id, *, employee_id):
    """Real, honest balance -- deliberately shows real days TAKEN this
    calendar year, grouped by leave_type, from real approved
    LeaveRequest rows. Does NOT show a "days remaining" figure: no
    real, configured annual entitlement exists anywhere in this
    codebase (Employee has no entitlement field of any kind) --
    inventing one (e.g. a hardcoded "21 days/year") would be fake
    data, not a real balance. See docs/WFM_SUB_GAPS.md."""
    from datetime import date

    year_start = date(date.today().year, 1, 1)
    approved = LeaveRequest.query.filter(
        LeaveRequest.tenant_id == tenant_id,
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == "approved",
        LeaveRequest.start_date >= year_start,
    ).all()

    days_taken_by_type = {}
    for leave in approved:
        days = (leave.end_date - leave.start_date).days + 1
        days_taken_by_type[leave.leave_type] = days_taken_by_type.get(leave.leave_type, 0) + days

    return days_taken_by_type


# --- Attendance (WFM-03) --------------------------------------------------------

def list_attendance(tenant_id, *, project_id=None, employee_id=None, attendance_date=None):
    """Real, previously genuinely missing -- POST /attendance existed
    (check-in/out capture), but no way to list or report on it at
    all."""
    query = AttendanceRecord.query.filter_by(tenant_id=tenant_id)
    if project_id:
        query = query.filter_by(project_id=project_id)
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    if attendance_date:
        query = query.filter_by(attendance_date=attendance_date)
    return query.order_by(AttendanceRecord.attendance_date.desc()).all()


def correct_attendance(record: AttendanceRecord, *, check_in_at=None, check_out_at=None):
    """Real, previously genuinely missing -- a real, ordinary
    correction (a missed check-out, a wrong time) had no way to be
    fixed short of deleting and recreating the row directly in the
    database."""
    if check_in_at is not None:
        record.check_in_at = check_in_at
    if check_out_at is not None:
        record.check_out_at = check_out_at
    db.session.commit()
    return record


def mark_absent(tenant_id, *, project_id, attendance_date, employee_id=None, casual_worker_id=None):
    """Real, previously genuinely missing -- a real absence (no
    check-in at all) had no way to be explicitly recorded; a real
    attendance report needs to distinguish "genuinely absent, recorded
    as such" from "no record exists for this person/day yet"."""
    if not employee_id and not casual_worker_id:
        raise APIError("Either employee_id or casual_worker_id is required", status=400)

    existing = AttendanceRecord.query.filter_by(
        tenant_id=tenant_id, project_id=project_id, attendance_date=attendance_date,
        employee_id=employee_id, casual_worker_id=casual_worker_id,
    ).first()
    if existing:
        raise APIError("An attendance record already exists for this person and date", status=409)

    record = AttendanceRecord(
        tenant_id=tenant_id, project_id=project_id, attendance_date=attendance_date,
        employee_id=employee_id, casual_worker_id=casual_worker_id, capture_method="manual",
    )
    db.session.add(record)
    db.session.commit()
    return record


# --- Certification lookup (WFM-08/09, feeds Module 9) -------------------------

def get_active_certification(tenant_id, *, employee_id, certification_type, as_of=None):
    """
    The real source of the certification data Module 9's operator
    assignment currently takes as a caller-supplied parameter (it was
    supplied externally specifically because this module didn't exist
    yet). A caller wiring the two modules together -- a route, or a
    future orchestration layer -- calls this to get
    `certification_valid_until` before calling
    app.modules.eqp.services.assign_operator, rather than EQP querying
    wfm_* tables directly.
    """
    from datetime import date

    as_of = as_of or date.today()
    cert = (
        Certification.query.filter_by(tenant_id=tenant_id, employee_id=employee_id, certification_type=certification_type)
        .order_by(Certification.expiry_date.desc())
        .first()
    )
    if not cert:
        return None
    return cert


def list_expiring_certifications(tenant_id, *, within_days: int = 30):
    from datetime import date, timedelta

    horizon = date.today() + timedelta(days=within_days)
    return Certification.query.filter(
        Certification.tenant_id == tenant_id,
        Certification.expiry_date.isnot(None),
        Certification.expiry_date <= horizon,
        Certification.expiry_date >= date.today(),
    ).all()


# --- Labor cost allocation (WFM-12) -------------------------------------------

def allocate_labor_cost(tenant_id, *, period_start, period_end, group_by="project_id"):
    """
    Sums approved timesheets' gross_amount grouped by project or
    activity, for Module 17/19 costing. Computed on read, like EST's
    Engineer's Estimate view -- there's nothing here that needs to be
    stored separately from the timesheets themselves.
    """
    if group_by not in ("project_id", "activity_id"):
        raise APIError("group_by must be 'project_id' or 'activity_id'", status=400)

    column = Timesheet.project_id if group_by == "project_id" else Timesheet.activity_id
    rows = (
        db.session.query(column, db.func.sum(Timesheet.gross_amount))
        .filter(
            Timesheet.tenant_id == tenant_id,
            Timesheet.status == "approved",
            Timesheet.period_start >= period_start,
            Timesheet.period_end <= period_end,
        )
        .group_by(column)
        .all()
    )
    return [{"group": str(key) if key else None, "total_cost": total} for key, total in rows]


# --- Payroll (WFM-10, business rule) -------------------------------------------

def generate_payroll_run(tenant_id, *, period_start, period_end):
    existing = PayrollRun.query.filter_by(tenant_id=tenant_id, period_start=period_start, period_end=period_end).first()
    if existing:
        raise APIError("A payroll run already exists for this period", status=409)

    run = PayrollRun(tenant_id=tenant_id, period_start=period_start, period_end=period_end)
    db.session.add(run)
    db.session.flush()

    timesheets = Timesheet.query.filter(
        Timesheet.tenant_id == tenant_id,
        Timesheet.period_start >= period_start,
        Timesheet.period_end <= period_end,
        Timesheet.payroll_run_id.is_(None),
        # Real, critical fix: this filter was previously entirely
        # missing -- a pending_approval or even rejected timesheet
        # would have been silently pulled into payroll. "locked" is
        # included since it's a stricter, already-verified state (see
        # lock_timesheet's own docstring) that should still be
        # payable.
        Timesheet.status.in_(("approved", "locked")),
    ).all()

    deduction_rules = StatutoryDeductionRule.query.filter_by(tenant_id=tenant_id).all()

    # Group timesheets by worker.
    by_worker = {}
    for ts in timesheets:
        ts.payroll_run_id = run.id
        key = ("employee", ts.employee_id) if ts.employee_id else ("casual", ts.casual_worker_id)
        by_worker.setdefault(key, []).append(ts)

    total_gross = Decimal("0")
    total_deductions = Decimal("0")

    for (worker_type, worker_id), worker_timesheets in by_worker.items():
        gross = sum((t.gross_amount for t in worker_timesheets), Decimal("0"))
        is_casual = worker_type == "casual"

        breakdown = {}
        deductions_total = Decimal("0")
        for rule in deduction_rules:
            if is_casual and not rule.applies_to_casuals:
                continue
            amount = (gross * rule.rate_or_amount / Decimal("100")) if rule.calculation_type == "percentage" else rule.rate_or_amount
            breakdown[rule.name] = str(amount)
            deductions_total += amount

        net = gross - deductions_total

        line = PayrollLine(
            tenant_id=tenant_id,
            payroll_run_id=run.id,
            employee_id=worker_id if worker_type == "employee" else None,
            casual_worker_id=worker_id if worker_type == "casual" else None,
            gross_pay=gross,
            deductions_breakdown=breakdown,
            total_deductions=deductions_total,
            net_pay=net,
        )
        db.session.add(line)

        total_gross += gross
        total_deductions += deductions_total

    run.total_gross = total_gross
    run.total_deductions = total_deductions
    run.total_net = total_gross - total_deductions

    db.session.commit()
    return run


def finalize_payroll_run(run: PayrollRun, *, finalized_by):
    """
    Business rule: cannot finalize while any linked timesheet remains
    in "pending_approval" status.
    """
    if run.status == "finalized":
        raise APIError("Payroll run is already finalized", status=409)

    pending = Timesheet.query.filter_by(tenant_id=run.tenant_id, payroll_run_id=run.id, status="pending_approval").count()
    if pending:
        raise APIError(
            "Cannot finalize payroll: timesheets pending approval",
            status=409,
            detail=f"{pending} linked timesheet(s) are still pending approval.",
        )

    run.status = "finalized"
    run.finalized_at = datetime.now(timezone.utc)
    run.finalized_by = finalized_by
    db.session.commit()
    return run
