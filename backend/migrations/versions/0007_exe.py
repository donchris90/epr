"""exe module tables

Revision ID: 0007_exe
Revises: 0006_pln
Create Date: 2026-07-26

Creates the tables defined in app/modules/exe/models.py (SRS Section 4.6)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_exe"
down_revision = "0006_pln"
branch_labels = None
depends_on = None


EXE_TABLES = [
    "exe_daily_site_diaries",
    "exe_diary_amendments",
    "exe_daily_reports",
    "exe_inspection_logs",
    "exe_site_media",
    "exe_weather_records",
    "exe_progress_entries",
    "exe_work_completed_records",
    "exe_site_issues",
    "exe_visitor_logs",
    "exe_equipment_usage_records",
    "exe_labor_usage_records",
    "exe_concrete_pour_records",
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
        "exe_daily_site_diaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_date", sa.Date, nullable=False, index=True),
        sa.Column("workforce_present_count", sa.Integer, nullable=True),
        sa.Column("equipment_on_site_summary", sa.Text, nullable=True),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("signed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("countersigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("countersigned_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','signed')", name="ck_exe_diaries_status"),
        sa.UniqueConstraint("tenant_id", "project_id", "diary_date", name="uq_exe_diaries_project_date"),
    )

    op.create_table(
        "exe_diary_amendments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amended_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "exe_daily_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "exe_inspection_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("itp_reference", sa.String(128), nullable=True),
        sa.Column("inspected_item", sa.String(255), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("inspector_name", sa.String(255), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("outcome IN ('pass','fail','conditional')", name="ck_exe_inspection_logs_outcome"),
    )

    op.create_table(
        "exe_site_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("media_type", sa.String(8), nullable=False),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("inspection_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_inspection_logs.id"), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("media_type IN ('photo','video')", name="ck_exe_site_media_type"),
    )

    op.create_table(
        "exe_weather_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("condition", sa.String(64), nullable=True),
        sa.Column("temperature_c", sa.Numeric(4, 1), nullable=True),
        sa.Column("rainfall_mm", sa.Numeric(6, 1), nullable=True),
        sa.Column("wind_kph", sa.Numeric(5, 1), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        *_audit_columns(),
    )

    op.create_table(
        "exe_progress_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("measurement_type", sa.String(16), nullable=False),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("measurement_type IN ('percentage','quantity')", name="ck_exe_progress_entries_type"),
    )

    op.create_table(
        "exe_work_completed_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("boq_item_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("variation_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exceeds_contracted_quantity", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "exe_site_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("assigned_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_exe_site_issues_severity"),
        sa.CheckConstraint("status IN ('open','in_progress','resolved','escalated')", name="ck_exe_site_issues_status"),
    )

    op.create_table(
        "exe_visitor_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("visitor_name", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("purpose", sa.String(255), nullable=True),
        sa.Column("hse_induction_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("signed_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_out_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "exe_equipment_usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("equipment_identifier", sa.String(128), nullable=False),
        sa.Column("hours_used", sa.Numeric(5, 2), nullable=False),
        sa.Column("fuel_used_litres", sa.Numeric(8, 2), nullable=True),
        sa.Column("operator_name", sa.String(255), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "exe_labor_usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=False, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trade", sa.String(128), nullable=False),
        sa.Column("headcount", sa.Integer, nullable=False),
        sa.Column("hours_worked", sa.Numeric(5, 2), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "exe_concrete_pour_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("diary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_daily_site_diaries.id"), nullable=True, index=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("inspection_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exe_inspection_logs.id"), nullable=True),
        sa.Column("mix_design", sa.String(255), nullable=True),
        sa.Column("volume_m3", sa.Numeric(8, 2), nullable=False),
        sa.Column("slump_mm", sa.Numeric(5, 1), nullable=True),
        sa.Column("cube_references", postgresql.JSONB, nullable=True),
        sa.Column("weather_at_pour", sa.String(64), nullable=True),
        sa.Column("pour_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pour_completed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    for table in EXE_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(EXE_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("exe_concrete_pour_records")
    op.drop_table("exe_labor_usage_records")
    op.drop_table("exe_equipment_usage_records")
    op.drop_table("exe_visitor_logs")
    op.drop_table("exe_site_issues")
    op.drop_table("exe_work_completed_records")
    op.drop_table("exe_progress_entries")
    op.drop_table("exe_weather_records")
    op.drop_table("exe_site_media")
    op.drop_table("exe_inspection_logs")
    op.drop_table("exe_daily_reports")
    op.drop_table("exe_diary_amendments")
    op.drop_table("exe_daily_site_diaries")
