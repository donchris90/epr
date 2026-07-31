"""bdc module tables

Revision ID: 0002_bdc
Revises: 0001_core
Create Date: 2026-07-24

Creates the tables defined in app/modules/bdc/models.py (SRS Section 4.1)
and enables Row-Level Security + the tenant_isolation policy on every one
of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_bdc"
down_revision = "0001_core"
branch_labels = None
depends_on = None


BDC_TABLES = [
    "bdc_clients",
    "bdc_consultants",
    "bdc_government_agencies",
    "bdc_contacts",
    "bdc_leads",
    "bdc_opportunities",
    "bdc_competitors",
    "bdc_proposals",
    "bdc_win_loss_records",
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
    # See migrations/versions/0001_core.py for why FORCE matters here.
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade():
    op.create_table(
        "bdc_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("billing_address", sa.Text, nullable=True),
        sa.Column("billing_email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_bdc_clients_tenant_name", "bdc_clients", ["tenant_id", "name"])

    op.create_table(
        "bdc_consultants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("discipline", sa.String(128), nullable=True),
        sa.Column("relationship_notes", sa.Text, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "bdc_government_agencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(128), nullable=True),
        sa.Column("tender_pattern_notes", sa.Text, nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "bdc_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_clients.id"), nullable=True, index=True),
        sa.Column("consultant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_consultants.id"), nullable=True, index=True),
        sa.Column(
            "government_agency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bdc_government_agencies.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(128), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "bdc_leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_clients.id"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("estimated_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("probability_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('open','converted','archived')", name="ck_bdc_leads_status"),
        sa.CheckConstraint(
            "probability_pct IS NULL OR (probability_pct >= 0 AND probability_pct <= 100)",
            name="ck_bdc_leads_probability_range",
        ),
    )

    op.create_table(
        "bdc_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_leads.id"), nullable=True, index=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_clients.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False, server_default="identified", index=True),
        sa.Column("estimated_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("bid_no_bid_decision", sa.String(16), nullable=True),
        sa.Column("bid_no_bid_scorecard", postgresql.JSONB, nullable=True),
        sa.Column("bid_no_bid_rationale", sa.Text, nullable=True),
        sa.Column("bid_no_bid_approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bid_no_bid_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("no_bid_reason_code", sa.String(64), nullable=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submission_deadline", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "stage IN ('identified','qualified','bid_no_bid','submitted','won','lost')",
            name="ck_bdc_opportunities_stage",
        ),
        sa.CheckConstraint(
            "bid_no_bid_decision IS NULL OR bid_no_bid_decision IN ('bid','no_bid')",
            name="ck_bdc_opportunities_decision",
        ),
    )
    op.create_index(
        "ix_bdc_opportunities_tenant_deadline", "bdc_opportunities", ["tenant_id", "submission_deadline"]
    )

    op.create_table(
        "bdc_competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("known_win_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("known_loss_count", sa.Integer, nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "bdc_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "opportunity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_opportunities.id"), nullable=False, index=True
        ),
        sa.Column("template_key", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("generated_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "bdc_win_loss_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bdc_opportunities.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("winning_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("competitor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bdc_competitors.id"), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("sector", sa.String(128), nullable=True),
        sa.Column("value_band", sa.String(32), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("outcome IN ('won','lost')", name="ck_bdc_winloss_outcome"),
    )

    for table in BDC_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(BDC_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("bdc_win_loss_records")
    op.drop_table("bdc_proposals")
    op.drop_table("bdc_competitors")
    op.drop_table("bdc_opportunities")
    op.drop_table("bdc_leads")
    op.drop_table("bdc_contacts")
    op.drop_table("bdc_government_agencies")
    op.drop_table("bdc_consultants")
    op.drop_table("bdc_clients")
