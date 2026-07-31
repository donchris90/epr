"""
Module 3 — Estimating & Cost Engineering (Code: EST)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.est.models import (
    ESTIMATE_VERSION_STATUSES,
    RATE_COMPONENT_TYPES,
    CONTINGENCY_KINDS,
    CONTINGENCY_BASES,
    MARKUP_SCOPES,
)


class EstimateVersionSchema(Schema):
    id = fields.UUID(dump_only=True)
    tender_id = fields.UUID(required=True)
    version_number = fields.Int(dump_only=True)
    label = fields.Str(allow_none=True)
    status = fields.Str(validate=validate.OneOf(ESTIMATE_VERSION_STATUSES), dump_only=True)
    notes = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class BOQItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    estimate_version_id = fields.UUID(dump_only=True)
    parent_id = fields.UUID(allow_none=True)
    source_tender_boq_item_id = fields.UUID(allow_none=True)
    item_code = fields.Str(allow_none=True)
    description = fields.Str(required=True)
    unit = fields.Str(allow_none=True)
    quantity = fields.Decimal(allow_none=True, as_string=True)
    sort_order = fields.Int(load_default=0)
    unit_rate = fields.Decimal(dump_only=True, as_string=True)


class RateAnalysisLineInputSchema(Schema):
    component_type = fields.Str(required=True, validate=validate.OneOf(RATE_COMPONENT_TYPES))
    description = fields.Str(required=True)
    quantity_per_unit = fields.Decimal(required=True, as_string=True)
    unit_cost = fields.Decimal(required=True, as_string=True)
    cost_library_item_id = fields.UUID(allow_none=True)


class SaveRateAnalysisSchema(Schema):
    lines = fields.List(fields.Nested(RateAnalysisLineInputSchema), required=True)
    markup_pct = fields.Decimal(load_default="0", as_string=True)


class RateAnalysisLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    component_type = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    quantity_per_unit = fields.Decimal(dump_only=True, as_string=True)
    unit_cost = fields.Decimal(dump_only=True, as_string=True)
    line_total = fields.Decimal(dump_only=True, as_string=True)


class RateAnalysisSchema(Schema):
    id = fields.UUID(dump_only=True)
    boq_item_id = fields.UUID(dump_only=True)
    lines = fields.List(fields.Nested(RateAnalysisLineSchema), dump_only=True)


class CostLibraryItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    code = fields.Str(required=True)
    description = fields.Str(required=True)
    component_type = fields.Str(required=True, validate=validate.OneOf(RATE_COMPONENT_TYPES))
    unit = fields.Str(allow_none=True)
    default_unit_cost = fields.Decimal(required=True, as_string=True)


class MaterialPriceSchema(Schema):
    id = fields.UUID(dump_only=True)
    cost_library_item_id = fields.UUID(allow_none=True)
    material_name = fields.Str(required=True)
    location = fields.Str(allow_none=True)
    unit = fields.Str(allow_none=True)
    price = fields.Decimal(required=True, as_string=True)
    effective_date = fields.Date(required=True)


class EquipmentRateSchema(Schema):
    id = fields.UUID(dump_only=True)
    equipment_type = fields.Str(required=True)
    source = fields.Str(load_default="owned", validate=validate.OneOf(("owned", "rental")))
    cost_per_hour = fields.Decimal(required=True, as_string=True)
    effective_date = fields.Date(allow_none=True)


class LaborRateSchema(Schema):
    id = fields.UUID(dump_only=True)
    trade = fields.Str(required=True)
    grade = fields.Str(allow_none=True)
    hourly_rate = fields.Decimal(required=True, as_string=True)
    statutory_oncost_pct = fields.Decimal(load_default="0", as_string=True)


class VendorQuotationSchema(Schema):
    id = fields.UUID(dump_only=True)
    boq_item_id = fields.UUID(allow_none=True)
    vendor_name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    quoted_price = fields.Decimal(required=True, as_string=True)
    quoted_at = fields.Date(allow_none=True)
    valid_until = fields.Date(allow_none=True)
    is_accepted = fields.Bool(dump_only=True)


class MarkupSchema(Schema):
    id = fields.UUID(dump_only=True)
    estimate_version_id = fields.UUID(dump_only=True)
    scope = fields.Str(required=True, validate=validate.OneOf(MARKUP_SCOPES))
    target_boq_item_id = fields.UUID(allow_none=True)
    overhead_pct = fields.Decimal(required=True, as_string=True)
    profit_pct = fields.Decimal(required=True, as_string=True)


class ContingencyItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    estimate_version_id = fields.UUID(dump_only=True)
    kind = fields.Str(required=True, validate=validate.OneOf(CONTINGENCY_KINDS))
    description = fields.Str(allow_none=True)
    basis = fields.Str(required=True, validate=validate.OneOf(CONTINGENCY_BASES))
    value = fields.Decimal(required=True, as_string=True)


class CBSLineItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    cbs_id = fields.UUID(dump_only=True)
    source_boq_item_id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    unit = fields.Str(dump_only=True)
    quantity = fields.Decimal(dump_only=True, as_string=True)
    unit_rate = fields.Decimal(dump_only=True, as_string=True)
    budgeted_amount = fields.Decimal(as_string=True)


class CostBreakdownStructureSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    source_estimate_version_id = fields.UUID(dump_only=True)
    is_approved = fields.Bool(dump_only=True)
    approved_at = fields.DateTime(dump_only=True)
    line_items = fields.List(fields.Nested(CBSLineItemSchema), dump_only=True)


class GenerateCBSSchema(Schema):
    project_id = fields.UUID(allow_none=True)


class BudgetRevisionSchema(Schema):
    id = fields.UUID(dump_only=True)
    cbs_line_item_id = fields.UUID(required=True)
    reason = fields.Str(required=True)
    revised_amount = fields.Decimal(required=True, as_string=True)
    previous_amount = fields.Decimal(dump_only=True, as_string=True)
