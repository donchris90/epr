"""dsar request log

Revision ID: 0054_dsar_requests
Revises: 0053_portal_pwd_reset
Create Date: 2026-10-26

Tracking table for Data Subject Access Requests (intake, due date,
outcome, and an id-only log of erasure actions). Tenant-scoped with RLS.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0054_dsar_requests"
down_revision = "0053_portal_pwd_reset"
branch_labels = None
depends_on = None

TYPES = "('access','correction','erasure','restriction','objection','portability')"
STATUSES = "('open','in_progress','completed','rejected')"


def upgrade():
    op.create_table(
        "dsar_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("request_type", sa.String(16), nullable=False),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("subject_email", sa.String(255), nullable=True),
        sa.Column("subject_phone", sa.String(64), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("actions", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(f"request_type IN {TYPES}", name="ck_dsar_requests_type"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_dsar_requests_status"),
    )
    op.create_index("ix_dsar_requests_due_at", "dsar_requests", ["due_at"])
    op.execute("ALTER TABLE dsar_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dsar_requests FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON dsar_requests "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON dsar_requests")
    op.drop_table("dsar_requests")
