"""users email reusable after removal

Revision ID: 0043_user_email_reuse
Revises: 0042_project_fields
Create Date: 2026-08-19

Real bug found from a live report, not by inspection: remove_user
(app/org/services.py) is a soft delete (status="removed", matching
this codebase's consistent audit-trail discipline -- nothing genuinely
disappears, it's marked), but uq_users_tenant_email was an
unconditional unique constraint on (tenant_id, email) with no
exception for status. A fix to the application-level duplicate check
alone isn't sufficient: even once that check correctly excludes
removed users, accepting a fresh invitation to that same email would
still fail with a raw database IntegrityError the moment
accept_invitation tries to insert the new User row, since the
database itself was still enforcing global uniqueness regardless of
status.

Real fix: drop the unconditional constraint, replace it with a
partial unique index that only applies to non-removed users -- the
exact same pattern already established for Invitation's own
uq_invitations_one_pending_per_email (migration 0040). A tenant can
now genuinely re-invite someone at the same email address after
removing them; the database only ever prevents two simultaneously
non-removed users at the same tenant/email.
"""
from alembic import op
import sqlalchemy as sa

revision = "0043_user_email_reuse"
down_revision = "0042_project_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.create_index(
        "uq_users_tenant_email_active",
        "users",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("status != 'removed'"),
    )


def downgrade():
    op.drop_index("uq_users_tenant_email_active", table_name="users")
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])
