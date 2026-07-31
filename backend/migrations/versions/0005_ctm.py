"""ctm module tables

Revision ID: 0005_ctm
Revises: 0004_est
Create Date: 2026-07-25

Creates the tables defined in app/modules/ctm/models.py (SRS Section 4.4)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_ctm"
down_revision = "0004_est"
branch_labels = None
depends_on = None


CTM_TABLES = [
    "ctm_contracts",
    "ctm_contract_documents",
    "ctm_payment_terms",
    "ctm_performance_bonds",
    "ctm_advance_payments",
    "ctm_retentions",
    "ctm_insurances",
    "ctm_guarantees",
    "ctm_contract_amendments",
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
        "ctm_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("cbs_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("contract_number", sa.String(128), nullable=False),
        sa.Column("contract_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("payment_cycle_days", sa.Integer, nullable=True),
        sa.Column("certification_frequency", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True, index=True),
        sa.Column("original_completion_date", sa.Date, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','completed','terminated')", name="ck_ctm_contracts_status"),
        sa.UniqueConstraint("tenant_id", "contract_number", name="uq_ctm_contracts_tenant_number"),
        sa.UniqueConstraint("tenant_id", "tender_id", name="uq_ctm_contracts_tenant_tender"),
    )

    op.create_table(
        "ctm_contract_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("doc_type", sa.String(64), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "ctm_payment_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("percentage_of_contract_value", sa.Numeric(5, 2), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "ctm_performance_bonds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("issuing_bank", sa.String(255), nullable=True),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','released','expired','claimed')", name="ck_ctm_perf_bonds_status"),
    )

    op.create_table(
        "ctm_advance_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("percentage_of_contract_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("recoupment_pct_per_certificate", sa.Numeric(5, 2), nullable=False),
        sa.Column("amount_recouped", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("paid_at", sa.Date, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "ctm_retentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ctm_contracts.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("cap_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("amount_withheld", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("release_substantial_completion_pct", sa.Numeric(5, 2), nullable=False, server_default="50"),
        sa.Column("release_end_of_dlp_pct", sa.Numeric(5, 2), nullable=False, server_default="50"),
        sa.Column("released_substantial_completion", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("released_end_of_dlp", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.CheckConstraint(
            "release_substantial_completion_pct + release_end_of_dlp_pct = 100",
            name="ck_ctm_retentions_release_sums_100",
        ),
    )

    op.create_table(
        "ctm_insurances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("policy_type", sa.String(64), nullable=False),
        sa.Column("insurer", sa.String(255), nullable=True),
        sa.Column("coverage_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','released','expired','claimed')", name="ck_ctm_insurances_status"),
    )

    op.create_table(
        "ctm_guarantees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("guarantee_type", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("issuing_bank", sa.String(255), nullable=True),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','released','expired','claimed')", name="ck_ctm_guarantees_status"),
    )

    op.create_table(
        "ctm_contract_amendments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ctm_contracts.id"), nullable=False, index=True),
        sa.Column("amendment_type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("time_extension_days", sa.Integer, nullable=True),
        sa.Column("price_delta", sa.Numeric(18, 4), nullable=True),
        sa.Column("scope_change_description", sa.Text, nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("amendment_type IN ('time','price','scope')", name="ck_ctm_amendments_type"),
    )

    for table in CTM_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(CTM_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("ctm_contract_amendments")
    op.drop_table("ctm_guarantees")
    op.drop_table("ctm_insurances")
    op.drop_table("ctm_retentions")
    op.drop_table("ctm_advance_payments")
    op.drop_table("ctm_performance_bonds")
    op.drop_table("ctm_payment_terms")
    op.drop_table("ctm_contract_documents")
    op.drop_table("ctm_contracts")
