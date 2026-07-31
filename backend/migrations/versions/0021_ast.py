"""ast module tables

Revision ID: 0021_ast
Revises: 0020_pc
Create Date: 2026-07-30

Creates the tables defined in app/modules/ast/models.py (SRS Section
4.20) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_ast"
down_revision = "0020_pc"
branch_labels = None
depends_on = None


AST_TABLES = [
    "ast_assets",
    "ast_maintenance_schedules",
    "ast_asset_inspections",
    "ast_warranty_records",
    "ast_defects_liability_records",
    "ast_defect_items",
    "ast_lifecycle_cost_records",
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
        "ast_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("parent_asset_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("as_built_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_category", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category_attributes", postgresql.JSONB, nullable=True),
        sa.Column("baseline_data", postgresql.JSONB, nullable=True),
        sa.Column("handover_date", sa.Date, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("asset_category IN ('building','road','bridge','drainage','utility')", name="ck_ast_assets_category"),
    )
    op.create_foreign_key("fk_ast_assets_parent", "ast_assets", "ast_assets", ["parent_asset_id"], ["id"])

    op.create_table(
        "ast_maintenance_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ast_assets.id"), nullable=False, index=True),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("task_type", sa.String(16), nullable=False, server_default="routine"),
        sa.Column("frequency_days", sa.Integer, nullable=True),
        sa.Column("next_due_date", sa.Date, nullable=True, index=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("task_type IN ('routine','periodic')", name="ck_ast_maint_task_type"),
    )

    op.create_table(
        "ast_asset_inspections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ast_assets.id"), nullable=False, index=True),
        sa.Column("inspected_at", sa.Date, nullable=True),
        sa.Column("condition_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("inspector_name", sa.String(255), nullable=True),
        sa.Column("photo_document_ids", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "ast_warranty_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ast_assets.id"), nullable=False, index=True),
        sa.Column("component_name", sa.String(255), nullable=True),
        sa.Column("warranty_provider", sa.String(255), nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        *_audit_columns(),
    )

    op.create_table(
        "ast_defects_liability_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ast_assets.id"), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("dlp_start", sa.Date, nullable=True),
        sa.Column("dlp_end", sa.Date, nullable=True),
        sa.Column("retention_released", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "ast_defect_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("dlp_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ast_defects_liability_records.id"), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("raised_at", sa.Date, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('open','resolved','verified')", name="ck_ast_defect_status"),
    )

    op.create_table(
        "ast_lifecycle_cost_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ast_assets.id"), nullable=False, index=True),
        sa.Column("cost_type", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("incurred_at", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("cost_type IN ('maintenance','rehabilitation')", name="ck_ast_lifecycle_cost_type"),
    )

    for table in AST_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(AST_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("ast_lifecycle_cost_records")
    op.drop_table("ast_defect_items")
    op.drop_table("ast_defects_liability_records")
    op.drop_table("ast_warranty_records")
    op.drop_table("ast_asset_inspections")
    op.drop_table("ast_maintenance_schedules")
    op.drop_constraint("fk_ast_assets_parent", "ast_assets", type_="foreignkey")
    op.drop_table("ast_assets")
