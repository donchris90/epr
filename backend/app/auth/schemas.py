from marshmallow import Schema, fields, validate


class ForgotPasswordSchema(Schema):
    email = fields.Str(required=True)


class ResetPasswordSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))


class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True, load_only=True)
    new_password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))
