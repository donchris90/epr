"""
Sales (Code: SAL)

Sells stock (finished goods or anything in the item catalog) to a
client: a sales order, delivery notes that take stock out of the
warehouse as goods leave, and invoices that post to the finance ledger
(receivable, revenue and output VAT).

Design notes:
  - Customers are BDC's `Client`; items are INV's `MaterialItem`.
  - An order's lines track `delivered_quantity` and `invoiced_quantity`,
    so partial deliveries and invoicing only what has gone out both work
    without a separate allocation table.
  - Totals and the VAT rate are snapshotted on the order, so changing the
    tenant's VAT setting later does not rewrite old orders.
"""
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin

ORDER_STATUSES = ("draft", "confirmed", "partially_delivered", "delivered", "cancelled")


class SalesSettings(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """One row per tenant: which company and ledger accounts sales
    invoices post to, and the default VAT and payment terms."""

    __tablename__ = "sal_settings"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False)
    receivable_account_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_chart_of_accounts.id"), nullable=False)
    revenue_account_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_chart_of_accounts.id"), nullable=False)
    vat_account_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_chart_of_accounts.id"), nullable=True)
    vat_percent = db.Column(db.Numeric(5, 2), nullable=False, default=7.5)
    payment_terms_days = db.Column(db.Integer, nullable=False, default=30)

    __table_args__ = (
        db.UniqueConstraint("tenant_id", name="uq_sal_settings_tenant"),
        db.CheckConstraint("vat_percent >= 0 AND vat_percent <= 100", name="ck_sal_settings_vat"),
        db.CheckConstraint("payment_terms_days >= 0", name="ck_sal_settings_terms"),
    )


class SalesOrder(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "sal_sales_orders"

    number = db.Column(db.String(32), nullable=False)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_clients.id"), nullable=False, index=True)
    warehouse_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_warehouses.id"), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="draft")
    order_date = db.Column(db.Date, nullable=False)
    delivery_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    vat_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    subtotal = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    vat_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(18, 2), nullable=False, default=0)

    lines = relationship("SalesOrderLine", back_populates="order", cascade="all, delete-orphan", order_by="SalesOrderLine.created_at")
    deliveries = relationship("Delivery", back_populates="order", order_by="Delivery.created_at")
    invoices = relationship("SalesInvoice", back_populates="order", order_by="SalesInvoice.created_at")

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "number", name="uq_sal_sales_orders_tenant_number"),
        db.CheckConstraint(f"status IN {ORDER_STATUSES}", name="ck_sal_sales_orders_status"),
    )


class SalesOrderLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "sal_sales_order_lines"

    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit_price = db.Column(db.Numeric(18, 4), nullable=False)
    delivered_quantity = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    invoiced_quantity = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    order = relationship("SalesOrder", back_populates="lines")

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_sal_order_lines_qty"),
        db.CheckConstraint("unit_price >= 0", name="ck_sal_order_lines_price"),
        db.CheckConstraint("delivered_quantity >= 0 AND delivered_quantity <= quantity", name="ck_sal_order_lines_delivered"),
        db.CheckConstraint("invoiced_quantity >= 0 AND invoiced_quantity <= delivered_quantity", name="ck_sal_order_lines_invoiced"),
    )


class Delivery(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """A delivery note: goods that left the warehouse for one order."""

    __tablename__ = "sal_deliveries"

    number = db.Column(db.String(32), nullable=False)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_sales_orders.id"), nullable=False, index=True)
    delivered_at = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    order = relationship("SalesOrder", back_populates="deliveries")
    lines = relationship("DeliveryLine", back_populates="delivery", cascade="all, delete-orphan", order_by="DeliveryLine.created_at")

    __table_args__ = (db.UniqueConstraint("tenant_id", "number", name="uq_sal_deliveries_tenant_number"),)


class DeliveryLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """`valued_cost` is what the stock cost (per the tenant's valuation
    method) at the moment it left -- the cost of goods sold."""

    __tablename__ = "sal_delivery_lines"

    delivery_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_deliveries.id", ondelete="CASCADE"), nullable=False, index=True)
    order_line_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_sales_order_lines.id"), nullable=False)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    valued_cost = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    delivery = relationship("Delivery", back_populates="lines")

    __table_args__ = (db.CheckConstraint("quantity > 0", name="ck_sal_delivery_lines_qty"),)


class SalesInvoice(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "sal_invoices"

    number = db.Column(db.String(32), nullable=False)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_sales_orders.id"), nullable=False, index=True)
    ar_invoice_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_ar_invoices.id"), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    net_amount = db.Column(db.Numeric(18, 2), nullable=False)
    vat_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    amount = db.Column(db.Numeric(18, 2), nullable=False)

    order = relationship("SalesOrder", back_populates="invoices")
    lines = relationship("SalesInvoiceLine", back_populates="invoice", cascade="all, delete-orphan", order_by="SalesInvoiceLine.created_at")

    __table_args__ = (db.UniqueConstraint("tenant_id", "number", name="uq_sal_invoices_tenant_number"),)


class SalesInvoiceLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    __tablename__ = "sal_invoice_lines"

    invoice_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    order_line_id = db.Column(UUID(as_uuid=True), db.ForeignKey("sal_sales_order_lines.id"), nullable=False)
    material_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("inv_material_items.id"), nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit_price = db.Column(db.Numeric(18, 4), nullable=False)
    line_total = db.Column(db.Numeric(18, 2), nullable=False)

    invoice = relationship("SalesInvoice", back_populates="lines")
