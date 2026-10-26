"""Manufacturing services: BOMs, production orders, completion and costing."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.modules.fuel import services as fuel_services
from app.modules.fuel.models import FuelPurchase, FuelTank
from app.modules.inv import services as inv_services
from app.modules.inv.models import BatchNumber, MaterialItem, Warehouse
from app.modules.mfg.models import Bom, BomLine, ProductionComponent, ProductionOrder, WorkCenter
from app.utils.errors import APIError

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _dec(value, field, *, minimum=None, allow_zero=True):
    try:
        d = Decimal(str(value))
    except Exception:
        raise APIError(f"{field} must be a number", status=422)
    if minimum is not None and (d < minimum or (d == minimum and not allow_zero)):
        raise APIError(f"{field} is out of range", status=422)
    return d


def _item_or_404(tenant_id, item_id, label="Item") -> MaterialItem:
    item = MaterialItem.query.filter_by(id=item_id, tenant_id=tenant_id).first()
    if not item:
        raise APIError(f"{label} not found", status=404)
    return item


# --- Bills of materials -----------------------------------------------------

def save_bom(tenant_id, *, bom: Bom = None, code, name, product_item_id, output_quantity, lines, is_active=True) -> Bom:
    """Creates a BOM, or replaces an existing one's header and lines.
    Editing a BOM never touches existing production orders (they hold
    their own snapshot of required quantities)."""
    _item_or_404(tenant_id, product_item_id, "Product")
    output_quantity = _dec(output_quantity, "output_quantity", minimum=ZERO, allow_zero=False)
    if not lines:
        raise APIError("A BOM needs at least one component", status=422)

    seen = set()
    clean = []
    for line in lines:
        cid = str(line["component_item_id"])
        if cid == str(product_item_id):
            raise APIError("A product cannot be a component of itself", status=422)
        if cid in seen:
            raise APIError("A component appears twice in the BOM", status=422, detail="Combine the quantities into one line.")
        seen.add(cid)
        _item_or_404(tenant_id, cid, "Component")
        qty = _dec(line["quantity"], "quantity", minimum=ZERO, allow_zero=False)
        scrap = _dec(line.get("scrap_percent", 0), "scrap_percent", minimum=ZERO)
        if scrap >= HUNDRED:
            raise APIError("scrap_percent must be below 100", status=422)
        clean.append((cid, qty, scrap))

    if bom is None:
        bom = Bom(tenant_id=tenant_id, code=code)
        db.session.add(bom)
    bom.name = name
    bom.product_item_id = product_item_id
    bom.output_quantity = output_quantity
    bom.is_active = is_active
    # Flush the deletes first: the unit of work inserts before it deletes,
    # which would trip the (bom, component) unique constraint when a
    # component is kept across the edit.
    try:
        bom.lines[:] = []
        db.session.flush()
        bom.lines[:] = [
            BomLine(tenant_id=tenant_id, component_item_id=cid, quantity=qty, scrap_percent=scrap) for cid, qty, scrap in clean
        ]
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise APIError("A BOM with this code already exists", status=409)
    return bom


def required_components(bom: Bom, quantity: Decimal):
    """Component quantities to make `quantity` of the product, including
    each line's expected scrap."""
    factor = quantity / bom.output_quantity
    return [(line.component_item_id, line.quantity * factor * (1 + line.scrap_percent / HUNDRED)) for line in bom.lines]


# --- Production orders --------------------------------------------------------

def _next_number(tenant_id) -> str:
    count = db.session.query(db.func.count(ProductionOrder.id)).filter(ProductionOrder.tenant_id == tenant_id).scalar()
    return f"PRD-{count + 1:05d}"


