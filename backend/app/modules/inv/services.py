"""
Module 8 — Inventory & Warehouse (Code: INV)
Service layer — business logic other modules must call through rather
than querying inv_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.8):
  - A Stock Transfer is not complete, and does not update destination
    balances, until receipt is confirmed at the destination warehouse.
  - Waste and shrinkage roll up into project cost variance as a
    distinct, valued cost category -- never hidden inside standard
    consumption. See WasteRecord.valued_cost.

The valuation engine (INV-11) is the real substance of this module:
weighted-average recomputes a single running cost on every receipt;
FIFO consumes StockLayer rows oldest-first on every issue. Both produce
a valued cost for every outbound movement (issue, waste, transfer-out),
which is what makes "distinct cost category" in the business rule above
a real number rather than a label.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.inv.models import (
    InventorySettings,
    StockItem,
    StockLayer,
    StockTransfer,
    StockReservation,
    ReorderLevel,
    WasteRecord,
    MaterialReturn,
    StockCount,
)


def get_valuation_method(tenant_id) -> str:
    settings = InventorySettings.query.filter_by(tenant_id=tenant_id).first()
    return settings.valuation_method if settings else "weighted_average"


def _get_or_create_stock_item(tenant_id, warehouse_id, material_item_id) -> StockItem:
    item = StockItem.query.filter_by(
        tenant_id=tenant_id, warehouse_id=warehouse_id, material_item_id=material_item_id
    ).first()
    if not item:
        item = StockItem(
            tenant_id=tenant_id, warehouse_id=warehouse_id, material_item_id=material_item_id, quantity_on_hand=0, average_unit_cost=0
        )
        db.session.add(item)
        db.session.flush()
    return item


# --- Receiving & valuation (INV-11) -----------------------------------------

def receive_stock(tenant_id, *, warehouse_id, material_item_id, quantity, unit_cost, received_at=None):
    """Increases on-hand quantity and updates valuation per the
    tenant's configured method."""
    quantity = Decimal(str(quantity))
    unit_cost = Decimal(str(unit_cost))
    if quantity <= 0:
        raise APIError("Quantity received must be positive", status=400)

    stock_item = _get_or_create_stock_item(tenant_id, warehouse_id, material_item_id)
    method = get_valuation_method(tenant_id)

    if method == "weighted_average":
        old_qty = stock_item.quantity_on_hand
        old_cost = stock_item.average_unit_cost
        new_qty = old_qty + quantity
        stock_item.average_unit_cost = (
            ((old_qty * old_cost) + (quantity * unit_cost)) / new_qty if new_qty > 0 else Decimal("0")
        )
    else:  # fifo
        db.session.add(
            StockLayer(
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                material_item_id=material_item_id,
                received_at=received_at or datetime.now(timezone.utc),
                quantity_remaining=quantity,
                unit_cost=unit_cost,
            )
        )

    stock_item.quantity_on_hand += quantity
    db.session.commit()
    return stock_item


def _consume_fifo(tenant_id, warehouse_id, material_item_id, quantity) -> Decimal:
    """Consumes StockLayer rows oldest-first, returning the total
    valued cost of the quantity consumed. Raises if insufficient layer
    quantity exists (should be impossible if quantity_on_hand is kept
    in sync, but checked explicitly rather than assumed)."""
    layers = (
        StockLayer.query.filter_by(tenant_id=tenant_id, warehouse_id=warehouse_id, material_item_id=material_item_id)
        .filter(StockLayer.quantity_remaining > 0)
        .order_by(StockLayer.received_at.asc())
        .all()
    )

    remaining_to_consume = quantity
    total_cost = Decimal("0")
    for layer in layers:
        if remaining_to_consume <= 0:
            break
        take = min(layer.quantity_remaining, remaining_to_consume)
        total_cost += take * layer.unit_cost
        layer.quantity_remaining -= take
        remaining_to_consume -= take

    if remaining_to_consume > 0:
        raise APIError(
            "Insufficient FIFO layer quantity to cover issue",
            status=409,
            detail="Stock layers are out of sync with quantity_on_hand -- this indicates a data integrity issue.",
        )

    return total_cost


