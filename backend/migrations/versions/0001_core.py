"""core cross-module tables

Revision ID: 0001_core
Revises:
Create Date: 2026-07-24

Creates the tables defined in app/models/core.py (SRS Section 5.2) and
enables Row-Level Security + the tenant_isolation policy on every
tenant-scoped table, per SRS Section 5.5. `tenants` itself is not
RLS-scoped (there is no "current tenant" before a tenant exists).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


TENANT_SCOPED_TABLES = ["companies", "roles", "users", "projects", "documents"]


def _enable_rls(table_name: str):
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    # FORCE makes the policy apply even to the table's OWNER. Without it,
    # a superuser or the owning role (often the same role the app
    # connects as, in simpler deployments) silently bypasses RLS
    # entirely -- the single easiest way for this architecture's core
    # guarantee to quietly stop holding.
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subscription_plan", sa.String(64), nullable=False, server_default="standard"),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("permission_set", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("file_key", sa.String(512), nullable=False),
        sa.Column("doc_type", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    for table in TENANT_SCOPED_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(TENANT_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("documents")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("companies")
    op.drop_table("tenants")
