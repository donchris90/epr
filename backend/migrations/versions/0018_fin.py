"""fin module tables

Revision ID: 0018_fin
Revises: 0017_pq
Create Date: 2026-07-30

Creates the tables defined in app/modules/fin/models.py (SRS Section
4.17) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_fin"
down_revision = "0017_pq"
branch_labels = None
depends_on = None


FIN_TABLES = [
    "fin_companies",
    "fin_chart_of_accounts",
    "fin_budget_control_policies",
    "fin_journal_entries",
    "fin_general_ledger_lines",
    "fin_ap_invoices",
    "fin_ar_invoices",
    "fin_fixed_assets",
    "fin_bank_statement_lines",
    "fin_tax_records",
    "fin_cash_flow_forecast_entries",
    "fin_financial_statements",
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
        "fin_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("functional_currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "fin_chart_of_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.CheckConstraint("account_type IN ('asset','liability','equity','revenue','expense')", name="ck_fin_coa_account_type"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_fin_coa_tenant_code"),
    )

    op.create_table(
        "fin_budget_control_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("cost_category", sa.String(64), nullable=True),
        sa.Column("enforcement_mode", sa.String(16), nullable=False, server_default="warning"),
        *_audit_columns(),
        sa.CheckConstraint("enforcement_mode IN ('hard_block','warning')", name="ck_fin_budget_policy_mode"),
    )

    op.create_table(
        "fin_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=False, index=True),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("source_module", sa.String(32), nullable=False),
        sa.Column("source_reference", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="posted"),
        sa.Column("posted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("exchange_rate", sa.Numeric(12, 6), nullable=False, server_default="1"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('posted')", name="ck_fin_journal_status"),
    )

    op.create_table(
        "fin_general_ledger_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=False, index=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_chart_of_accounts.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("cost_code", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("debit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "fin_ap_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=False, index=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=False),
        sa.Column("counterparty_reference", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_number", sa.String(128), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="unpaid"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('unpaid','paid')", name="ck_fin_ap_status"),
    )

    op.create_table(
        "fin_ar_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=False, index=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=False),
        sa.Column("client_reference", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_number", sa.String(128), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="unpaid"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('unpaid','paid')", name="ck_fin_ar_status"),
    )

    op.create_table(
        "fin_fixed_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=False, index=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("salvage_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("useful_life_years", sa.Integer, nullable=True),
        sa.Column("acquired_at", sa.Date, nullable=True),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
    )

    op.create_table(
        "fin_bank_statement_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=False, index=True),
        sa.Column("bank_account_ref", sa.String(128), nullable=True),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("matched_journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="unmatched"),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('unmatched','matched','exception')", name="ck_fin_bank_line_status"),
    )

    op.create_table(
        "fin_tax_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=False, index=True),
        sa.Column("tax_type", sa.String(16), nullable=False),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("tax_type IN ('vat','withholding','other')", name="ck_fin_tax_type"),
    )

    op.create_table(
        "fin_cash_flow_forecast_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("forecast_inflow", sa.Numeric(18, 4), nullable=True),
        sa.Column("forecast_outflow", sa.Numeric(18, 4), nullable=True),
        sa.Column("actual_inflow", sa.Numeric(18, 4), nullable=True),
        sa.Column("actual_outflow", sa.Numeric(18, 4), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "fin_financial_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_companies.id"), nullable=True),
        sa.Column("statement_type", sa.String(24), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("data", postgresql.JSONB, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "statement_type IN ('income_statement','balance_sheet','cash_flow_statement')", name="ck_fin_statement_type"
        ),
    )

    for table in FIN_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(FIN_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("fin_financial_statements")
    op.drop_table("fin_cash_flow_forecast_entries")
    op.drop_table("fin_tax_records")
    op.drop_table("fin_bank_statement_lines")
    op.drop_table("fin_fixed_assets")
    op.drop_table("fin_ar_invoices")
    op.drop_table("fin_ap_invoices")
    op.drop_table("fin_general_ledger_lines")
    op.drop_table("fin_journal_entries")
    op.drop_table("fin_budget_control_policies")
    op.drop_table("fin_chart_of_accounts")
    op.drop_table("fin_companies")
