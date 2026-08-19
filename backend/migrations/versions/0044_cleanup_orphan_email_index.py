"""cleanup orphaned email_tenant_index rows for removed users

Revision ID: 0044_cleanup_orphan_email_idx
Revises: 0043_user_email_reuse
Create Date: 2026-08-19

Real data migration, not just a schema change -- fixes existing,
already-broken data left over from before app/org/services.py's
remove_user was fixed to also clean up EmailTenantIndex (a genuinely
global unique-per-email table, necessarily so, since it resolves
which tenant an email belongs to before login has any tenant context
to filter by at all -- see that model's own docstring).

Before that fix, removing a user left their email_tenant_index row
behind. Migration 0043 correctly made users.email reusable after
removal, but that stale index row still globally occupied the email
-- so a fresh invitation to the same address could create a real new
User row, but accepting it then failed with a raw IntegrityError the
moment it tried to insert its own index row for that same,
still-occupied email. Runs automatically on the next deploy, needing
no direct database access from anyone operating this deployment.

Safe to delete outright, not just flag: a removed user was already
unable to log in regardless of this row's existence (the real
status != "active" check in authenticate_user), so any such row is
confirmed dead weight, not an active protection for anything.
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_cleanup_orphan_email_idx"
down_revision = "0043_user_email_reuse"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # users has FORCE RLS -- a bare cross-tenant query has no tenant
    # context to see any rows at all. tenants itself carries no RLS
    # (the root table everything else scopes against), so this is
    # real, complete tenant coverage, not a guess at which tenants
    # might have removed users.
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants"))]
    for tenant_id in tenant_ids:
        connection.execute(sa.text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        connection.execute(
            sa.text(
                """
                DELETE FROM email_tenant_index
                WHERE user_id IN (SELECT id FROM users WHERE status = 'removed')
                """
            )
        )


def downgrade():
    # Real, deliberate no-op -- the deleted rows were confirmed dead
    # weight (see this migration's own docstring on why), and their
    # exact prior contents (which specific removed users had which
    # index rows) aren't meaningfully recoverable or worth restoring.
    pass
