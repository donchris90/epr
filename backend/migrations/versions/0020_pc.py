"""pc module tables

Revision ID: 0020_pc
Revises: 0019_bil
Create Date: 2026-07-30

Creates the tables defined in app/modules/pc/models.py (SRS Section
4.19) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020_pc"
down_revision = "0019_bil"
branch_labels = None
depends_on = None


PC_TABLES = [
    "pc_evm_snapshots",
    "pc_forecasts_at_completion",
    "pc_risk_register_entries",
    "pc_delay_analysis_summaries",
    "pc_project_cash_flow_forecasts",
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
        "pc_evm_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period_end", sa.Date, nullable=False, index=True),
        sa.Column("baseline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("planned_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("earned_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("actual_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("budget_at_completion", sa.Numeric(18, 4), nullable=False),
        sa.Column("cost_variance", sa.Numeric(18, 4), nullable=False),
        sa.Column("schedule_variance", sa.Numeric(18, 4), nullable=False),
        sa.Column("cpi", sa.Numeric(8, 4), nullable=True),
        sa.Column("spi", sa.Numeric(8, 4), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculated_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pc_forecasts_at_completion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("evm_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pc_evm_snapshots.id"), nullable=False, index=True),
        sa.Column("method", sa.String(24), nullable=False, server_default="cpi_based"),
        sa.Column("estimate_at_completion", sa.Numeric(18, 4), nullable=False),
        sa.Column("estimate_to_complete", sa.Numeric(18, 4), nullable=False),
        sa.Column("variance_at_completion", sa.Numeric(18, 4), nullable=False),
        sa.Column("manual_reestimate_reason", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("method IN ('cpi_based','atypical_variance','manual')", name="ck_pc_forecast_method"),
    )

    op.create_table(
        "pc_risk_register_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("probability", sa.Numeric(5, 4), nullable=False),
        sa.Column("impact_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("exposure_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("mitigation_owner", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("identified_at", sa.Date, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("probability >= 0 AND probability <= 1", name="ck_pc_risk_probability_range"),
        sa.CheckConstraint("status IN ('open','mitigated','closed')", name="ck_pc_risk_status"),
    )

    op.create_table(
        "pc_delay_analysis_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("evm_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pc_evm_snapshots.id"), nullable=True),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("total_float_consumed_days", sa.Integer, nullable=True),
        sa.Column("critical_path_delay_days", sa.Integer, nullable=True),
        sa.Column("classification", sa.String(16), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "classification IN ('schedule_driven','cost_driven','both','neither')", name="ck_pc_delay_classification"
        ),
    )

    op.create_table(
        "pc_project_cash_flow_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("committed_costs", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("planned_billing", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_cash_flow", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    for table in PC_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(PC_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("pc_project_cash_flow_forecasts")
    op.drop_table("pc_delay_analysis_summaries")
    op.drop_table("pc_risk_register_entries")
    op.drop_table("pc_forecasts_at_completion")
    op.drop_table("pc_evm_snapshots")
