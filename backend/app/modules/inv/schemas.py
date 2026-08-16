"""
Module 8 — Inventory & Warehouse (Code: INV)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.inv.models import (
    WAREHOUSE_TYPES,
    CODE_TYPES,
    WASTE_CAUSES,
    RETURN_TYPES,
    RETURN_CONDITIONS,
    VALUATION_METHODS,
    COUNT_TYPES,
)


class InventorySettingsSchema(Schema):
    id = fields.UUID(dump_only=True)
    valuation_method = fields.Str(required=True, validate=validate.OneOf(VALUATION_METHODS))


class WarehouseSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    warehouse_type = fields.Str(required=True, validate=validate.OneOf(WAREHOUSE_TYPES))
    project_id = fields.UUID(allow_none=True)
    location = fields.Str(allow_none=True)


class MaterialItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    code = fields.Str(required=True)
    description = fields.Str(required=True)
    unit = fields.Str(allow_none=True)
    is_batch_tracked = fields.Bool(load_default=False)
    is_serial_tracked = fields.Bool(load_default=False)


class StockItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    quantity_on_hand = fields.Decimal(dump_only=True, as_string=True)
    average_unit_cost = fields.Decimal(dump_only=True, as_string=True)


class ReceiveStockSchema(Schema):
    warehouse_id = fields.UUID(required=True)
    material_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit_cost = fields.Decimal(required=True, as_string=True)


class IssueStockSchema(Schema):
    warehouse_id = fields.UUID(required=True)
    material_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)


class StockTransferSchema(Schema):
    id = fields.UUID(dump_only=True)
    from_warehouse_id = fields.UUID(required=True)
    to_warehouse_id = fields.UUID(required=True)
    material_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    status = fields.Str(dump_only=True)


class StockReservationSchema(Schema):
    id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(required=True)
    material_item_id = fields.UUID(required=True)
    project_id = fields.UUID(allow_none=True)
    activity_id = fields.UUID(allow_none=True)
    quantity = fields.Decimal(required=True, as_string=True)
    status = fields.Str(dump_only=True)


class ReorderLevelSchema(Schema):
    id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(required=True)
    material_item_id = fields.UUID(required=True)
    reorder_point = fields.Decimal(required=True, as_string=True)
    reorder_quantity = fields.Decimal(required=True, as_string=True)
    auto_create_pr = fields.Bool(load_default=False)


class ItemCodeSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(required=True)
    code_type = fields.Str(required=True, validate=validate.OneOf(CODE_TYPES))
    code_value = fields.Str(required=True)


class BatchNumberSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(required=True)
    warehouse_id = fields.UUID(required=True)
    batch_number = fields.Str(required=True)
    manufactured_date = fields.Date(allow_none=True)
    expiry_date = fields.Date(allow_none=True)
    quality_cert_document_id = fields.UUID(allow_none=True)
    quantity_remaining = fields.Decimal(load_default="0", as_string=True)


class SerialNumberSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(required=True)
    serial_number = fields.Str(required=True)
    current_warehouse_id = fields.UUID(allow_none=True)
    status = fields.Str(dump_only=True)


class WasteRecordInputSchema(Schema):
    warehouse_id = fields.UUID(required=True)
    material_item_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    cause_classification = fields.Str(required=True, validate=validate.OneOf(WASTE_CAUSES))
    project_id = fields.UUID(allow_none=True, load_default=None)
    notes = fields.Str(allow_none=True)


class WasteRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    cause_classification = fields.Str(dump_only=True)
    valued_cost = fields.Decimal(dump_only=True, as_string=True)


class ReturnToYardSchema(Schema):
    material_item_id = fields.UUID(required=True)
    source_warehouse_id = fields.UUID(required=True)
    destination_warehouse_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    condition = fields.Str(load_default="good", validate=validate.OneOf(RETURN_CONDITIONS))


class ReturnToVendorSchema(Schema):
    material_item_id = fields.UUID(required=True)
    source_warehouse_id = fields.UUID(required=True)
    vendor_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    condition = fields.Str(load_default="good", validate=validate.OneOf(RETURN_CONDITIONS))
    credit_note_reference = fields.Str(allow_none=True)


class MaterialReturnSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    return_type = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)


class StartStockCountSchema(Schema):
    warehouse_id = fields.UUID(required=True)
    count_type = fields.Str(required=True, validate=validate.OneOf(COUNT_TYPES))
    material_item_ids = fields.List(fields.UUID(), required=True)


class RecordCountLineSchema(Schema):
    counted_quantity = fields.Decimal(required=True, as_string=True)


class StockCountLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    material_item_id = fields.UUID(dump_only=True)
    system_quantity = fields.Decimal(dump_only=True, as_string=True)
    counted_quantity = fields.Decimal(dump_only=True, as_string=True)
    variance = fields.Decimal(dump_only=True, as_string=True)


class StockCountSchema(Schema):
    id = fields.UUID(dump_only=True)
    warehouse_id = fields.UUID(dump_only=True)
    count_type = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    lines = fields.List(fields.Nested(StockCountLineSchema), dump_only=True)
