"""scp and vnp portal authentication

Revision ID: 0049_scp_vnp_auth
Revises: 0048_last_login
Create Date: 2026-08-23

Real login for the Subcontractor Portal (Module 27 / SCP) and Vendor
Portal (Module 23 / VNP) external users -- confirmed genuinely missing
before writing this, the same way migration 0046_clp_client_auth found
and closed the identical gap for the Client Portal: neither
SubcontractorPortalUser (scp_portal_users) nor VendorPortalUser
(vnp_portal_users) had a password of any kind, and every real SCP/VNP
route required the internal @require_permission("scp:*"/"vnp:*")
grant -- staff acting on a subcontractor/vendor's behalf, with no way
for the subcontractor or vendor to ever obtain a session token
themselves.

Deliberately mirrors 0046_clp_client_auth's own design as closely as
possible rather than inventing a new pattern for each portal -- same
Argon2id password_hash column (nullable: a portal user with no
password yet simply can't log in, a real visible state, not a crash),
same reasoning for a dedicated, non-RLS email-index table per module.

One real, deliberate difference from CLP: SubcontractorPortalUser and
VendorPortalUser are both already one-to-one with their real-world
counterpart (subcontractor_id / vendor_id, both "loose reference,
belongs to exactly ONE" per their own model docstrings) -- unlike
CLP's client, which can legitimately span multiple tenants at once.
scp_email_index/vnp_email_index still allow the same email to exist
across multiple tenants (a subcontractor or vendor working with more
than one contractor is completely ordinary), so login still resolves
every matching tenant and tries each one's password in turn, the same
real cross-tenant login shape as CLP and staff login both already use
-- just without CLP's own multi-project-per-client complexity
elsewhere in the system.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0049_scp_vnp_auth"
down_revision = "0048_last_login"
branch_labels = None
depends_on = None


def _add_portal_auth(op, connection, *, user_table, index_table, user_fk_column):
    op.add_column(user_table, sa.Column("password_hash", sa.String(255), nullable=True))

    op.create_table(
        index_table,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(user_fk_column, postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{user_table}.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(f"ix_{index_table}_email", index_table, ["email"])
    op.create_index(f"ix_{index_table}_tenant_id", index_table, ["tenant_id"])
    op.create_unique_constraint(f"uq_{index_table}_email_tenant", index_table, ["email", "tenant_id"])

    # Backfill any already-seeded rows -- same real per-tenant SET
    # LOCAL looping pattern as 0046_clp_client_auth, for the same
    # FORCE RLS reason.
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    for tenant_id in tenant_ids:
        connection.execute(sa.text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        connection.execute(
            sa.text(
                f"""
                INSERT INTO {index_table} (id, email, {user_fk_column}, tenant_id, created_at, updated_at)
                SELECT gen_random_uuid(), email, id, tenant_id, now(), now()
                FROM {user_table}
                WHERE tenant_id = :tid
                ON CONFLICT (email, tenant_id) DO NOTHING
                """
            ),
            {"tid": str(tenant_id)},
        )


def _drop_portal_auth(op, *, user_table, index_table):
    op.drop_constraint(f"uq_{index_table}_email_tenant", index_table, type_="unique")
    op.drop_index(f"ix_{index_table}_tenant_id", table_name=index_table)
    op.drop_index(f"ix_{index_table}_email", table_name=index_table)
    op.drop_table(index_table)
    op.drop_column(user_table, "password_hash")


def upgrade():
    connection = op.get_bind()
    _add_portal_auth(op, connection, user_table="scp_portal_users", index_table="scp_email_index", user_fk_column="portal_user_id")
    _add_portal_auth(op, connection, user_table="vnp_portal_users", index_table="vnp_email_index", user_fk_column="vendor_user_id")


def downgrade():
    _drop_portal_auth(op, user_table="vnp_portal_users", index_table="vnp_email_index")
    _drop_portal_auth(op, user_table="scp_portal_users", index_table="scp_email_index")
