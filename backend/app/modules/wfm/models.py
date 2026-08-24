"""
Module 11 — Workforce Management (Code: WFM)
SRS Section 4.11.

The mixed-workforce reality of construction: permanent employees, daily
casual labor, competency/certification tracking, attendance, timesheets,
leave, and payroll.

Key Data Entities (SRS 4.11): Employee, CasualWorker, AttendanceRecord,
Timesheet, LeaveRequest, TrainingRecord, MedicalRecord, Competency,
Certification, PayrollRun.

Design notes:
  - `PayrollLine` and `StatutoryDeductionRule` are not in the SRS's
    named entity list but are necessary to make PayrollRun (WFM-10)
    real: a payroll run has to have per-worker lines with actual
    computed deductions, and deductions have to come from somewhere
    configurable ("statutory deductions... configurable per
    jurisdiction").
  - This is the module Module 9's operator-assignment check and cost
    calculation have been waiting on: `certification_valid_until` and
    `operator_cost` were caller-supplied parameters specifically
    because this module didn't exist yet. See
    services.get_active_certification -- a caller (e.g. a route or a
    future orchestration layer) now has a real source for that data,
    without EQP reaching into wfm_* tables directly (bounded-context
    discipline, SRS 3.3; a later module's service may be called by an
    even-later module or an orchestrating caller, but EQP itself,
    being an earlier module, still does not call into WFM).
  - Business rule (SRS 4.11): Medical Record access is restricted at
    the field level regardless of general role permissions -- enforced
    via a distinct `wfm:medical` permission gate in routes.py, checked
    in addition to (never instead of) the normal `wfm:read`/`wfm:write`
    checks other WFM endpoints use.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


EMPLOYMENT_TYPES = ("permanent", "contract")
WORKER_STATUSES = ("active", "inactive")
CAPTURE_METHODS = ("manual", "qr", "biometric")
PAY_BASES = ("time_based", "piece_rate")
TIMESHEET_STATUSES = ("pending_approval", "approved", "rejected", "returned", "locked")
LEAVE_STATUSES = ("pending", "approved", "rejected", "cancelled")
FITNESS_STATUSES = ("fit", "fit_with_restrictions", "unfit")
PAYROLL_STATUSES = ("draft", "finalized")
DEDUCTION_CALC_TYPES = ("percentage", "fixed")


class Employee(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-01: permanent/contract staff."""

    __tablename__ = "wfm_employees"

    name = db.Column(db.String(255), nullable=False)
    employee_number = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(128), nullable=True)
    trade = db.Column(db.String(128), nullable=True)
    pay_grade = db.Column(db.String(32), nullable=True)
    employment_type = db.Column(db.String(16), nullable=False, default="permanent")
    monthly_rate = db.Column(db.Numeric(18, 4), nullable=True)
    assigned_project_ids = db.Column(JSONB, nullable=True)  # list of project UUIDs, as strings
    status = db.Column(db.String(16), nullable=False, default="active")

    __table_args__ = (
        db.CheckConstraint(f"employment_type IN {EMPLOYMENT_TYPES}", name="ck_wfm_employees_employment_type"),
        db.CheckConstraint(f"status IN {WORKER_STATUSES}", name="ck_wfm_employees_status"),
    )


class CasualWorker(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-02: minimal-field, same-day-engagement daily labor record."""

    __tablename__ = "wfm_casual_workers"

    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(32), nullable=True)
    id_number = db.Column(db.String(64), nullable=True)
    daily_rate = db.Column(db.Numeric(18, 4), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="active")
    onboarded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    onboarded_by = db.Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {WORKER_STATUSES}", name="ck_wfm_casual_workers_status"),)


class AttendanceRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-03: per project per day, from manual/QR/biometric capture."""

    __tablename__ = "wfm_attendance_records"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=True, index=True)
    casual_worker_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_casual_workers.id"), nullable=True, index=True)

    attendance_date = db.Column(db.Date, nullable=False, index=True)
    check_in_at = db.Column(db.DateTime(timezone=True), nullable=True)
    check_out_at = db.Column(db.DateTime(timezone=True), nullable=True)
    capture_method = db.Column(db.String(16), nullable=False, default="manual")

    __table_args__ = (
        db.CheckConstraint(f"capture_method IN {CAPTURE_METHODS}", name="ck_wfm_attendance_capture_method"),
        db.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_wfm_attendance_exactly_one_worker",
        ),
    )


class Timesheet(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-04: generated from attendance + activity assignment,
    supporting time-based or piece-rate pay. `project_id`/`activity_id`
    are what WFM-12's labor cost allocation groups by."""

    __tablename__ = "wfm_timesheets"

    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=True, index=True)
    casual_worker_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_casual_workers.id"), nullable=True, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    activity_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # pln_activities.id, loose reference
    payroll_run_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_payroll_runs.id"), nullable=True, index=True)

    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    pay_basis = db.Column(db.String(16), nullable=False, default="time_based")
    hours_or_units = db.Column(db.Numeric(10, 2), nullable=False)
    rate_applied = db.Column(db.Numeric(18, 4), nullable=False)
    gross_amount = db.Column(db.Numeric(18, 4), nullable=False)

    status = db.Column(db.String(16), nullable=False, default="pending_approval", index=True)
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"pay_basis IN {PAY_BASES}", name="ck_wfm_timesheets_pay_basis"),
        db.CheckConstraint(f"status IN {TIMESHEET_STATUSES}", name="ck_wfm_timesheets_status"),
        db.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_wfm_timesheets_exactly_one_worker",
        ),
    )


