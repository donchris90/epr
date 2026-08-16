"""notifications table

Revision ID: 0033_notifications
Revises: 0032_scp
Create Date: 2026-08-15

Creates the table defined in app/notifications/models.py and enables
Row-Level Security + FORCE + the tenant_isolation policy, per the same
standard as every other tenant-scoped table since migration 0002.

First notification infrastructure of any kind in this platform --
adapted from a real, working implementation found in a separate,
independent codebase generated against the same underlying SRS (see
README.md's session notes and app/notifications/models.py's module
docstring for the full story).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0033_notifications"
down_revision = "0032_scp"
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
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("data", postgresql.JSONB, nullable=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="in_app"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True, index=True),
        *_audit_columns(),
        sa.CheckConstraint("channel IN ('in_app','email','sms')", name="ck_notifications_channel"),
    )
    op.create_index("ix_notifications_user_unread", "notifications", ["tenant_id", "user_id", "read_at"])

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notifications
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notifications")
    op.drop_table("notifications")
