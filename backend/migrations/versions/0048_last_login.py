"""last login tracking

Revision ID: 0048_last_login
Revises: 0047_password_reset
Create Date: 2026-08-23

Small, additive, real capability: users.last_login_at, set on every
successful login (app/auth/jwt_utils.py:authenticate_user). Confirmed
genuinely missing before adding this -- no last-login tracking existed
anywhere in this backend. Directly unlocks part of the Security
Settings requirement ("last login information if available") with a
real value rather than a placeholder.
"""
from alembic import op
import sqlalchemy as sa

revision = "0048_last_login"
down_revision = "0047_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "last_login_at")
