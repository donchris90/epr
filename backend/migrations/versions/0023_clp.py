"""clp module tables

Revision ID: 0023_clp
Revises: 0022_exd
Create Date: 2026-07-30

Creates the tables defined in app/modules/clp/models.py (SRS Section
4.22) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023_clp"
down_revision = "0022_exd"
branch_labels = None
depends_on = None


CLP_TABLES = [
    "clp_portal_users",
    "clp_project_assignments",
    "clp_approval_actions",
    "clp_client_requests",
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
        "clp_portal_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("client_organization_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("tenant_id", "email", name="uq_clp_portal_users_tenant_email"),
    )

    op.create_table(
        "clp_project_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("client_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clp_portal_users.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        *_audit_columns(),
        sa.UniqueConstraint("client_user_id", "project_id", name="uq_clp_assignment_user_project"),
    )

    op.create_table(
        "clp_approval_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("client_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clp_portal_users.id"), nullable=False, index=True),
        sa.Column("action_type", sa.String(24), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("action_type IN ('variation_order','progress_certificate')", name="ck_clp_approval_action_type"),
        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_clp_approval_decision"),
    )

    op.create_table(
        "clp_client_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("client_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clp_portal_users.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("request_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("request_type IN ('rfi','service_request')", name="ck_clp_request_type"),
        sa.CheckConstraint("status IN ('open','in_progress','resolved')", name="ck_clp_request_status"),
    )

    for table in CLP_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(CLP_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("clp_client_requests")
    op.drop_table("clp_approval_actions")
    op.drop_table("clp_project_assignments")
    op.drop_table("clp_portal_users")
