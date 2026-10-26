from marshmallow import Schema, fields, validate


class DSARSearchResultSchema(Schema):
    """Deliberately minimal, not a full dump of every column -- a DSAR
    search result should tell an operator WHERE a person's data lives
    and let them go look at the real record through the normal module
    UI (with its normal audit logging of that access), not become a
    second, unaudited channel for viewing full record detail."""

    id = fields.UUID(dump_only=True)
    table = fields.Str(dump_only=True)
    summary = fields.Str(dump_only=True)


class DSARRequestInputSchema(Schema):
    request_type = fields.Str(required=True)
    subject_name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    subject_email = fields.Str(allow_none=True)
    subject_phone = fields.Str(allow_none=True)
    details = fields.Str(allow_none=True)


class DSARRequestUpdateSchema(Schema):
    status = fields.Str()
    resolution_notes = fields.Str(allow_none=True)


class DSARRecordRefSchema(Schema):
    table = fields.Str(required=True)
    id = fields.UUID(required=True)


class DSAREraseSchema(Schema):
    records = fields.List(fields.Nested(DSARRecordRefSchema), required=True)


class DSARRequestSchema(Schema):
    id = fields.UUID(dump_only=True)
    request_type = fields.Str(dump_only=True)
    subject_name = fields.Str(dump_only=True)
    subject_email = fields.Str(dump_only=True)
    subject_phone = fields.Str(dump_only=True)
    details = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    received_at = fields.DateTime(dump_only=True)
    due_at = fields.DateTime(dump_only=True)
    resolved_at = fields.DateTime(dump_only=True)
    resolution_notes = fields.Str(dump_only=True)
    actions = fields.List(fields.Dict(), dump_only=True)
    is_overdue = fields.Method("get_is_overdue", dump_only=True)

    def get_is_overdue(self, obj):
        from app.dsar.services import is_overdue

        return is_overdue(obj)
