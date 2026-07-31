"""
Module 19 — Project Controls (Code: PC)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.pc.models import FORECAST_METHODS


class CreateEVMSnapshotSchema(Schema):
    project_id = fields.UUID(required=True)
    period_end = fields.Date(required=True)
    planned_value = fields.Decimal(required=True, as_string=True)
    earned_value = fields.Decimal(required=True, as_string=True)
    actual_cost = fields.Decimal(required=True, as_string=True)
    budget_at_completion = fields.Decimal(required=True, as_string=True)
    baseline_id = fields.UUID(allow_none=True, load_default=None)


class EVMSnapshotSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    period_end = fields.Date(dump_only=True)
    planned_value = fields.Decimal(dump_only=True, as_string=True)
    earned_value = fields.Decimal(dump_only=True, as_string=True)
    actual_cost = fields.Decimal(dump_only=True, as_string=True)
    budget_at_completion = fields.Decimal(dump_only=True, as_string=True)
    cost_variance = fields.Decimal(dump_only=True, as_string=True)
    schedule_variance = fields.Decimal(dump_only=True, as_string=True)
    cpi = fields.Decimal(dump_only=True, as_string=True, allow_none=True)
    spi = fields.Decimal(dump_only=True, as_string=True, allow_none=True)


class GenerateForecastSchema(Schema):
    method = fields.Str(load_default="cpi_based", validate=validate.OneOf(FORECAST_METHODS))
    manual_eac = fields.Decimal(allow_none=True, as_string=True)
    manual_reason = fields.Str(allow_none=True)


class ForecastSchema(Schema):
    id = fields.UUID(dump_only=True)
    evm_snapshot_id = fields.UUID(dump_only=True)
    method = fields.Str(dump_only=True)
    estimate_at_completion = fields.Decimal(dump_only=True, as_string=True)
    estimate_to_complete = fields.Decimal(dump_only=True, as_string=True)
    variance_at_completion = fields.Decimal(dump_only=True, as_string=True)


class RiskEntryInputSchema(Schema):
    project_id = fields.UUID(required=True)
    description = fields.Str(required=True)
    probability = fields.Decimal(required=True, as_string=True)
    impact_value = fields.Decimal(required=True, as_string=True)
    mitigation_owner = fields.UUID(allow_none=True)
    identified_at = fields.Date(allow_none=True)


class RiskEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    description = fields.Str(dump_only=True)
    probability = fields.Decimal(dump_only=True, as_string=True)
    impact_value = fields.Decimal(dump_only=True, as_string=True)
    exposure_value = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)


class DelayAnalysisInputSchema(Schema):
    project_id = fields.UUID(required=True)
    period_end = fields.Date(required=True)
    evm_snapshot_id = fields.UUID(required=True)
    total_float_consumed_days = fields.Int(allow_none=True)
    critical_path_delay_days = fields.Int(allow_none=True)


class DelayAnalysisSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    classification = fields.Str(dump_only=True)


class CashFlowForecastInputSchema(Schema):
    project_id = fields.UUID(required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    committed_costs = fields.Decimal(load_default="0", as_string=True)
    planned_billing = fields.Decimal(load_default="0", as_string=True)


class CashFlowForecastSchema(Schema):
    id = fields.UUID(dump_only=True)
    committed_costs = fields.Decimal(dump_only=True, as_string=True)
    planned_billing = fields.Decimal(dump_only=True, as_string=True)
    net_cash_flow = fields.Decimal(dump_only=True, as_string=True)
