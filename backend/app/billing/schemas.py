from marshmallow import Schema, fields, validate

from app.billing.models import BILLING_CYCLES


class SubscriptionPlanSchema(Schema):
    id = fields.UUID(dump_only=True)
    code = fields.Str(dump_only=True)
    name = fields.Str(dump_only=True)
    monthly_price_ngn = fields.Decimal(dump_only=True, as_string=True)
    annual_price_ngn = fields.Decimal(dump_only=True, as_string=True)
    seat_limit = fields.Int(dump_only=True, allow_none=True)


class TenantSubscriptionSchema(Schema):
    id = fields.UUID(dump_only=True)
    plan = fields.Nested(SubscriptionPlanSchema, dump_only=True)
    billing_cycle = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    trial_ends_at = fields.DateTime(dump_only=True, allow_none=True)
    current_period_start = fields.DateTime(dump_only=True, allow_none=True)
    current_period_end = fields.DateTime(dump_only=True, allow_none=True)


class ChangePlanInputSchema(Schema):
    plan_code = fields.Str(required=True)
    billing_cycle = fields.Str(required=True, validate=validate.OneOf(BILLING_CYCLES))
