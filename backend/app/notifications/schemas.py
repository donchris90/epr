from marshmallow import Schema, fields, validate

from app.notifications.models import NOTIFICATION_CATEGORIES


class NotificationSchema(Schema):
    id = fields.UUID(dump_only=True)
    type = fields.Str(dump_only=True)
    title = fields.Str(dump_only=True)
    body = fields.Str(dump_only=True)
    data = fields.Dict(dump_only=True)
    channel = fields.Str(dump_only=True)
    read_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class PreferenceItemSchema(Schema):
    category = fields.Str(required=True, validate=validate.OneOf(NOTIFICATION_CATEGORIES))
    in_app = fields.Bool(required=True)
    email = fields.Bool(required=True)


class PreferencesUpdateSchema(Schema):
    preferences = fields.List(fields.Nested(PreferenceItemSchema), required=True, validate=validate.Length(min=1))
