"""qms module tables

Revision ID: 0014_qms
Revises: 0013_sub
Create Date: 2026-07-30

Creates the tables defined in app/modules/qms/models.py (SRS Section
4.13) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_qms"
down_revision = "0013_sub"
branch_labels = None
depends_on = None


QMS_TABLES = [
    "qms_itps",
    "qms_itp_hold_points",
    "qms_material_approvals",
    "qms_lab_results",
    "qms_ncrs",
    "qms_corrective_actions",
    "qms_punch_list_items",
    "qms_snag_list_items",
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
        "qms_itps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("activity_type", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_qms_itps_status"),
    )

    op.create_table(
        "qms_itp_hold_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("itp_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("qms_itps.id"), nullable=False, index=True),
        sa.Column("sequence_order", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("required_check", sa.Text, nullable=True),
        sa.Column("acceptance_criteria", sa.Text, nullable=True),
        sa.Column("is_mandatory_hold", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("inspection_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_recorded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concession_reason", sa.Text, nullable=True),
        sa.Column("concession_approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("concession_approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('pending','passed','failed','concession_approved')", name="ck_qms_hold_points_status"
        ),
        sa.UniqueConstraint("itp_id", "sequence_order", name="uq_qms_hold_points_itp_order"),
    )

    op.create_table(
        "qms_material_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("material_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("submittal_reference", sa.String(128), nullable=False),
        sa.Column("technical_data_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('submitted','approved','rejected')", name="ck_qms_material_approvals_status"),
    )

    op.create_table(
        "qms_lab_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("pour_or_lot_reference", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("test_type", sa.String(32), nullable=False),
        sa.Column("sample_reference", sa.String(128), nullable=True),
        sa.Column("tested_at", sa.Date, nullable=True),
        sa.Column("result_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("acceptance_threshold", sa.Numeric(12, 4), nullable=True),
        sa.Column("pass_fail", sa.Boolean, nullable=True),
        sa.Column("lab_name", sa.String(255), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "test_type IN ('concrete_cube_strength','compaction_density','asphalt_extraction','other')",
            name="ck_qms_lab_results_test_type",
        ),
    )

    op.create_table(
        "qms_ncrs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("photo_document_ids", postgresql.JSONB, nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("disposition", sa.String(16), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("raised_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "disposition IS NULL OR disposition IN ('rework','accept_as_is','reject')", name="ck_qms_ncrs_disposition"
        ),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_qms_ncrs_status"),
    )

    op.create_table(
        "qms_corrective_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("ncr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("qms_ncrs.id"), nullable=True, index=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="ncr"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("source IN ('ncr','audit')", name="ck_qms_corrective_actions_source"),
        sa.CheckConstraint("status IN ('open','completed','verified')", name="ck_qms_corrective_actions_status"),
    )

    op.create_table(
        "qms_punch_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("area_building_section", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_qms_punch_list_status"),
    )

    op.create_table(
        "qms_snag_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("area_building_section", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_qms_snag_list_status"),
    )

    for table in QMS_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(QMS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("qms_snag_list_items")
    op.drop_table("qms_punch_list_items")
    op.drop_table("qms_corrective_actions")
    op.drop_table("qms_ncrs")
    op.drop_table("qms_lab_results")
    op.drop_table("qms_material_approvals")
    op.drop_table("qms_itp_hold_points")
    op.drop_table("qms_itps")
