"""Sales — Flask Blueprint. Base path: /v1/sal"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.sal import services
from app.modules.sal.models import SalesInvoice, SalesOrder
from app.modules.sal.schemas import (
    DeliveryInputSchema,
    DeliverySchema,
    InvoiceSchema,
    OrderInputSchema,
    OrderSchema,
    SalesSettingsSchema,
)

bp = Blueprint("sal", __name__, url_prefix="/v1/sal")

settings_schema = SalesSettingsSchema()
order_schema = OrderSchema()
delivery_schema = DeliverySchema()
invoice_schema = InvoiceSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _order_or_404(order_id) -> SalesOrder:
    order = SalesOrder.query.filter_by(id=order_id, tenant_id=g.tenant_id).first()
    if not order:
        raise APIError("Sales order not found", status=404)
    return order


@bp.get("/health")
def health():
    return jsonify({"module": "sal", "name": "Sales", "status": "ok"})


@bp.get("/settings")
@require_permission("sal:read")
def get_settings():
    row = services.get_settings(g.tenant_id)
    return jsonify({"data": settings_schema.dump(row) if row else None})


@bp.put("/settings")
@require_permission("sal:approve")
def put_settings():
    data = _load(settings_schema)
    return jsonify(settings_schema.dump(services.save_settings(g.tenant_id, **data)))


@bp.post("/sales-orders")
@require_permission("sal:write")
def create_order():
    data = _load(OrderInputSchema())
    order = services.save_order(g.tenant_id, actor_id=g.user_id, **data)
    return jsonify(order_schema.dump(order)), 201


@bp.get("/sales-orders")
@require_permission("sal:read")
def list_orders():
    q = SalesOrder.query.filter_by(tenant_id=g.tenant_id)
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    if request.args.get("client_id"):
        q = q.filter_by(client_id=request.args["client_id"])
    return jsonify(envelope(order_schema.dump(q.order_by(SalesOrder.number.desc()).all(), many=True)))


@bp.get("/sales-orders/<uuid:order_id>")
@require_permission("sal:read")
def get_order(order_id):
    return jsonify(order_schema.dump(_order_or_404(order_id)))


@bp.put("/sales-orders/<uuid:order_id>")
@require_permission("sal:write")
def update_order(order_id):
    order = _order_or_404(order_id)
    data = _load(OrderInputSchema())
    return jsonify(order_schema.dump(services.save_order(g.tenant_id, order=order, actor_id=g.user_id, **data)))


@bp.post("/sales-orders/<uuid:order_id>/confirm")
@require_permission("sal:write")
def confirm_order(order_id):
    return jsonify(order_schema.dump(services.confirm_order(_order_or_404(order_id))))


@bp.post("/sales-orders/<uuid:order_id>/cancel")
@require_permission("sal:write")
def cancel_order(order_id):
    return jsonify(order_schema.dump(services.cancel_order(_order_or_404(order_id))))


@bp.post("/sales-orders/<uuid:order_id>/deliveries")
@require_permission("sal:write")
def deliver(order_id):
    order = _order_or_404(order_id)
    data = _load(DeliveryInputSchema())
    delivery = services.deliver(g.tenant_id, order, actor_id=g.user_id, **data)
    return jsonify(delivery_schema.dump(delivery)), 201


@bp.post("/sales-orders/<uuid:order_id>/invoice")
@require_permission("sal:approve")
def invoice_order(order_id):
    order = _order_or_404(order_id)
    invoice = services.invoice_delivered(g.tenant_id, order, actor_id=g.user_id)
    return jsonify(invoice_schema.dump(invoice)), 201


@bp.get("/invoices")
@require_permission("sal:read")
def list_invoices():
    rows = SalesInvoice.query.filter_by(tenant_id=g.tenant_id).order_by(SalesInvoice.number.desc()).all()
    return jsonify(envelope(invoice_schema.dump(rows, many=True)))
