"""
Module 10 — Fuel Management (Code: FUEL)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.fuel.models import TANK_TYPES, THEFT_FLAG_STATUSES


class FuelTankSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    tank_type = fields.Str(required=True, validate=validate.OneOf(TANK_TYPES))
    capacity_litres = fields.Decimal(allow_none=True, as_string=True)
    current_level_litres = fields.Decimal(dump_only=True, as_string=True)
    project_id = fields.UUID(allow_none=True)
    equipment_id = fields.UUID(allow_none=True)


class FuelPurchaseInputSchema(Schema):
    tank_id = fields.UUID(required=True)
    vendor_id = fields.UUID(allow_none=True, load_default=None)
    quantity_litres = fields.Decimal(required=True, as_string=True)
    unit_price = fields.Decimal(required=True, as_string=True)
    delivered_at = fields.DateTime(allow_none=True)


class FuelPurchaseSchema(Schema):
    id = fields.UUID(dump_only=True)
    tank_id = fields.UUID(dump_only=True)
    quantity_litres = fields.Decimal(dump_only=True, as_string=True)
    unit_price = fields.Decimal(dump_only=True, as_string=True)
    total_cost = fields.Decimal(dump_only=True, as_string=True)
    delivery_confirmed = fields.Bool(dump_only=True)


class ReconcileTankSchema(Schema):
    dip_reading_litres = fields.Decimal(required=True, as_string=True)
    tolerance_litres = fields.Decimal(load_default="20", as_string=True)


class FuelIssueInputSchema(Schema):
    tank_id = fields.UUID(required=True)
    equipment_id = fields.UUID(required=True)
    operator_id = fields.UUID(allow_none=True, load_default=None)
    quantity_litres = fields.Decimal(required=True, as_string=True)
    meter_reading = fields.Decimal(allow_none=True, as_string=True)
    issued_at = fields.DateTime(required=True)
    countersignature_threshold = fields.Decimal(load_default="200", as_string=True)


class FuelIssueSchema(Schema):
    id = fields.UUID(dump_only=True)
    tank_id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    quantity_litres = fields.Decimal(dump_only=True, as_string=True)
    issued_at = fields.DateTime(dump_only=True)
    requires_countersignature = fields.Bool(dump_only=True)
    countersigned = fields.Bool(dump_only=True)


class UsageLogCheckSchema(Schema):
    has_usage_log = fields.Bool(required=True)


class FuelBurnRateProfileSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(required=True)
    expected_litres_per_hour = fields.Decimal(required=True, as_string=True)
    source = fields.Str(load_default="historical")


class FuelVarianceQuerySchema(Schema):
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    hours_operated = fields.Decimal(required=True, as_string=True)


class FuelVarianceRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    expected_litres = fields.Decimal(dump_only=True, as_string=True)
    actual_litres = fields.Decimal(dump_only=True, as_string=True)
    variance_litres = fields.Decimal(dump_only=True, as_string=True)
    variance_pct = fields.Decimal(dump_only=True, as_string=True)
    variance_cost = fields.Decimal(dump_only=True, as_string=True)


class TheftFlagSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_id = fields.UUID(dump_only=True)
    tank_id = fields.UUID(dump_only=True)
    flag_reason = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(validate=validate.OneOf(THEFT_FLAG_STATUSES), dump_only=True)
    raised_at = fields.DateTime(dump_only=True)
