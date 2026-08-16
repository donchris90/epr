"""
Module 8 — Inventory & Warehouse (Code: INV)
SRS Section 4.8 — Flask Blueprint. Base path: /v1/inv
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.inv import services
from app.modules.inv.models import (
    InventorySettings,
    Warehouse,
    MaterialItem,
    StockItem,
    StockTransfer,
    StockReservation,
    ReorderLevel,
    ItemCode,
    BatchNumber,
    SerialNumber,
    StockCount,
    StockCountLine,
)
from app.modules.inv.schemas import (
    InventorySettingsSchema,
    WarehouseSchema,
    MaterialItemSchema,
    StockItemSchema,
    ReceiveStockSchema,
    IssueStockSchema,
    StockTransferSchema,
    StockReservationSchema,
    ReorderLevelSchema,
    ItemCodeSchema,
    BatchNumberSchema,
    SerialNumberSchema,
    WasteRecordInputSchema,
    WasteRecordSchema,
    ReturnToYardSchema,
    ReturnToVendorSchema,
    MaterialReturnSchema,
    StartStockCountSchema,
    RecordCountLineSchema,
    StockCountSchema,
)

bp = Blueprint("inv", __name__, url_prefix="/v1/inv")

settings_schema = InventorySettingsSchema()
warehouse_schema = WarehouseSchema()
material_item_schema = MaterialItemSchema()
stock_item_schema = StockItemSchema()
transfer_schema = StockTransferSchema()
reservation_schema = StockReservationSchema()
reorder_level_schema = ReorderLevelSchema()
item_code_schema = ItemCodeSchema()
batch_schema = BatchNumberSchema()
serial_schema = SerialNumberSchema()
waste_schema = WasteRecordSchema()
material_return_schema = MaterialReturnSchema()
stock_count_schema = StockCountSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_warehouse_or_404(warehouse_id) -> Warehouse:
    w = Warehouse.query.filter_by(id=warehouse_id, tenant_id=g.tenant_id).first()
    if not w:
        raise APIError("Warehouse not found", status=404)
    return w


@bp.get("/health")
def health():
    return jsonify({"module": "inv", "name": "Inventory & Warehouse", "status": "ok"})


# --- Settings (INV-11) --------------------------------------------------------

@bp.put("/settings")
@require_permission("inv:approve")
def set_inventory_settings():
    data = _load(settings_schema)
    settings = InventorySettings.query.filter_by(tenant_id=g.tenant_id).first()
    if settings:
        settings.valuation_method = data["valuation_method"]
    else:
        settings = InventorySettings(tenant_id=g.tenant_id, **data)
        db.session.add(settings)
    db.session.commit()
    return jsonify(settings_schema.dump(settings))


# --- Warehouses (INV-01) -------------------------------------------------------

@bp.post("/warehouses")
@require_permission("inv:write")
def create_warehouse():
    data = _load(warehouse_schema)
    warehouse = Warehouse(tenant_id=g.tenant_id, **data)
    db.session.add(warehouse)
    db.session.commit()
    return jsonify(warehouse_schema.dump(warehouse)), 201


@bp.get("/warehouses")
@require_permission("inv:read")
def list_warehouses():
    warehouses = Warehouse.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(warehouse_schema.dump(warehouses, many=True)))


@bp.get("/warehouses/<uuid:warehouse_id>/stock")
@require_permission("inv:read")
def list_warehouse_stock(warehouse_id):
    _get_warehouse_or_404(warehouse_id)
    items = StockItem.query.filter_by(warehouse_id=warehouse_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(stock_item_schema.dump(items, many=True)))


# --- Material items (catalog) --------------------------------------------------

@bp.post("/material-items")
@require_permission("inv:write")
def create_material_item():
    data = _load(material_item_schema)
    item = MaterialItem(tenant_id=g.tenant_id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(material_item_schema.dump(item)), 201


@bp.get("/material-items")
@require_permission("inv:read")
def list_material_items():
    items = MaterialItem.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(material_item_schema.dump(items, many=True)))


# --- Receiving & issuing (INV-11 valuation) -------------------------------------

@bp.post("/stock/receive")
@require_permission("inv:write")
def receive_stock():
    data = _load(ReceiveStockSchema())
    _get_warehouse_or_404(data["warehouse_id"])
    stock_item = services.receive_stock(g.tenant_id, **data)
    return jsonify(stock_item_schema.dump(stock_item)), 201


@bp.post("/stock/issue")
@require_permission("inv:write")
def issue_stock():
    data = _load(IssueStockSchema())
    _get_warehouse_or_404(data["warehouse_id"])
    result = services.issue_stock(g.tenant_id, **data)
    return jsonify({"quantity": str(result["quantity"]), "valued_cost": str(result["valued_cost"])})


@bp.get("/stock/available")
@require_permission("inv:read")
def get_available_quantity():
    warehouse_id = request.args.get("warehouse_id")
    material_item_id = request.args.get("material_item_id")
    if not warehouse_id or not material_item_id:
        raise APIError("warehouse_id and material_item_id are required", status=400)

    available = services.available_quantity(g.tenant_id, warehouse_id, material_item_id)
    return jsonify({"available_quantity": str(available)})


# --- Reservations (INV-03) -------------------------------------------------------

@bp.post("/stock/reservations")
@require_permission("inv:write")
def create_reservation():
    data = _load(reservation_schema)
    reservation = services.reserve_stock(g.tenant_id, reserved_by=g.user_id, **data)
    return jsonify(reservation_schema.dump(reservation)), 201


@bp.post("/stock/reservations/<uuid:reservation_id>/release")
@require_permission("inv:write")
def release_reservation(reservation_id):
    reservation = StockReservation.query.filter_by(id=reservation_id, tenant_id=g.tenant_id).first()
    if not reservation:
        raise APIError("Reservation not found", status=404)
    reservation = services.release_reservation(reservation)
    return jsonify(reservation_schema.dump(reservation))


# --- Stock transfers (INV-02, business rule) --------------------------------------

@bp.post("/stock-transfers")
@require_permission("inv:write")
def initiate_transfer():
    data = _load(transfer_schema)
    transfer = services.initiate_transfer(g.tenant_id, dispatched_by=g.user_id, **data)
    return jsonify(transfer_schema.dump(transfer)), 201


@bp.post("/stock-transfers/<uuid:transfer_id>/confirm-receipt")
@require_permission("inv:write")
def confirm_transfer_receipt(transfer_id):
    transfer = StockTransfer.query.filter_by(id=transfer_id, tenant_id=g.tenant_id).first()
    if not transfer:
        raise APIError("Transfer not found", status=404)
    transfer = services.confirm_transfer_receipt(transfer, received_by=g.user_id)
    return jsonify(transfer_schema.dump(transfer))


# --- Reorder levels (INV-04) --------------------------------------------------------

@bp.post("/reorder-levels")
@require_permission("inv:write")
def create_reorder_level():
    data = _load(reorder_level_schema)
    level = ReorderLevel(tenant_id=g.tenant_id, **data)
    db.session.add(level)
    db.session.commit()
    return jsonify(reorder_level_schema.dump(level)), 201


@bp.get("/reorder-levels/below-threshold")
@require_permission("inv:read")
def list_below_reorder():
    warehouse_id = request.args.get("warehouse_id")
    results = services.check_reorder_levels(g.tenant_id, warehouse_id=warehouse_id)
    return jsonify(
        envelope(
            [
                {
                    "reorder_level": reorder_level_schema.dump(r["reorder_level"]),
                    "available_quantity": str(r["available_quantity"]),
                }
                for r in results
            ]
        )
    )


# --- Codes, batches, serials (INV-05, INV-06, INV-07) -------------------------------

@bp.post("/item-codes")
@require_permission("inv:write")
def create_item_code():
    data = _load(item_code_schema)
    code = ItemCode(tenant_id=g.tenant_id, **data)
    db.session.add(code)
    db.session.commit()
    return jsonify(item_code_schema.dump(code)), 201


@bp.post("/batch-numbers")
@require_permission("inv:write")
def create_batch_number():
    data = _load(batch_schema)
    batch = BatchNumber(tenant_id=g.tenant_id, **data)
    db.session.add(batch)
    db.session.commit()
    return jsonify(batch_schema.dump(batch)), 201


@bp.get("/batch-numbers/expiring")
@require_permission("inv:read")
def list_expiring_batches():
    from datetime import date, timedelta

    within_days = request.args.get("within_days", 30, type=int)
    horizon = date.today() + timedelta(days=within_days)
    batches = BatchNumber.query.filter(
        BatchNumber.tenant_id == g.tenant_id,
        BatchNumber.expiry_date.isnot(None),
        BatchNumber.expiry_date <= horizon,
        BatchNumber.quantity_remaining > 0,
    ).all()
    return jsonify(envelope(batch_schema.dump(batches, many=True)))


@bp.post("/serial-numbers")
@require_permission("inv:write")
def create_serial_number():
    data = _load(serial_schema)
    serial = SerialNumber(tenant_id=g.tenant_id, **data)
    db.session.add(serial)
    db.session.commit()
    return jsonify(serial_schema.dump(serial)), 201


# --- Waste (INV-08, business rule) --------------------------------------------------

@bp.post("/waste-records")
@require_permission("inv:write")
def record_waste():
    data = _load(WasteRecordInputSchema())
    _get_warehouse_or_404(data["warehouse_id"])
    record = services.record_waste(g.tenant_id, **data)
    return jsonify(waste_schema.dump(record)), 201


# --- Material returns (INV-09) ---------------------------------------------------------

@bp.post("/material-returns/to-yard")
@require_permission("inv:write")
def return_to_yard():
    data = _load(ReturnToYardSchema())
    ret = services.process_return_to_yard(g.tenant_id, **data)
    return jsonify(material_return_schema.dump(ret)), 201


@bp.post("/material-returns/to-vendor")
@require_permission("inv:write")
def return_to_vendor():
    data = _load(ReturnToVendorSchema())
    ret = services.process_return_to_vendor(g.tenant_id, **data)
    return jsonify(material_return_schema.dump(ret)), 201


# --- Stock counts (INV-10) ---------------------------------------------------------------

@bp.post("/stock-counts")
@require_permission("inv:write")
def start_stock_count():
    data = _load(StartStockCountSchema())
    _get_warehouse_or_404(data["warehouse_id"])
    count = services.start_stock_count(g.tenant_id, counted_by=g.user_id, **data)
    return jsonify(stock_count_schema.dump(count)), 201


@bp.post("/stock-count-lines/<uuid:line_id>/record")
@require_permission("inv:write")
def record_count_line(line_id):
    line = StockCountLine.query.filter_by(id=line_id, tenant_id=g.tenant_id).first()
    if not line:
        raise APIError("Stock count line not found", status=404)

    data = _load(RecordCountLineSchema())
    line.counted_quantity = data["counted_quantity"]
    db.session.commit()
    return jsonify(
        {"id": str(line.id), "system_quantity": str(line.system_quantity), "counted_quantity": str(line.counted_quantity), "variance": str(line.variance)}
    )


@bp.post("/stock-counts/<uuid:count_id>/complete")
@require_permission("inv:write")
def complete_stock_count(count_id):
    count = StockCount.query.filter_by(id=count_id, tenant_id=g.tenant_id).first()
    if not count:
        raise APIError("Stock count not found", status=404)
    count.status = "completed"
    db.session.commit()
    return jsonify(stock_count_schema.dump(count))


@bp.post("/stock-counts/<uuid:count_id>/apply-adjustment")
@require_permission("inv:approve")
def apply_stock_count_adjustment(count_id):
    count = StockCount.query.filter_by(id=count_id, tenant_id=g.tenant_id).first()
    if not count:
        raise APIError("Stock count not found", status=404)
    count = services.apply_stock_count_adjustment(count, actor_id=g.user_id)
    return jsonify(stock_count_schema.dump(count))
