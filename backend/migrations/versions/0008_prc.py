"""prc module tables

Revision ID: 0008_prc
Revises: 0007_exe
Create Date: 2026-07-26

Creates the tables defined in app/modules/prc/models.py (SRS Section 4.7)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_prc"
down_revision = "0007_exe"
branch_labels = None
depends_on = None


PRC_TABLES = [
    "prc_vendors",
    "prc_vendor_compliance_documents",
    "prc_rfqs",
    "prc_rfq_invitations",
    "prc_rfq_quotations",
    "prc_purchase_requests",
    "prc_purchase_orders",
    "prc_purchase_order_lines",
    "prc_po_approval_steps",
    "prc_goods_receipt_notes",
    "prc_goods_receipt_lines",
    "prc_invoice_matches",
    "prc_vendor_performance_records",
    "prc_supplier_ratings",
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
        "prc_vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tax_registration_number", sa.String(64), nullable=True),
        sa.Column("banking_details", postgresql.JSONB, nullable=True),
        sa.Column("categories_supplied", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_prc_vendors_status"),
    )

    op.create_table(
        "prc_vendor_compliance_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_vendors.id"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("doc_type", sa.String(64), nullable=False),
        sa.Column("valid_until", sa.Date, nullable=True, index=True),
        *_audit_columns(),
    )

    op.create_table(
        "prc_rfqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_prc_rfqs_status"),
    )

    op.create_table(
        "prc_rfq_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_rfqs.id"), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_vendors.id"), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="invited"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('invited','responded','declined')", name="ck_prc_rfq_invitations_status"),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="uq_prc_rfq_invitations_pair"),
    )

    op.create_table(
        "prc_rfq_quotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_rfqs.id"), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_vendors.id"), nullable=False, index=True),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("lead_time_days", sa.Integer, nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="uq_prc_rfq_quotations_pair"),
    )

    op.create_table(
        "prc_purchase_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("cbs_line_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("estimated_unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("estimated_total", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("budget_override", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("budget_override_reason", sa.Text, nullable=True),
        sa.Column("budget_override_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('draft','submitted','approved','rejected','converted')", name="ck_prc_purchase_requests_status"
        ),
    )

    op.create_table(
        "prc_purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("purchase_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_purchase_requests.id"), nullable=True),
        sa.Column("rfq_quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_rfq_quotations.id"), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_vendors.id"), nullable=False, index=True),
        sa.Column("po_number", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft", index=True),
        sa.Column("total_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("is_blanket", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("compliance_waiver", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("compliance_waiver_reason", sa.Text, nullable=True),
        sa.Column("compliance_waiver_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("budget_override", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("budget_override_reason", sa.Text, nullable=True),
        sa.Column("budget_override_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('draft','pending_approval','approved','issued','closed','cancelled')",
            name="ck_prc_purchase_orders_status",
        ),
        sa.UniqueConstraint("tenant_id", "po_number", name="uq_prc_purchase_orders_tenant_number"),
    )

    op.create_table(
        "prc_purchase_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True),
        sa.Column("boq_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cbs_line_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "prc_po_approval_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("role_required", sa.String(128), nullable=False),
        sa.Column("value_threshold", sa.Numeric(18, 4), nullable=True),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_prc_po_approval_steps_status"),
        sa.UniqueConstraint("purchase_order_id", "step_order", name="uq_prc_po_approval_steps_po_order"),
    )

    op.create_table(
        "prc_goods_receipt_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('draft','confirmed')", name="ck_prc_grn_status"),
    )

    op.create_table(
        "prc_goods_receipt_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("grn_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_goods_receipt_notes.id"), nullable=False, index=True),
        sa.Column("po_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_purchase_order_lines.id"), nullable=False, index=True),
        sa.Column("quantity_received", sa.Numeric(18, 4), nullable=False),
        sa.Column("condition", sa.String(16), nullable=False, server_default="good"),
        sa.Column("discrepancy_notes", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("condition IN ('good','damaged','partial')", name="ck_prc_grn_lines_condition"),
    )

    op.create_table(
        "prc_invoice_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_purchase_orders.id"), nullable=False, index=True),
        sa.Column("goods_receipt_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_goods_receipt_notes.id"), nullable=True),
        sa.Column("vendor_invoice_reference", sa.String(128), nullable=False),
        sa.Column("invoice_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("po_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("grn_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("match_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exception_approved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("exception_approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exception_reason", sa.Text, nullable=True),
        sa.Column("released_for_payment", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.CheckConstraint("match_status IN ('pending','matched','discrepancy')", name="ck_prc_invoice_matches_status"),
    )

    op.create_table(
        "prc_vendor_performance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_vendors.id"), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("on_time_delivery_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("quality_rejection_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("price_competitiveness_score", sa.Numeric(5, 2), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "prc_supplier_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prc_vendors.id"), nullable=False, index=True),
        sa.Column("rating_period", sa.String(32), nullable=True),
        sa.Column("scorecard", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    for table in PRC_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(PRC_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("prc_supplier_ratings")
    op.drop_table("prc_vendor_performance_records")
    op.drop_table("prc_invoice_matches")
    op.drop_table("prc_goods_receipt_lines")
    op.drop_table("prc_goods_receipt_notes")
    op.drop_table("prc_po_approval_steps")
    op.drop_table("prc_purchase_order_lines")
    op.drop_table("prc_purchase_orders")
    op.drop_table("prc_purchase_requests")
    op.drop_table("prc_rfq_quotations")
    op.drop_table("prc_rfq_invitations")
    op.drop_table("prc_rfqs")
    op.drop_table("prc_vendor_compliance_documents")
    op.drop_table("prc_vendors")
