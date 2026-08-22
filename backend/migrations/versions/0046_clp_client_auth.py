"""clp client portal authentication

Revision ID: 0046_clp_client_auth
Revises: 0045_user_avatar
Create Date: 2026-08-20

Adds real login for external Client Portal users (Module 22 / CLP).

Before this migration, `ClientPortalUser` (clp_portal_users) had no
password of any kind, and `authenticate_user`
(app/auth/jwt_utils.py) only ever looks up the internal `users` table
-- there was no way for a client to ever obtain a session token, only
for staff to administer client records on their behalf via the
Client Portal Admin page. This was flagged clearly in
docs/CLIENT_PORTAL_GAPS.md rather than silently worked around.

Two additions, deliberately mirroring the existing, already-proven
staff-login design (migration 0030_email_tenant_index) as closely as
possible rather than inventing a new pattern:

  1. `clp_portal_users.password_hash` -- same Argon2id scheme as
     `users.password_hash` (see app/auth/jwt_utils.py's already-shared
     `hash_password`/`verify_password` -- that module's own docstring
     says verify_password exists so "other real account types outside
     app.models.core.User" can use it without reaching into its
     PasswordHasher instance directly; this is that other account
     type). Nullable: a client user created before a password is set
     (or before this migration, for any already-seeded rows) simply
     cannot log in yet -- a real, visible state (`GET
     .../client-users` shows it), not a crash.

  2. `clp_email_index` -- deliberately NOT a copy-paste of
     `email_tenant_index`. That table enforces one email -> exactly
     one tenant, which is correct for internal staff (one person, one
     employer) but wrong here: `clp_portal_users` already allows the
     same client email to exist independently across MULTIPLE tenants
     (uq_clp_portal_users_tenant_email is scoped to tenant_id, not
     global) because a real client organization routinely works with
     more than one contractor at once. So `email` here has NO unique
     constraint -- a login resolves ALL matching rows and tries each
     tenant in turn (see app/modules/clp/services.py:
     authenticate_client_user) until one's password matches. Same
     "deliberately outside RLS, contains nothing but what a pre-tenant
     lookup needs" reasoning as email_tenant_index otherwise.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0046_clp_client_auth"
down_revision = "0045_user_avatar"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clp_portal_users", sa.Column("password_hash", sa.String(255), nullable=True))

    op.create_table(
        "clp_email_index",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("client_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clp_portal_users.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_clp_email_index_email", "clp_email_index", ["email"])
    op.create_index("ix_clp_email_index_tenant_id", "clp_email_index", ["tenant_id"])
    # One row per (email, tenant) -- matches uq_clp_portal_users_tenant_email
    # (a given tenant can't have two client users sharing an email), while
    # deliberately allowing multiple tenants to each have their own row for
    # the same email, unlike email_tenant_index.
    op.create_unique_constraint("uq_clp_email_index_email_tenant", "clp_email_index", ["email", "tenant_id"])

    # Deliberately NOT enabling RLS -- see the module docstring above;
    # this table exists specifically to be queryable before any tenant
    # context is known, the same reasoning as email_tenant_index.

    # Backfill: any client user rows that already exist (e.g. seeded in
    # a lower environment) need an index row too, following the same
    # per-tenant SET LOCAL looping pattern as migration
    # 0030_email_tenant_index, for the same FORCE RLS reason -- a bare
    # cross-tenant SELECT against clp_portal_users has no app.tenant_id
    # set during a migration.
    connection = op.get_bind()
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    for tenant_id in tenant_ids:
        connection.execute(sa.text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        connection.execute(
            sa.text(
                """
                INSERT INTO clp_email_index (id, email, client_user_id, tenant_id, created_at, updated_at)
                SELECT gen_random_uuid(), email, id, tenant_id, now(), now()
                FROM clp_portal_users
                WHERE tenant_id = :tid
                ON CONFLICT (email, tenant_id) DO NOTHING
                """
            ),
            {"tid": str(tenant_id)},
        )


def downgrade():
    op.drop_constraint("uq_clp_email_index_email_tenant", "clp_email_index", type_="unique")
    op.drop_index("ix_clp_email_index_tenant_id", table_name="clp_email_index")
    op.drop_index("ix_clp_email_index_email", table_name="clp_email_index")
    op.drop_table("clp_email_index")
    op.drop_column("clp_portal_users", "password_hash")
