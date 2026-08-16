from marshmallow import Schema, fields


class CommitmentSummarySchema(Schema):
    cbs_line_item_id = fields.UUID(dump_only=True)
    budgeted_amount = fields.Decimal(dump_only=True, as_string=True)
    committed_amount = fields.Decimal(dump_only=True, as_string=True)
    remaining_amount = fields.Decimal(dump_only=True, as_string=True)
