"""notification preferences

Revision ID: 0056_notification_prefs
Revises: 0055_wfm_leave_entitlements
Create Date: 2026-10-26

Per-user, per-category in-app/email toggles. Tenant-scoped with RLS.
No row means both channels on.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0056_notification_prefs"
down_revision = "0055_wfm_leave_entitlements"
branch_labels = None
depends_on = None

CATEGORIES = "('approvals','projects','finance','hse','system')"


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("in_app", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("email", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "user_id", "category", name="uq_notification_preferences_user_category"),
        sa.CheckConstraint(f"category IN {CATEGORIES}", name="ck_notification_preferences_category"),
    )
    op.execute("ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_preferences FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON notification_preferences "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notification_preferences")
    op.drop_table("notification_preferences")
