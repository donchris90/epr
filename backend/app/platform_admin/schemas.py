from marshmallow import Schema, fields


class TenantOverviewSchema(Schema):
    id = fields.UUID()
    name = fields.Str()
    region = fields.Str(allow_none=True)
    is_suspended = fields.Bool()
    created_at = fields.DateTime()
    user_count = fields.Int()
    subscription_status = fields.Str(allow_none=True)
    subscription_plan_code = fields.Str(allow_none=True)


class TenantDetailSchema(TenantOverviewSchema):
    trial_ends_at = fields.DateTime(allow_none=True)


class PlatformAdminLoginSchema(Schema):
    email = fields.Str(required=True)
    password = fields.Str(required=True)
