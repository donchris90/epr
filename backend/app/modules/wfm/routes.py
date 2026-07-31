"""
Module 11 — Workforce Management (Code: WFM)
SRS Section 4.11 — Flask Blueprint. Base path: /v1/wfm
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.wfm import services
from app.modules.wfm.models import (
    Employee,
    CasualWorker,
    AttendanceRecord,
    Timesheet,
    LeaveRequest,
    TrainingRecord,
    MedicalRecord,
    Competency,
    Certification,
    StatutoryDeductionRule,
    PayrollRun,
)
from app.modules.wfm.schemas import (
    EmployeeSchema,
    CasualWorkerSchema,
    AttendanceRecordSchema,
    GenerateTimesheetSchema,
    TimesheetSchema,
    LeaveRequestInputSchema,
    LeaveRequestSchema,
    LeaveDecisionSchema,
    TrainingRecordSchema,
    MedicalRecordSchema,
    CompetencySchema,
    CertificationSchema,
    StatutoryDeductionRuleSchema,
    GeneratePayrollRunSchema,
    PayrollRunSchema,
)

bp = Blueprint("wfm", __name__, url_prefix="/v1/wfm")

employee_schema = EmployeeSchema()
casual_schema = CasualWorkerSchema()
attendance_schema = AttendanceRecordSchema()
timesheet_schema = TimesheetSchema()
leave_schema = LeaveRequestSchema()
training_schema = TrainingRecordSchema()
medical_schema = MedicalRecordSchema()
competency_schema = CompetencySchema()
certification_schema = CertificationSchema()
deduction_rule_schema = StatutoryDeductionRuleSchema()
payroll_run_schema = PayrollRunSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_employee_or_404(employee_id) -> Employee:
    e = Employee.query.filter_by(id=employee_id, tenant_id=g.tenant_id).first()
    if not e:
        raise APIError("Employee not found", status=404)
    return e


@bp.get("/health")
def health():
    return jsonify({"module": "wfm", "name": "Workforce Management", "status": "ok"})


# --- Employees & casual workers (WFM-01, WFM-02) ----------------------------

@bp.post("/employees")
@require_permission("wfm:write")
def create_employee():
    data = _load(employee_schema)
    employee = Employee(tenant_id=g.tenant_id, **data)
    db.session.add(employee)
    db.session.commit()
    return jsonify(employee_schema.dump(employee)), 201


@bp.get("/employees")
@require_permission("wfm:read")
def list_employees():
    employees = Employee.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(employee_schema.dump(employees, many=True)))


@bp.post("/casual-workers")
@require_permission("wfm:write")
def onboard_casual_worker():
    """WFM-02: minimal fields for same-day engagement -- deliberately
    just name + optional phone/ID/rate, no approval workflow."""
    from datetime import datetime, timezone

    data = _load(casual_schema)
    worker = CasualWorker(tenant_id=g.tenant_id, onboarded_by=g.user_id, onboarded_at=datetime.now(timezone.utc), **data)
    db.session.add(worker)
    db.session.commit()
    return jsonify(casual_schema.dump(worker)), 201


@bp.get("/casual-workers")
@require_permission("wfm:read")
def list_casual_workers():
    workers = CasualWorker.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(casual_schema.dump(workers, many=True)))


# --- Attendance (WFM-03) -----------------------------------------------------

@bp.post("/attendance")
@require_permission("wfm:write")
def record_attendance():
    data = _load(attendance_schema)
    if bool(data.get("employee_id")) == bool(data.get("casual_worker_id")):
        raise APIError("Exactly one of employee_id or casual_worker_id is required", status=400)

    record = AttendanceRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(attendance_schema.dump(record)), 201


# --- Timesheets (WFM-04) ------------------------------------------------------

@bp.post("/timesheets")
@require_permission("wfm:write")
def create_timesheet():
    data = _load(GenerateTimesheetSchema())
    timesheet = services.generate_timesheet(g.tenant_id, **data)
    return jsonify(timesheet_schema.dump(timesheet)), 201


@bp.get("/timesheets")
@require_permission("wfm:read")
def list_timesheets():
    status = request.args.get("status")
    query = Timesheet.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    timesheets = query.all()
    return jsonify(envelope(timesheet_schema.dump(timesheets, many=True)))


@bp.post("/timesheets/<uuid:timesheet_id>/approve")
@require_permission("wfm:approve")
def approve_timesheet(timesheet_id):
    timesheet = Timesheet.query.filter_by(id=timesheet_id, tenant_id=g.tenant_id).first()
    if not timesheet:
        raise APIError("Timesheet not found", status=404)
    timesheet = services.approve_timesheet(timesheet, approver_id=g.user_id)
    return jsonify(timesheet_schema.dump(timesheet))


@bp.post("/timesheets/<uuid:timesheet_id>/reject")
@require_permission("wfm:approve")
def reject_timesheet(timesheet_id):
    timesheet = Timesheet.query.filter_by(id=timesheet_id, tenant_id=g.tenant_id).first()
    if not timesheet:
        raise APIError("Timesheet not found", status=404)
    timesheet = services.reject_timesheet(timesheet, approver_id=g.user_id)
    return jsonify(timesheet_schema.dump(timesheet))


# --- Labor cost allocation (WFM-12) -------------------------------------------

@bp.get("/labor-cost-allocation")
@require_permission("wfm:read")
def get_labor_cost_allocation():
    period_start = request.args.get("period_start")
    period_end = request.args.get("period_end")
    group_by = request.args.get("group_by", "project_id")
    if not period_start or not period_end:
        raise APIError("period_start and period_end are required", status=400)

    result = services.allocate_labor_cost(g.tenant_id, period_start=period_start, period_end=period_end, group_by=group_by)
    return jsonify(envelope([{"group": r["group"], "total_cost": str(r["total_cost"])} for r in result]))


# --- Leave (WFM-05) -------------------------------------------------------------

@bp.post("/leave-requests")
@require_permission("wfm:write")
def create_leave_request():
    data = _load(LeaveRequestInputSchema())
    _get_employee_or_404(data["employee_id"])
    leave = LeaveRequest(tenant_id=g.tenant_id, **data)
    db.session.add(leave)
    db.session.commit()
    return jsonify(leave_schema.dump(leave)), 201


@bp.post("/leave-requests/<uuid:leave_id>/decide")
@require_permission("wfm:approve")
def decide_leave_request(leave_id):
    leave = LeaveRequest.query.filter_by(id=leave_id, tenant_id=g.tenant_id).first()
    if not leave:
        raise APIError("Leave request not found", status=404)
    data = _load(LeaveDecisionSchema())
    leave = services.decide_leave_request(leave, decision=data["decision"], approver_id=g.user_id)
    return jsonify(leave_schema.dump(leave))


# --- Training (WFM-06) -----------------------------------------------------------

@bp.post("/employees/<uuid:employee_id>/training-records")
@require_permission("wfm:write")
def add_training_record(employee_id):
    employee = _get_employee_or_404(employee_id)
    data = _load(training_schema)
    record = TrainingRecord(tenant_id=g.tenant_id, employee_id=employee.id, **{k: v for k, v in data.items() if k != "employee_id"})
    db.session.add(record)
    db.session.commit()
    return jsonify(training_schema.dump(record)), 201


@bp.get("/training-records/expiring")
@require_permission("wfm:read")
def list_expiring_training():
    from datetime import date, timedelta

    within_days = request.args.get("within_days", 30, type=int)
    horizon = date.today() + timedelta(days=within_days)
    records = TrainingRecord.query.filter(
        TrainingRecord.tenant_id == g.tenant_id,
        TrainingRecord.expiry_date.isnot(None),
        TrainingRecord.expiry_date <= horizon,
    ).all()
    return jsonify(envelope(training_schema.dump(records, many=True)))


# --- Medical records (WFM-07, business rule: field-level access gate) ------------

@bp.post("/employees/<uuid:employee_id>/medical-records")
@require_permission("wfm:medical")
def add_medical_record(employee_id):
    """Business rule: requires the distinct `wfm:medical` permission,
    checked IN ADDITION to whatever general WFM access the caller has
    -- a Project Manager with broad `wfm:*`-style access still cannot
    reach this endpoint without an explicit HR/HSE grant of
    `wfm:medical` specifically."""
    employee = _get_employee_or_404(employee_id)
    data = _load(medical_schema)
    record = MedicalRecord(tenant_id=g.tenant_id, employee_id=employee.id, **{k: v for k, v in data.items() if k != "employee_id"})
    db.session.add(record)
    db.session.commit()
    return jsonify(medical_schema.dump(record)), 201


@bp.get("/employees/<uuid:employee_id>/medical-records")
@require_permission("wfm:medical")
def list_medical_records(employee_id):
    _get_employee_or_404(employee_id)
    records = MedicalRecord.query.filter_by(employee_id=employee_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(medical_schema.dump(records, many=True)))


# --- Competency & certification (WFM-08, WFM-09) ---------------------------------

@bp.post("/employees/<uuid:employee_id>/competencies")
@require_permission("wfm:write")
def add_competency(employee_id):
    employee = _get_employee_or_404(employee_id)
    data = _load(competency_schema)
    competency = Competency(tenant_id=g.tenant_id, employee_id=employee.id, **{k: v for k, v in data.items() if k != "employee_id"})
    db.session.add(competency)
    db.session.commit()
    return jsonify(competency_schema.dump(competency)), 201


@bp.post("/employees/<uuid:employee_id>/certifications")
@require_permission("wfm:write")
def add_certification(employee_id):
    employee = _get_employee_or_404(employee_id)
    data = _load(certification_schema)
    cert = Certification(tenant_id=g.tenant_id, employee_id=employee.id, **{k: v for k, v in data.items() if k != "employee_id"})
    db.session.add(cert)
    db.session.commit()
    return jsonify(certification_schema.dump(cert)), 201


@bp.get("/employees/<uuid:employee_id>/certifications/active")
@require_permission("wfm:read")
def get_active_certification(employee_id):
    """The endpoint a caller wiring this module to Module 9's operator
    assignment would use -- see services.get_active_certification."""
    _get_employee_or_404(employee_id)
    certification_type = request.args.get("certification_type")
    if not certification_type:
        raise APIError("certification_type query parameter is required", status=400)

    cert = services.get_active_certification(g.tenant_id, employee_id=employee_id, certification_type=certification_type)
    if not cert:
        return jsonify({"certification": None})
    return jsonify({"certification": certification_schema.dump(cert)})


@bp.get("/certifications/expiring")
@require_permission("wfm:read")
def list_expiring_certifications():
    within_days = request.args.get("within_days", 30, type=int)
    certs = services.list_expiring_certifications(g.tenant_id, within_days=within_days)
    return jsonify(envelope(certification_schema.dump(certs, many=True)))


# --- Statutory deduction rules ----------------------------------------------------

@bp.post("/statutory-deduction-rules")
@require_permission("wfm:approve")
def create_deduction_rule():
    data = _load(deduction_rule_schema)
    rule = StatutoryDeductionRule(tenant_id=g.tenant_id, **data)
    db.session.add(rule)
    db.session.commit()
    return jsonify(deduction_rule_schema.dump(rule)), 201


# --- Payroll (WFM-10, business rule) ----------------------------------------------

@bp.post("/payroll-runs")
@require_permission("wfm:approve")
def create_payroll_run():
    data = _load(GeneratePayrollRunSchema())
    run = services.generate_payroll_run(g.tenant_id, **data)
    return jsonify(payroll_run_schema.dump(run)), 201


@bp.get("/payroll-runs/<uuid:run_id>")
@require_permission("wfm:approve")
def get_payroll_run(run_id):
    run = PayrollRun.query.filter_by(id=run_id, tenant_id=g.tenant_id).first()
    if not run:
        raise APIError("Payroll run not found", status=404)
    return jsonify(payroll_run_schema.dump(run))


@bp.post("/payroll-runs/<uuid:run_id>/finalize")
@require_permission("wfm:approve")
def finalize_payroll_run(run_id):
    run = PayrollRun.query.filter_by(id=run_id, tenant_id=g.tenant_id).first()
    if not run:
        raise APIError("Payroll run not found", status=404)
    run = services.finalize_payroll_run(run, finalized_by=g.user_id)
    return jsonify(payroll_run_schema.dump(run))
