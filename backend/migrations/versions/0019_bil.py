"""bil module tables

Revision ID: 0019_bil
Revises: 0018_fin
Create Date: 2026-07-30

Creates the tables defined in app/modules/bil/models.py (SRS Section
4.18) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.

Table order matters: VariationOrder must exist before
ProgressCertificateLine, since a line's variation_order_id is a
foreign key to it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_bil"
down_revision = "0018_fin"
branch_labels = None
depends_on = None


BIL_TABLES = [
    "bil_progress_certificates",
    "bil_variation_orders",
    "bil_progress_certificate_lines",
    "bil_milestone_schedules",
    "bil_retention_ledgers",
    "bil_claims",
    "bil_payment_tracking",
    "bil_revenue_recognition_records",
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
        "bil_progress_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("certificate_number", sa.String(128), nullable=False),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("gross_certified_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("retention_withheld", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_payable", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft", index=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_approval_method", sa.String(16), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','submitted','client_approved','rejected')", name="ck_bil_certificate_status"),
        sa.UniqueConstraint("tenant_id", "certificate_number", name="uq_bil_certificate_tenant_number"),
    )

    op.create_table(
        "bil_variation_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("boq_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("varied_quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("varied_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_bil_vo_status"),
    )

    op.create_table(
        "bil_progress_certificate_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("certificate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bil_progress_certificates.id"), nullable=False, index=True),
        sa.Column("boq_item_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("variation_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bil_variation_orders.id"), nullable=True),
        sa.Column("certified_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "bil_milestone_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("milestone_name", sa.String(255), nullable=False),
        sa.Column("milestone_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("sequence_order", sa.Integer, nullable=False, server_default="1"),
        sa.Column("achieved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("billed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("certificate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bil_progress_certificates.id"), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "bil_retention_ledgers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False, server_default="5"),
        sa.Column("amount_withheld", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("released_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "bil_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("claim_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("claimed_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("supporting_document_ids", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("claim_type IN ('delay_costs','disruption','unforeseen_conditions','other')", name="ck_bil_claim_type"),
        sa.CheckConstraint("status IN ('submitted','under_review','approved','rejected')", name="ck_bil_claim_status"),
    )

    op.create_table(
        "bil_payment_tracking",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "certificate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bil_progress_certificates.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted", index=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_amount", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('submitted','certified','paid','overdue')", name="ck_bil_payment_status"),
    )

    op.create_table(
        "bil_revenue_recognition_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("method", sa.String(24), nullable=False, server_default="percentage_of_completion"),
        sa.Column("percentage_complete", sa.Numeric(5, 2), nullable=True),
        sa.Column("cumulative_revenue_recognized", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cumulative_billed", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("over_under_billing_position", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("method IN ('percentage_of_completion','completed_contract')", name="ck_bil_revenue_method"),
    )

    for table in BIL_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(BIL_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("bil_revenue_recognition_records")
    op.drop_table("bil_payment_tracking")
    op.drop_table("bil_claims")
    op.drop_table("bil_retention_ledgers")
    op.drop_table("bil_milestone_schedules")
    op.drop_table("bil_progress_certificate_lines")
    op.drop_table("bil_variation_orders")
    op.drop_table("bil_progress_certificates")
