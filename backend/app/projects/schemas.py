from marshmallow import Schema, fields


class ProjectSchema(Schema):
    id = fields.UUID(dump_only=True)
    company_id = fields.UUID(dump_only=True)
    contract_id = fields.UUID(dump_only=True, allow_none=True)
    name = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
