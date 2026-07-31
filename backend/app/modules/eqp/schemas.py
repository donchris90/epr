"""
Module 9 — Equipment & Fleet Management (Code: EQP)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.eqp.models import (
    OWNERSHIP_TYPES,
    EQUIPMENT_STATUSES,
    GPS_SOURCES,
    MAINTENANCE_TYPES,
    DOWNTIME_REASONS,
)


class EquipmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    make = fields.Str(allow_none=True)
    model = fields.Str(allow_none=True)
    serial_chassis_number = fields.Str(allow_none=True)
    ownership_type = fields.Str(load_default="owned", validate=validate.OneOf(OWNERSHIP_TYPES))
    acquisition_cost = fields.Decimal(allow_none=True, as_string=True)
    acquisition_date = fields.Date(allow_none=True)
    salvage_value = fields.Decimal(load_default="0", as_string=True)
    useful_life_years = fields.Int(allow_none=True)
    status = fields.Str(validate=validate.OneOf(EQUIPMENT_STATUSES), dump_only=True)
    current_project_id = fields.UUID(allow_none=True, dump_only=True)


class GPSPositionSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    latitude = fields.Decimal(required=True, as_string=True)
    longitude = fields.Decimal(required=True, as_string=True)
    recorded_at = fields.DateTime(required=True)
    source = fields.Str(load_default="gps_device", validate=validate.OneOf(GPS_SOURCES))


class AssignOperatorSchema(Schema):
    operator_id = fields.UUID(required=True)
    shift_start = fields.DateTime(required=True)
    shift_end = fields.DateTime(allow_none=True, load_default=None)
    certification_valid_until = fields.Date(allow_none=True, load_default=None)


class OperatorAssignmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    operator_id = fields.UUID(dump_only=True)
    shift_start = fields.DateTime(dump_only=True)
    shift_end = fields.DateTime(dump_only=True)
    certification_valid_until = fields.Date(dump_only=True)
    status = fields.Str(dump_only=True)


class MaintenanceRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    maintenance_type = fields.Str(load_default="scheduled", validate=validate.OneOf(MAINTENANCE_TYPES))
    description = fields.Str(required=True)
    due_at_hours = fields.Decimal(allow_none=True, as_string=True)
    due_at_date = fields.Date(allow_none=True)
    due_at_mileage = fields.Decimal(allow_none=True, as_string=True)
    completed_at = fields.DateTime(allow_none=True)
    cost = fields.Decimal(allow_none=True, as_string=True)
    performed_by = fields.Str(allow_none=True)
    status = fields.Str(dump_only=True)


class SparePartUsageSchema(Schema):
    id = fields.UUID(dump_only=True)
    maintenance_record_id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit_cost = fields.Decimal(allow_none=True, as_string=True)


class RepairHistorySchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    maintenance_record_id = fields.UUID(allow_none=True)
    description = fields.Str(required=True)
    cost = fields.Decimal(allow_none=True, as_string=True)
    downtime_hours = fields.Decimal(allow_none=True, as_string=True)
    root_cause = fields.Str(allow_none=True)
    repaired_at = fields.DateTime(allow_none=True)


class DowntimeEventSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    reason_classification = fields.Str(required=True, validate=validate.OneOf(DOWNTIME_REASONS))
    started_at = fields.DateTime(required=True)
    ended_at = fields.DateTime(allow_none=True)
    notes = fields.Str(allow_none=True)


class UtilizationRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    record_date = fields.Date(required=True)
    hours_operated = fields.Decimal(load_default="0", as_string=True)
    hours_scheduled = fields.Decimal(load_default="0", as_string=True)


class UtilizationQuerySchema(Schema):
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    fuel_normal_cost = fields.Decimal(allow_none=True, as_string=True, load_default=None)
    fuel_variance_cost = fields.Decimal(allow_none=True, as_string=True, load_default=None)
    operator_cost = fields.Decimal(allow_none=True, as_string=True, load_default=None)


class EquipmentTransferSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    from_project_id = fields.UUID(allow_none=True, dump_only=True)
    to_project_id = fields.UUID(required=True)
    status = fields.Str(dump_only=True)
    cutover_date = fields.Date(allow_none=True)


class ApproveTransferSchema(Schema):
    cutover_date = fields.Date(allow_none=True)
