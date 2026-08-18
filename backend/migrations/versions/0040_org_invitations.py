"""org invitations and user profile fields

Revision ID: 0040_org_invitations
Revises: 0039_platform_admin
Create Date: 2026-08-17

Real invitation system, not a placeholder: department/job_title added
to users (Phase 35's user-detail profile fields), and a new
invitations table -- tenant-scoped, real RLS, matching every other
tenant-owned table.

Security note on token_hash: the raw invitation token only ever exists
in the email sent to the invitee and briefly in the acceptance
request -- never stored in the database in plaintext, matching the
same discipline already applied to passwords (Argon2, not a reversible
encryption). See app/org/services.py for the actual hashing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0040_org_invitations"
down_revision = "0039_platform_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("department", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(128), nullable=True))

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("job_title", sa.String(128), nullable=True),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        # Never the raw token -- see this migration's own docstring.
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'cancelled')", name="ck_invitations_status"
        ),
        # One real, live (pending) invitation per email per tenant --
        # re-inviting the same address while a real invite is still
        # outstanding should update/resend that one, not create a
        # second seat-reserving row for the same person. Partial
        # index, not a table-wide UniqueConstraint, since the same
        # email genuinely can have multiple non-pending (expired/
        # cancelled/accepted) rows over time.
        sa.Index(
            "uq_invitations_one_pending_per_email",
            "tenant_id", "email",
            unique=True,
            postgresql_where=sa.text("status = 'pending'"),
        ),
    )
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON invitations "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invitations")
    op.drop_table("invitations")
    op.drop_column("users", "job_title")
    op.drop_column("users", "department")
