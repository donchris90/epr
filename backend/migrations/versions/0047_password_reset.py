"""password reset support

Revision ID: 0047_password_reset
Revises: 0046_clp_client_auth
Create Date: 2026-08-23

Real, missing capability, confirmed genuinely absent before writing
this: no forgot-password, reset-password, or change-password endpoint
existed anywhere in this backend -- only invitation-accept (setting an
*initial* password) and avatar-related /me endpoints. Every real SaaS
app needs this; it's foundational account security, not a nice-to-have,
so this is built as a real, additive migration rather than left as a
documented gap.

Two real pieces:

1. password_reset_tokens -- same real pattern already established for
   InvitationTokenIndex (migration 0041): a token-hash lookup table,
   deliberately outside RLS (see its own model docstring), since
   resolving "which tenant does this token belong to" is exactly the
   same structural problem invitation-accept already solved. Never
   stores the raw token, only its SHA-256 hash, matching
   Invitation.token_hash's own established pattern.

2. users.password_changed_at -- a real, standard security mechanism
   for "invalidate all existing sessions on password change/reset",
   not just the one token being used right now. Every login/refresh/
   signup/invitation-accept now embeds this timestamp as a JWT claim
   (pwd_ts); the tenant-context middleware rejects any token whose
   claim doesn't match the user's current value. Changing a password
   naturally changes this column, which makes every previously-issued
   token -- on every device, everywhere -- stop working immediately,
   without needing to track individual sessions/JTIs at all.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0047_password_reset"
down_revision = "0046_clp_client_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])
    # NOT VALID -- matches the same real, previously-found issue with
    # inline FKs against RLS-protected tables during a schema migration
    # (see migration 0042's own note): this table is brand new and
    # empty, so validation is unnecessary and would fail with no
    # app.tenant_id set anyway.
    op.create_foreign_key(
        "fk_password_reset_tokens_user_id", "password_reset_tokens", "users", ["user_id"], ["id"], postgresql_not_valid=True
    )


def downgrade():
    op.drop_constraint("fk_password_reset_tokens_user_id", "password_reset_tokens", type_="foreignkey")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "password_changed_at")
