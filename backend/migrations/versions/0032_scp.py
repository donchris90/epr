"""scp module tables

Revision ID: 0032_scp
Revises: 0031_workflow_engine
Create Date: 2026-08-15

Creates the table defined in app/modules/scp/models.py (Module 27,
Subcontractor Portal) and enables Row-Level Security + FORCE + the
tenant_isolation policy, per the same standard as every other
tenant-scoped table since migration 0002.

Only one new table -- see the module docstring for why: SCP writes to
Module 12 (SUB)'s existing SubcontractProgressEntry and SubcontractClaim
tables rather than duplicating them, the same "reuse over redesign"
principle CLP and VNP already established.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0032_scp"
down_revision = "0031_workflow_engine"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def upgrade():
    op.create_table(
        "scp_portal_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("subcontractor_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("tenant_id", "email", name="uq_scp_portal_users_tenant_email"),
    )

    op.execute("ALTER TABLE scp_portal_users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scp_portal_users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON scp_portal_users
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON scp_portal_users")
    op.drop_table("scp_portal_users")
