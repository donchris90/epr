"""pln module tables

Revision ID: 0006_pln
Revises: 0005_ctm
Create Date: 2026-07-26

Creates the tables defined in app/modules/pln/models.py (SRS Section 4.5)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_pln"
down_revision = "0005_ctm"
branch_labels = None
depends_on = None


PLN_TABLES = [
    "pln_wbs_nodes",
    "pln_activities",
    "pln_activity_dependencies",
    "pln_resource_assignments",
    "pln_baselines",
    "pln_baseline_activity_snapshots",
    "pln_look_ahead_plans",
    "pln_look_ahead_items",
    "pln_delay_events",
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
        "pln_wbs_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("cbs_line_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *_audit_columns(),
    )
    op.create_foreign_key("fk_pln_wbs_nodes_parent", "pln_wbs_nodes", "pln_wbs_nodes", ["parent_id"], ["id"])

    op.create_table(
        "pln_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("wbs_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_wbs_nodes.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("planned_start", sa.Date, nullable=False),
        sa.Column("duration_days", sa.Integer, nullable=False),
        sa.Column("percent_complete", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("early_start", sa.Date, nullable=True),
        sa.Column("early_finish", sa.Date, nullable=True),
        sa.Column("late_start", sa.Date, nullable=True),
        sa.Column("late_finish", sa.Date, nullable=True),
        sa.Column("total_float_days", sa.Integer, nullable=True),
        sa.Column("is_critical", sa.Boolean, nullable=False, server_default=sa.false(), index=True),
        *_audit_columns(),
        sa.CheckConstraint("duration_days > 0", name="ck_pln_activities_duration_positive"),
        sa.CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_pln_activities_pct_range"),
    )

    op.create_table(
        "pln_activity_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("predecessor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_activities.id"), nullable=False, index=True),
        sa.Column("successor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_activities.id"), nullable=False, index=True),
        sa.Column("dependency_type", sa.String(2), nullable=False, server_default="FS"),
        sa.Column("lag_days", sa.Integer, nullable=False, server_default="0"),
        *_audit_columns(),
        sa.CheckConstraint("dependency_type IN ('FS','SS','FF','SF')", name="ck_pln_activity_deps_type"),
        sa.CheckConstraint("predecessor_id != successor_id", name="ck_pln_activity_deps_no_self_loop"),
        sa.UniqueConstraint("predecessor_id", "successor_id", name="uq_pln_activity_deps_pair"),
    )

    op.create_table(
        "pln_resource_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_activities.id"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(16), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(32), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("resource_type IN ('labor','equipment','material')", name="ck_pln_resource_assignments_type"),
    )

    op.create_table(
        "pln_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "pln_baseline_activity_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("baseline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_baselines.id"), nullable=False, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("planned_start", sa.Date, nullable=False),
        sa.Column("planned_finish", sa.Date, nullable=False),
        sa.Column("duration_days", sa.Integer, nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "pln_look_ahead_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("plan_type", sa.String(16), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("plan_type IN ('two_week','six_week')", name="ck_pln_look_ahead_type"),
    )

    op.create_table(
        "pln_look_ahead_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_look_ahead_plans.id"), nullable=False, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_activities.id"), nullable=False, index=True),
        sa.Column("adjusted_start", sa.Date, nullable=True),
        sa.Column("adjusted_end", sa.Date, nullable=True),
        sa.Column("site_notes", sa.Text, nullable=True),
        sa.Column("constraint_flag", sa.String(64), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "pln_delay_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pln_activities.id"), nullable=True),
        sa.Column("cause_classification", sa.String(16), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("delay_days", sa.Integer, nullable=False),
        sa.Column("analysis_method", sa.String(64), nullable=True),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("affected_critical_path", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("flagged_for_review", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.CheckConstraint(
            "cause_classification IN ('client','contractor','weather','force_majeure')",
            name="ck_pln_delay_events_cause",
        ),
    )

    for table in PLN_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(PLN_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("pln_delay_events")
    op.drop_table("pln_look_ahead_items")
    op.drop_table("pln_look_ahead_plans")
    op.drop_table("pln_baseline_activity_snapshots")
    op.drop_table("pln_baselines")
    op.drop_table("pln_resource_assignments")
    op.drop_table("pln_activity_dependencies")
    op.drop_table("pln_activities")
    op.drop_constraint("fk_pln_wbs_nodes_parent", "pln_wbs_nodes", type_="foreignkey")
    op.drop_table("pln_wbs_nodes")
