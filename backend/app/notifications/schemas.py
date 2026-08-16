from marshmallow import Schema, fields


class NotificationSchema(Schema):
    id = fields.UUID(dump_only=True)
    type = fields.Str(dump_only=True)
    title = fields.Str(dump_only=True)
    body = fields.Str(dump_only=True)
    data = fields.Dict(dump_only=True)
    channel = fields.Str(dump_only=True)
    read_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
