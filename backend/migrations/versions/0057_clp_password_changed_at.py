"""client portal password_changed_at

Revision ID: 0057_clp_pwd_changed_at
Revises: 0056_notification_prefs
Create Date: 2026-10-26

Basis for the `pwd_ts` session-invalidation claim on client portal
tokens, so a self-service reset (reusing portal_password_reset_tokens
from 0053) ends every earlier client session.
"""
from alembic import op
import sqlalchemy as sa

revision = "0057_clp_pwd_changed_at"
down_revision = "0056_notification_prefs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clp_portal_users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("clp_portal_users", "password_changed_at")
