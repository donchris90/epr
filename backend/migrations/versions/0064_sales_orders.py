"""sales: orders, deliveries, invoices, settings

Revision ID: 0064_sales_orders
Revises: 0063_factory_manufacturing
Create Date: 2026-10-27

Adds a default selling price to inventory items and the sales tables
(settings, orders and lines, delivery notes and lines, invoices and
lines). Every new table is RLS-isolated like the rest.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0064_sales_orders"
down_revision = "0063_factory_manufacturing"
branch_labels = None
depends_on = None

ORDER_STATUSES = "('draft', 'confirmed', 'partially_delivered', 'delivered', 'cancelled')"
NEW_TABLES = [
    "sal_settings", "sal_sales_orders", "sal_sales_order_lines", "sal_deliveries",
    "sal_delivery_lines", "sal_invoices", "sal_invoice_lines",
]


def _pk():
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _tenant():
    return sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _audit():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _ref(name, fk, nullable=False, index=False, ondelete=None):
    return sa.Column(name, postgresql.UUID(as_uuid=True), sa.ForeignKey(fk, ondelete=ondelete), nullable=nullable, index=index)


def upgrade():
    op.add_column("inv_material_items", sa.Column("sale_price", sa.Numeric(18, 4), nullable=True))

    op.create_table(
        "sal_settings", _pk(), _tenant(),
        _ref("company_id", "fin_companies.id"),
        _ref("receivable_account_id", "fin_chart_of_accounts.id"),
        _ref("revenue_account_id", "fin_chart_of_accounts.id"),
        _ref("vat_account_id", "fin_chart_of_accounts.id", nullable=True),
        sa.Column("vat_percent", sa.Numeric(5, 2), nullable=False, server_default="7.5"),
        sa.Column("payment_terms_days", sa.Integer, nullable=False, server_default="30"),
        *_audit(),
        sa.UniqueConstraint("tenant_id", name="uq_sal_settings_tenant"),
        sa.CheckConstraint("vat_percent >= 0 AND vat_percent <= 100", name="ck_sal_settings_vat"),
        sa.CheckConstraint("payment_terms_days >= 0", name="ck_sal_settings_terms"),
    )
    op.create_table(
        "sal_sales_orders", _pk(), _tenant(),
        sa.Column("number", sa.String(32), nullable=False),
        _ref("client_id", "bdc_clients.id", index=True),
        _ref("warehouse_id", "inv_warehouses.id"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("delivery_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("vat_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        *_audit(),
        sa.UniqueConstraint("tenant_id", "number", name="uq_sal_sales_orders_tenant_number"),
        sa.CheckConstraint(f"status IN {ORDER_STATUSES}", name="ck_sal_sales_orders_status"),
    )
    op.create_table(
        "sal_sales_order_lines", _pk(), _tenant(),
        _ref("order_id", "sal_sales_orders.id", index=True, ondelete="CASCADE"),
        _ref("material_item_id", "inv_material_items.id"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("delivered_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("invoiced_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit(),
        sa.CheckConstraint("quantity > 0", name="ck_sal_order_lines_qty"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sal_order_lines_price"),
        sa.CheckConstraint("delivered_quantity >= 0 AND delivered_quantity <= quantity", name="ck_sal_order_lines_delivered"),
        sa.CheckConstraint("invoiced_quantity >= 0 AND invoiced_quantity <= delivered_quantity", name="ck_sal_order_lines_invoiced"),
    )
    op.create_table(
        "sal_deliveries", _pk(), _tenant(),
        sa.Column("number", sa.String(32), nullable=False),
        _ref("order_id", "sal_sales_orders.id", index=True),
        sa.Column("delivered_at", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        *_audit(),
        sa.UniqueConstraint("tenant_id", "number", name="uq_sal_deliveries_tenant_number"),
    )
    op.create_table(
        "sal_delivery_lines", _pk(), _tenant(),
        _ref("delivery_id", "sal_deliveries.id", index=True, ondelete="CASCADE"),
        _ref("order_line_id", "sal_sales_order_lines.id"),
        _ref("material_item_id", "inv_material_items.id"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("valued_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit(),
        sa.CheckConstraint("quantity > 0", name="ck_sal_delivery_lines_qty"),
    )
    op.create_table(
        "sal_invoices", _pk(), _tenant(),
        sa.Column("number", sa.String(32), nullable=False),
        _ref("order_id", "sal_sales_orders.id", index=True),
        _ref("ar_invoice_id", "fin_ar_invoices.id"),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        *_audit(),
        sa.UniqueConstraint("tenant_id", "number", name="uq_sal_invoices_tenant_number"),
    )
    op.create_table(
        "sal_invoice_lines", _pk(), _tenant(),
        _ref("invoice_id", "sal_invoices.id", index=True, ondelete="CASCADE"),
        _ref("order_line_id", "sal_sales_order_lines.id"),
        _ref("material_item_id", "inv_material_items.id"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        *_audit(),
    )

    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_setting('app.tenant_id')::uuid)")


def downgrade():
    for table in reversed(NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
    op.drop_column("inv_material_items", "sale_price")
