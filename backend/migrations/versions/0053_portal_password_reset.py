"""portal self-service password reset

Revision ID: 0053_portal_pwd_reset
Revises: 0052_workflow_sla_escalation
Create Date: 2026-10-26

Adds what SCP/VNP forgot-password needs: a hashed single-use token
table (outside RLS, like password_reset_tokens) and
`password_changed_at` on both portal user tables, the basis for the
`pwd_ts` session-invalidation claim.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0053_portal_pwd_reset"
down_revision = "0052_workflow_sla_escalation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portal_type", sa.String(8), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("portal_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_portal_password_reset_tokens_token_hash", "portal_password_reset_tokens", ["token_hash"], unique=True)
    op.add_column("scp_portal_users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vnp_portal_users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("vnp_portal_users", "password_changed_at")
    op.drop_column("scp_portal_users", "password_changed_at")
    op.drop_index("ix_portal_password_reset_tokens_token_hash", table_name="portal_password_reset_tokens")
    op.drop_table("portal_password_reset_tokens")