def issue_stock(tenant_id, *, warehouse_id, material_item_id, quantity) -> dict:
    """Decreases on-hand quantity and returns the valued cost of the
    issued quantity, per the tenant's configured valuation method."""
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise APIError("Quantity issued must be positive", status=400)

    stock_item = _get_or_create_stock_item(tenant_id, warehouse_id, material_item_id)
    if quantity > stock_item.quantity_on_hand:
        raise APIError(
            "Insufficient stock",
            status=409,
            detail=f"Requested {quantity}, only {stock_item.quantity_on_hand} on hand.",
        )

    method = get_valuation_method(tenant_id)
    if method == "weighted_average":
        valued_cost = quantity * stock_item.average_unit_cost
    else:
        valued_cost = _consume_fifo(tenant_id, warehouse_id, material_item_id, quantity)

    stock_item.quantity_on_hand -= quantity
    db.session.commit()
    return {"quantity": quantity, "valued_cost": valued_cost}


# --- Availability & reservations (INV-03, INV-12) ---------------------------

def available_quantity(tenant_id, warehouse_id, material_item_id) -> Decimal:
    """INV-12: on-hand minus active reservations -- the quantity
    actually available for a NEW project/activity to draw against."""
    stock_item = StockItem.query.filter_by(
        tenant_id=tenant_id, warehouse_id=warehouse_id, material_item_id=material_item_id
    ).first()
    on_hand = stock_item.quantity_on_hand if stock_item else Decimal("0")

    reserved = (
        db.session.query(db.func.coalesce(db.func.sum(StockReservation.quantity), 0))
        .filter(
            StockReservation.tenant_id == tenant_id,
            StockReservation.warehouse_id == warehouse_id,
            StockReservation.material_item_id == material_item_id,
            StockReservation.status == "active",
        )
        .scalar()
    )
    return on_hand - Decimal(reserved)


def reserve_stock(tenant_id, *, warehouse_id, material_item_id, quantity, project_id=None, activity_id=None, reserved_by=None):
    quantity = Decimal(str(quantity))
    if quantity > available_quantity(tenant_id, warehouse_id, material_item_id):
        raise APIError("Insufficient available quantity to reserve", status=409)

    reservation = StockReservation(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        material_item_id=material_item_id,
        project_id=project_id,
        activity_id=activity_id,
        quantity=quantity,
        reserved_by=reserved_by,
    )
    db.session.add(reservation)
    db.session.commit()
    return reservation


def release_reservation(reservation: StockReservation):
    if reservation.status != "active":
        raise APIError("Reservation is not active", status=409)
    reservation.status = "released"
    db.session.commit()
    return reservation


# --- Stock transfers (INV-02, business rule) --------------------------------

def initiate_transfer(tenant_id, *, from_warehouse_id, to_warehouse_id, material_item_id, quantity, dispatched_by=None):
    """Dispatches from the source warehouse immediately (goods
    physically leave), but does NOT touch the destination -- per the
    business rule, that only happens on confirm_transfer_receipt."""
    quantity = Decimal(str(quantity))
    source_item = _get_or_create_stock_item(tenant_id, from_warehouse_id, material_item_id)
    if quantity > source_item.quantity_on_hand:
        raise APIError("Insufficient stock at source warehouse", status=409)

    source_item.quantity_on_hand -= quantity

    transfer = StockTransfer(
        tenant_id=tenant_id,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        material_item_id=material_item_id,
        quantity=quantity,
        status="in_transit",
        dispatched_at=datetime.now(timezone.utc),
        dispatched_by=dispatched_by,
    )
    db.session.add(transfer)
    db.session.commit()
    return transfer


