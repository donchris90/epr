"""email tenant index - login lookup without elevated privileges

Revision ID: 0030_email_tenant_index
Revises: 0029_reorder_auto_pr
Create Date: 2026-08-01

Replaces the BYPASSRLS-role approach to the pre-tenant login lookup
entirely. That approach (backend/scripts/setup_auth_role.sql,
app/extensions.py:get_auth_engine) required a database role with the
BYPASSRLS attribute, which -- discovered only once actually deployed
against a real managed Postgres instance -- cannot be granted from
application code even by a role with CREATEROLE: Postgres requires
the GRANTING role to itself have BYPASSRLS to hand that attribute to
anyone else. This blocked every login in production with no way to
self-serve a fix short of requesting elevated privileges from the
hosting provider's own support team.

This migration creates a tiny table, deliberately outside RLS
entirely, containing only what's needed to resolve an email to its
tenant before any session has tenant context to set -- see
app/models/core.py:EmailTenantIndex for the full reasoning. No
special database role, no BYPASSRLS, no external dependency: any
connection this app already has can read and write it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0030_email_tenant_index"
down_revision = "0029_reorder_auto_pr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_tenant_index",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_email_tenant_index_email", "email_tenant_index", ["email"])
    op.create_index("ix_email_tenant_index_tenant_id", "email_tenant_index", ["tenant_id"])

    # Deliberately NOT enabling RLS on this table at all -- see the
    # module docstring for why that's the entire point, not an
    # oversight.

    # Backfill: every user that already exists needs an index row too,
    # or they'd be unable to log in despite a real account existing.
    #
    # Loops per-tenant rather than one INSERT...SELECT scanning `users`
    # across every tenant at once -- a real bug caught only by an
    # actual production run: `users` has FORCE ROW LEVEL SECURITY, and
    # migrations run through this same connection as everything else
    # in production (the single non-superuser role Render provisions,
    # the entire reason this migration exists in the first place). A
    # bare cross-tenant SELECT with no app.tenant_id ever set hits the
    # exact same "unrecognized configuration parameter" wall this
    # whole migration was built to get around -- missed locally because
    # local testing ran migrations as the Postgres superuser, which
    # bypasses RLS regardless of FORCE. `tenants` itself has no RLS at
    # all (it's the root of the tenant hierarchy), so it's safe to
    # enumerate directly; `SET LOCAL` is reissued once per tenant,
    # valid for the remainder of this migration's single transaction
    # until superseded by the next iteration's call.
    connection = op.get_bind()
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    for tenant_id in tenant_ids:
        connection.execute(sa.text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        connection.execute(
            sa.text(
                """
                INSERT INTO email_tenant_index (id, email, user_id, tenant_id, created_at, updated_at)
                SELECT gen_random_uuid(), email, id, tenant_id, now(), now()
                FROM users
                WHERE tenant_id = :tid
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"tid": str(tenant_id)},
        )


def downgrade():
    op.drop_index("ix_email_tenant_index_tenant_id", table_name="email_tenant_index")
    op.drop_index("ix_email_tenant_index_email", table_name="email_tenant_index")
    op.drop_table("email_tenant_index")