class LeaveRequest(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-05: leave types are tenant-configurable strings, not a fixed
    enum, per the SRS's "distinguishing leave types per tenant policy"."""

    __tablename__ = "wfm_leave_requests"

    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=False, index=True)
    leave_type = db.Column(db.String(64), nullable=False)  # e.g. "annual", "sick", "compassionate"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"status IN {LEAVE_STATUSES}", name="ck_wfm_leave_requests_status"),)


class TrainingRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-06: course/provider/completion, with optional expiry (e.g.
    first-aid refreshers)."""

    __tablename__ = "wfm_training_records"

    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=False, index=True)
    course_name = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(255), nullable=True)
    completion_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)


class MedicalRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-07: business rule -- access restricted at the field level to
    HR/HSE roles regardless of general permissions (enforced in
    routes.py via a distinct `wfm:medical` permission gate)."""

    __tablename__ = "wfm_medical_records"

    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=False, index=True)
    fitness_status = db.Column(db.String(24), nullable=False)
    assessed_at = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    restricted_details = db.Column(db.Text, nullable=True)  # the actual sensitive detail
    assessed_by = db.Column(db.String(255), nullable=True)

    __table_args__ = (db.CheckConstraint(f"fitness_status IN {FITNESS_STATUSES}", name="ck_wfm_medical_fitness_status"),)


class Competency(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-08: skills/equipment authorizations, referenced by Module
    9's operator-assignment check and Module 13/14 role qualifications
    -- via services.get_active_certification, not a direct table
    reference (see module docstring)."""

    __tablename__ = "wfm_competencies"

    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=False, index=True)
    skill_or_equipment_type = db.Column(db.String(128), nullable=False)
    proficiency_level = db.Column(db.String(32), nullable=True)
    verified_by = db.Column(db.String(255), nullable=True)
    verified_at = db.Column(db.Date, nullable=True)


class Certification(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-09: expiry-tracked certifications (crane operator license,
    scaffold certificate, etc.)."""

    __tablename__ = "wfm_certifications"

    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=False, index=True)
    certification_type = db.Column(db.String(128), nullable=False, index=True)
    certificate_number = db.Column(db.String(128), nullable=True)
    issued_at = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    issuing_body = db.Column(db.String(255), nullable=True)


class StatutoryDeductionRule(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """The configurable-per-jurisdiction deduction rules WFM-10 applies
    when running payroll."""

    __tablename__ = "wfm_statutory_deduction_rules"

    name = db.Column(db.String(128), nullable=False)  # e.g. "PAYE", "Pension"
    calculation_type = db.Column(db.String(16), nullable=False, default="percentage")
    rate_or_amount = db.Column(db.Numeric(10, 4), nullable=False)  # percentage points, or a fixed currency amount
    applies_to_casuals = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.CheckConstraint(f"calculation_type IN {DEDUCTION_CALC_TYPES}", name="ck_wfm_deduction_calc_type"),
    )


class PayrollRun(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """WFM-10: business rule -- cannot be finalized while any linked
    timesheet remains in "pending_approval" status."""

    __tablename__ = "wfm_payroll_runs"

    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")
    finalized_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finalized_by = db.Column(UUID(as_uuid=True), nullable=True)

    total_gross = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    total_deductions = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    total_net = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    lines = relationship("PayrollLine", back_populates="payroll_run", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"status IN {PAYROLL_STATUSES}", name="ck_wfm_payroll_runs_status"),
        db.UniqueConstraint("tenant_id", "period_start", "period_end", name="uq_wfm_payroll_runs_period"),
    )


class PayrollLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One worker's computed pay within a PayrollRun."""

    __tablename__ = "wfm_payroll_lines"

    payroll_run_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_payroll_runs.id"), nullable=False, index=True)
    employee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_employees.id"), nullable=True, index=True)
    casual_worker_id = db.Column(UUID(as_uuid=True), db.ForeignKey("wfm_casual_workers.id"), nullable=True, index=True)

    gross_pay = db.Column(db.Numeric(18, 4), nullable=False)
    deductions_breakdown = db.Column(JSONB, nullable=True)  # {"PAYE": 12000, "Pension": 8000, ...}
    total_deductions = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    net_pay = db.Column(db.Numeric(18, 4), nullable=False)
    bank_account_ref = db.Column(db.String(128), nullable=True)

    payroll_run = relationship("PayrollRun", back_populates="lines")

    __table_args__ = (
        db.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_wfm_payroll_lines_exactly_one_worker",
        ),
    )
