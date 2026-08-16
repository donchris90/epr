"""mfa module tables

Revision ID: 0025_mfa
Revises: 0024_vnp
Create Date: 2026-07-30

Creates the tables defined in app/modules/mfa/models.py (SRS Section
4.24) and enables Row-Level Security + FORCE + the tenant_isolation
policy on both of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025_mfa"
down_revision = "0024_vnp"
branch_labels = None
depends_on = None


MFA_TABLES = [
    "mfa_sync_queue_entries",
    "mfa_conflict_records",
]


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _enable_rls(table_name: str):
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade():
    op.create_table(
        "mfa_sync_queue_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("device_id", sa.String(128), nullable=False, index=True),
        sa.Column("client_record_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("target_module", sa.String(32), nullable=False),
        sa.Column("target_entity_type", sa.String(32), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False, server_default="create"),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("device_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("server_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("operation IN ('create','update')", name="ck_mfa_sync_operation"),
        sa.CheckConstraint("status IN ('pending','synced','conflict','rejected')", name="ck_mfa_sync_status"),
        sa.UniqueConstraint("tenant_id", "client_record_id", name="uq_mfa_sync_tenant_client_record"),
    )

    op.create_table(
        "mfa_conflict_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sync_queue_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mfa_sync_queue_entries.id"), nullable=False, index=True),
        sa.Column("conflict_type", sa.String(24), nullable=False),
        sa.Column("client_payload", postgresql.JSONB, nullable=False),
        sa.Column("server_current_state", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="unresolved", index=True),
        sa.Column("resolution", postgresql.JSONB, nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("conflict_type IN ('concurrent_update','validation_failure','permission_denied')", name="ck_mfa_conflict_type"),
        sa.CheckConstraint("status IN ('unresolved','resolved')", name="ck_mfa_conflict_status"),
    )

    for table in MFA_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(MFA_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("mfa_conflict_records")
    op.drop_table("mfa_sync_queue_entries")
