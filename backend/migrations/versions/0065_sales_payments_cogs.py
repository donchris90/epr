"""sales: customer payments and cost-of-goods-sold posting

Revision ID: 0065_sales_payments_cogs
Revises: 0064_sales_orders
Create Date: 2026-10-27

Optional COGS / inventory / receipt accounts on the sales settings, the
COGS journal entry on each delivery, amount paid on each invoice, and a
payments table (RLS-isolated like the rest).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0065_sales_payments_cogs"
down_revision = "0064_sales_orders"
branch_labels = None
depends_on = None

METHODS = "('cash', 'transfer', 'cheque', 'card', 'other')"


def upgrade():
    for col in ("cogs_account_id", "inventory_account_id", "receipt_account_id"):
        op.add_column("sal_settings", sa.Column(col, postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_chart_of_accounts.id"), nullable=True))
    op.add_column("sal_deliveries", sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=True))
    op.add_column("sal_invoices", sa.Column("amount_paid", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.create_check_constraint("ck_sal_invoices_paid", "sal_invoices", "amount_paid >= 0 AND amount_paid <= amount")

    op.create_table(
        "sal_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sal_invoices.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_at", sa.Date, nullable=False),
        sa.Column("method", sa.String(16), nullable=False, server_default="transfer"),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column("deposit_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_chart_of_accounts.id"), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fin_journal_entries.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_sal_payments_amount"),
        sa.CheckConstraint(f"method IN {METHODS}", name="ck_sal_payments_method"),
    )
    op.execute("ALTER TABLE sal_payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sal_payments FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON sal_payments USING (tenant_id = current_setting('app.tenant_id')::uuid)")


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON sal_payments")
    op.drop_table("sal_payments")
    op.drop_constraint("ck_sal_invoices_paid", "sal_invoices", type_="check")
    op.drop_column("sal_invoices", "amount_paid")
    op.drop_column("sal_deliveries", "journal_entry_id")
    for col in ("receipt_account_id", "inventory_account_id", "cogs_account_id"):
        op.drop_column("sal_settings", col)