def create_order(tenant_id, *, bom_id, quantity, warehouse_id, work_center_id=None, planned_start=None, notes=None, actor_id=None):
    bom = Bom.query.filter_by(id=bom_id, tenant_id=tenant_id).first()
    if not bom:
        raise APIError("BOM not found", status=404)
    if not bom.is_active:
        raise APIError("This BOM is inactive", status=409)
    quantity = _dec(quantity, "quantity", minimum=ZERO, allow_zero=False)
    if not Warehouse.query.filter_by(id=warehouse_id, tenant_id=tenant_id).first():
        raise APIError("Warehouse not found", status=404)
    if work_center_id:
        wc = WorkCenter.query.filter_by(id=work_center_id, tenant_id=tenant_id).first()
        if not wc:
            raise APIError("Work center not found", status=404)
        if not wc.is_active:
            raise APIError("This work center is inactive", status=409)

    order = ProductionOrder(
        tenant_id=tenant_id,
        number=_next_number(tenant_id),
        bom_id=bom.id,
        product_item_id=bom.product_item_id,
        warehouse_id=warehouse_id,
        work_center_id=work_center_id,
        quantity_planned=quantity,
        planned_start=planned_start,
        notes=notes,
        status="draft",
        created_by=actor_id,
    )
    for cid, qty in required_components(bom, quantity):
        order.components.append(ProductionComponent(tenant_id=tenant_id, component_item_id=cid, planned_quantity=qty))
    db.session.add(order)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise APIError("Could not allocate an order number, please retry", status=409)
    return order


def _transition(order: ProductionOrder, allowed_from, to, label):
    if order.status not in allowed_from:
        raise APIError(f"Cannot {label} a {order.status.replace('_', ' ')} order", status=409)
    order.status = to


def release_order(order):
    _transition(order, ("draft",), "released", "release")
    db.session.commit()
    return order


def start_order(order):
    _transition(order, ("released",), "in_progress", "start")
    order.started_at = datetime.now(timezone.utc)
    db.session.commit()
    return order


def cancel_order(order):
    """Nothing is drawn from stock until completion, so cancelling an
    unfinished order has nothing to reverse."""
    _transition(order, ("draft", "released", "in_progress"), "cancelled", "cancel")
    db.session.commit()
    return order


def availability(tenant_id, order: ProductionOrder):
    """Per component: needed vs available in the order's warehouse, so
    a planner can see a shortage before starting."""
    rows = []
    for comp in order.components:
        item = MaterialItem.query.get(comp.component_item_id)
        have = inv_services.available_quantity(tenant_id, order.warehouse_id, comp.component_item_id)
        rows.append(
            {
                "component_item_id": comp.component_item_id,
                "code": item.code,
                "required": comp.planned_quantity,
                "available": have,
                "short": max(comp.planned_quantity - have, ZERO),
            }
        )
    return rows


def _fuel_unit_cost(tenant_id, tank_id) -> Decimal:
    purchase = (
        FuelPurchase.query.filter_by(tenant_id=tenant_id, tank_id=tank_id, delivery_confirmed=True)
        .order_by(FuelPurchase.delivered_at.desc().nullslast(), FuelPurchase.created_at.desc())
        .first()
    )
    if not purchase:
        raise APIError(
            "No fuel price to cost this run with",
            status=422,
            detail="This tank has no confirmed purchase yet. Pass fuel_unit_cost, or confirm a delivery first.",
        )
    return purchase.unit_price