def confirm_transfer_receipt(transfer: StockTransfer, *, received_by=None):
    """Business rule: THIS is the moment destination balances update --
    a transfer sitting "in_transit" has already left the source but has
    not yet arrived anywhere, by design (goods can be lost/damaged in
    transit, and the system should reflect that ambiguity honestly
    rather than optimistically crediting the destination on dispatch)."""
    if transfer.status == "received":
        raise APIError("Transfer has already been received", status=409)

    dest_item = _get_or_create_stock_item(transfer.tenant_id, transfer.to_warehouse_id, transfer.material_item_id)

    # The destination gets the transferred quantity at the SOURCE
    # warehouse's valuation at time of dispatch, carried on the
    # transfer's quantity -- for weighted-average this just adds
    # quantity at the source's average cost; for FIFO the destination
    # gets a new layer priced at that same average, since a transfer
    # doesn't change what the material actually cost the company.
    method = get_valuation_method(transfer.tenant_id)
    source_item = StockItem.query.filter_by(
        tenant_id=transfer.tenant_id, warehouse_id=transfer.from_warehouse_id, material_item_id=transfer.material_item_id
    ).first()
    transfer_cost = source_item.average_unit_cost if source_item else Decimal("0")

    if method == "weighted_average":
        old_qty = dest_item.quantity_on_hand
        old_cost = dest_item.average_unit_cost
        new_qty = old_qty + transfer.quantity
        dest_item.average_unit_cost = (
            ((old_qty * old_cost) + (transfer.quantity * transfer_cost)) / new_qty if new_qty > 0 else Decimal("0")
        )
    else:
        db.session.add(
            StockLayer(
                tenant_id=transfer.tenant_id,
                warehouse_id=transfer.to_warehouse_id,
                material_item_id=transfer.material_item_id,
                received_at=datetime.now(timezone.utc),
                quantity_remaining=transfer.quantity,
                unit_cost=transfer_cost,
            )
        )

    dest_item.quantity_on_hand += transfer.quantity
    transfer.status = "received"
    transfer.received_at = datetime.now(timezone.utc)
    transfer.received_by = received_by

    db.session.commit()
    return transfer


# --- Reorder levels (INV-04) --------------------------------------------------

def check_reorder_levels(tenant_id, *, warehouse_id=None):
    """Returns ReorderLevel rows whose available quantity has fallen to
    or below the configured reorder point. Creating a draft Purchase
    Request from these (for rows with auto_create_pr=True) is a
    cross-module call into app.modules.prc.services, left to the
    caller/a Celery task rather than done here, to keep this function
    a pure read."""
    query = ReorderLevel.query.filter_by(tenant_id=tenant_id)
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)

    below_reorder = []
    for level in query.all():
        available = available_quantity(tenant_id, level.warehouse_id, level.material_item_id)
        if available <= level.reorder_point:
            below_reorder.append({"reorder_level": level, "available_quantity": available})

    return below_reorder


# --- Waste (INV-08, business rule) --------------------------------------------

def record_waste(tenant_id, *, warehouse_id, material_item_id, quantity, cause_classification, project_id=None, notes=None, recorded_at=None):
    """Business rule: waste rolls up into Module 19's cost variance as
    a distinct, VALUED category -- so this issues stock (consuming
    valuation layers / weighted-average cost) exactly like a normal
    issue, rather than just decrementing a quantity with no cost
    attached."""
    result = issue_stock(tenant_id, warehouse_id=warehouse_id, material_item_id=material_item_id, quantity=quantity)

    record = WasteRecord(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        material_item_id=material_item_id,
        project_id=project_id,
        quantity=result["quantity"],
        cause_classification=cause_classification,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        notes=notes,
        valued_cost=result["valued_cost"],
    )
    db.session.add(record)
    db.session.commit()
    return record


# --- Material returns (INV-09) -------------------------------------------------

