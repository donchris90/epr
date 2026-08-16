"""
Module 20 — Asset Management (Code: AST)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.ast.models import ASSET_CATEGORIES, MAINTENANCE_TASK_TYPES, LIFECYCLE_COST_TYPES


class AssetInputSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    parent_asset_id = fields.UUID(allow_none=True)
    as_built_record_id = fields.UUID(allow_none=True)
    asset_category = fields.Str(required=True, validate=validate.OneOf(ASSET_CATEGORIES))
    name = fields.Str(required=True)
    category_attributes = fields.Dict(allow_none=True)
    baseline_data = fields.Dict(allow_none=True)
    handover_date = fields.Date(allow_none=True)


class UpdateAssetAttributesSchema(Schema):
    name = fields.Str(allow_none=True)
    category_attributes = fields.Dict(allow_none=True)


class AssetSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    parent_asset_id = fields.UUID(dump_only=True)
    asset_category = fields.Str(dump_only=True)
    name = fields.Str(dump_only=True)
    category_attributes = fields.Dict(dump_only=True)
    baseline_data = fields.Dict(dump_only=True)
    handover_date = fields.Date(dump_only=True)


class MaintenanceScheduleInputSchema(Schema):
    task_name = fields.Str(required=True)
    task_type = fields.Str(load_default="routine", validate=validate.OneOf(MAINTENANCE_TASK_TYPES))
    frequency_days = fields.Int(allow_none=True)
    next_due_date = fields.Date(allow_none=True)


class MaintenanceScheduleSchema(Schema):
    id = fields.UUID(dump_only=True)
    asset_id = fields.UUID(dump_only=True)
    task_name = fields.Str(dump_only=True)
    next_due_date = fields.Date(dump_only=True)
    last_completed_at = fields.DateTime(dump_only=True)


class AssetInspectionInputSchema(Schema):
    inspected_at = fields.Date(allow_none=True)
    condition_score = fields.Decimal(allow_none=True, as_string=True)
    inspector_name = fields.Str(allow_none=True)
    photo_document_ids = fields.List(fields.UUID(), allow_none=True)
    notes = fields.Str(allow_none=True)


class AssetInspectionSchema(Schema):
    id = fields.UUID(dump_only=True)
    asset_id = fields.UUID(dump_only=True)
    inspected_at = fields.Date(dump_only=True)
    condition_score = fields.Decimal(dump_only=True, as_string=True)


class WarrantyRecordInputSchema(Schema):
    component_name = fields.Str(allow_none=True)
    warranty_provider = fields.Str(allow_none=True)
    valid_until = fields.Date(allow_none=True)


class WarrantyRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    asset_id = fields.UUID(dump_only=True)
    component_name = fields.Str(dump_only=True)
    valid_until = fields.Date(dump_only=True)


class DLPRecordInputSchema(Schema):
    contract_id = fields.UUID(allow_none=True)
    dlp_start = fields.Date(allow_none=True)
    dlp_end = fields.Date(allow_none=True)


class DLPRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    asset_id = fields.UUID(dump_only=True)
    dlp_start = fields.Date(dump_only=True)
    dlp_end = fields.Date(dump_only=True)
    retention_released = fields.Bool(dump_only=True)
    released_at = fields.DateTime(dump_only=True)


class DefectItemInputSchema(Schema):
    description = fields.Str(required=True)
    raised_at = fields.Date(allow_none=True)


class DefectItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    dlp_record_id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)


class LifecycleCostInputSchema(Schema):
    cost_type = fields.Str(required=True, validate=validate.OneOf(LIFECYCLE_COST_TYPES))
    amount = fields.Decimal(required=True, as_string=True)
    incurred_at = fields.Date(allow_none=True)
    description = fields.Str(allow_none=True)


class LifecycleCostSchema(Schema):
    id = fields.UUID(dump_only=True)
    asset_id = fields.UUID(dump_only=True)
    cost_type = fields.Str(dump_only=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
