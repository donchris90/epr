"""
Module 5 — Project Planning (Code: PLN)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.pln.models import DEPENDENCY_TYPES, RESOURCE_TYPES, LOOK_AHEAD_TYPES, DELAY_CAUSES


class WBSNodeSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    parent_id = fields.UUID(allow_none=True)
    cbs_line_item_id = fields.UUID(allow_none=True)
    code = fields.Str(allow_none=True)
    name = fields.Str(required=True)
    sort_order = fields.Int(load_default=0)


class ActivitySchema(Schema):
    id = fields.UUID(dump_only=True)
    wbs_node_id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    planned_start = fields.Date(required=True)
    duration_days = fields.Int(required=True)
    percent_complete = fields.Decimal(load_default="0", as_string=True)
    early_start = fields.Date(dump_only=True)
    early_finish = fields.Date(dump_only=True)
    late_start = fields.Date(dump_only=True)
    late_finish = fields.Date(dump_only=True)
    total_float_days = fields.Int(dump_only=True)
    is_critical = fields.Bool(dump_only=True)


class ActivityDependencySchema(Schema):
    id = fields.UUID(dump_only=True)
    predecessor_id = fields.UUID(required=True)
    successor_id = fields.UUID(required=True)
    dependency_type = fields.Str(load_default="FS", validate=validate.OneOf(DEPENDENCY_TYPES))
    lag_days = fields.Int(load_default=0)


class ResourceAssignmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    activity_id = fields.UUID(dump_only=True)
    resource_type = fields.Str(required=True, validate=validate.OneOf(RESOURCE_TYPES))
    resource_name = fields.Str(required=True)
    quantity = fields.Decimal(load_default="1", as_string=True)
    unit = fields.Str(allow_none=True)


class BaselineSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    label = fields.Str(required=True)
    is_current = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class CreateBaselineSchema(Schema):
    project_id = fields.UUID(allow_none=True)
    wbs_root_id = fields.UUID(required=True)
    label = fields.Str(required=True)
    mark_current = fields.Bool(load_default=False)


class LookAheadPlanSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True)
    plan_type = fields.Str(required=True, validate=validate.OneOf(LOOK_AHEAD_TYPES))
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)


class LookAheadItemSchema(Schema):
    id = fields.UUID(dump_only=True)
    plan_id = fields.UUID(dump_only=True)
    activity_id = fields.UUID(required=True)
    adjusted_start = fields.Date(allow_none=True)
    adjusted_end = fields.Date(allow_none=True)
    site_notes = fields.Str(allow_none=True)
    constraint_flag = fields.Str(allow_none=True)


class DelayEventSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(allow_none=True, load_default=None)
    activity_id = fields.UUID(allow_none=True, load_default=None)
    cause_classification = fields.Str(required=True, validate=validate.OneOf(DELAY_CAUSES))
    description = fields.Str(required=True)
    delay_days = fields.Int(required=True)
    analysis_method = fields.Str(allow_none=True)
    occurred_on = fields.Date(required=True)
    affected_critical_path = fields.Bool(dump_only=True)
    flagged_for_review = fields.Bool(dump_only=True)
