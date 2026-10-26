"""Sales services: orders, deliveries and invoices."""
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.modules.bdc.models import Client
from app.modules.fin import services as fin_services
from app.modules.fin.models import ChartOfAccounts, Company
from app.modules.inv import services as inv_services
from app.modules.inv.models import MaterialItem, Warehouse
from app.modules.sal.models import (
    Delivery,
    DeliveryLine,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
    SalesSettings,
)
from app.utils.errors import APIError

ZERO = Decimal("0")
CENT = Decimal("0.01")
DEFAULT_VAT = Decimal("7.5")


def _money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _dec(value, field, *, allow_zero=False):
    try:
        d = Decimal(str(value))
    except Exception:
        raise APIError(f"{field} must be a number", status=422)
    if d < 0 or (d == 0 and not allow_zero):
        raise APIError(f"{field} must be {'zero or more' if allow_zero else 'greater than zero'}", status=422)
    return d


# --- Settings ----------------------------------------------------------------

def get_settings(tenant_id):
    return SalesSettings.query.filter_by(tenant_id=tenant_id).first()


def save_settings(tenant_id, *, company_id, receivable_account_id, revenue_account_id, vat_account_id, vat_percent, payment_terms_days):
    if not Company.query.filter_by(id=company_id, tenant_id=tenant_id).first():
        raise APIError("Company not found", status=404)
    for label, acc in (("Receivable", receivable_account_id), ("Revenue", revenue_account_id), ("VAT", vat_account_id)):
        if acc and not ChartOfAccounts.query.filter_by(id=acc, tenant_id=tenant_id).first():
            raise APIError(f"{label} account not found", status=404)
    vat_percent = Decimal(str(vat_percent))
    if vat_percent > 0 and not vat_account_id:
        raise APIError("Choose a VAT account (output VAT payable), or set the VAT rate to 0", status=422)
    row = get_settings(tenant_id) or SalesSettings(tenant_id=tenant_id)
    row.company_id = company_id
    row.receivable_account_id = receivable_account_id
    row.revenue_account_id = revenue_account_id
    row.vat_account_id = vat_account_id
    row.vat_percent = vat_percent
    row.payment_terms_days = payment_terms_days
    db.session.add(row)
    db.session.commit()
    return row


# --- Orders ---------------------------------------------------------------------

def _next_number(model, tenant_id, prefix) -> str:
    count = db.session.query(db.func.count(model.id)).filter(model.tenant_id == tenant_id).scalar()
    return f"{prefix}-{count + 1:05d}"


def _totals(order: SalesOrder):
    subtotal = _money(sum((l.quantity * l.unit_price for l in order.lines), ZERO))
    vat = _money(subtotal * order.vat_percent / 100)
    order.subtotal, order.vat_amount, order.total = subtotal, vat, subtotal + vat


def _build_lines(tenant_id, lines):
    if not lines:
        raise APIError("An order needs at least one line", status=422)
    built, seen = [], set()
    for line in lines:
        item_id = str(line["material_item_id"])
        if item_id in seen:
            raise APIError("An item appears twice on the order", status=422, detail="Combine the quantities into one line.")
        seen.add(item_id)
        item = MaterialItem.query.filter_by(id=item_id, tenant_id=tenant_id).first()
        if not item:
            raise APIError("Item not found", status=404)
        qty = _dec(line["quantity"], "quantity")
        price = line.get("unit_price")
        if price is None:
            price = item.sale_price
        if price is None:
            raise APIError(f"{item.code} has no selling price", status=422, detail="Enter a unit price, or set a sale price on the item.")
        built.append(SalesOrderLine(tenant_id=tenant_id, material_item_id=item.id, quantity=qty, unit_price=_dec(price, "unit_price", allow_zero=True)))
    return built


def save_order(tenant_id, *, order: SalesOrder = None, client_id, warehouse_id, lines, order_date=None, delivery_date=None, notes=None, actor_id=None):
    """Creates a draft order, or replaces a draft order's header and lines."""
    if order is not None and order.status != "draft":
        raise APIError("Only a draft order can be edited", status=409)
    if not Client.query.filter_by(id=client_id, tenant_id=tenant_id, deleted_at=None).first():
        raise APIError("Client not found", status=404)
    if not Warehouse.query.filter_by(id=warehouse_id, tenant_id=tenant_id).first():
        raise APIError("Warehouse not found", status=404)
    built = _build_lines(tenant_id, lines)

    if order is None:
        settings = get_settings(tenant_id)
        order = SalesOrder(
            tenant_id=tenant_id,
            number=_next_number(SalesOrder, tenant_id, "SO"),
            status="draft",
            vat_percent=settings.vat_percent if settings else DEFAULT_VAT,
            created_by=actor_id,
        )
        db.session.add(order)
    order.client_id = client_id
    order.warehouse_id = warehouse_id
    order.order_date = order_date or date.today()
    order.delivery_date = delivery_date
    order.notes = notes
    try:
        order.lines[:] = []
        db.session.flush()
        order.lines[:] = built
        _totals(order)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise APIError("Could not allocate an order number, please retry", status=409)
    return order


def confirm_order(order: SalesOrder):
    if order.status != "draft":
        raise APIError(f"Cannot confirm a {order.status.replace('_', ' ')} order", status=409)
    order.status = "confirmed"
    db.session.commit()
    return order


