"""Manufacturing request/response schemas."""
from marshmallow import Schema, fields, validate

from app.modules.mfg.models import ORDER_STATUSES


class WorkCenterSchema(Schema):
    id = fields.UUID(dump_only=True)
    code = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    name = fields.Str(required=True)
    hourly_rate = fields.Decimal(load_default="0", as_string=True, validate=validate.Range(min=0))
    equipment_id = fields.UUID(allow_none=True, load_default=None)
    is_active = fields.Bool(load_default=True)


class BomLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    component_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    scrap_percent = fields.Decimal(load_default="0", as_string=True)


class BomSchema(Schema):
    id = fields.UUID(dump_only=True)
    code = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    name = fields.Str(required=True)
    product_item_id = fields.UUID(required=True)
    output_quantity = fields.Decimal(load_default="1", as_string=True)
    is_active = fields.Bool(load_default=True)
    lines = fields.List(fields.Nested(BomLineSchema), required=True)


class ProductionComponentSchema(Schema):
    id = fields.UUID(dump_only=True)
    component_item_id = fields.UUID(dump_only=True)
    planned_quantity = fields.Decimal(dump_only=True, as_string=True)
    consumed_quantity = fields.Decimal(dump_only=True, as_string=True)
    valued_cost = fields.Decimal(dump_only=True, as_string=True)


class ProductionOrderInputSchema(Schema):
    bom_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    warehouse_id = fields.UUID(required=True)
    work_center_id = fields.UUID(allow_none=True, load_default=None)
    planned_start = fields.Date(allow_none=True, load_default=None)
    notes = fields.Str(allow_none=True, load_default=None)


class ConsumptionSchema(Schema):
    component_item_id = fields.UUID(required=True)
    consumed_quantity = fields.Decimal(required=True, as_string=True)


class CompleteOrderSchema(Schema):
    quantity_produced = fields.Decimal(required=True, as_string=True)
    quantity_scrapped = fields.Decimal(load_default="0", as_string=True)
    labour_hours = fields.Decimal(load_default="0", as_string=True)
    consumptions = fields.List(fields.Nested(ConsumptionSchema), load_default=list)
    fuel_litres = fields.Decimal(load_default="0", as_string=True)
    fuel_tank_id = fields.UUID(allow_none=True, load_default=None)
    fuel_unit_cost = fields.Decimal(allow_none=True, load_default=None, as_string=True)
    batch_number = fields.Str(allow_none=True, load_default=None)
    manufactured_date = fields.Date(allow_none=True, load_default=None)
    expiry_date = fields.Date(allow_none=True, load_default=None)
    quarantine = fields.Bool(load_default=False)


class ProductionOrderSchema(Schema):
    id = fields.UUID(dump_only=True)
    number = fields.Str(dump_only=True)
    bom_id = fields.UUID(dump_only=True)
    product_item_id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(dump_only=True)
    work_center_id = fields.UUID(dump_only=True, allow_none=True)
    status = fields.Str(dump_only=True, validate=validate.OneOf(ORDER_STATUSES))
    quantity_planned = fields.Decimal(dump_only=True, as_string=True)
    quantity_produced = fields.Decimal(dump_only=True, as_string=True)
    quantity_scrapped = fields.Decimal(dump_only=True, as_string=True)
    planned_start = fields.Date(dump_only=True, allow_none=True)
    started_at = fields.DateTime(dump_only=True, allow_none=True)
    completed_at = fields.DateTime(dump_only=True, allow_none=True)
    labour_hours = fields.Decimal(dump_only=True, as_string=True)
    fuel_litres = fields.Decimal(dump_only=True, as_string=True)
    material_cost = fields.Decimal(dump_only=True, as_string=True)
    labour_cost = fields.Decimal(dump_only=True, as_string=True)
    fuel_cost = fields.Decimal(dump_only=True, as_string=True)
    total_cost = fields.Decimal(dump_only=True, as_string=True)
    unit_cost = fields.Decimal(dump_only=True, as_string=True)
    batch_id = fields.UUID(dump_only=True, allow_none=True)
    notes = fields.Str(dump_only=True, allow_none=True)
    components = fields.List(fields.Nested(ProductionComponentSchema), dump_only=True)
