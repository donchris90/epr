"""wfm leave entitlements

Revision ID: 0055_wfm_leave_entitlements
Revises: 0054_dsar_requests
Create Date: 2026-10-26

Per-employee, per-leave-type, per-year allowance (days), so the leave
balance can show days remaining. RLS-isolated like every tenant table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0055_wfm_leave_entitlements"
down_revision = "0054_dsar_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wfm_leave_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wfm_employees.id"), nullable=False, index=True),
        sa.Column("leave_type", sa.String(64), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("days", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "employee_id", "leave_type", "year", name="uq_wfm_leave_entitlements_emp_type_year"),
        sa.CheckConstraint("days >= 0", name="ck_wfm_leave_entitlements_days"),
    )
    op.execute("ALTER TABLE wfm_leave_entitlements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wfm_leave_entitlements FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON wfm_leave_entitlements "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON wfm_leave_entitlements")
    op.drop_table("wfm_leave_entitlements")
