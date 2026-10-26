"""Manufacturing — Flask Blueprint. Base path: /v1/mfg"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.mfg import services
from app.modules.mfg.models import Bom, ProductionOrder, WorkCenter
from app.modules.mfg.schemas import (
    BomSchema,
    CompleteOrderSchema,
    ProductionOrderInputSchema,
    ProductionOrderSchema,
    WorkCenterSchema,
)

bp = Blueprint("mfg", __name__, url_prefix="/v1/mfg")

work_center_schema = WorkCenterSchema()
bom_schema = BomSchema()
order_schema = ProductionOrderSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _order_or_404(order_id) -> ProductionOrder:
    order = ProductionOrder.query.filter_by(id=order_id, tenant_id=g.tenant_id).first()
    if not order:
        raise APIError("Production order not found", status=404)
    return order


def _bom_or_404(bom_id) -> Bom:
    bom = Bom.query.filter_by(id=bom_id, tenant_id=g.tenant_id).first()
    if not bom:
        raise APIError("BOM not found", status=404)
    return bom


@bp.get("/health")
def health():
    return jsonify({"module": "mfg", "name": "Manufacturing", "status": "ok"})


# --- Work centers -------------------------------------------------------------

@bp.post("/work-centers")
@require_permission("mfg:write")
def create_work_center():
    data = _load(work_center_schema)
    wc = WorkCenter(tenant_id=g.tenant_id, **data)
    db.session.add(wc)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise APIError("A work center with this code already exists", status=409)
    return jsonify(work_center_schema.dump(wc)), 201


@bp.get("/work-centers")
@require_permission("mfg:read")
def list_work_centers():
    rows = WorkCenter.query.filter_by(tenant_id=g.tenant_id).order_by(WorkCenter.code).all()
    return jsonify(envelope(work_center_schema.dump(rows, many=True)))


@bp.put("/work-centers/<uuid:wc_id>")
@require_permission("mfg:write")
def update_work_center(wc_id):
    wc = WorkCenter.query.filter_by(id=wc_id, tenant_id=g.tenant_id).first()
    if not wc:
        raise APIError("Work center not found", status=404)
    data = _load(work_center_schema)
    for key in ("name", "hourly_rate", "equipment_id", "is_active"):
        setattr(wc, key, data[key])
    db.session.commit()
    return jsonify(work_center_schema.dump(wc))


# --- Bills of materials ---------------------------------------------------------

@bp.post("/boms")
@require_permission("mfg:write")
def create_bom():
    data = _load(bom_schema)
    bom = services.save_bom(g.tenant_id, **data)
    return jsonify(bom_schema.dump(bom)), 201


@bp.get("/boms")
@require_permission("mfg:read")
def list_boms():
    q = Bom.query.filter_by(tenant_id=g.tenant_id)
    if request.args.get("product_item_id"):
        q = q.filter_by(product_item_id=request.args["product_item_id"])
    if request.args.get("active") == "true":
        q = q.filter_by(is_active=True)
    return jsonify(envelope(bom_schema.dump(q.order_by(Bom.code).all(), many=True)))


@bp.get("/boms/<uuid:bom_id>")
@require_permission("mfg:read")
def get_bom(bom_id):
    return jsonify(bom_schema.dump(_bom_or_404(bom_id)))


@bp.put("/boms/<uuid:bom_id>")
@require_permission("mfg:write")
def update_bom(bom_id):
    bom = _bom_or_404(bom_id)
    data = _load(bom_schema)
    data["code"] = bom.code  # a BOM's code is its identity
    return jsonify(bom_schema.dump(services.save_bom(g.tenant_id, bom=bom, **data)))


# --- Production orders ------------------------------------------------------------

@bp.post("/production-orders")
@require_permission("mfg:write")
def create_order():
    data = _load(ProductionOrderInputSchema())
    order = services.create_order(g.tenant_id, actor_id=g.user_id, **data)
    return jsonify(order_schema.dump(order)), 201


@bp.get("/production-orders")
@require_permission("mfg:read")
def list_orders():
    q = ProductionOrder.query.filter_by(tenant_id=g.tenant_id)
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    rows = q.order_by(ProductionOrder.number.desc()).all()
    return jsonify(envelope(order_schema.dump(rows, many=True)))


@bp.get("/production-orders/<uuid:order_id>")
@require_permission("mfg:read")
def get_order(order_id):
    return jsonify(order_schema.dump(_order_or_404(order_id)))


@bp.get("/production-orders/<uuid:order_id>/availability")
@require_permission("mfg:read")
def order_availability(order_id):
    rows = services.availability(g.tenant_id, _order_or_404(order_id))
    return jsonify(
        envelope(
            [
                {
                    "component_item_id": str(r["component_item_id"]),
                    "code": r["code"],
                    "required": str(r["required"]),
                    "available": str(r["available"]),
                    "short": str(r["short"]),
                }
                for r in rows
            ]
        )
    )


@bp.get("/production-orders/<uuid:order_id>/variances")
@require_permission("mfg:read")
def order_variances(order_id):
    rows = services.variances(_order_or_404(order_id))
    return jsonify(envelope([{k: str(v) for k, v in r.items()} for r in rows]))


@bp.post("/production-orders/<uuid:order_id>/release")
@require_permission("mfg:write")
def release_order(order_id):
    return jsonify(order_schema.dump(services.release_order(_order_or_404(order_id))))


@bp.post("/production-orders/<uuid:order_id>/start")
@require_permission("mfg:write")
def start_order(order_id):
    return jsonify(order_schema.dump(services.start_order(_order_or_404(order_id))))


@bp.post("/production-orders/<uuid:order_id>/cancel")
@require_permission("mfg:write")
def cancel_order(order_id):
    return jsonify(order_schema.dump(services.cancel_order(_order_or_404(order_id))))


@bp.post("/production-orders/<uuid:order_id>/complete")
@require_permission("mfg:approve")
def complete_order(order_id):
    order = _order_or_404(order_id)
    data = _load(CompleteOrderSchema())
    done = services.complete_order(g.tenant_id, order, actor_id=g.user_id, **data)
    return jsonify(order_schema.dump(done))
