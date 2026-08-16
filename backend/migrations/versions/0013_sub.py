"""sub module tables

Revision ID: 0013_sub
Revises: 0012_wfm
Create Date: 2026-07-29

Creates the tables defined in app/modules/sub/models.py (SRS Section
4.12) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_sub"
down_revision = "0012_wfm"
branch_labels = None
depends_on = None


SUB_TABLES = [
    "sub_subcontractors",
    "sub_agreements",
    "sub_scope_items",
    "sub_progress_entries",
    "sub_measurement_sheets",
    "sub_payment_certificates",
    "sub_payment_certificate_lines",
    "sub_back_charges",
    "sub_retentions",
    "sub_claims",
    "sub_performance_ratings",
    "sub_compliance_documents",
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
        "sub_subcontractors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trade_specialty", sa.String(128), nullable=True),
        sa.Column("tax_registration_number", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_sub_subcontractors_status"),
    )

    op.create_table(
        "sub_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("subcontractor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_subcontractors.id"), nullable=False, index=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("agreement_number", sa.String(128), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("payment_terms_summary", sa.Text, nullable=True),
        sa.Column("retention_percentage", sa.Numeric(5, 2), nullable=False, server_default="5"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','completed','terminated')", name="ck_sub_agreements_status"),
        sa.UniqueConstraint("tenant_id", "agreement_number", name="uq_sub_agreements_tenant_number"),
    )

    op.create_table(
        "sub_scope_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_agreements.id"), nullable=False, index=True),
        sa.Column("boq_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cbs_line_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("is_lump_sum", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("lump_sum_amount", sa.Numeric(18, 4), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "sub_progress_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_agreements.id"), nullable=False, index=True),
        sa.Column("scope_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_scope_items.id"), nullable=True),
        sa.Column("submitted_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('submitted','verified','rejected')", name="ck_sub_progress_status"),
    )

    op.create_table(
        "sub_measurement_sheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_agreements.id"), nullable=False, index=True),
        sa.Column("scope_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_scope_items.id"), nullable=False, index=True),
        sa.Column("progress_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_progress_entries.id"), nullable=True),
        sa.Column("verified_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("measured_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subcontractor_countersigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','verified')", name="ck_sub_measurement_status"),
    )

    op.create_table(
        "sub_payment_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_agreements.id"), nullable=False, index=True),
        sa.Column("certificate_number", sa.String(128), nullable=False),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("gross_certified_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("retention_withheld", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("back_charges_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_payable", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compliance_waiver", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("compliance_waiver_reason", sa.Text, nullable=True),
        sa.Column("compliance_waiver_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','issued')", name="ck_sub_certificates_status"),
        sa.UniqueConstraint("tenant_id", "certificate_number", name="uq_sub_certificates_tenant_number"),
    )

    op.create_table(
        "sub_payment_certificate_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("certificate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_payment_certificates.id"), nullable=False, index=True),
        sa.Column("measurement_sheet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_measurement_sheets.id"), nullable=False),
        sa.Column("certified_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "sub_back_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_agreements.id"), nullable=False, index=True),
        sa.Column("payment_certificate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_payment_certificates.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason_category", sa.String(24), nullable=False, server_default="other"),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raised_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("reason_category IN ('rework','materials_supplied','other')", name="ck_sub_back_charges_category"),
    )

    op.create_table(
        "sub_retentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "agreement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sub_agreements.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("amount_withheld", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("release_substantial_completion_pct", sa.Numeric(5, 2), nullable=False, server_default="50"),
        sa.Column("release_final_pct", sa.Numeric(5, 2), nullable=False, server_default="50"),
        sa.Column("released_substantial_completion", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("released_final", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.CheckConstraint(
            "release_substantial_completion_pct + release_final_pct = 100",
            name="ck_sub_retentions_release_sums_100",
        ),
    )

    op.create_table(
        "sub_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_agreements.id"), nullable=False, index=True),
        sa.Column("claim_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("claimed_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("claimed_days", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("claim_type IN ('delay','additional_scope','other')", name="ck_sub_claims_type"),
        sa.CheckConstraint("status IN ('submitted','under_review','approved','rejected')", name="ck_sub_claims_status"),
    )

    op.create_table(
        "sub_performance_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("subcontractor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_subcontractors.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("period_label", sa.String(32), nullable=True),
        sa.Column("quality_score", sa.Numeric(4, 1), nullable=False),
        sa.Column("schedule_score", sa.Numeric(4, 1), nullable=False),
        sa.Column("safety_score", sa.Numeric(4, 1), nullable=False),
        sa.Column("responsiveness_score", sa.Numeric(4, 1), nullable=False),
        sa.Column("overall_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("rated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "sub_compliance_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("subcontractor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sub_subcontractors.id"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "doc_type IN ('insurance','safety_certification','tax_clearance','labor_law_compliance')",
            name="ck_sub_compliance_doc_type",
        ),
    )

    for table in SUB_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(SUB_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("sub_compliance_documents")
    op.drop_table("sub_performance_ratings")
    op.drop_table("sub_claims")
    op.drop_table("sub_retentions")
    op.drop_table("sub_back_charges")
    op.drop_table("sub_payment_certificate_lines")
    op.drop_table("sub_payment_certificates")
    op.drop_table("sub_measurement_sheets")
    op.drop_table("sub_progress_entries")
    op.drop_table("sub_scope_items")
    op.drop_table("sub_agreements")
    op.drop_table("sub_subcontractors")
