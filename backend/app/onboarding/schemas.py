from marshmallow import Schema, fields


class SignupSchema(Schema):
    company_name = fields.Str(required=True)
    admin_email = fields.Str(required=True)
    admin_password = fields.Str(required=True, load_only=True)


class SignupResponseSchema(Schema):
    tenant_id = fields.UUID(dump_only=True)
    access_token = fields.Str(dump_only=True)
    refresh_token = fields.Str(dump_only=True)
