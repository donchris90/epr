"""vnp module tables

Revision ID: 0024_vnp
Revises: 0023_clp
Create Date: 2026-07-30

Creates the tables defined in app/modules/vnp/models.py (SRS Section
4.23) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_vnp"
down_revision = "0023_clp"
branch_labels = None
depends_on = None


VNP_TABLES = [
    "vnp_portal_users",
    "vnp_order_acknowledgments",
    "vnp_invoice_uploads",
    "vnp_banking_change_requests",
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
        "vnp_portal_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("tenant_id", "email", name="uq_vnp_portal_users_tenant_email"),
    )

    op.create_table(
        "vnp_order_acknowledgments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vnp_portal_users.id"), nullable=False, index=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_delivery_date", sa.Date, nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("purchase_order_id", name="uq_vnp_order_ack_po"),
    )

    op.create_table(
        "vnp_invoice_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vnp_portal_users.id"), nullable=False, index=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("subcontract_certificate_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("invoice_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("invoice_number", sa.String(128), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('submitted','matched','rejected')", name="ck_vnp_invoice_upload_status"),
        sa.CheckConstraint(
            "(purchase_order_id IS NOT NULL AND subcontract_certificate_id IS NULL) OR "
            "(purchase_order_id IS NULL AND subcontract_certificate_id IS NOT NULL)",
            name="ck_vnp_invoice_upload_exactly_one_reference",
        ),
    )

    op.create_table(
        "vnp_banking_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vnp_portal_users.id"), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("proposed_banking_details", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_vnp_banking_change_status"),
    )

    for table in VNP_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(VNP_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("vnp_banking_change_requests")
    op.drop_table("vnp_invoice_uploads")
    op.drop_table("vnp_order_acknowledgments")
    op.drop_table("vnp_portal_users")