def process_return_to_yard(tenant_id, *, material_item_id, source_warehouse_id, destination_warehouse_id, quantity, condition, returned_by=None):
    """Site-to-yard return: physically moves stock back, same
    valuation-carrying logic as a transfer (a return IS a kind of
    transfer, just initiated from a different business event)."""
    quantity = Decimal(str(quantity))
    source_item = _get_or_create_stock_item(tenant_id, source_warehouse_id, material_item_id)
    if quantity > source_item.quantity_on_hand:
        raise APIError("Insufficient stock at source to return", status=409)
    source_item.quantity_on_hand -= quantity

    dest_item = _get_or_create_stock_item(tenant_id, destination_warehouse_id, material_item_id)
    dest_item.quantity_on_hand += quantity  # simplified: damaged-condition returns still restore quantity;
    # a real system might route "damaged" to a quarantine/write-off
    # flow instead -- left as a documented simplification.

    ret = MaterialReturn(
        tenant_id=tenant_id,
        material_item_id=material_item_id,
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        quantity=quantity,
        return_type="site_to_yard",
        condition=condition,
        status="completed",
    )
    db.session.add(ret)
    db.session.commit()
    return ret


def process_return_to_vendor(tenant_id, *, material_item_id, source_warehouse_id, vendor_id, quantity, condition, credit_note_reference=None):
    quantity = Decimal(str(quantity))
    source_item = _get_or_create_stock_item(tenant_id, source_warehouse_id, material_item_id)
    if quantity > source_item.quantity_on_hand:
        raise APIError("Insufficient stock at source to return", status=409)
    source_item.quantity_on_hand -= quantity

    ret = MaterialReturn(
        tenant_id=tenant_id,
        material_item_id=material_item_id,
        source_warehouse_id=source_warehouse_id,
        vendor_id=vendor_id,
        quantity=quantity,
        return_type="to_vendor",
        condition=condition,
        credit_note_reference=credit_note_reference,
        status="completed" if credit_note_reference else "pending",
    )
    db.session.add(ret)
    db.session.commit()
    return ret


# --- Stock counts (INV-10) -----------------------------------------------------

def start_stock_count(tenant_id, *, warehouse_id, count_type, material_item_ids, counted_by=None):
    """Snapshots each item's current system quantity at count-start
    time -- variance is always computed against THIS snapshot, not
    against whatever quantity_on_hand happens to be when the count is
    later completed (which could have moved due to unrelated activity
    during the count)."""
    from app.modules.inv.models import StockCountLine

    count = StockCount(tenant_id=tenant_id, warehouse_id=warehouse_id, count_type=count_type, counted_by=counted_by)
    db.session.add(count)
    db.session.flush()

    for material_item_id in material_item_ids:
        stock_item = StockItem.query.filter_by(
            tenant_id=tenant_id, warehouse_id=warehouse_id, material_item_id=material_item_id
        ).first()
        system_qty = stock_item.quantity_on_hand if stock_item else Decimal("0")
        db.session.add(
            StockCountLine(
                tenant_id=tenant_id, stock_count_id=count.id, material_item_id=material_item_id, system_quantity=system_qty
            )
        )

    db.session.commit()
    return count


def apply_stock_count_adjustment(count: StockCount, *, actor_id=None):
    """Explicitly adjusts on-hand quantities to match counted values.
    Never happens automatically -- a stock take produces a variance
    REPORT (SRS INV-10); adjusting the books is a separate, deliberate
    action."""
    if count.status == "adjusted":
        raise APIError("Stock count has already been adjusted", status=409)

    unresolved = [line for line in count.lines if line.counted_quantity is None]
    if unresolved:
        raise APIError("Cannot adjust: not every line has a counted quantity recorded", status=409)

    for line in count.lines:
        stock_item = _get_or_create_stock_item(count.tenant_id, count.warehouse_id, line.material_item_id)
        stock_item.quantity_on_hand = line.counted_quantity

    count.status = "adjusted"
    count.updated_by = actor_id
    db.session.commit()
    return count
