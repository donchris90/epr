from marshmallow import Schema, fields


class DSARSearchResultSchema(Schema):
    """Deliberately minimal, not a full dump of every column -- a DSAR
    search result should tell an operator WHERE a person's data lives
    and let them go look at the real record through the normal module
    UI (with its normal audit logging of that access), not become a
    second, unaudited channel for viewing full record detail."""

    id = fields.UUID(dump_only=True)
    table = fields.Str(dump_only=True)
    summary = fields.Str(dump_only=True)