def complete_order(
    tenant_id,
    order: ProductionOrder,
    *,
    quantity_produced,
    quantity_scrapped=0,
    labour_hours=0,
    consumptions=None,
    fuel_litres=0,
    fuel_tank_id=None,
    fuel_unit_cost=None,
    batch_number=None,
    manufactured_date=None,
    expiry_date=None,
    quarantine=False,
    actor_id=None,
):
    """Finishes a run in ONE transaction: consume components, receive the
    finished goods at their real unit cost, record the batch. Any failure
    (e.g. a component out of stock) rolls everything back, so stock never
    ends up half-consumed."""
    if order.status != "in_progress":
        raise APIError(f"Only an in-progress order can be completed (this one is {order.status.replace('_', ' ')})", status=409)

    produced = _dec(quantity_produced, "quantity_produced", minimum=ZERO, allow_zero=False)
    scrapped = _dec(quantity_scrapped, "quantity_scrapped", minimum=ZERO)
    labour_hours = _dec(labour_hours, "labour_hours", minimum=ZERO)
    fuel_litres = _dec(fuel_litres, "fuel_litres", minimum=ZERO)

    product = MaterialItem.query.get(order.product_item_id)
    if product.is_batch_tracked and not batch_number:
        raise APIError("This product is batch-tracked: a batch number is required", status=422)

    overrides = {}
    for c in consumptions or []:
        overrides[str(c["component_item_id"])] = _dec(c["consumed_quantity"], "consumed_quantity", minimum=ZERO)
    known = {str(c.component_item_id) for c in order.components}
    stray = set(overrides) - known
    if stray:
        raise APIError("consumptions include an item that is not a component of this order", status=422)

    # Default: draw what the BOM says for the quantity actually run
    # (good + scrap), so the person only types what differed.
    run_factor = (produced + scrapped) / order.quantity_planned

    try:
        material_cost = ZERO
        for comp in order.components:
            key = str(comp.component_item_id)
            qty = overrides[key] if key in overrides else comp.planned_quantity * run_factor
            comp.consumed_quantity = qty
            if qty > 0:
                issued = inv_services.issue_stock(
                    tenant_id, warehouse_id=order.warehouse_id, material_item_id=comp.component_item_id, quantity=qty, commit=False
                )
                comp.valued_cost = issued["valued_cost"]
            else:
                comp.valued_cost = ZERO
            material_cost += comp.valued_cost

        wc = WorkCenter.query.get(order.work_center_id) if order.work_center_id else None
        labour_cost = labour_hours * (wc.hourly_rate if wc else ZERO)

        fuel_cost = ZERO
        if fuel_litres > 0:
            if fuel_tank_id:
                if not FuelTank.query.filter_by(id=fuel_tank_id, tenant_id=tenant_id).first():
                    raise APIError("Fuel tank not found", status=404)
                if not wc or not wc.equipment_id:
                    raise APIError(
                        "Cannot draw fuel from a tank without a machine",
                        status=422,
                        detail="Link the work center to a piece of equipment, or leave the tank out and pass fuel_unit_cost.",
                    )
                unit = Decimal(str(fuel_unit_cost)) if fuel_unit_cost is not None else _fuel_unit_cost(tenant_id, fuel_tank_id)
                fuel_services.record_issue(
                    tenant_id,
                    tank_id=fuel_tank_id,
                    equipment_id=wc.equipment_id,
                    quantity_litres=fuel_litres,
                    issued_at=datetime.now(timezone.utc),
                    issued_by=actor_id,
                    commit=False,
                )
            else:
                if fuel_unit_cost is None:
                    raise APIError("fuel_unit_cost is required when no tank is given", status=422)
                unit = Decimal(str(fuel_unit_cost))
            fuel_cost = fuel_litres * unit

        total = material_cost + labour_cost + fuel_cost
        unit_cost = total / produced  # scrap cost is carried by the good units

        inv_services.receive_stock(
            tenant_id, warehouse_id=order.warehouse_id, material_item_id=order.product_item_id, quantity=produced, unit_cost=unit_cost, commit=False
        )

        if batch_number:
            batch = BatchNumber(
                tenant_id=tenant_id,
                material_item_id=order.product_item_id,
                warehouse_id=order.warehouse_id,
                batch_number=batch_number,
                manufactured_date=manufactured_date,
                expiry_date=expiry_date,
                quantity_remaining=produced,
                status="quarantined" if quarantine else "released",
                production_order_id=order.id,
            )
            db.session.add(batch)
            db.session.flush()
            order.batch_id = batch.id

        order.quantity_produced = produced
        order.quantity_scrapped = scrapped
        order.labour_hours = labour_hours
        order.fuel_litres = fuel_litres
        order.material_cost = material_cost
        order.labour_cost = labour_cost
        order.fuel_cost = fuel_cost
        order.total_cost = total
        order.unit_cost = unit_cost
        order.status = "done"
        order.completed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return order


def variances(order: ProductionOrder):
    """Consumed minus what the BOM expected for the quantity actually run
    (good plus scrap). Positive = used more than the BOM said. Only
    meaningful once the order is done."""
    run = order.quantity_produced + order.quantity_scrapped
    factor = run / order.quantity_planned if order.status == "done" else Decimal("1")
    return [
        {
            "component_item_id": c.component_item_id,
            "planned": c.planned_quantity * factor,
            "consumed": c.consumed_quantity,
            "variance": c.consumed_quantity - c.planned_quantity * factor,
            "valued_cost": c.valued_cost,
        }
        for c in order.components
    ]
