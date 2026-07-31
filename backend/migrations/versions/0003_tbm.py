"""tbm module tables

Revision ID: 0003_tbm
Revises: 0002_bdc
Create Date: 2026-07-24

Creates the tables defined in app/modules/tbm/models.py (SRS Section 4.2)
and enables Row-Level Security + FORCE + the tenant_isolation policy on
every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_tbm"
down_revision = "0002_bdc"
branch_labels = None
depends_on = None


TBM_TABLES = [
    "tbm_tenders",
    "tbm_tender_boq_items",
    "tbm_scope_items",
    "tbm_bid_documents",
    "tbm_rfis",
    "tbm_clarifications",
    "tbm_approval_steps",
    "tbm_tender_checklist_items",
    "tbm_submissions",
    "tbm_jv_partners",
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
        "tbm_tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("reference_number", sa.String(128), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("consultant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submission_deadline", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("bid_bond_required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("bid_bond_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("tender_fee", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("is_joint_venture", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("estimate_locked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("estimate_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopen_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_reopen_reason", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('draft','in_estimate','in_approval','submitted','awarded','lost')",
            name="ck_tbm_tenders_status",
        ),
        sa.UniqueConstraint("tenant_id", "reference_number", name="uq_tbm_tenders_tenant_reference"),
    )
    op.create_index("ix_tbm_tenders_tenant_deadline", "tbm_tenders", ["tenant_id", "submission_deadline"])

    op.create_table(
        "tbm_tender_boq_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("item_code", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        *_audit_columns(),
    )
    op.create_foreign_key(
        "fk_tbm_tender_boq_items_parent", "tbm_tender_boq_items", "tbm_tender_boq_items", ["parent_id"], ["id"]
    )

    op.create_table(
        "tbm_scope_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "tender_boq_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tbm_tender_boq_items.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("annotation_type", sa.String(32), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "annotation_type IN ('clarifying_note','assumption','exclusion')", name="ck_tbm_scope_items_type"
        ),
    )

    op.create_table(
        "tbm_bid_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        *_audit_columns(),
        sa.CheckConstraint(
            "doc_type IN ('technical_proposal','financial_proposal','bid_bond','power_of_attorney','certification','other')",
            name="ck_tbm_bid_documents_type",
        ),
    )

    op.create_table(
        "tbm_rfis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("related_boq_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tender_boq_items.id"), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('open','answered','overdue')", name="ck_tbm_rfis_status"),
    )

    op.create_table(
        "tbm_clarifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("addendum_number", sa.String(32), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("affected_boq_item_ids", postgresql.JSONB, nullable=True),
        sa.Column("requires_reestimate", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "tbm_approval_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("role_required", sa.String(128), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_tbm_approval_steps_status"),
        sa.UniqueConstraint("tender_id", "step_order", name="uq_tbm_approval_steps_tender_order"),
    )

    op.create_table(
        "tbm_tender_checklist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "tbm_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "tender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tbm_tenders.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("receipt_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("acknowledgment_reference", sa.String(255), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("method IN ('portal','email','hand_delivery','courier')", name="ck_tbm_submissions_method"),
    )

    op.create_table(
        "tbm_jv_partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tbm_tenders.id"), nullable=False, index=True),
        sa.Column("partner_name", sa.String(255), nullable=False),
        sa.Column("scope_share_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("financial_share_pct", sa.Numeric(5, 2), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "scope_share_pct >= 0 AND scope_share_pct <= 100", name="ck_tbm_jv_partners_scope_share_range"
        ),
        sa.CheckConstraint(
            "financial_share_pct >= 0 AND financial_share_pct <= 100",
            name="ck_tbm_jv_partners_financial_share_range",
        ),
    )

    for table in TBM_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(TBM_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("tbm_jv_partners")
    op.drop_table("tbm_submissions")
    op.drop_table("tbm_tender_checklist_items")
    op.drop_table("tbm_approval_steps")
    op.drop_table("tbm_clarifications")
    op.drop_table("tbm_rfis")
    op.drop_table("tbm_bid_documents")
    op.drop_table("tbm_scope_items")
    op.drop_constraint("fk_tbm_tender_boq_items_parent", "tbm_tender_boq_items", type_="foreignkey")
    op.drop_table("tbm_tender_boq_items")
    op.drop_table("tbm_tenders")
