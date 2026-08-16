"""exd module tables

Revision ID: 0022_exd
Revises: 0021_ast
Create Date: 2026-07-30

Creates the tables defined in app/modules/exd/models.py (SRS Section
4.21) and enables Row-Level Security + FORCE + the tenant_isolation
policy on both of them, per SRS Section 5.5. Only two tables --
per the SRS's own framing, this module introduces no new core business
entities beyond widget/configuration metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_exd"
down_revision = "0021_ast"
branch_labels = None
depends_on = None


EXD_TABLES = [
    "exd_dashboard_widgets",
    "exd_dashboard_configurations",
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
        "exd_dashboard_widgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("widget_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("configuration", postgresql.JSONB, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "widget_type IN ('company_revenue','project_profitability','cash_position','equipment_utilization',"
            "'safety_score','active_projects','tender_pipeline','ar_ap_aging','profit_margin_trend',"
            "'labor_productivity','project_risks')",
            name="ck_exd_widget_type",
        ),
    )

    op.create_table(
        "exd_dashboard_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("role_name", sa.String(128), nullable=False),
        sa.Column("widget_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("region_project_ids", postgresql.JSONB, nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("tenant_id", "role_name", name="uq_exd_config_tenant_role"),
    )

    for table in EXD_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(EXD_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("exd_dashboard_configurations")
    op.drop_table("exd_dashboard_widgets")