def cancel_order(order: SalesOrder):
    if order.status not in ("draft", "confirmed"):
        raise APIError(f"Cannot cancel a {order.status.replace('_', ' ')} order", status=409,
                       detail="Goods have already been delivered against it." if order.status != "cancelled" else None)
    order.status = "cancelled"
    db.session.commit()
    return order


# --- Deliveries ---------------------------------------------------------------------

def deliver(tenant_id, order: SalesOrder, *, lines, delivered_at=None, notes=None, actor_id=None):
    """Sends goods out against an order. Takes the stock out of the
    order's warehouse and records its cost. All-or-nothing: if any item
    is short, nothing leaves stock and no delivery note is created."""
    if order.status not in ("confirmed", "partially_delivered"):
        raise APIError(f"Cannot deliver a {order.status.replace('_', ' ')} order", status=409,
                       detail="Confirm the order first." if order.status == "draft" else None)
    if not lines:
        raise APIError("Nothing to deliver", status=422)

    by_id = {str(l.id): l for l in order.lines}
    wanted = {}
    for l in lines:
        key = str(l["order_line_id"])
        if key not in by_id:
            raise APIError("Delivery includes a line that is not on this order", status=422)
        if key in wanted:
            raise APIError("A line appears twice in the delivery", status=422)
        qty = _dec(l["quantity"], "quantity")
        line = by_id[key]
        remaining = line.quantity - line.delivered_quantity
        if qty > remaining:
            raise APIError("Cannot deliver more than is left on the order", status=409,
                           detail=f"Only {remaining.normalize():f} left to deliver on one line (asked for {qty.normalize():f}).")
        wanted[key] = qty

    try:
        delivery = Delivery(
            tenant_id=tenant_id, number=_next_number(Delivery, tenant_id, "DN"), order_id=order.id,
            delivered_at=delivered_at or date.today(), notes=notes, created_by=actor_id,
        )
        for key, qty in wanted.items():
            line = by_id[key]
            issued = inv_services.issue_stock(
                tenant_id, warehouse_id=order.warehouse_id, material_item_id=line.material_item_id, quantity=qty, commit=False
            )
            line.delivered_quantity += qty
            delivery.lines.append(
                DeliveryLine(tenant_id=tenant_id, order_line_id=line.id, material_item_id=line.material_item_id,
                             quantity=qty, valued_cost=issued["valued_cost"])
            )
        db.session.add(delivery)
        fully = all(l.delivered_quantity >= l.quantity for l in order.lines)
        order.status = "delivered" if fully else "partially_delivered"
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return delivery


# --- Invoicing ---------------------------------------------------------------------------

def uninvoiced(order: SalesOrder):
    return [(l, l.delivered_quantity - l.invoiced_quantity) for l in order.lines if l.delivered_quantity > l.invoiced_quantity]


def invoice_delivered(tenant_id, order: SalesOrder, *, actor_id=None, invoice_date=None):
    """Invoices everything delivered but not yet invoiced, and posts it
    to the ledger: Dr receivable, Cr revenue (net), Cr output VAT."""
    settings = get_settings(tenant_id)
    if not settings:
        raise APIError("Sales accounting is not set up", status=409,
                       detail="Choose the company and the receivable, revenue and VAT accounts in the sales settings first.")
    pending = uninvoiced(order)
    if not pending:
        raise APIError("Nothing to invoice", status=409, detail="Everything delivered so far has already been invoiced.")
    invoice_date = invoice_date or date.today()

    try:
        invoice = SalesInvoice(
            tenant_id=tenant_id, number=_next_number(SalesInvoice, tenant_id, "SI"), order_id=order.id,
            invoice_date=invoice_date, due_date=invoice_date + timedelta(days=settings.payment_terms_days), created_by=actor_id,
        )
        net = ZERO
        for line, qty in pending:
            total = _money(qty * line.unit_price)
            net += total
            line.invoiced_quantity += qty
            invoice.lines.append(
                SalesInvoiceLine(tenant_id=tenant_id, order_line_id=line.id, material_item_id=line.material_item_id,
                                 quantity=qty, unit_price=line.unit_price, line_total=total)
            )
        vat = _money(net * order.vat_percent / 100)
        if net + vat <= 0:
            raise APIError("Nothing to invoice", status=409, detail="The delivered items have no value.")
        if vat and not settings.vat_account_id:
            raise APIError("A VAT account is required", status=409, detail="Set the VAT account in the sales settings.")

        ar = fin_services.post_accounts_receivable_invoice(
            tenant_id,
            company_id=settings.company_id,
            source_module="SAL",
            source_reference=order.id,
            invoice_number=invoice.number,
            amount=net,
            receivable_account_id=settings.receivable_account_id,
            revenue_account_id=settings.revenue_account_id,
            client_reference=order.client_id,
            due_date=invoice.due_date,
            posted_by=actor_id,
            vat_amount=vat,
            vat_account_id=settings.vat_account_id,
            commit=False,
        )
        invoice.ar_invoice_id = ar.id
        invoice.net_amount, invoice.vat_amount, invoice.amount = net, vat, net + vat
        db.session.add(invoice)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return invoice


def delivered_cost(order: SalesOrder) -> Decimal:
    return sum((dl.valued_cost for d in order.deliveries for dl in d.lines), ZERO)


def delivered_value(order: SalesOrder) -> Decimal:
    return _money(sum((l.delivered_quantity * l.unit_price for l in order.lines), ZERO))
