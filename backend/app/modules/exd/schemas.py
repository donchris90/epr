"""
Module 21 — Executive Dashboard (Code: EXD)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.exd.models import WIDGET_TYPES


class DashboardWidgetInputSchema(Schema):
    widget_type = fields.Str(required=True, validate=validate.OneOf(WIDGET_TYPES))
    title = fields.Str(required=True)
    configuration = fields.Dict(allow_none=True)


class DashboardWidgetSchema(Schema):
    id = fields.UUID(dump_only=True)
    widget_type = fields.Str(dump_only=True)
    title = fields.Str(dump_only=True)
    configuration = fields.Dict(dump_only=True)


class DashboardConfigurationInputSchema(Schema):
    role_name = fields.Str(required=True)
    widget_ids = fields.List(fields.UUID(), load_default=list)
    region_project_ids = fields.List(fields.UUID(), allow_none=True)


class DashboardConfigurationSchema(Schema):
    id = fields.UUID(dump_only=True)
    role_name = fields.Str(dump_only=True)
    widget_ids = fields.List(fields.Str(), dump_only=True)
    region_project_ids = fields.List(fields.Str(), dump_only=True, allow_none=True)


class CompanyRevenueQuerySchema(Schema):
    company_id = fields.UUID(allow_none=True, load_default=None)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    budget_amount = fields.Decimal(allow_none=True, as_string=True, load_default=None)


class EquipmentUtilizationQuerySchema(Schema):
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
