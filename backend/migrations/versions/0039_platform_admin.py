"""platform admin

Revision ID: 0039_platform_admin
Revises: 0038_billing_plans
Create Date: 2026-08-17

Real platform administration: platform_admins (no RLS -- same
reasoning as tenants itself, this is the root of the whole hierarchy)
and tenants.is_suspended (real enforcement, checked at login -- see
app/auth/jwt_utils.py).

Does NOT create a bootstrap platform admin account here -- migrations
run automatically on every deploy, and hardcoding even a placeholder
password into a migration file that ends up in version control is
exactly the class of mistake this project's own security review would
flag. Use the real CLI command instead:

    flask create-platform-admin --email you@example.com

which prompts for a password interactively rather than taking one as
a plain-text argument or embedding one anywhere.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0039_platform_admin"
down_revision = "0038_billing_plans"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_platform_admins_status"),
    )

    op.add_column("tenants", sa.Column("is_suspended", sa.Boolean, nullable=False, server_default="false"))


def downgrade():
    op.drop_column("tenants", "is_suspended")
    op.drop_table("platform_admins")
