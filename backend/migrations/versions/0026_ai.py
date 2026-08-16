"""ai module tables

Revision ID: 0026_ai
Revises: 0025_mfa
Create Date: 2026-07-30

Creates the tables defined in app/modules/ai/models.py (SRS Section
4.25) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0026_ai"
down_revision = "0025_mfa"
branch_labels = None
depends_on = None


AI_TABLES = [
    "ai_query_logs",
    "ai_generated_reports",
    "ai_document_extraction_jobs",
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
        "ai_query_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("query_params", postgresql.JSONB, nullable=True),
        sa.Column("context_retrieved", postgresql.JSONB, nullable=True),
        sa.Column("queried_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "ai_generated_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("source_citations", postgresql.JSONB, nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("report_type IN ('cash_flow_forecast','executive_summary','diary_summary')", name="ck_ai_report_type"),
    )

    op.create_table(
        "ai_document_extraction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("extraction_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("extracted_data", postgresql.JSONB, nullable=True),
        sa.Column("confidence_scores", postgresql.JSONB, nullable=True),
        sa.Column("low_confidence_fields", postgresql.JSONB, nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corrected_data", postgresql.JSONB, nullable=True),
        sa.Column("committed_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("extraction_type IN ('boq','invoice')", name="ck_ai_extraction_type"),
        sa.CheckConstraint("status IN ('pending','extracted','reviewed','committed','rejected')", name="ck_ai_extraction_status"),
    )

    for table in AI_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(AI_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("ai_document_extraction_jobs")
    op.drop_table("ai_generated_reports")
    op.drop_table("ai_query_logs")
