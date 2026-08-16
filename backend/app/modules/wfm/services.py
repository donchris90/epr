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
    Timesheet,
    LeaveRequest,
    Certification,
    PayrollRun,
    PayrollLine,
    StatutoryDeductionRule,
)


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
