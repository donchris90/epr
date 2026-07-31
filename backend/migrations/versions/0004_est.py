"""est module tables

Revision ID: 0004_est
Revises: 0003_tbm
Create Date: 2026-07-24

Creates the tables defined in app/modules/est/models.py (SRS Section 4.3)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_est"
down_revision = "0003_tbm"
branch_labels = None
depends_on = None


EST_TABLES = [
    "est_estimate_versions",
    "est_boq_items",
    "est_cost_library_items",
    "est_material_prices",
    "est_equipment_rates",
    "est_labor_rates",
    "est_vendor_quotations",
    "est_rate_analyses",
    "est_rate_analysis_lines",
    "est_markups",
    "est_contingency_items",
    "est_cost_breakdown_structures",
    "est_cbs_line_items",
    "est_budget_revisions",
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
        "est_estimate_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','submitted','superseded')", name="ck_est_estimate_versions_status"),
        sa.UniqueConstraint("tender_id", "version_number", name="uq_est_estimate_versions_tender_version"),
    )

    op.create_table(
        "est_boq_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "estimate_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_estimate_versions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("source_tender_boq_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("item_code", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_rate", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
    )
    op.create_foreign_key("fk_est_boq_items_parent", "est_boq_items", "est_boq_items", ["parent_id"], ["id"])

    op.create_table(
        "est_cost_library_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("component_type", sa.String(16), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("default_unit_cost", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "component_type IN ('material','labor','equipment','subcontract')",
            name="ck_est_cost_library_items_type",
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_est_cost_library_items_tenant_code"),
    )

    op.create_table(
        "est_material_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "cost_library_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("est_cost_library_items.id"), nullable=True
        ),
        sa.Column("material_name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        "ix_est_material_prices_tenant_material_date",
        "est_material_prices",
        ["tenant_id", "material_name", "effective_date"],
    )

    op.create_table(
        "est_equipment_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("equipment_type", sa.String(128), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="owned"),
        sa.Column("cost_per_hour", sa.Numeric(18, 4), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("source IN ('owned','rental')", name="ck_est_equipment_rates_source"),
    )

    op.create_table(
        "est_labor_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("trade", sa.String(128), nullable=False),
        sa.Column("grade", sa.String(64), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("statutory_oncost_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "est_vendor_quotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("boq_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("est_boq_items.id"), nullable=True, index=True),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("quoted_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("quoted_at", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("is_accepted", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "est_rate_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "boq_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_boq_items.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        *_audit_columns(),
    )

    op.create_table(
        "est_rate_analysis_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "rate_analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("est_rate_analyses.id"), nullable=False, index=True
        ),
        sa.Column(
            "cost_library_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("est_cost_library_items.id"), nullable=True
        ),
        sa.Column("component_type", sa.String(16), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "component_type IN ('material','labor','equipment','subcontract')",
            name="ck_est_rate_analysis_lines_type",
        ),
    )

    op.create_table(
        "est_markups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "estimate_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_estimate_versions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("scope", sa.String(16), nullable=False, server_default="whole_tender"),
        sa.Column("target_boq_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("est_boq_items.id"), nullable=True),
        sa.Column("overhead_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("profit_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.CheckConstraint("scope IN ('whole_tender','section','item')", name="ck_est_markups_scope"),
    )

    op.create_table(
        "est_contingency_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "estimate_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_estimate_versions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("basis", sa.String(16), nullable=False, server_default="percentage"),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("kind IN ('contingency','risk_allowance')", name="ck_est_contingency_items_kind"),
        sa.CheckConstraint("basis IN ('percentage','fixed')", name="ck_est_contingency_items_basis"),
    )

    op.create_table(
        "est_cost_breakdown_structures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column(
            "source_estimate_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_estimate_versions.id"),
            nullable=False,
        ),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "est_cbs_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "cbs_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_cost_breakdown_structures.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("source_boq_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("budgeted_amount", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "est_budget_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "cbs_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("est_cost_breakdown_structures.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("cbs_line_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("est_cbs_line_items.id"), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("previous_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("revised_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    for table in EST_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(EST_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("est_budget_revisions")
    op.drop_table("est_cbs_line_items")
    op.drop_table("est_cost_breakdown_structures")
    op.drop_table("est_contingency_items")
    op.drop_table("est_markups")
    op.drop_table("est_rate_analysis_lines")
    op.drop_table("est_rate_analyses")
    op.drop_table("est_vendor_quotations")
    op.drop_table("est_labor_rates")
    op.drop_table("est_equipment_rates")
    op.drop_table("est_material_prices")
    op.drop_table("est_cost_library_items")
    op.drop_constraint("fk_est_boq_items_parent", "est_boq_items", type_="foreignkey")
    op.drop_table("est_boq_items")
    op.drop_table("est_estimate_versions")
