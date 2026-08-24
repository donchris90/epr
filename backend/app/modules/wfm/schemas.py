"""
Module 11 — Workforce Management (Code: WFM)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.wfm.models import (
    EMPLOYMENT_TYPES,
    CAPTURE_METHODS,
    PAY_BASES,
    FITNESS_STATUSES,
    DEDUCTION_CALC_TYPES,
)


class EmployeeSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    employee_number = fields.Str(allow_none=True)
    role = fields.Str(allow_none=True)
    trade = fields.Str(allow_none=True)
    pay_grade = fields.Str(allow_none=True)
    employment_type = fields.Str(load_default="permanent", validate=validate.OneOf(EMPLOYMENT_TYPES))
    monthly_rate = fields.Decimal(allow_none=True, as_string=True)
    assigned_project_ids = fields.List(fields.UUID(), allow_none=True)
    status = fields.Str(dump_only=True)


class EmployeeUpdateSchema(Schema):
    """Every field optional -- a real partial update, not a full
    replace; omitted fields are left untouched (see
    services.update_employee)."""

    name = fields.Str(allow_none=True)
    employee_number = fields.Str(allow_none=True)
    role = fields.Str(allow_none=True)
    trade = fields.Str(allow_none=True)
    pay_grade = fields.Str(allow_none=True)
    employment_type = fields.Str(allow_none=True, validate=validate.OneOf(EMPLOYMENT_TYPES))
    monthly_rate = fields.Decimal(allow_none=True, as_string=True)


class AssignProjectSchema(Schema):
    project_id = fields.UUID(required=True)


class TransferProjectSchema(Schema):
    from_project_id = fields.UUID(required=True)
    to_project_id = fields.UUID(required=True)


class CasualWorkerSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    phone = fields.Str(allow_none=True)
    id_number = fields.Str(allow_none=True)
    daily_rate = fields.Decimal(allow_none=True, as_string=True)
    status = fields.Str(dump_only=True)


class AttendanceRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)
    employee_id = fields.UUID(allow_none=True, load_default=None)
    casual_worker_id = fields.UUID(allow_none=True, load_default=None)
    attendance_date = fields.Date(required=True)
    check_in_at = fields.DateTime(allow_none=True)
    check_out_at = fields.DateTime(allow_none=True)
    capture_method = fields.Str(load_default="manual", validate=validate.OneOf(CAPTURE_METHODS))


class AttendanceCorrectionSchema(Schema):
    check_in_at = fields.DateTime(allow_none=True)
    check_out_at = fields.DateTime(allow_none=True)


class MarkAbsentSchema(Schema):
    project_id = fields.UUID(required=True)
    attendance_date = fields.Date(required=True)
    employee_id = fields.UUID(allow_none=True, load_default=None)
    casual_worker_id = fields.UUID(allow_none=True, load_default=None)


class GenerateTimesheetSchema(Schema):
    employee_id = fields.UUID(allow_none=True, load_default=None)
    casual_worker_id = fields.UUID(allow_none=True, load_default=None)
    project_id = fields.UUID(allow_none=True, load_default=None)
    activity_id = fields.UUID(allow_none=True, load_default=None)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    pay_basis = fields.Str(load_default="time_based", validate=validate.OneOf(PAY_BASES))
    hours_or_units = fields.Decimal(required=True, as_string=True)
    rate_applied = fields.Decimal(required=True, as_string=True)


class TimesheetSchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    casual_worker_id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    activity_id = fields.UUID(dump_only=True)
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    pay_basis = fields.Str(dump_only=True)
    hours_or_units = fields.Decimal(dump_only=True, as_string=True)
    rate_applied = fields.Decimal(dump_only=True, as_string=True)
    gross_amount = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    approved_by = fields.UUID(dump_only=True, allow_none=True)
    approved_at = fields.DateTime(dump_only=True, allow_none=True)
    payroll_run_id = fields.UUID(dump_only=True, allow_none=True)


class TimesheetUpdateSchema(Schema):
    hours_or_units = fields.Decimal(allow_none=True, as_string=True)
    rate_applied = fields.Decimal(allow_none=True, as_string=True)


class LeaveRequestInputSchema(Schema):
    employee_id = fields.UUID(required=True)
    leave_type = fields.Str(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    reason = fields.Str(allow_none=True)


class LeaveRequestSchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    leave_type = fields.Str(dump_only=True)
    start_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)
    reason = fields.Str(dump_only=True, allow_none=True)
    status = fields.Str(dump_only=True)
    approved_by = fields.UUID(dump_only=True, allow_none=True)
    approved_at = fields.DateTime(dump_only=True, allow_none=True)


class LeaveDecisionSchema(Schema):
    decision = fields.Str(required=True, validate=validate.OneOf(("approved", "rejected")))


class TrainingRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    course_name = fields.Str(required=True)
    provider = fields.Str(allow_none=True)
    completion_date = fields.Date(allow_none=True)
    expiry_date = fields.Date(allow_none=True)


class MedicalRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    fitness_status = fields.Str(required=True, validate=validate.OneOf(FITNESS_STATUSES))
    assessed_at = fields.Date(allow_none=True)
    expiry_date = fields.Date(allow_none=True)
    restricted_details = fields.Str(allow_none=True)
    assessed_by = fields.Str(allow_none=True)


class CompetencySchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    skill_or_equipment_type = fields.Str(required=True)
    proficiency_level = fields.Str(allow_none=True)
    verified_by = fields.Str(allow_none=True)
    verified_at = fields.Date(allow_none=True)


class CertificationSchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    certification_type = fields.Str(required=True)
    certificate_number = fields.Str(allow_none=True)
    issued_at = fields.Date(allow_none=True)
    expiry_date = fields.Date(allow_none=True)
    issuing_body = fields.Str(allow_none=True)


class StatutoryDeductionRuleSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    calculation_type = fields.Str(load_default="percentage", validate=validate.OneOf(DEDUCTION_CALC_TYPES))
    rate_or_amount = fields.Decimal(required=True, as_string=True)
    applies_to_casuals = fields.Bool(load_default=False)


class GeneratePayrollRunSchema(Schema):
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)


class PayrollLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    employee_id = fields.UUID(dump_only=True)
    casual_worker_id = fields.UUID(dump_only=True)
    gross_pay = fields.Decimal(dump_only=True, as_string=True)
    deductions_breakdown = fields.Dict(dump_only=True)
    total_deductions = fields.Decimal(dump_only=True, as_string=True)
    net_pay = fields.Decimal(dump_only=True, as_string=True)
    bank_account_ref = fields.Str(dump_only=True, allow_none=True)


class PayrollRunSchema(Schema):
    id = fields.UUID(dump_only=True)
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    status = fields.Str(dump_only=True)
    total_gross = fields.Decimal(dump_only=True, as_string=True)
    total_deductions = fields.Decimal(dump_only=True, as_string=True)
    total_net = fields.Decimal(dump_only=True, as_string=True)
    lines = fields.List(fields.Nested(PayrollLineSchema), dump_only=True)
