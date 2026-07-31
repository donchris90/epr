"""
Module 9 — Equipment & Fleet Management (Code: EQP)
SRS Section 4.9 — Flask Blueprint. Base path: /v1/eqp
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.eqp import services
from app.modules.eqp.models import (
    Equipment,
    GPSPosition,
    MaintenanceRecord,
    SparePartUsage,
    RepairHistory,
    DowntimeEvent,
    UtilizationRecord,
    EquipmentTransfer,
)
from app.modules.eqp.schemas import (
    EquipmentSchema,
    GPSPositionSchema,
    AssignOperatorSchema,
    OperatorAssignmentSchema,
    MaintenanceRecordSchema,
    SparePartUsageSchema,
    RepairHistorySchema,
    DowntimeEventSchema,
    UtilizationRecordSchema,
    UtilizationQuerySchema,
    EquipmentTransferSchema,
    ApproveTransferSchema,
)

bp = Blueprint("eqp", __name__, url_prefix="/v1/eqp")

equipment_schema = EquipmentSchema()
gps_schema = GPSPositionSchema()
assignment_schema = OperatorAssignmentSchema()
maintenance_schema = MaintenanceRecordSchema()
spare_part_schema = SparePartUsageSchema()
repair_schema = RepairHistorySchema()
downtime_schema = DowntimeEventSchema()
utilization_record_schema = UtilizationRecordSchema()
transfer_schema = EquipmentTransferSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_equipment_or_404(equipment_id) -> Equipment:
    e = Equipment.query.filter_by(id=equipment_id, tenant_id=g.tenant_id).first()
    if not e:
        raise APIError("Equipment not found", status=404)
    return e


def _get_maintenance_or_404(record_id) -> MaintenanceRecord:
    m = MaintenanceRecord.query.filter_by(id=record_id, tenant_id=g.tenant_id).first()
    if not m:
        raise APIError("Maintenance record not found", status=404)
    return m


@bp.get("/health")
def health():
    return jsonify({"module": "eqp", "name": "Equipment & Fleet Management", "status": "ok"})


# --- Equipment register (EQP-01) ----------------------------------------------

@bp.post("/equipment")
@require_permission("eqp:write")
def create_equipment():
    data = _load(equipment_schema)
    equipment = Equipment(tenant_id=g.tenant_id, **data)
    db.session.add(equipment)
    db.session.commit()
    return jsonify(equipment_schema.dump(equipment)), 201


@bp.get("/equipment")
@require_permission("eqp:read")
def list_equipment():
    status = request.args.get("status")
    query = Equipment.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    items = query.all()
    return jsonify(envelope(equipment_schema.dump(items, many=True)))


@bp.get("/equipment/<uuid:equipment_id>")
@require_permission("eqp:read")
def get_equipment(equipment_id):
    return jsonify(equipment_schema.dump(_get_equipment_or_404(equipment_id)))


@bp.get("/equipment/idle")
@require_permission("eqp:read")
def list_idle_equipment():
    threshold_days = request.args.get("threshold_days", 7, type=int)
    idle = services.find_idle_equipment(g.tenant_id, threshold_days=threshold_days)
    return jsonify(envelope(equipment_schema.dump(idle, many=True)))


# --- GPS tracking (EQP-02) --------------------------------------------------------

@bp.post("/equipment/<uuid:equipment_id>/gps-positions")
@require_permission("eqp:write")
def add_gps_position(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(gps_schema)
    position = GPSPosition(tenant_id=g.tenant_id, equipment_id=equipment.id, **data)
    db.session.add(position)
    db.session.commit()
    return jsonify(gps_schema.dump(position)), 201


@bp.get("/equipment/<uuid:equipment_id>/gps-positions/latest")
@require_permission("eqp:read")
def get_latest_position(equipment_id):
    _get_equipment_or_404(equipment_id)
    position = (
        GPSPosition.query.filter_by(equipment_id=equipment_id, tenant_id=g.tenant_id)
        .order_by(GPSPosition.recorded_at.desc())
        .first()
    )
    if not position:
        raise APIError("No GPS positions recorded for this equipment", status=404)
    return jsonify(gps_schema.dump(position))


# --- Operator assignment (EQP-04, business rule) -----------------------------------

@bp.post("/equipment/<uuid:equipment_id>/operator-assignments")
@require_permission("eqp:write")
def assign_operator(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(AssignOperatorSchema())
    assignment = services.assign_operator(g.tenant_id, equipment_id=equipment.id, **data)
    return jsonify(assignment_schema.dump(assignment)), 201


# --- Maintenance (EQP-05) ------------------------------------------------------------

@bp.post("/equipment/<uuid:equipment_id>/maintenance-records")
@require_permission("eqp:write")
def create_maintenance_record(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(maintenance_schema)
    record = MaintenanceRecord(tenant_id=g.tenant_id, equipment_id=equipment.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(maintenance_schema.dump(record)), 201


@bp.get("/equipment/<uuid:equipment_id>/maintenance-records")
@require_permission("eqp:read")
def list_maintenance_records(equipment_id):
    _get_equipment_or_404(equipment_id)
    records = MaintenanceRecord.query.filter_by(equipment_id=equipment_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(maintenance_schema.dump(records, many=True)))


@bp.post("/maintenance-records/<uuid:record_id>/complete")
@require_permission("eqp:write")
def complete_maintenance_record(record_id):
    """Transitions a maintenance record to 'completed', setting
    completed_at if not already set. `status` is dump_only on the
    schema deliberately (SRS: a record's lifecycle state shouldn't be
    settable to an arbitrary value on create) -- this is the sanctioned
    transition path."""
    from datetime import datetime, timezone

    record = _get_maintenance_or_404(record_id)
    if record.status == "completed":
        raise APIError("Maintenance record is already completed", status=409)

    record.status = "completed"
    if not record.completed_at:
        record.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(maintenance_schema.dump(record))


@bp.get("/maintenance-records/overdue")
@require_permission("eqp:read")
def list_overdue_maintenance():
    from datetime import date

    records = MaintenanceRecord.query.filter(
        MaintenanceRecord.tenant_id == g.tenant_id,
        MaintenanceRecord.status == "scheduled",
        MaintenanceRecord.due_at_date.isnot(None),
        MaintenanceRecord.due_at_date < date.today(),
    ).all()
    return jsonify(envelope(maintenance_schema.dump(records, many=True)))


# --- Spare parts (EQP-06) ------------------------------------------------------------

@bp.post("/maintenance-records/<uuid:record_id>/spare-parts")
@require_permission("eqp:write")
def add_spare_part_usage(record_id):
    record = _get_maintenance_or_404(record_id)
    data = _load(spare_part_schema)
    usage = SparePartUsage(tenant_id=g.tenant_id, maintenance_record_id=record.id, **data)
    db.session.add(usage)
    db.session.commit()
    return jsonify(spare_part_schema.dump(usage)), 201


# --- Repair history (EQP-07) ---------------------------------------------------------

@bp.post("/equipment/<uuid:equipment_id>/repairs")
@require_permission("eqp:write")
def add_repair(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(repair_schema)
    repair = RepairHistory(tenant_id=g.tenant_id, equipment_id=equipment.id, **data)
    db.session.add(repair)
    db.session.commit()
    return jsonify(repair_schema.dump(repair)), 201


# --- Downtime (EQP-08) ----------------------------------------------------------------

@bp.post("/equipment/<uuid:equipment_id>/downtime-events")
@require_permission("eqp:write")
def add_downtime_event(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(downtime_schema)
    event = DowntimeEvent(tenant_id=g.tenant_id, equipment_id=equipment.id, **data)
    db.session.add(event)
    db.session.commit()
    return jsonify(downtime_schema.dump(event)), 201


@bp.post("/downtime-events/<uuid:event_id>/close")
@require_permission("eqp:write")
def close_downtime_event(event_id):
    from datetime import datetime, timezone

    event = DowntimeEvent.query.filter_by(id=event_id, tenant_id=g.tenant_id).first()
    if not event:
        raise APIError("Downtime event not found", status=404)
    if event.ended_at:
        raise APIError("Downtime event is already closed", status=409)

    event.ended_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(downtime_schema.dump(event))


# --- Utilization records (EQP-09) ------------------------------------------------------

@bp.post("/equipment/<uuid:equipment_id>/utilization-records")
@require_permission("eqp:write")
def add_utilization_record(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(utilization_record_schema)
    record = UtilizationRecord(tenant_id=g.tenant_id, equipment_id=equipment.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(utilization_record_schema.dump(record)), 201


@bp.get("/equipment/<uuid:equipment_id>/availability")
@require_permission("eqp:read")
def get_availability(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    args = UtilizationQuerySchema().load(request.args)
    result = services.calculate_availability_utilization(
        equipment, period_start=args["period_start"], period_end=args["period_end"]
    )
    return jsonify({k: (str(v) if v is not None else None) for k, v in result.items()})


# --- Cost per hour (EQP-10, business rule) -----------------------------------------------

@bp.get("/equipment/<uuid:equipment_id>/cost-per-hour")
@require_permission("eqp:read")
def get_cost_per_hour(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    args = UtilizationQuerySchema().load(request.args)
    result = services.calculate_cost_per_hour(
        equipment,
        period_start=args["period_start"],
        period_end=args["period_end"],
        fuel_normal_cost=args.get("fuel_normal_cost"),
        fuel_variance_cost=args.get("fuel_variance_cost"),
        operator_cost=args.get("operator_cost"),
    )
    return jsonify({k: (str(v) if v is not None else None) for k, v in result.items()})


# --- Equipment transfers (EQP-12) --------------------------------------------------------

@bp.post("/equipment/<uuid:equipment_id>/transfers")
@require_permission("eqp:write")
def request_transfer(equipment_id):
    equipment = _get_equipment_or_404(equipment_id)
    data = _load(transfer_schema)
    transfer = EquipmentTransfer(
        tenant_id=g.tenant_id,
        equipment_id=equipment.id,
        from_project_id=equipment.current_project_id,
        requested_by=g.user_id,
        **data,
    )
    db.session.add(transfer)
    db.session.commit()
    return jsonify(transfer_schema.dump(transfer)), 201


@bp.post("/transfers/<uuid:transfer_id>/approve")
@require_permission("eqp:approve")
def approve_transfer(transfer_id):
    transfer = EquipmentTransfer.query.filter_by(id=transfer_id, tenant_id=g.tenant_id).first()
    if not transfer:
        raise APIError("Transfer not found", status=404)

    data = _load(ApproveTransferSchema())
    transfer = services.approve_transfer(transfer, approved_by=g.user_id, cutover_date=data.get("cutover_date"))
    return jsonify(transfer_schema.dump(transfer))
