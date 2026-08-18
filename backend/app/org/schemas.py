from marshmallow import Schema, fields, validate


class RoleSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(dump_only=True)
    permission_set = fields.List(fields.Str(), dump_only=True)


class CreateRoleSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=128))
    permission_set = fields.List(fields.Str(), required=True)


class UpdateRoleSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=128))
    permission_set = fields.List(fields.Str(), required=False)


class UserSchema(Schema):
    id = fields.UUID(dump_only=True)
    email = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    department = fields.Str(dump_only=True, allow_none=True)
    job_title = fields.Str(dump_only=True, allow_none=True)
    role = fields.Nested(RoleSchema, dump_only=True, attribute="role", allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class InvitationSchema(Schema):
    id = fields.UUID(dump_only=True)
    email = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    department = fields.Str(dump_only=True, allow_none=True)
    job_title = fields.Str(dump_only=True, allow_none=True)
    role = fields.Nested(RoleSchema, dump_only=True, attribute="role")
    expires_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class CreateInvitationSchema(Schema):
    email = fields.Email(required=True)
    role_id = fields.UUID(required=True)
    department = fields.Str(required=False, allow_none=True)
    job_title = fields.Str(required=False, allow_none=True)
    message = fields.Str(required=False, allow_none=True)


class AcceptInvitationSchema(Schema):
    token = fields.Str(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))


class ChangeRoleSchema(Schema):
    role_id = fields.UUID(required=True)
