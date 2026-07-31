"""wfm module tables

Revision ID: 0012_wfm
Revises: 0011_fuel
Create Date: 2026-07-29

Creates the tables defined in app/modules/wfm/models.py (SRS Section
4.11) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.

Table order matters here: PayrollRun must exist before Timesheet, since
Timesheet.payroll_run_id is a foreign key to it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_wfm"
down_revision = "0011_fuel"
branch_labels = None
depends_on = None


WFM_TABLES = [
    "wfm_employees",
    "wfm_casual_workers",
    "wfm_payroll_runs",
    "wfm_attendance_records",
    "wfm_timesheets",
    "wfm_leave_requests",
    "wfm_training_records",
    "wfm_medical_records",
    "wfm_competencies",
    "wfm_certifications",
    "wfm_statutory_deduction_rules",
    "wfm_payroll_lines",
]


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _enable_rls(table_name: str):
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade():
    op.create_table(
        "wfm_employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("employee_number", sa.String(64), nullable=True),
        sa.Column("role", sa.String(128), nullable=True),
        sa.Column("trade", sa.String(128), nullable=True),
        sa.Column("pay_grade", sa.String(32), nullable=True),
        sa.Column("employment_type", sa.String(16), nullable=False, server_default="permanent"),
        sa.Column("monthly_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("assigned_project_ids", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("employment_type IN ('permanent','contract')", name="ck_wfm_employees_employment_type"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_wfm_employees_status"),
    )

    op.create_table(
        "wfm_casual_workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("id_number", sa.String(64), nullable=True),
        sa.Column("daily_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("onboarded_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_wfm_casual_workers_status"),
    )

    op.create_table(
        "wfm_payroll_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("total_gross", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_deductions", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_net", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','finalized')", name="ck_wfm_payroll_runs_status"),
        sa.UniqueConstraint("tenant_id", "period_start", "period_end", name="uq_wfm_payroll_runs_period"),
    )

    op.create_table(
        "wfm_attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=True, index=True),
        sa.Column("casual_worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_casual_workers.id"), nullable=True, index=True),
        sa.Column("attendance_date", sa.Date, nullable=False, index=True),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_method", sa.String(16), nullable=False, server_default="manual"),
        *_audit_columns(),
        sa.CheckConstraint("capture_method IN ('manual','qr','biometric')", name="ck_wfm_attendance_capture_method"),
        sa.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_wfm_attendance_exactly_one_worker",
        ),
    )

    op.create_table(
        "wfm_timesheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=True, index=True),
        sa.Column("casual_worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_casual_workers.id"), nullable=True, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_payroll_runs.id"), nullable=True, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("pay_basis", sa.String(16), nullable=False, server_default="time_based"),
        sa.Column("hours_or_units", sa.Numeric(10, 2), nullable=False),
        sa.Column("rate_applied", sa.Numeric(18, 4), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending_approval", index=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("pay_basis IN ('time_based','piece_rate')", name="ck_wfm_timesheets_pay_basis"),
        sa.CheckConstraint("status IN ('pending_approval','approved','rejected')", name="ck_wfm_timesheets_status"),
        sa.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_wfm_timesheets_exactly_one_worker",
        ),
    )

    op.create_table(
        "wfm_leave_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=False, index=True),
        sa.Column("leave_type", sa.String(64), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_wfm_leave_requests_status"),
    )

    op.create_table(
        "wfm_training_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=False, index=True),
        sa.Column("course_name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(255), nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True, index=True),
        *_audit_columns(),
    )

    op.create_table(
        "wfm_medical_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=False, index=True),
        sa.Column("fitness_status", sa.String(24), nullable=False),
        sa.Column("assessed_at", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("restricted_details", sa.Text, nullable=True),
        sa.Column("assessed_by", sa.String(255), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("fitness_status IN ('fit','fit_with_restrictions','unfit')", name="ck_wfm_medical_fitness_status"),
    )

    op.create_table(
        "wfm_competencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=False, index=True),
        sa.Column("skill_or_equipment_type", sa.String(128), nullable=False),
        sa.Column("proficiency_level", sa.String(32), nullable=True),
        sa.Column("verified_by", sa.String(255), nullable=True),
        sa.Column("verified_at", sa.Date, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "wfm_certifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=False, index=True),
        sa.Column("certification_type", sa.String(128), nullable=False, index=True),
        sa.Column("certificate_number", sa.String(128), nullable=True),
        sa.Column("issued_at", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True, index=True),
        sa.Column("issuing_body", sa.String(255), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "wfm_statutory_deduction_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("calculation_type", sa.String(16), nullable=False, server_default="percentage"),
        sa.Column("rate_or_amount", sa.Numeric(10, 4), nullable=False),
        sa.Column("applies_to_casuals", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.CheckConstraint("calculation_type IN ('percentage','fixed')", name="ck_wfm_deduction_calc_type"),
    )

    op.create_table(
        "wfm_payroll_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_payroll_runs.id"), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=True, index=True),
        sa.Column("casual_worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_casual_workers.id"), nullable=True, index=True),
        sa.Column("gross_pay", sa.Numeric(18, 4), nullable=False),
        sa.Column("deductions_breakdown", postgresql.JSONB, nullable=True),
        sa.Column("total_deductions", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_pay", sa.Numeric(18, 4), nullable=False),
        sa.Column("bank_account_ref", sa.String(128), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "(employee_id IS NOT NULL AND casual_worker_id IS NULL) OR "
            "(employee_id IS NULL AND casual_worker_id IS NOT NULL)",
            name="ck_wfm_payroll_lines_exactly_one_worker",
        ),
    )

    for table in WFM_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(WFM_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("wfm_payroll_lines")
    op.drop_table("wfm_statutory_deduction_rules")
    op.drop_table("wfm_certifications")
    op.drop_table("wfm_competencies")
    op.drop_table("wfm_medical_records")
    op.drop_table("wfm_training_records")
    op.drop_table("wfm_leave_requests")
    op.drop_table("wfm_timesheets")
    op.drop_table("wfm_attendance_records")
    op.drop_table("wfm_payroll_runs")
    op.drop_table("wfm_casual_workers")
    op.drop_table("wfm_employees")
